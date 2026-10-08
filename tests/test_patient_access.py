import asyncio
import json
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api import security
from api.main import app
from api.routers import patients, chat_sessions
from agents.access_policy import PRIVACY_REFUSAL, dispatch_for_patient
from agents.orchestrator import AgentOrchestrator
from agents.tools.crm_tool import CRMTool
from infrastructure.db.crm_models import Base, Patient, ChatSession, Booking, Doctor, Location

NATHAN = "11111111-1111-4111-8111-111111111111"
CLAIRE = "22222222-2222-4222-8222-222222222222"
SECRET = "health-access-test-secret-at-least-32-characters"


@pytest.fixture
def secured(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "patients.db"), connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s, s.begin():
        s.add_all([
            Patient(patient_id=NATHAN, full_name="Nathan James", phone="+64211030736", dob="1986-01-01", gender="M", active=1),
            Patient(patient_id=CLAIRE, full_name="Claire Webster", phone="+64212030736", dob="1990-01-01", gender="F", active=1),
            ChatSession(session_id="nathan-session", patient_id=NATHAN, title="Nathan's conversation", archived=0),
            ChatSession(session_id="claire-session", patient_id=CLAIRE, title="Claire's conversation", archived=0),
            Doctor(doctor_id="doctor", full_name="Dr. Aroha Williams", active=1),
            Location(location_id="clinic", name="Auckland Clinic", type="CLINIC", tz="Pacific/Auckland", active=1),
        ])
    with factory() as s, s.begin():
        s.add(Booking(booking_id="claire-booking", patient_id=CLAIRE, doctor_id="doctor", location_id="clinic", title="Consultation", status="CONFIRMED", source="CRM", start_at=int(time.time())+86400, end_at=int(time.time())+88200))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE st_turns (user_id TEXT, session_id TEXT, content TEXT)"))
        conn.execute(text("INSERT INTO st_turns VALUES (:u, 'claire-session', 'private Claire record')"), {"u": CLAIRE})
    monkeypatch.setattr(patients, "get_sql_engine", lambda: engine)
    monkeypatch.setattr(chat_sessions, "get_sql_engine", lambda: engine)
    account_file = tmp_path / "accounts.json"
    account_file.write_text(json.dumps({
        "nathan": {"sub": NATHAN, "role": "patient", "active": True, "session_version": 1, "password_hash": security.password_hash("nathan-test-password")},
        "claire": {"sub": CLAIRE, "role": "patient", "active": True, "session_version": 1, "password_hash": security.password_hash("claire-test-password")},
        "staff": {"sub": "staff", "role": "staff", "active": True, "session_version": 1, "password_hash": security.password_hash("staff-test-password")},
    }))
    for key, value in {"MODE":"local", "ENV":"local", "SECRET":SECRET, "ACCOUNTS_FILE":str(account_file)}.items():
        monkeypatch.setenv("HEALTH_AUTH_" + key, value)
    monkeypatch.setenv("APP_ENV", "offline")
    security._attempts.clear()
    def headers(subject=NATHAN, role="patient", **changes):
        now=int(time.time())
        data={"sub":subject,"role":role,"ver":1,"iss":"health-local","aud":"health-api","iat":now,"exp":now+900,**changes}
        return {"Authorization":"Bearer "+jwt.encode(data,SECRET,algorithm="HS256")}
    monkeypatch.setattr(app.state, "agent", SimpleNamespace(st_store=SimpleNamespace(recent=lambda *a: [],clear=lambda *a:None),lt_store=SimpleNamespace(get_all_facts=lambda *a:[])),raising=False)
    monkeypatch.setattr(app.state, "session_cache", {}, raising=False)
    return SimpleNamespace(client=TestClient(app), headers=headers, engine=engine, factory=factory, accounts=account_file)


@pytest.mark.parametrize("method,path", [
    ("GET", "/patients/"+CLAIRE), ("POST", "/patients/lookup"),
    ("POST", "/chat"), ("POST", "/chat/stream"),
    ("GET", "/chat_sessions"), ("DELETE", "/chat_sessions/claire-session"),
    ("POST", "/voice/token"), ("POST", "/tools/crm/lookup_patient"),
    ("GET", "/tools/memory/facts/"+CLAIRE), ("POST", "/tools/cag/set"),
])
def test_anonymous_requests_stop_before_body_parsing(secured, method, path):
    assert secured.client.request(method,path,content="invalid-json",headers={"Content-Type":"application/json"}).status_code == 401


