"""Provision this demo's database and secret without writing or printing credentials.

Run explicitly after cloud approval. Reuses an existing secret on subsequent runs.
The local proxy binds loopback only; its upstream connection is IAM-authorised TLS.
"""
import base64
import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

import google.auth
import psycopg
import requests
from google.auth.transport.requests import AuthorizedSession
from psycopg import sql
from sqlalchemy import URL

from claimcascade.core import candidates, snapshot
from claimcascade.persistence import Store
from claimcascade.schemas import Settings
from claimcascade.services import offline_analysis
from claimcascade.synthetic import generate


PROJECT = os.environ['GOOGLE_CLOUD_PROJECT']
INSTANCE = 'claimcascade-demo'
CONNECTION = f'{PROJECT}:europe-west2:{INSTANCE}'
SECRET = f'projects/{PROJECT}/secrets/claimcascade-database-url'
ROOT = f'https://sqladmin.googleapis.com/sql/v1beta4/projects/{PROJECT}'


def main():
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    session = AuthorizedSession(credentials)

    def call(method, url, **kwargs):
        response = session.request(method,url,timeout=60,**kwargs)
        if not response.ok:
            raise RuntimeError(f'Cloud administration request failed: HTTP {response.status_code}; credentials suppressed')
        return response.json()

    def operation(payload):
        name = payload['name']
        for _ in range(90):
            result = call('GET',f'{ROOT}/operations/{name}')
            if result['status']=='DONE':
                if result.get('error'):
                    raise RuntimeError('Cloud SQL operation failed; inspect the operation in Cloud Console')
                return
            time.sleep(2)
        raise TimeoutError('Cloud SQL administration operation timed out')

    for attempt in range(90):
        state = call('GET',f'{ROOT}/instances/{INSTANCE}')['state']
        if state=='RUNNABLE':
            break
        if state!='PENDING_CREATE':
            raise RuntimeError(f'Database is not ready: {state}')
        if attempt % 6==0:
            print('Waiting for PostgreSQL provisioning',flush=True)
        time.sleep(10)
    else:
        raise TimeoutError('PostgreSQL provisioning did not finish within 15 minutes')

    existing = session.get(f'https://secretmanager.googleapis.com/v1/{SECRET}/versions/latest:access',timeout=30)
    if existing.status_code not in (200,404):
        raise RuntimeError(f'Cannot inspect existing database secret: HTTP {existing.status_code}')
    if existing.ok:
        from sqlalchemy.engine import make_url
        saved = make_url(base64.b64decode(existing.json()['payload']['data']).decode())
        password = saved.password
        admin_password = None
        print('Reusing existing database secret',flush=True)
    else:
        password, admin_password = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
        print('Initialising one-time PostgreSQL administrator credential (not displayed)',flush=True)
        operation(call('PUT',f'{ROOT}/instances/{INSTANCE}/users',params={'name':'postgres'},
                       json={'name':'postgres','instance':INSTANCE,'project':PROJECT,'password':admin_password}))
        print('Administrator initialisation complete',flush=True)

    folder = Path('data/cloud-validation')
    folder.mkdir(parents=True,exist_ok=True)
    executable = folder/'cloud-sql-proxy.exe'
    if not executable.exists():
        response = requests.get('https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.26.2/cloud-sql-proxy.x64.exe',timeout=120)
        response.raise_for_status()
        executable.write_bytes(response.content)
    with (folder/'proxy.log').open('w',encoding='utf-8') as log:
        proxy = subprocess.Popen([str(executable.resolve()),'--address=127.0.0.1','--port=15432',CONNECTION],
            stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for _ in range(30):
                try:
                    with socket.create_connection(('127.0.0.1',15432),timeout=1):
                        break
                except OSError:
                    if proxy.poll() is not None:
                        raise RuntimeError('Cloud SQL proxy exited; inspect local proxy log')
                    time.sleep(1)
            if admin_password:
                with psycopg.connect(host='127.0.0.1',port=15432,user='postgres',password=admin_password,dbname='postgres',sslmode='disable',autocommit=True) as conn:
                    exists = conn.execute("SELECT rolcreatedb,rolcreaterole,rolsuper,rolreplication FROM pg_roles WHERE rolname='claimcascade_app'").fetchone()
                    if exists:
                        if any(exists):
                            raise RuntimeError('Existing application role has unexpected privileges; refusing to adopt it')
                        conn.execute(sql.SQL('ALTER ROLE claimcascade_app PASSWORD {}').format(sql.Literal(password)))
                    else:
                        conn.execute(sql.SQL('CREATE ROLE claimcascade_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Literal(password)))
                    # PostgreSQL 16 requires SET ROLE permission to assign database ownership.
                    conn.execute('GRANT claimcascade_app TO postgres')
                    database = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='claimcascade'").fetchone()
                    if database and database[0]!='claimcascade_app':
                        raise RuntimeError('Existing database has an unexpected owner; refusing to change ownership')
                    if not database:
                        conn.execute('CREATE DATABASE claimcascade OWNER claimcascade_app')
                cloud_url = URL.create('postgresql+psycopg',username='claimcascade_app',password=password,
                    database='claimcascade',query={'host':f'/cloudsql/{CONNECTION}'}).render_as_string(hide_password=False)
                call('POST',f'https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets',
                     params={'secretId':'claimcascade-database-url'},json={'replication':{'automatic':{}}})
                call('POST',f'https://secretmanager.googleapis.com/v1/{SECRET}:addVersion',
                     json={'payload':{'data':base64.b64encode(cloud_url.encode()).decode()}})
                print('Created dedicated non-admin database role and Secret Manager URL',flush=True)

            local_url = URL.create('postgresql+psycopg',username='claimcascade_app',password=password,host='127.0.0.1',port=15432,database='claimcascade')
            store = Store(local_url.render_as_string(hide_password=False))
            claims, bulletins, truth = generate()
            settings = Settings(distance_km=10.0,time_gap_hours=24.0)
            digest, content = snapshot(claims,bulletins,settings,'gemini-3.5-flash','Rules only — no model calls')
            previous = next((r for r in store.list_runs() if r['snapshot_hash']==digest and r['status']=='complete'),None)
            if previous:
                run_id = previous['id']
            else:
                run_id = store.start(digest,content)
                edges = candidates(claims,settings)
                result = offline_analysis(claims,edges)
                result.update(edges=edges,baseline=[c['members'] for c in result['proposals']['clusters']],evaluation_truth=truth)
                store.finish(run_id,result=result)
                store.save_review(run_id,{'groups':[dict(cluster_id=c['cluster_id'],members=c['members'],decision='pending',note='Deployment smoke check — synthetic data') for c in result['proposals']['clusters']], 'duplicates':{},'dismissed_duplicates':[]})
            store.engine.dispose()
            reopened = Store(local_url.render_as_string(hide_password=False))
            assert any(r['id']==run_id for r in reopened.list_runs())
            assert reopened.history(run_id)
            with reopened.engine.connect() as conn:
                from sqlalchemy import text
                privileges = conn.execute(text('SELECT rolcreatedb, rolcreaterole, rolsuper FROM pg_roles WHERE rolname=current_user')).one()
                assert not any(privileges)
            reopened.engine.dispose()
            evidence = {'run_id':run_id,'database':'claimcascade','instance':CONNECTION,
                        'reopened_run_and_review':True,'non_admin_role':True}
            (folder/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
            print(json.dumps(evidence,indent=2))
        finally:
            proxy.terminate()
            proxy.wait(timeout=15)


if __name__ == '__main__':
    main()
