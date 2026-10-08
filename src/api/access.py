"""HTTP access rules checked before patient data or tools are used."""
import asyncio

from fastapi import HTTPException, Request

from api.security import require_principal


async def protect_request(request: Request):
    path = request.url.path
    if path in {"/", "/health", "/auth/login", "/auth/me"}:
        return
    principal = require_principal(request)
    if path in {"/ready", "/config", "/patients/lookup", "/patients/register"} or (path.startswith("/tools/") and not path.startswith("/tools/memory/")):
        if principal.role not in {"staff", "admin"}:
            raise HTTPException(403, "Staff role required")
        if path == "/tools/cag/set":
            raise HTTPException(403, "Shared cache accepts trusted startup reference data only")
        return
    if principal.role != "patient":
        raise HTTPException(403, "Patient role required")

    from api.routers.patients import _find_by_id
    patient = await asyncio.to_thread(_find_by_id, principal.sub)
    if patient is None or not patient.active:
        raise HTTPException(403, "An active patient account is required")
    request.state.patient = patient

    body = {}
    if request.method in {"POST", "PUT", "PATCH"} and "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(422, "Expected a JSON object")
    for values in (body, request.query_params, request.path_params):
        for key in ("user_id", "patient_id"):
            if key in values and values[key] != principal.sub:
                raise HTTPException(403, "Patient identity must match the signed-in account")

    session_id = body.get("session_id") or request.path_params.get("session_id") or request.query_params.get("session_id")
    if session_id:
        from api.routers.chat_sessions import ensure_session_owner
        allow_new = request.method == "POST" and path in {"/chat", "/chat/stream", "/sessions/warmup", "/chat_sessions"}
        await asyncio.to_thread(ensure_session_owner, principal.sub, session_id, allow_new, path != "/chat_sessions")
