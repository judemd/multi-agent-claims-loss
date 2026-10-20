import asyncio

import pytest

from claimcascade.requests import BoundedRequests, RequestBudgetExceeded, RequestPolicy, provider_status


class ProviderError(Exception):
    def __init__(self,code):
        self.code=code


class Clock:
    def __init__(self):
        self.now=0
        self.sleeps=[]

    def __call__(self):
        return self.now

    async def sleep(self,delay):
        self.sleeps.append(delay)
        self.now+=delay


def test_pacing_and_wrapped_429_retry():
    clock=Clock()
    requests=BoundedRequests(RequestPolicy(jitter_seconds=0),clock=clock,sleep=clock.sleep)
    calls=[]
    async def operation():
        calls.append(clock.now)
        if len(calls)==1:
            try:
                raise ProviderError(429)
            except ProviderError as error:
                raise RuntimeError('ADK wrapper') from error
        return 'ok'
    async def scenario():
        assert await requests.run('extractor',operation)=='ok'
        assert await requests.run('investigator',operation)=='ok'
    asyncio.run(scenario())
    assert calls==[0,30,60]
    assert [r['status'] for r in requests.attempts]==['failed','complete','complete']


@pytest.mark.parametrize('code',[400,401,403,404,None])
def test_no_retry_for_nontransient_errors(code):
    clock=Clock()
    requests=BoundedRequests(clock=clock,sleep=clock.sleep)
    async def operation():
        if code is None:
            raise TimeoutError('Unknown request outcome')
        raise ProviderError(code)
    with pytest.raises(Exception):
        asyncio.run(requests.run('stage',operation))
    assert len(requests.attempts)==1
    assert not clock.sleeps


def test_stage_retry_and_global_budget_are_bounded():
    clock=Clock()
    requests=BoundedRequests(RequestPolicy(max_attempts=2,min_interval_seconds=0,initial_backoff_seconds=0,jitter_seconds=0),clock=clock,sleep=clock.sleep)
    async def exhausted():
        raise ProviderError(429)
    with pytest.raises(ProviderError):
        asyncio.run(requests.run('extractor',exhausted))
    assert len(requests.attempts)==2
    with pytest.raises(RequestBudgetExceeded):
        asyncio.run(requests.run('reporter',exhausted))
    assert len(requests.attempts)==2


def test_retry_after_is_respected_and_cancel_is_not_retried():
    clock=Clock()
    requests=BoundedRequests(RequestPolicy(jitter_seconds=0),clock=clock,sleep=clock.sleep)
    count=0
    async def operation():
        nonlocal count
        count+=1
        if count==1:
            error=ProviderError(503)
            error.response=type('Response',(),{'headers':{'Retry-After':'75'}})()
            raise error
    asyncio.run(requests.run('stage',operation))
    assert clock.now==75 and max(clock.sleeps)<=30
    async def cancelled():
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(requests.run('cancelled',cancelled))
    assert len(requests.attempts)==3
    assert requests.attempts[-1]['status']=='failed'
