"""Validate the production token verifier with real RSA signatures without an IdP network call."""
import time
from types import SimpleNamespace
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from api import security


@pytest.fixture
def issuer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for name, value in {"MODE":"oidc", "ISSUER":"https://idp.example", "AUDIENCE":"health-api", "JWKS_URL":"https://idp.example/keys"}.items():
        monkeypatch.setenv("HEALTH_AUTH_"+name, value)
    monkeypatch.setattr(security,"_jwks",lambda _:SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key())))
    now=int(time.time())
    claims={"sub":"verified-subject","role":"patient","iss":"https://idp.example","aud":"health-api","iat":now,"exp":now+300}
    return key,claims


def test_verified_oidc_subject_and_role(issuer):
    key,claims=issuer
    p=security.verify_token(jwt.encode(claims,key,algorithm="RS256"))
    assert (p.sub,p.role)==("verified-subject","patient")


@pytest.mark.parametrize("change",[{"aud":"another-api"},{"iss":"https://other-idp.example"},{"exp":1},{"iat":int(time.time())+3600},{"sub":""},{"role":"chosen-by-caller"}])
def test_invalid_signed_claims_are_rejected(issuer,change):
    key,claims=issuer
    with pytest.raises(HTTPException) as error:
        security.verify_token(jwt.encode({**claims,**change},key,algorithm="RS256"))
    assert error.value.status_code==401


def test_missing_required_claim_and_algorithm_confusion_are_rejected(issuer):
    key,claims=issuer
    for name in ["sub","exp","iat","iss","aud"]:
        changed={k:v for k,v in claims.items() if k!=name}
        with pytest.raises(HTTPException):security.verify_token(jwt.encode(changed,key,algorithm="RS256"))
    with pytest.raises(HTTPException):security.verify_token(jwt.encode(claims,"attacker-controlled-secret-32-characters",algorithm="HS256"))


def test_insecure_oidc_configuration_is_unavailable(issuer,monkeypatch):
    key,claims=issuer
    monkeypatch.setenv("HEALTH_AUTH_JWKS_URL","http://idp.example/keys")
    with pytest.raises(HTTPException) as error:security.verify_token(jwt.encode(claims,key,algorithm="RS256"))
    assert error.value.status_code==503


def test_local_auth_cannot_be_enabled_in_production(monkeypatch):
    monkeypatch.setenv("HEALTH_AUTH_MODE","local")
    monkeypatch.setenv("HEALTH_AUTH_ENV","local")
    monkeypatch.setenv("APP_ENV","production")
    with pytest.raises(HTTPException) as error:security.auth_mode()
    assert error.value.status_code==503
