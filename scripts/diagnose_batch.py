"""One streaming request for a synthetic extraction batch; no retries or continuation."""
import asyncio
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path

from google import genai
from google.genai import types

from claimcascade.agents import POLICY,narrative_schema
from claimcascade.core import validate_evidence
from claimcascade.synthetic import generate


async def main():
    if os.getenv('CLAIMCASCADE_ALLOW_PAID_CALLS','false').lower()!='true' or os.getenv('CLAIMCASCADE_PUBLIC_DEMO','false').lower()=='true':
        raise RuntimeError('Operator-only paid diagnostic is disabled')
    claims,_,_=generate(42,False)
    batch=claims[20:30]
    schema=narrative_schema(batch)
    client=genai.Client(enterprise=True,project=os.environ['GOOGLE_CLOUD_PROJECT'],location='global',
                        http_options=types.HttpOptions(timeout=90000,retry_options=types.HttpRetryOptions(attempts=1)))
    chunks,text,usage=0,[],None
    started=time.monotonic()
    first_chunk=None
    async def request():
        nonlocal chunks,usage,first_chunk
        stream=await client.aio.models.generate_content_stream(model='gemini-3.5-flash',
            contents=json.dumps({'claims':[{'claim_id':c.claim_id,'narrative':c.narrative} for c in batch]}),
            config=types.GenerateContentConfig(temperature=1.0,max_output_tokens=8192,automatic_continuation=False,
                response_schema=schema,response_mime_type='application/json',thinking_config=types.ThinkingConfig(thinking_level='LOW'),
                system_instruction=POLICY+' Extract only facts stated in narratives. For every fact copy the entire source narrative verbatim into excerpt. Unknown facts remain unknown.'))
        async for chunk in stream:
            chunks+=1
            if first_chunk is None:
                first_chunk=round(time.monotonic()-started,2)
                print(f'First stream chunk after {first_chunk} seconds',flush=True)
            for candidate in chunk.candidates or []:
                for part in candidate.content.parts if candidate.content else []:
                    if part.text and not part.thought:
                        text.append(part.text)
            if chunk.usage_metadata:
                usage=chunk.usage_metadata.model_dump(mode='json')
    try:
        await asyncio.wait_for(request(),timeout=90)
        output=schema.model_validate_json(''.join(text))
        validate_evidence(output.facts,batch)
        result={'status':'complete','seed':42,'held_out':False,'claim_count':50,'model':'gemini-3.5-flash',
                'request_policy':{'temperature':1.0,'thinking_level':'LOW'},
                'schema_validated_outputs':{'extractor_2':output.model_dump()},
                'chunks':chunks,'first_chunk_seconds':first_chunk,'elapsed_seconds':round(time.monotonic()-started,2),'usage':usage}
        folder=Path('data/live-tests')
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-stream-diagnostic.json')
        path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'result_file':str(path),'chunks':chunks,'first_chunk_seconds':first_chunk,
                          'elapsed_seconds':result['elapsed_seconds'],'valid_facts':len(output.facts)}))
    finally:
        await client.aio.aclose()


if __name__=='__main__':
    asyncio.run(main())
