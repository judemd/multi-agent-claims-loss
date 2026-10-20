"""Guard against SDK follow-up generation calls outside our attempt counter."""
import asyncio
from unittest.mock import AsyncMock
import pytest

from google import genai
from google.auth.credentials import AnonymousCredentials
from google.genai import types


@pytest.mark.parametrize('streaming',[False,True])
def test_sdk_does_not_follow_continuation_when_disabled(monkeypatch,streaming):
    client = genai.Client(enterprise=True,project='offline-test',location='global',credentials=AnonymousCredentials())
    response = types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role='model',parts=[types.Part(text='{}')]),
        finish_reason=types.FinishReason.CONTINUATION,continuation_token=b'offline-only')])
    async def chunks():
        yield response
    request = AsyncMock(return_value=chunks() if streaming else response)
    monkeypatch.setattr(client.aio.models,'_generate_content_stream' if streaming else '_generate_content',request)
    async def scenario():
        try:
            config=types.GenerateContentConfig(automatic_continuation=False)
            if streaming:
                stream=await client.aio.models.generate_content_stream(model='gemini-3.5-flash',contents='Offline test',config=config)
                async for _ in stream:
                    pass
            else:
                await client.aio.models.generate_content(model='gemini-3.5-flash',contents='Offline test',config=config)
        finally:
            await client.aio.aclose()
    asyncio.run(scenario())
    assert request.await_count==1
