"""IngressTrustPolicy: header-based principal extraction."""

from paradoc.serve.auth import AuthDecision, IngressTrustPolicy


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = {k.lower(): v for k, v in headers.items()}


def test_allows_anonymous_by_default():
    policy = IngressTrustPolicy()
    decision = policy.authorize(doc_id="d", request=FakeRequest({}))
    assert decision.allowed
    assert decision.principal is None


def test_extracts_oauth2_proxy_user():
    policy = IngressTrustPolicy()
    req = FakeRequest({"X-Auth-Request-User": "alice@example.com"})
    decision = policy.authorize(doc_id="d", request=req)
    assert decision.allowed
    assert decision.principal == "alice@example.com"


def test_extracts_x_user_id():
    policy = IngressTrustPolicy()
    req = FakeRequest({"X-User-Id": "bob"})
    decision = policy.authorize(doc_id="d", request=req)
    assert decision.allowed
    assert decision.principal == "bob"


def test_require_principal_rejects_anonymous():
    policy = IngressTrustPolicy(require_principal=True)
    decision = policy.authorize(doc_id="d", request=FakeRequest({}))
    assert not decision.allowed
    assert decision.status_code == 401


def test_decision_helpers():
    allow = AuthDecision.allow("alice")
    assert allow.allowed and allow.principal == "alice"
    deny = AuthDecision.deny(status_code=404, reason="missing")
    assert not deny.allowed and deny.status_code == 404
