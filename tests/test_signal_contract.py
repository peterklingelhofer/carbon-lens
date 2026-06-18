"""Contract test for /carbon/signal -- the stable shape the carbon-aware-dispatcher
(and the SDK, Action, k8s controller, integrations) consume. If a field is renamed,
retyped, or dropped, this fails -- keeping the loosely-coupled contract honest."""

from fastapi.testclient import TestClient


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def test_signal_contract(client: TestClient):
    body = client.get("/api/v1/carbon/signal/aws/us-east-1").json()

    # Identity + the run-now/wait decision the dispatcher keys on.
    for key in ("provider", "region", "grid_zone", "state", "advice", "marginal_basis"):
        assert isinstance(body[key], str), key
    assert body["state"] in {"green", "yellow", "red"}
    assert body["advice"] in {"run_now", "wait_for_cleaner"}
    assert body["marginal_basis"] in {"measured", "heuristic"}
    assert _is_num(body["intensity_gco2_kwh"])
    assert isinstance(body["clean_surplus"], bool)

    # Optional/nullable fields: present in the schema, null or typed.
    assert body["surplus_window_in_hours"] is None or isinstance(
        body["surplus_window_in_hours"], int
    )
    assert body["cleaner_window_in_hours"] is None or isinstance(
        body["cleaner_window_in_hours"], int
    )
    assert body["marginal_intensity_gco2_kwh"] is None or _is_num(
        body["marginal_intensity_gco2_kwh"]
    )
    assert body["marginal_note"] is None or isinstance(body["marginal_note"], str)
