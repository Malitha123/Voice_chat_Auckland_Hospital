"""Trust only signed LiveKit metadata produced by the health API."""
import time
from fastapi import HTTPException
from api.security import accounts, auth_mode


def validate_voice_session(identity: str, metadata: dict) -> None:
    if (
        not isinstance(metadata, dict)
        or metadata.get("health_authenticated") is not True
        or metadata.get("patient_id") != identity
        or not isinstance(metadata.get("auth_expires_at"), int)
        or metadata["auth_expires_at"] <= int(time.time())
    ):
        raise PermissionError("A current authenticated voice session is required")
    try:
        from api.routers.patients import _find_by_id
        patient = _find_by_id(identity)
        if patient is None or not patient.active:
            raise PermissionError("An active patient account is required")
        if metadata.get("account_version") is not None:
            if auth_mode() != "local":
                raise PermissionError("Local voice session is unavailable")
            account = next((a for a in accounts().values() if isinstance(a, dict) and a.get("sub") == identity), None)
            if not account or account.get("active") is not True or account.get("role") != "patient" or account.get("session_version") != metadata["account_version"]:
                raise PermissionError("Voice access has been revoked")
    except (HTTPException, OSError) as exc:
        raise PermissionError("Voice account validation failed") from exc
