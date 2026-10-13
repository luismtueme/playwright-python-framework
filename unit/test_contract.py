from config import ROOT
from utils.contract import Contract, ContractResponse, ContractViolation

SPEC = str(ROOT / "contracts" / "openapi.yaml")


def test_accepts_a_documented_item() -> None:
    contract = Contract(SPEC)
    problems = contract.check(
        ContractResponse(
            method="POST",
            path="/api/items",
            status=201,
            body={"id": 1, "name": "Manhole", "createdAt": "2026-01-05T09:00:00.000Z"},
        )
    )
    assert problems == []


def test_rejects_an_undocumented_field() -> None:
    contract = Contract(SPEC)
    problems = contract.check(
        ContractResponse(
            method="GET",
            path="/api/items/7",
            status=200,
            body={"id": 7, "name": "Manhole", "createdAt": "2026-01-05T09:00:00.000Z", "secret": "nope"},
        )
    )
    assert problems
    assert any("secret" in problem for problem in problems)


def test_rejects_an_unknown_route_and_status() -> None:
    contract = Contract(SPEC)
    assert contract.check(ContractResponse(method="GET", path="/api/missing", status=200, body={}))
    problems = contract.check(ContractResponse(method="GET", path="/api/items", status=418, body={}))
    assert "418" in problems[0]


def test_empty_body_is_allowed_when_the_status_has_no_schema() -> None:
    contract = Contract(SPEC)
    assert contract.check(ContractResponse(method="DELETE", path="/api/items/4", status=204, body="")) == []
    problems = contract.check(ContractResponse(method="DELETE", path="/api/items/4", status=204, body={"extra": True}))
    assert problems


def test_ref_response_uses_the_error_schema() -> None:
    contract = Contract(SPEC)
    problems = contract.check(
        ContractResponse(method="GET", path="/api/items", status=401, body={"error": {"code": "UNAUTHORIZED"}})
    )
    assert problems == []


def test_violation_lists_every_problem() -> None:
    error = ContractViolation(["one", "two"])
    assert "one" in str(error)
    assert "two" in str(error)


def test_template_for_a_concrete_id() -> None:
    contract = Contract(SPEC)
    assert contract.template_for("/api/items/9?x=1") == "/api/items/{id}"
