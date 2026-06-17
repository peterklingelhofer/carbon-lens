// Mirror of engine/surplus.py: clean-surplus (likely oversupply) heuristic.
// Renewables dominant, very low carbon, and a clean margin together imply extra
// load soaks up power that might otherwise be curtailed - the highest-value time
// to run flexible jobs. A heuristic from share + intensity + marginal, not measured
// curtailment. Kept in sync with the backend so the globe reads the same as the API.
export function isCleanSurplus(
  renewablePct: number,
  intensityGco2Kwh: number,
  marginalGco2Kwh: number | null | undefined,
): boolean {
  if (renewablePct < 85) return false;
  if (intensityGco2Kwh > 80) return false;
  if (marginalGco2Kwh != null && marginalGco2Kwh > 100) return false;
  return true;
}
