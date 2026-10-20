"""Single operator-only ADK request with SDK/ADK timing; never retries."""
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.models import AsyncModels

from claimcascade.agents import POLICY, narrative_schema
from claimcascade.core import validate_evidence
from claimcascade.requests import provider_status
from claimcascade.synthetic import generate

INSTRUCTION = 'Extract only facts stated in the supplied narratives: cause, timing, assets and wider event indicators. Unknown information stays unknown. For every fact copy the entire source narrative verbatim into excerpt, choosing the narrative belonging to its claim ID. Do not infer dates, assets or amounts from other fields.'


async def diagnose(*, provider=None, timeout=90):
    if os.getenv('CLAIMCASCADE_ALLOW_PAID_CALLS', 'false').lower() != 'true' or os.getenv('CLAIMCASCADE_PUBLIC_DEMO', 'false').lower() == 'true':
        raise RuntimeError('Operator-only paid diagnostic is disabled')
    os.environ['GOOGLE_GENAI_USE_ENTERPRISE'] = 'true'
    claims, _, _ = generate(42, False)
    batch = claims[30:40]
    schema = narrative_schema(batch)
    started = time.monotonic()
    result = dict(status='running', seed=42, held_out=False, claim_count=50,
                  batch_index=3, model='gemini-3.5-flash', events=[], sdk_calls=0,
                  sdk_chunks=0, adk_events=0, usage=[],
                  request_policy=dict(temperature=1.0, thinking_level='LOW', retries=0,
                                      automatic_continuation=False, timeout_seconds=timeout))

    def record(event, **fields):
        entry = dict(event=event, seconds=round(time.monotonic()-started, 3), **fields)
        result['events'].append(entry)
        print(json.dumps(entry), flush=True)

    original = AsyncModels.generate_content_stream

    async def traced_stream(self, **kwargs):
        result['sdk_calls'] += 1
        if result['sdk_calls'] > 1:
            raise RuntimeError('Diagnostic permits only one SDK call')
        config = kwargs['config']
        record('sdk_enter', temperature=config.temperature,
               response_mime_type=config.response_mime_type,
               automatic_continuation=config.automatic_continuation)
        stream = await original(self, **kwargs)
        record('sdk_stream_returned')

        async def chunks():
            async for chunk in stream:
                result['sdk_chunks'] += 1
                if result['sdk_chunks'] == 1:
                    record('first_sdk_chunk')
                yield chunk
            record('sdk_stream_end')
        return chunks()

    def before_model(callback_context, llm_request):
        record('before_model')

    async def execute():
        agent = LlmAgent(name='extractor_3',
            model=provider or Gemini(model='gemini-3.5-flash', retry_options=types.HttpRetryOptions(attempts=1)),
            instruction=POLICY+'\n'+INSTRUCTION, output_schema=schema,
            before_model_callback=before_model,
            generate_content_config=types.GenerateContentConfig(temperature=1.0,
                max_output_tokens=8192, automatic_continuation=False,
                thinking_config=types.ThinkingConfig(thinking_level='LOW')))
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name='claimcascade', user_id='reviewer')
        runner = Runner(agent=agent, app_name='claimcascade', session_service=sessions)
        final = None
        async for event in runner.run_async(user_id='reviewer', session_id=session.id,
            new_message=types.Content(role='user', parts=[types.Part(text=json.dumps(
                {'claims':[{'claim_id':c.claim_id, 'narrative':c.narrative} for c in batch]}))]),
            run_config=RunConfig(max_llm_calls=1, streaming_mode=StreamingMode.SSE)):
            result['adk_events'] += 1
            if event.content and not any(e['event']=='first_adk_content' for e in result['events']):
                record('first_adk_content', partial=bool(event.partial))
            if event.usage_metadata:
                result['usage'].append(event.usage_metadata.model_dump(mode='json'))
            if event.is_final_response() and event.content:
                record('adk_final')
                final = ''.join(p.text or '' for p in event.content.parts)
        output = schema.model_validate_json(final)
        validate_evidence(output.facts, batch)
        result['valid_facts'] = len(output.facts)
        result['schema_validated_outputs'] = {'extractor_3':output.model_dump()}

    try:
        with patch.object(AsyncModels, 'generate_content_stream', traced_stream):
            await asyncio.wait_for(execute(), timeout=timeout)
        result['status'] = 'complete'
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__, provider_code=provider_status(exc))
        record('failed', error_type=type(exc).__name__)
    result['elapsed_seconds'] = round(time.monotonic()-started, 3)
    return result


async def main():
    result = await diagnose()
    folder = Path('data/live-tests')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-adk-diagnostic.json')
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(result_file=str(path), status=result['status'], sdk_calls=result['sdk_calls'])))


if __name__ == '__main__':
    asyncio.run(main())
