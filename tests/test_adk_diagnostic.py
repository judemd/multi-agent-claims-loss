import asyncio

from google import genai
from google.auth.credentials import AnonymousCredentials
from google.adk.models.google_llm import Gemini
from google.genai import types
from google.genai.models import AsyncModels

from scripts.diagnose_adk_batch import diagnose


def test_single_request_timings_and_timeout(monkeypatch):
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS', 'true')
    monkeypatch.setenv('CLAIMCASCADE_PUBLIC_DEMO', 'false')
    client = genai.Client(enterprise=True, project='offline-test', location='global',
                          credentials=AnonymousCredentials())
    calls = []

    async def fake_stream(self, **kwargs):
        calls.append(kwargs)
        async def chunks():
            yield types.GenerateContentResponse(candidates=[types.Candidate(index=0,
                content=types.Content(role='model', parts=[types.Part(text='{"facts":[]}')]),
                finish_reason=types.FinishReason.STOP)])
        return chunks()

    monkeypatch.setattr(AsyncModels, 'generate_content_stream', fake_stream)

    async def scenario():
        try:
            provider = Gemini(model='offline-test', client=client,
                              retry_options=types.HttpRetryOptions(attempts=1))
            result = await diagnose(provider=provider, timeout=5)
            assert result['status'] == 'complete'
            assert result['sdk_calls'] == 1 and len(calls) == 1
            events = [e['event'] for e in result['events']]
            assert events.index('before_model') < events.index('sdk_enter')
            assert events.index('first_sdk_chunk') < events.index('first_adk_content')
            assert 'adk_final' in events

            async def stalled(self, **kwargs):
                await asyncio.sleep(10)
            monkeypatch.setattr(AsyncModels, 'generate_content_stream', stalled)
            failed = await diagnose(provider=provider, timeout=0.1)
            assert failed['status'] == 'failed'
            assert failed['error_type'] == 'TimeoutError'
            assert failed['sdk_calls'] == 1 and failed['sdk_chunks'] == 0
        finally:
            await client.aio.aclose()
    asyncio.run(scenario())