def test_verified_login_returns_only_own_patient(secured):
    response=secured.client.post("/auth/login",json={"username":"nathan","password":"nathan-test-password"})
    assert response.status_code == 200
    headers={"Authorization":"Bearer "+response.json()["access_token"]}
    assert secured.client.get("/patients/me",headers=headers).json()["full_name"] == "Nathan James"
    assert secured.client.get("/patients/"+CLAIRE,headers=headers).status_code == 403


@pytest.mark.parametrize("path,body", [
    ("/chat",{"user_id":CLAIRE,"session_id":"claire-session","message":"my appointments"}),
    ("/chat_sessions",{"user_id":CLAIRE}),
    ("/tools/memory/recall",{"user_id":CLAIRE,"session_id":"claire-session","query":"allergies"}),
    ("/voice/token",{"user_id":CLAIRE}),
])
def test_signed_in_account_cannot_spoof_subject(secured, path, body):
    assert secured.client.post(path,json=body,headers=secured.headers()).status_code == 403


def test_session_read_rename_delete_and_reuse_are_owned(secured):
    c,h=secured.client,secured.headers()
    assert c.get(f"/sessions/claire-session/turns?user_id={NATHAN}",headers=h).status_code == 404
    assert c.patch("/chat_sessions/claire-session",json={"title":"stolen"},headers=h).status_code == 404
    assert c.delete("/chat_sessions/claire-session",headers=h).status_code == 404
    assert c.post("/chat",json={"user_id":NATHAN,"session_id":"claire-session","message":"hello"},headers=h).status_code == 404
    with secured.factory() as s:
        assert s.get(ChatSession,"claire-session").title == "Claire's conversation"
    assert c.patch("/chat_sessions/nathan-session",json={"title":"My appointments"},headers=h).status_code == 200
    assert c.get(f"/tools/memory/facts/{NATHAN}",headers=h).status_code == 200


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_nathan_cannot_request_claires_appointments(secured, path):
    response=secured.client.post(path,headers=secured.headers(),json={"user_id":NATHAN,"session_id":"nathan-session","message":"I want to see the upcoming appointments of Claire Webster"})
    assert response.status_code == 200
    if path=="/chat": assert response.json()["answer"] == PRIVACY_REFUSAL and response.json()["route"] == "privacy"
    else: assert "signed-in account" in response.text and '"route": "privacy"' in response.text


def test_llm_tool_arguments_cannot_choose_another_patient():
    calls=[]
    tool=SimpleNamespace(dispatch=lambda a,p:calls.append((a,p)) or "own result")
    for params in [{"patient_id":CLAIRE},{"name":"Claire Webster"},{"phone":"+64212030736"}]:
        assert dispatch_for_patient(tool,"lookup_patient",params,NATHAN)==PRIVACY_REFUSAL
    assert not calls
    assert dispatch_for_patient(tool,"lookup_patient",{},NATHAN)=="own result"
    assert calls[0][1]["patient_id"]==NATHAN


def test_graph_and_fast_voice_refuse_before_model_or_memory():
    agent=object.__new__(AgentOrchestrator)
    message="I want to see the upcoming appointments of Claire Webster"
    assert agent.chat(message,NATHAN,"session").answer==PRIVACY_REFUSAL
    async def run():
        assert (await agent.achat(message,NATHAN,"session")).answer==PRIVACY_REFUSAL
        for method in [agent.achat_stream, agent.achat_stream_fast]:
            events=[event async for event in method(message,NATHAN,"session")]
            assert events[0]==("token",PRIVACY_REFUSAL)
    asyncio.run(run())


def test_crm_booking_ownership_is_checked_in_sql(secured):
    tool=object.__new__(CRMTool);tool.engine=secured.engine;tool._tz=ZoneInfo("Pacific/Auckland")
    assert "required" in tool.cancel_booking(booking_id="claire-booking")
    assert "required" in tool.reschedule_booking(booking_id="claire-booking",new_start_at="2090-01-01T12:00:00+13:00")
    assert "not belong" in tool.cancel_booking(patient_id=NATHAN,booking_id="claire-booking")
    assert "not belong" in tool.reschedule_booking(patient_id=NATHAN,booking_id="claire-booking",new_start_at="2090-01-01T12:00:00+13:00")
    assert "Claire Webster" not in tool.lookup_patient(patient_id="missing",name="Claire Webster")
    with secured.factory() as s: assert s.get(Booking,"claire-booking").status=="CONFIRMED"


