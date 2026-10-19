"""Run the actual ADK graph with a deterministic model double; no network."""
import asyncio
import json
from collections import deque
from typing import ClassVar

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from claimcascade.core import candidates
from claimcascade.schemas import Settings
from claimcascade.services import offline_analysis
from claimcascade.synthetic import generate


class ScriptedModel(BaseLlm):
    outputs: ClassVar[deque] = deque()
    requests: ClassVar[list] = []

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append('\n'.join(part.text or '' for content in llm_request.contents for part in content.parts or []))
        yield LlmResponse(content=types.Content(role='model',parts=[types.Part(text=json.dumps(self.outputs.popleft()))]), turn_complete=True)


def test_actual_adk_workflow_offline(monkeypatch):
    import google.adk.agents
    from claimcascade.agents import analyse_live
    claims, bulletins, _ = generate()
    edges = candidates(claims,Settings())
    result = offline_analysis(claims,edges)
    ScriptedModel.outputs = deque([{'facts':[]} for _ in range(5)] + [result['proposals'],{'objections':[]},
        {'explanations':[dict(cluster_id=c['cluster_id'],observed_facts=[],hypotheses=['Test double'],missing_information=[]) for c in result['proposals']['clusters']]}])
    ScriptedModel.requests = []
    original = google.adk.agents.LlmAgent
    def factory(**kwargs):
        kwargs['model']=ScriptedModel(model='offline-test')
        return original(**kwargs)
    monkeypatch.setattr(google.adk.agents,'LlmAgent',factory)
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','true')
    actual = analyse_live(claims,bulletins,edges,'unused')
    assert actual['proposals']==result['proposals']
    assert len(actual['telemetry'])==8
    assert not ScriptedModel.outputs
    assert all('"events"' not in request and '"seed"' not in request and '"duplicate_of_claim_id"' not in request for request in ScriptedModel.requests)
