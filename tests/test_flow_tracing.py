from carbon_mesh.carbon_sources.flow_tracing import trace_consumption_intensity


def test_no_flows_consumption_equals_production():
    prod_mw = {"A": 100.0, "B": 100.0}
    prod_i = {"A": 500.0, "B": 0.0}
    c = trace_consumption_intensity(prod_mw, prod_i, {})
    assert c == {"A": 500.0, "B": 0.0}


def test_import_of_clean_power_lowers_consumption_intensity():
    # A is all coal (500), B is all hydro (0). B sends 50 MW into A.
    # A consumes 100 MW own coal + 50 MW clean import => (100*500)/(150) = 333.3.
    prod_mw = {"A": 100.0, "B": 100.0}
    prod_i = {"A": 500.0, "B": 0.0}
    flows = {("B", "A"): 50.0}
    c = trace_consumption_intensity(prod_mw, prod_i, flows)
    assert c["B"] == 0.0  # exporter's own consumption is unchanged
    assert abs(c["A"] - 333.3) < 0.5  # importer is pulled cleaner


def test_import_of_dirty_power_raises_consumption_intensity():
    # Clean zone B imports coal from A -> its consumption intensity rises above 0.
    prod_mw = {"A": 100.0, "B": 100.0}
    prod_i = {"A": 500.0, "B": 0.0}
    flows = {("A", "B"): 50.0}
    c = trace_consumption_intensity(prod_mw, prod_i, flows)
    assert abs(c["B"] - (50.0 * 500.0 / 150.0)) < 0.5  # 166.7
    assert c["A"] == 500.0


def test_unknown_zones_and_negative_flows_ignored():
    prod_mw = {"A": 100.0}
    prod_i = {"A": 300.0}
    flows = {("X", "A"): 40.0, ("A", "A"): -5.0}  # unknown src + negative
    c = trace_consumption_intensity(prod_mw, prod_i, flows)
    assert c == {"A": 300.0}


def test_loop_converges():
    # Mutual exchange between two zones still converges to a fixed point.
    prod_mw = {"A": 200.0, "B": 200.0}
    prod_i = {"A": 400.0, "B": 100.0}
    flows = {("A", "B"): 60.0, ("B", "A"): 40.0}
    c = trace_consumption_intensity(prod_mw, prod_i, flows)
    # Both finite, A dirtier than B, and each between the two production values.
    assert 100.0 <= c["B"] <= c["A"] <= 400.0
