"""Run the actual ADK graph with a deterministic model double; no network."""
import asyncio
import json
import pytest
from collections import deque
from typing import ClassVar

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from claimcascade.core import candidates
from claimcascade.schemas import Settings
from claimcascade.services import offline_analysis
from claimcascade.synthetic import generate


def test_extraction_schema_requires_source_narrative():
    from pydantic import ValidationError
    from claimcascade.agents import narrative_schema
    claims,_,_=generate()
    schema=narrative_schema(claims[:10])
    fact={'claim_id':claims[0].claim_id,'kind':'cause','value':'test','excerpt':claims[0].narrative}
    schema.model_validate({'facts':[fact]})
    fact['excerpt']='incident_start: 2026-01-01'
    with pytest.raises(ValidationError):
        schema.model_validate({'facts':[fact]})


class ScriptedModel(BaseLlm):
    outputs: ClassVar[deque] = deque()
    requests: ClassVar[list] = []
    inject_429: ClassVar[bool] = False

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append('\n'.join(part.text or '' for content in llm_request.contents for part in content.parts or []))
        if self.inject_429 and len(self.requests)==2:
            from google.genai.errors import ClientError
            raise ClientError(429,{'error':{'code':429,'message':'Synthetic capacity error','status':'RESOURCE_EXHAUSTED'}})
        yield LlmResponse(content=types.Content(role='model',parts=[types.Part(text=json.dumps(self.outputs.popleft()))]), turn_complete=True)


@pytest.mark.parametrize('transient',[False,True])
@pytest.mark.parametrize('reuse',[False,True])
def test_actual_adk_workflow_offline(monkeypatch,transient,reuse):
    import google.adk.agents
    from claimcascade.agents import analyse_live
    claims, bulletins, _ = generate()
    edges = candidates(claims,Settings())
    result = offline_analysis(claims,edges)
    ScriptedModel.outputs = deque([{'facts':[]} for _ in range(5-int(reuse))] + [result['proposals'],{'objections':[]},
        {'explanations':[dict(cluster_id=c['cluster_id'],observed_facts=[],hypotheses=['Test double'],missing_information=[]) for c in result['proposals']['clusters']]}])
    ScriptedModel.requests = []
    ScriptedModel.inject_429 = transient
    original = google.adk.agents.LlmAgent
    def factory(**kwargs):
        assert kwargs['model'].retry_options.attempts==1
        assert kwargs['generate_content_config'].thinking_config.thinking_level.value=='LOW'
        assert kwargs['generate_content_config'].automatic_continuation is False
        assert kwargs['generate_content_config'].temperature==1.0
        kwargs['model']=ScriptedModel(model='offline-test')
        return original(**kwargs)
    monkeypatch.setattr(google.adk.agents,'LlmAgent',factory)
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','true')
    from claimcascade.requests import RequestPolicy
    actual = analyse_live(claims,bulletins,edges,'unused',request_policy=RequestPolicy(min_interval_seconds=0,initial_backoff_seconds=0,jitter_seconds=0),
                          completed_extractions={'extractor_0':{'facts':[]}} if reuse else None)
    assert actual['proposals']==result['proposals']
    assert len(actual['telemetry'])==8-int(reuse)
    assert len(actual['request_attempts'])==8-int(reuse)+int(transient)
    assert len(actual['reused_extractions'])==int(reuse)
    assert not ScriptedModel.outputs
    assert all('"events"' not in request and '"seed"' not in request and '"duplicate_of_claim_id"' not in request for request in ScriptedModel.requests)


def test_invalid_recovery_is_rejected_before_model_invocation(monkeypatch):
    from pydantic import ValidationError
    from claimcascade.agents import analyse_live
    import google.adk.agents
    claims,bulletins,_=generate()
    def forbidden(**kwargs):
        raise AssertionError('Model must not be invoked with invalid recovery data')
    monkeypatch.setattr(google.adk.agents,'LlmAgent',forbidden)
    monkeypatch.setenv('CLAIMCASCADE_ALLOW_PAID_CALLS','true')
    fact={'claim_id':claims[-1].claim_id,'kind':'cause','value':'test','excerpt':claims[-1].narrative}
    with pytest.raises(ValidationError):
        analyse_live(claims,bulletins,[],'unused',completed_extractions={'extractor_0':{'facts':[fact]}})