@pytest.mark.parametrize("change",[{"exp":1},{"role":"staff"},{"ver":0}])
def test_expired_or_spoofed_account_is_rejected(secured, change):
    assert secured.client.get("/patients/me",headers=secured.headers(**change)).status_code == 401


def test_deactivated_patient_and_revoked_local_token_are_rejected(secured):
    h=secured.headers()
    data=json.loads(secured.accounts.read_text());data["nathan"]["session_version"]=2;secured.accounts.write_text(json.dumps(data))
    assert secured.client.get("/patients/me",headers=h).status_code==401
    data["nathan"]["session_version"]=1;secured.accounts.write_text(json.dumps(data))
    with secured.factory() as s,s.begin():s.get(Patient,NATHAN).active=0
    assert secured.client.get("/patients/me",headers=h).status_code==403


def test_voice_token_has_verified_identity_isolated_room_and_expiry(secured,monkeypatch):
    from api.routers import voice
    if voice.livekit_api is None:pytest.skip("Install livekit-api to verify signed voice grants")
    monkeypatch.setenv("LIVEKIT_URL","wss://voice.example.test")
    monkeypatch.setenv("LIVEKIT_API_KEY","voice-test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET","voice-test-secret-with-at-least-32-characters")
    c,h=secured.client,secured.headers(exp=int(time.time())+120)
    assert c.post("/voice/token",headers=h,json={"room":"claires-room"}).status_code==403
    tokens=[c.post("/voice/token",headers=h,json={"name":"Claire Webster"}).json() for _ in range(2)]
    assert tokens[0]["room"] != tokens[1]["room"]
    payload=jwt.decode(tokens[0]["token"],options={"verify_signature":False})
    assert payload["sub"]==NATHAN and payload["name"]=="Nathan James"
    assert payload["video"]["room"]==tokens[0]["room"] and payload["video"]["canUpdateOwnMetadata"] is False
    assert payload["exp"]-payload["nbf"]<=120


def test_voice_checks_expiry_and_account_revocation_on_every_turn(secured):
    from api.voice_access import validate_voice_session
    metadata={"health_authenticated":True,"patient_id":NATHAN,"auth_expires_at":int(time.time())+60,"account_version":1}
    validate_voice_session(NATHAN,metadata)
    with pytest.raises(PermissionError):validate_voice_session(CLAIRE,metadata)
    with pytest.raises(PermissionError):validate_voice_session(NATHAN,{**metadata,"auth_expires_at":1})
    data=json.loads(secured.accounts.read_text());data["nathan"]["active"]=False;secured.accounts.write_text(json.dumps(data))
    with pytest.raises(PermissionError):validate_voice_session(NATHAN,metadata)


def test_private_mcp_cannot_read_other_patient(secured):
    from mcp_servers import crm_server,memory_server
    token=secured.headers()["Authorization"][7:]
    with pytest.raises(PermissionError):memory_server.list_facts(CLAIRE,actor_token=token)
    with pytest.raises(PermissionError):memory_server.list_facts(NATHAN)
    with pytest.raises(PermissionError):crm_server.lookup_patient(patient_id=CLAIRE)


def test_shared_cache_and_sensitive_traces_are_disabled_by_default(monkeypatch):
    from services.chat_service.cag_cache import CAGCache
    from infrastructure.observability import _is_enabled
    monkeypatch.delenv("HEALTH_ALLOW_SENSITIVE_TRACES",raising=False)
    cache=object.__new__(CAGCache);cache.allow_write=False
    cache.set("Nathan's condition",{"answer":"private"})
    assert _is_enabled() is False


def test_patient_cannot_use_staff_tools_or_runtime_cache_writes(secured):
    assert secured.client.post("/patients/lookup",headers=secured.headers(),json={"phone":"021 203 0736"}).status_code==403
    assert secured.client.get("/config",headers=secured.headers()).status_code==403
    assert secured.client.post("/tools/cag/set",headers=secured.headers("staff","staff"),json={"query":"hello","answer":"private"}).status_code==403
