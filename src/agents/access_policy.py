"""Bind private CRM calls to verified identity independently of model output."""
import re

PRIVACY_REFUSAL = (
    "I can only access appointments and health records for your signed-in account. "
    "I can't access another person's records. They need to sign in themselves "
    "or contact the clinic about authorised access."
)
PRIVATE_ACTIONS = {"lookup_patient", "create_booking", "cancel_booking", "reschedule_booking"}


def asks_for_other_patient(message: str, patient_name: str = "") -> bool:
    # This wording check improves the refusal. Authorization always binds the
    # actual tool arguments below, even if a paraphrase bypasses this check.
    patterns = (
        r"\b(?:appointments?|health records?|medical records?|bookings?)\s+(?:of|for|belonging to)\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+)",
        r"\b([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)+)'s\s+(?:appointments?|health records?|medical records?|bookings?)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, message):
            target = match.group(1).strip()
            if not patient_name or target.casefold() != patient_name.casefold():
                return True
    return False


def dispatch_for_patient(tool, action: str, params: dict, patient_id: str):
    params = dict(params or {})
    if action in PRIVATE_ACTIONS:
        if not patient_id or (params.get("patient_id") and params["patient_id"] != patient_id):
            return PRIVACY_REFUSAL
        if any(params.get(k) for k in ("name", "patient_name", "phone", "external_user_id", "user_id")):
            return PRIVACY_REFUSAL
        params["patient_id"] = patient_id
    return tool.dispatch(action, params)
