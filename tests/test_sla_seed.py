"""Tests for the idempotent, self-healing demo-SLA seeder."""

from carbon_mesh.sla.repository import InMemorySLARepository
from carbon_mesh.sla.seed import DEMO_SLA_ID, ensure_demo_sla, seed_demo_sla


async def test_ensure_demo_sla_is_idempotent_and_self_heals():
    repo = InMemorySLARepository()
    assert await ensure_demo_sla(repo) is True  # created
    assert await ensure_demo_sla(repo) is False  # already exists -> no-op

    sla = await repo.get_sla(DEMO_SLA_ID)
    assert sla is not None and sla.org_id == "demo"

    # Self-heal: after a wipe (DB reset, redeploy, or a visitor deleting it) the
    # next call recreates it.
    await repo.delete_sla(DEMO_SLA_ID)
    assert await ensure_demo_sla(repo) is True


async def test_seed_demo_sla_creates_sla_and_one_initial_check():
    """In-memory mode: seeding creates the SLA and a single initial check, and a
    repeat run adds nothing (idempotent)."""
    from carbon_mesh.api.deps import _in_memory_sla_repo

    await _in_memory_sla_repo.delete_sla(DEMO_SLA_ID)
    try:
        await seed_demo_sla()
        assert await _in_memory_sla_repo.get_sla(DEMO_SLA_ID) is not None
        assert len(await _in_memory_sla_repo.list_checks(DEMO_SLA_ID)) == 1

        await seed_demo_sla()  # idempotent: no new SLA, no new check
        assert len(await _in_memory_sla_repo.list_checks(DEMO_SLA_ID)) == 1
    finally:
        await _in_memory_sla_repo.delete_sla(DEMO_SLA_ID)
