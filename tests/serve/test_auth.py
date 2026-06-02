"""Tests for the OIDC auth layer.

These exercise the parts that don't require a real JWKS endpoint:
config parsing, bearer extraction, and the synthetic local-dev user.
Full token-verification flow is left for an integration test that
mocks JWKS (TODO: add when needed).
"""

from __future__ import annotations

import json

import pytest

# paradoc.serve.auth imports fastapi at module load, so skip this whole
# module in the lightweight `test` env (fastapi only ships in serve/e2e).
pytest.importorskip("fastapi")

from paradoc.serve.auth import (  # noqa: E402
    TokenError,
    User,
    _bearer_token,
    load_config_from_env,
)


class _CaseInsensitiveHeaders(dict):
    """Mimic Starlette's case-insensitive Headers."""

    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__({k.lower(): v for k, v in headers.items()})

    def get(self, key: str, default=None):
        return super().get(key.lower(), default)


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = _CaseInsensitiveHeaders(headers)


def test_local_dev_user_is_admin():
    u = User.local_dev()
    assert u.is_admin is True
    assert u.iss == "local-dev"
    assert u.subject == "local-dev"


def test_load_config_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PARADOC_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("PARADOC_OIDC_PROVIDERS_JSON", raising=False)
    cfg = load_config_from_env()
    assert cfg.enabled is False
    assert cfg.providers == ()


def test_load_config_with_providers(monkeypatch):
    monkeypatch.setenv("PARADOC_AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "PARADOC_OIDC_PROVIDERS_JSON",
        json.dumps(
            [
                {
                    "name": "authentik",
                    "issuer": "https://auth.example.com/app/o/paradoc/",
                    "client_id": "paradoc-client",
                },
                {
                    "name": "azure-ad",
                    "issuer": "https://login.microsoftonline.com/tid/v2.0",
                    "client_id": "paradoc-aad",
                    "audience": "api://paradoc-aad",
                    "subject_claim": "oid",
                },
            ]
        ),
    )
    cfg = load_config_from_env()
    assert cfg.enabled is True
    assert len(cfg.providers) == 2
    authentik, aad = cfg.providers
    # Trailing slashes stripped so iss exact-compare during decode lines up.
    assert authentik.issuer == "https://auth.example.com/app/o/paradoc"
    assert authentik.subject_claim == "sub"  # default
    assert authentik.audience == "paradoc-client"  # defaulted from client_id
    assert aad.subject_claim == "oid"  # explicit
    assert aad.audience == "api://paradoc-aad"


def test_load_config_enabled_without_providers_raises(monkeypatch):
    monkeypatch.setenv("PARADOC_AUTH_ENABLED", "true")
    monkeypatch.delenv("PARADOC_OIDC_PROVIDERS_JSON", raising=False)
    with pytest.raises(RuntimeError):
        load_config_from_env()


def test_load_config_malformed_json_raises(monkeypatch):
    monkeypatch.setenv("PARADOC_AUTH_ENABLED", "true")
    monkeypatch.setenv("PARADOC_OIDC_PROVIDERS_JSON", "not-json")
    with pytest.raises(RuntimeError):
        load_config_from_env()


def test_load_config_missing_required_field_raises(monkeypatch):
    monkeypatch.setenv("PARADOC_AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "PARADOC_OIDC_PROVIDERS_JSON",
        json.dumps([{"name": "x", "issuer": "https://x"}]),  # missing client_id
    )
    with pytest.raises(RuntimeError):
        load_config_from_env()


def test_bearer_token_extracts():
    req = _FakeRequest({"Authorization": "Bearer abc.def.ghi"})
    assert _bearer_token(req) == "abc.def.ghi"


def test_bearer_token_missing_raises():
    req = _FakeRequest({})
    with pytest.raises(TokenError):
        _bearer_token(req)


def test_bearer_token_wrong_scheme_raises():
    req = _FakeRequest({"Authorization": "Basic abc"})
    with pytest.raises(TokenError):
        _bearer_token(req)
