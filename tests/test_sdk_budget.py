"""Guard against SDK follow-up generation calls outside our attempt counter."""
import asyncio
from unittest.mock import AsyncMock

from google import genai
from google.auth.credentials import AnonymousCredentials
from google.genai import types


def test_sdk_does_not_follow_continuation_when_disabled(monkeypatch):
    client = genai.Client(enterprise=True,project='offline-test',location='global',credentials=AnonymousCredentials())
    response = types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role='model',parts=[types.Part(text='{}')]),
        finish_reason=types.FinishReason.CONTINUATION,continuation_token=b'offline-only')])
    request = AsyncMock(return_value=response)
    monkeypatch.setattr(client.aio.models,'_generate_content',request)
    async def scenario():
        try:
            await client.aio.models.generate_content(model='gemini-3.5-flash',contents='Offline test',
                config=types.GenerateContentConfig(automatic_continuation=False))
        finally:
            await client.aio.aclose()
    asyncio.run(scenario())
    assert request.await_count==1
