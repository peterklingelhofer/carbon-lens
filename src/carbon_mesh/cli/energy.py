"""Measure a job's actual energy from Intel RAPL counters (Linux, no dependencies).

`carbonlens run --measure-energy` reads the CPU-package energy counter before and
after the command and records the real kWh consumed -- turning the impact ledger's
avoided-CO2 from an operator estimate into a measurement. RAPL covers the CPU package
(and DRAM where exposed), not the whole machine, so it's labelled as such; still far
better than a guess, and free on most Linux servers. Unavailable elsewhere -> we fall
back to the operator-supplied --energy-kwh.
"""

from __future__ import annotations

import glob

# Package-level RAPL domains (intel-rapl:0, intel-rapl:1, ...), not their subdomains
# (intel-rapl:0:0), so we don't double-count.
_RAPL_GLOB = "/sys/class/powercap/intel-rapl:[0-9]*/energy_uj"


def _read_int(path: str) -> int | None:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def read_rapl_uj() -> tuple[int, int] | None:
    """Total RAPL energy (microjoules) and total wrap range across package domains.

    Returns ``(total_uj, total_max_range_uj)`` or None when RAPL isn't available.
    """
    domains = glob.glob(_RAPL_GLOB)
    if not domains:
        return None
    total = 0
    total_max = 0
    found = False
    for energy_path in domains:
        uj = _read_int(energy_path)
        if uj is None:
            continue
        found = True
        total += uj
        max_uj = _read_int(energy_path.replace("energy_uj", "max_energy_range_uj"))
        total_max += max_uj or 0
    return (total, total_max) if found else None


def energy_kwh_between(before_uj: int, after_uj: int, max_range_uj: int) -> float:
    """kWh consumed between two RAPL readings, accounting for counter wrap-around."""
    delta = after_uj - before_uj
    if delta < 0 and max_range_uj > 0:
        delta += max_range_uj  # counter wrapped once
    joules = max(0, delta) / 1_000_000
    return joules / 3_600_000  # J -> kWh
