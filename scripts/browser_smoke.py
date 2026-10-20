"""Operator-run public synthetic demo browser check. Requires Playwright + Chrome."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--private',action='store_true',help='Use the active gcloud identity for a private Cloud Run smoke check')
    args = parser.parse_args()
    folder = Path('data/cloud-validation')
    folder.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome',headless=True)
        page = browser.new_page(viewport={'width':1440,'height':1100})
        if args.private:
            identity = subprocess.run([shutil.which('gcloud.cmd') or 'gcloud','auth','print-identity-token'],
                                      capture_output=True,text=True,check=True)
            # Credentials stay in memory; block every external origin before adding the header.
            origin = urlparse(args.url).netloc
            page.route('**/*',lambda route: route.continue_() if urlparse(route.request.url).netloc==origin else route.abort())
            page.set_extra_http_headers({'Authorization':'Bearer '+identity.stdout.strip()})
        page.goto(args.url,wait_until='domcontentloaded',timeout=90000)
        page.get_by_role('heading',name='ClaimCascade',exact=True).wait_for(timeout=90000)
        page.get_by_text('Public demo: synthetic data only; uploads and paid model calls are disabled.',exact=True).wait_for(timeout=90000)
        page.get_by_text('Snapshot ',exact=False).first.wait_for(timeout=90000)
        if not args.verify_only:
            page.get_by_role('button',name='Generate 50 synthetic notifications',exact=True).click()
            page.get_by_role('button',name='Analyse',exact=True).wait_for(timeout=60000)
            page.get_by_role('button',name='Analyse',exact=True).click()
            page.get_by_text('Using the existing run for this snapshot.',exact=False).wait_for(timeout=60000)
            page.get_by_role('tab',name='Review',exact=True).click()
            page.get_by_role('button',name='Save review revision',exact=True).click()
            page.get_by_role('button',name='Save review revision',exact=True).wait_for(timeout=60000)
            page.wait_for_timeout(3000)
        page.get_by_role('tab',name='Event investigation',exact=True).click()
        page.get_by_test_id('stPlotlyChart').first.wait_for(timeout=60000)
        assert page.get_by_test_id('stException').count()==0
        page.screenshot(path=str(folder/('browser-reopened.png' if args.verify_only else 'browser-smoke.png')),full_page=True)
        page.get_by_role('tab',name='Data',exact=True).click()
        upload_buttons = page.get_by_test_id('stFileUploader').locator('button')
        assert upload_buttons.count()==2
        assert all(button.is_disabled() for button in upload_buttons.all())
        page.reload(wait_until='domcontentloaded')
        page.get_by_text('Snapshot ',exact=False).first.wait_for(timeout=90000)
        page.get_by_role('tab',name='Review',exact=True).click()
        page.get_by_text('Immutable review history',exact=True).click()
        page.get_by_text('Deployment smoke check',exact=False).first.wait_for(timeout=60000)
        assert page.get_by_test_id('stException').count()==0
        print(json.dumps({'url':args.url,'websocket_ui':True,'history_reopened':True,
                          'uploads_disabled':True,'paid_mode_unavailable':True,'verify_only':args.verify_only}))
        browser.close()


if __name__=='__main__':
    main()
