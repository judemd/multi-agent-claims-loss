"""Exercise ADK's real Gemini stream aggregator without an inference request."""
import asyncio
import json
from collections import deque

from google import genai
from google.auth.credentials import AnonymousCredentials
from google.genai import types

from claimcascade.agents import run_agents
from claimcascade.core import candidates
from claimcascade.requests import RequestPolicy
from claimcascade.schemas import Settings
from claimcascade.services import offline_analysis
from claimcascade.synthetic import generate


def test_real_adk_gemini_aggregation_and_forwarded_config(monkeypatch):
    import google.adk.agents
    from google.adk.models.google_llm import Gemini
    from google.genai.models import AsyncModels
    claims,bulletins,_=generate()
    edges=candidates(claims,Settings())
    reference=offline_analysis(claims,edges)
    outputs=deque([{'facts':[]} for _ in range(5)]+[reference['proposals'],{'objections':[]},
        {'explanations':[dict(cluster_id=c['cluster_id'],observed_facts=[],hypotheses=[],missing_information=[]) for c in reference['proposals']['clusters']]}])
    client=genai.Client(enterprise=True,project='offline-test',location='global',credentials=AnonymousCredentials())
    calls=[]
    async def fake_stream(self,*,model,contents,config):
        calls.append(model)
        assert config.temperature==1.0
        assert config.thinking_config.thinking_level.value=='LOW'
        assert config.automatic_continuation is False
        assert config.response_mime_type=='application/json'
        text=json.dumps(outputs.popleft())
        async def chunks():
            for i,part in enumerate([text[:len(text)//2],text[len(text)//2:]]):
                yield types.GenerateContentResponse(candidates=[types.Candidate(index=0,
                    content=types.Content(role='model',parts=[types.Part(text=part)]),
                    finish_reason=types.FinishReason.STOP if i else None)])
        return chunks()
    monkeypatch.setattr(AsyncModels,'generate_content_stream',fake_stream)
    original=google.adk.agents.LlmAgent
    def factory(**kwargs):
        kwargs['model']=Gemini(model='offline-test',client=client,retry_options=types.HttpRetryOptions(attempts=1))
        return original(**kwargs)
    monkeypatch.setattr(google.adk.agents,'LlmAgent',factory)
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','true')
    monkeypatch.setenv('CLAIMCASCADE_PUBLIC_DEMO','false')
    events=[]
    async def scenario():
        try:
            return await asyncio.wait_for(run_agents(claims,bulletins,edges,'offline-test',
                request_policy=RequestPolicy(min_interval_seconds=0),on_request=events.append),timeout=5)
        finally:
            await client.aio.aclose()
    result=asyncio.run(scenario())
    assert result['proposals']==reference['proposals']
    assert len(calls)==8 and not outputs
    assert sum(e['event']=='first_adk_content' for e in events)==8
