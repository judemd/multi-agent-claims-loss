import asyncio
import json
import pytest

from google import genai
from google.auth.credentials import AnonymousCredentials
from google.adk.models.google_llm import Gemini
from google.genai import types
from google.genai.models import AsyncModels

from scripts.diagnose_adk_batch import diagnose
from scripts.diagnose_challenger import prepare
from claimcascade.synthetic import generate


@pytest.mark.parametrize('challenger', [False, True])
def test_single_request_timings_and_timeout(monkeypatch, tmp_path, challenger):
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS', 'true')
    monkeypatch.setenv('CLAIMCASCADE_PUBLIC_DEMO', 'false')
    client = genai.Client(enterprise=True, project='offline-test', location='global',
                          credentials=AnonymousCredentials())
    calls = []
    prepared = None
    if challenger:
        claims, _, _ = generate(42, False)
        source = tmp_path/'checkpoint.json'
        source.write_text(json.dumps(dict(seed=42, held_out=False, claim_count=50,
            model='gemini-3.5-flash', request_policy=dict(temperature=1.0, thinking_level='LOW'),
            schema_validated_outputs={**{f'extractor_{i}':{'facts':[]} for i in range(5)},
                'investigator':{'clusters':[], 'unassigned':[c.claim_id for c in claims]}})))
        prepared = prepare(source)
        with pytest.raises(ValueError, match='unknown cluster'):
            prepared[4](prepared[2].model_validate({'objections':[{'cluster_id':'unknown', 'concern':'test'}]}))

    async def fake_stream(self, **kwargs):
        calls.append(kwargs)
        async def chunks():
            yield types.GenerateContentResponse(candidates=[types.Candidate(index=0,
                content=types.Content(role='model', parts=[types.Part(text='{"objections":[]}' if challenger else '{"facts":[]}')]),
                finish_reason=types.FinishReason.STOP)])
        return chunks()

    monkeypatch.setattr(AsyncModels, 'generate_content_stream', fake_stream)

    async def scenario():
        try:
            provider = Gemini(model='offline-test', client=client,
                              retry_options=types.HttpRetryOptions(attempts=1))
            result = await diagnose(provider=provider, timeout=5, prepared=prepared)
            assert result['status'] == 'complete'
            assert result['sdk_calls'] == 1 and len(calls) == 1
            events = [e['event'] for e in result['events']]
            assert events.index('before_model') < events.index('sdk_enter')
            assert events.index('first_sdk_chunk') < events.index('first_adk_content')
            assert 'adk_final' in events

            async def stalled(self, **kwargs):
                await asyncio.sleep(10)
            monkeypatch.setattr(AsyncModels, 'generate_content_stream', stalled)
            failed = await diagnose(provider=provider, timeout=0.1, prepared=prepared)
            assert failed['status'] == 'failed'
            assert failed['error_type'] == 'TimeoutError'
            assert failed['sdk_calls'] == 1 and failed['sdk_chunks'] == 0
        finally:
            await client.aio.aclose()
    asyncio.run(scenario())
