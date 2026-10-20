"""Single-run pacing and a strict, visible provider-attempt budget."""
import asyncio
import random
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True)
    thinking_level: Literal['LOW','MEDIUM','HIGH'] | None = 'LOW'
    temperature: float = Field(default=1.0,ge=0,le=2,allow_inf_nan=False)
    min_interval_seconds: float = Field(default=30.0,ge=0,le=60,allow_inf_nan=False)
    max_attempts: int = Field(default=12,ge=1,le=12)
    retries_per_stage: int = Field(default=1,ge=0,le=1)
    initial_backoff_seconds: float = Field(default=30.0,ge=0,le=60,allow_inf_nan=False)
    max_backoff_seconds: float = Field(default=60.0,ge=0,le=60,allow_inf_nan=False)
    jitter_seconds: float = Field(default=3.0,ge=0,le=5,allow_inf_nan=False)


class RequestBudgetExceeded(RuntimeError):
    pass


def provider_status(error):
    """ADK can wrap provider errors; inspect structured codes, never message text."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        for attribute in ('code','status_code'):
            code = getattr(current,attribute,None)
            if isinstance(code,int) and not isinstance(code,bool):
                return code
        pending.extend(e for e in [current.__cause__,current.__context__] if e is not None)
        pending.extend(getattr(current,'exceptions',()))
    return None


def retry_after(error):
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        response = getattr(current,'response',None)
        headers = getattr(response,'headers',{}) or {}
        try:
            value = float(headers.get('Retry-After',headers.get('retry-after',0)))
            if 0 < value < float('inf'):
                return value
        except (ValueError,TypeError):
            pass
        pending.extend(e for e in [current.__cause__,current.__context__] if e is not None)
    return 0


class BoundedRequests:
    def __init__(self,policy=None,on_event=None,*,clock=time.monotonic,sleep=asyncio.sleep,jitter=random.uniform):
        self.policy = policy or RequestPolicy()
        self.on_event = on_event
        self.clock,self.sleep,self.jitter = clock,sleep,jitter
        self.attempts = []
        self.last_start = None

    async def run(self,stage,operation):
        backoff = 0
        for retry in range(self.policy.retries_per_stage+1):
            if len(self.attempts)>=self.policy.max_attempts:
                raise RequestBudgetExceeded(f'Provider request budget exhausted ({self.policy.max_attempts} attempts)')
            spacing = max(0,self.policy.min_interval_seconds-(self.clock()-self.last_start)) if self.last_start is not None else 0
            wait = max(spacing,backoff)
            if wait and self.on_event:
                self.on_event({'event':'waiting','stage':stage,'seconds':round(wait,2)})
            # Yield regularly, including when the provider requests a longer Retry-After.
            while wait>0:
                chunk = min(wait,30)
                await self.sleep(chunk)
                wait-=chunk
            started = self.clock()
            self.last_start=started
            record = dict(stage=stage,attempt=len(self.attempts)+1,stage_attempt=retry+1,status='running')
            self.attempts.append(record)
            if self.on_event:
                self.on_event(dict(record,event='attempt_started'))
            try:
                result = await operation()
            except BaseException as error:
                record.update(status='failed',provider_code=provider_status(error),error_type=type(error).__name__,latency_seconds=round(self.clock()-started,2))
                if self.on_event:
                    self.on_event(dict(record,event='attempt_finished'))
                if not isinstance(error,Exception) or record['provider_code'] not in (429,503) or retry==self.policy.retries_per_stage or len(self.attempts)>=self.policy.max_attempts:
                    raise
                delay = min(self.policy.max_backoff_seconds,self.policy.initial_backoff_seconds*2**retry+self.jitter(0,self.policy.jitter_seconds))
                backoff = max(delay,retry_after(error))
            else:
                record.update(status='complete',latency_seconds=round(self.clock()-started,2))
                if self.on_event:
                    self.on_event(dict(record,event='attempt_finished'))
                return result
