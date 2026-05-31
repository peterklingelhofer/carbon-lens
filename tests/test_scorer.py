from carbon_mesh.engine.scorer import score_candidates


def test_score_ranks_by_carbon():
    candidates = [
        {
            "provider": "aws",
            "region": "us-east-1",
            "grid_zone": "PJM",
            "carbon_intensity": 350,
            "renewable_percentage": 15,
        },
        {
            "provider": "gcp",
            "region": "europe-north1",
            "grid_zone": "FI",
            "carbon_intensity": 80,
            "renewable_percentage": 85,
        },
        {
            "provider": "aws",
            "region": "us-west-2",
            "grid_zone": "BPAT",
            "carbon_intensity": 50,
            "renewable_percentage": 90,
        },
    ]
    scored = score_candidates(candidates)
    assert scored[0].region == "us-west-2"  # Lowest carbon
    assert scored[-1].region == "us-east-1"  # Highest carbon


def test_score_savings_calculation():
    candidates = [
        {
            "provider": "a",
            "region": "clean",
            "grid_zone": "C",
            "carbon_intensity": 100,
            "renewable_percentage": 80,
        },
        {
            "provider": "b",
            "region": "dirty",
            "grid_zone": "D",
            "carbon_intensity": 500,
            "renewable_percentage": 10,
        },
    ]
    scored = score_candidates(candidates)
    best = scored[0]
    assert best.region == "clean"
    assert best.carbon_savings_vs_worst_pct == 80.0  # 100 is 80% less than 500


def test_score_empty():
    assert score_candidates([]) == []


def test_score_single_candidate():
    candidates = [
        {
            "provider": "aws",
            "region": "us-west-2",
            "grid_zone": "BPAT",
            "carbon_intensity": 50,
            "renewable_percentage": 90,
        },
    ]
    scored = score_candidates(candidates)
    assert len(scored) == 1
    assert scored[0].score == 0.0  # Only candidate gets perfect score
