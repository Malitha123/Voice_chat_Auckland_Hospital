# Authentication and patient access

Every patient API request needs a verified bearer token and an active patient profile. A phone number, name, browser profile cache or model-generated patient ID cannot grant access. Patient identities must match `patients.patient_id`; chat sessions are checked against their owner before retrieval or mutation. Staff-only registration, phone lookup, diagnostics and tool endpoints require a signed staff/admin role.

Private CRM tool calls bind the subject outside the model. Another patient ID, phone or name is refused. Appointment cancellation and rescheduling check booking ownership in SQL. The Nathan James / Claire Webster regression returns: “I can only access appointments and health records for your signed-in account. I can't access another person's records. They need to sign in themselves or contact the clinic about authorised access.” Family and representative access is not implemented; the clinic must handle those requests through its authorised process.

## Local authentication mode

Provision separate accounts against existing synthetic patient UUIDs:

```bash
export PYTHONPATH=src
python -m api.security private-auth/accounts.json nathan --subject "$HEALTH_PATIENT_ID" --role patient
```

The command prompts for a password of at least 12 characters and stores a salted scrypt hash. Set `HEALTH_PATIENT_ID` to that patient's real database UUID before provisioning. There are no bundled credentials. Keep the account file private; re-provisioning increments its session version and revokes previous local tokens.

For local authentication configure:

```dotenv
HEALTH_AUTH_MODE=local
HEALTH_AUTH_ENV=local
HEALTH_AUTH_ACCOUNTS_FILE=private-auth/accounts.json
HEALTH_AUTH_SECRET=<generated-secret-of-at-least-32-characters>
```

Generate a secret with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. Local authentication mode is rejected with `APP_ENV=production` or without the matching local environment setting. Password sign-in uses `POST /auth/login` with `username` and `password`, then `GET /patients/me` with the returned bearer token. Local tokens last 15 minutes; every verification reloads the account's active flag, role and version. The basic login rate limiter is local to each process.

Compose mounts `./private-auth` read-only into both API and voice containers. Use `/app/private-auth/accounts.json` for the account-file setting there. Keep the same account file and secret on both processes. Account hashes and secrets must not be committed or included in a Docker build.

## Production identity provider

The default verifier mode is OIDC, with RS256 only. Configure `HEALTH_AUTH_ISSUER`, `HEALTH_AUTH_AUDIENCE` and `HEALTH_AUTH_JWKS_URL`. Issuer and key URLs require HTTPS. The signed `sub` identifies the patient UUID and `role` must be `patient`, `staff` or `admin`; configured `HEALTH_AUTH_IDENTITY_CLAIM` and `HEALTH_AUTH_ROLE_CLAIM` can select the equivalent server-managed claims. Issuer, audience, signature, expiry and issued-at claims are validated. Key discovery uses the configured URL, never a URL supplied by a token.

The local credential form serves local accounts. A production deployment still needs its identity provider's browser sign-in integration to supply bearer tokens, account provisioning/mapping, short token lifetimes and gateway/session revocation. Staff permissions are broad within one deployment; finer clinical responsibilities and organisation boundaries need an explicit policy.

## Voice and shared services

Voice tokens use the verified patient UUID, the stored display name, and a random room assigned by the server. Caller-supplied room names are refused. The signed metadata cannot be edited by the participant. Room grants last at most ten minutes and never outlive the API token. Worker access is checked at joining, before each turn and periodically; expiry, disabled patient profiles and local-account revocation end access. LiveKit signing credentials remain privileged server secrets. Private CRM and memory MCP tools require an application bearer token and the same patient binding. Cache maintenance and crawling MCP operations require an administrator. Shared semantic caches use fresh reference namespaces and only trusted startup FAQ/reference seeds; generated replies are not written to the shared cache. Stale responses from a previous account cannot populate a new account's sidebar or chat. A lost stream does not automatically resubmit a potentially completed booking.

Sensitive Langfuse tracing is off by default, and routine voice logging omits transcript previews. `HEALTH_ALLOW_SENSITIVE_TRACES=true` is an explicit deployment decision requiring retention, recipient and redaction review. Production deployment requires organisation-specific decisions for durable access logging, retention and deletion workflows, delegated access, distributed login throttling, and formal compliance review.

See [NZ_PRIVACY_POLICY.md](NZ_PRIVACY_POLICY.md) for the NZ policy draft and remaining operational decisions.
