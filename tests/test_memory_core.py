"""Real offline regressions for phone identity, voice settings and memory."""
import math
import pytest
from api.utils import normalize_phone, display_phone
from voice.config import VoiceConfig, load_voice_config
from memory.policies import score_memory_fact, apply_decay, dedupe_facts
from memory.schemas import MemoryFact, ConversationTurn
from memory.st_store import ShortTermMemoryStore


@pytest.mark.parametrize('raw', ['021 103 0736','+64 21 103 0736','64211030736','0064 21 103 0736'])
def test_nz_mobile_formats_match(raw):
    assert normalize_phone(raw) == '64211030736'
    assert display_phone(normalize_phone(raw)) == '+64211030736'


def test_landline_and_long_mobile():
    assert normalize_phone('09 555 0101') == '6495550101'
    assert normalize_phone('021 123 45678') == '642112345678'


@pytest.mark.parametrize('raw',['+94 78 103 0736','+61 412 884 291','abc0211030736','111','',None])
def test_foreign_or_invalid_phone_rejected(raw):
    assert normalize_phone(raw) == ''


def test_voice_false_is_false_and_defaults_match(monkeypatch):
    import voice.config as module
    monkeypatch.setattr(module,'_PARAMS',{'voice':{'interruption_enabled':'false'}})
    cfg=load_voice_config()
    assert cfg.interruption_enabled is False
    assert cfg.silence_threshold_ms == VoiceConfig.silence_threshold_ms
    assert cfg.min_endpointing_delay == VoiceConfig.min_endpointing_delay


@pytest.mark.parametrize('kwargs',[{'tts_provider':'typo'},{'stt_provider':'typo'},{'vad_threshold':float('nan')},{'sample_rate':1},{'min_endpointing_delay':-1}])
def test_invalid_voice_config_rejected(kwargs):
    with pytest.raises(ValueError): VoiceConfig(**kwargs)


def test_score_uses_seven_day_half_life_and_empty_keywords():
    assert score_memory_fact('plain',0,7*86400,0,[]) == .25
    assert 0 <= score_memory_fact('remember',86400,0) <= 1


def test_decay_rejects_invalid_half_life():
    fact=MemoryFact('x','user','text',.8,last_used_at=86400)
    for days in [0,-1,float('nan')]:
        with pytest.raises(ValueError):apply_decay(fact,0,days)
    assert apply_decay(fact,0,7) == .8


def test_dedup_keeps_distinct_facts_after_bridge_is_removed():
    facts=[MemoryFact(str(i),'user','text',score) for i,score in enumerate([.6,.5,.9])]
    class Embedder:
        def embed_documents(self,texts):
            return [[1,0],[math.cos(.3),math.sin(.3)],[math.cos(.6),math.sin(.6)]]
    assert [f.id for f in dedupe_facts(facts,.9,Embedder())] == ['0','2']


def test_short_term_append_rolls_back_insert_if_trim_fails():
    class Session:
        calls=0;commits=0;rollbacks=0;closed=False
        def execute(self,sql,params):
            self.calls+=1
            if self.calls==1: assert params['ttl_at'].tzinfo is not None
            if self.calls==2: raise RuntimeError('trim failed')
        def commit(self):self.commits+=1
        def rollback(self):self.rollbacks+=1
        def close(self):self.closed=True
    session=Session();store=ShortTermMemoryStore(lambda:session)
    turn=ConversationTurn(user_id='u',session_id='s',role='user',content='hello',ts=0)
    with pytest.raises(RuntimeError):store.append(turn,30,60)
    assert session.commits == 0 and session.rollbacks == 1 and session.closed


def test_voice_save_executes_and_persists_interrupted_text(monkeypatch):
    # Run the real method while isolating external model and LiveKit dependencies.
    import ast, asyncio, time, sys, types
    from pathlib import Path
    from loguru import logger
    source=Path(__file__).resolve().parents[1]/'src/agents/orchestrator.py'
    tree=ast.parse(source.read_text())
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_save_voice_turn_async')
    namespace={'ConversationTurn':ConversationTurn,'time':time,'logger':logger}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(source),'exec'),namespace)
    saved=[]
    fake=types.SimpleNamespace(st_store=types.SimpleNamespace(add=lambda u,s,t:saved.append(t),recent=lambda *a,**kw:[]),distiller=types.SimpleNamespace(should_distill=lambda _:False),llm_fast=None,llm_chat=None)
    stub=types.ModuleType('api.routers.chat_sessions');stub.touch_session_sync=lambda *a:None;stub.maybe_auto_title_sync=lambda **kw:None
    monkeypatch.setitem(sys.modules,'api.routers.chat_sessions',stub)
    async def direct_thread(func):func()
    monkeypatch.setattr(asyncio,'to_thread',direct_thread)
    async def run():
        result=namespace['_save_voice_turn_async'](fake,user_id='u',session_id='s',user_message='question',assistant_message='partial reply',was_interrupted=True)
        assert result is None
        await asyncio.sleep(0)
    asyncio.run(run())
    assert [turn.content for turn in saved]==['question','[interrupted] partial reply']
