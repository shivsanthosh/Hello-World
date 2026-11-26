// Unit conversion between the engine's SI values and display units.
// US customary uses the units ASCE 7-22 is written in (psf, mph, ft).

export const DIMS = {
  none: { si: '', us: '', k: 1, dp: 2 },
  ratio: { si: '', us: '', k: 1, dp: 2 },
  int: { si: '', us: '', k: 1, dp: 0 },
  span: { si: 'm', us: 'ft', k: 3.28084, dp: 2 },
  height: { si: 'm', us: 'ft', k: 3.28084, dp: 1 },
  mm: { si: 'mm', us: 'in', k: 1 / 25.4, dp: [0, 2] },
  thk: { si: 'mm', us: 'in', k: 1 / 25.4, dp: [2, 4] },
  defl: { si: 'mm', us: 'in', k: 1 / 25.4, dp: [1, 2] },
  modulus: { si: 'MPa', us: 'ksi', k: 0.1450377, dp: [0, 0] },
  stress: { si: 'MPa', us: 'ksi', k: 0.1450377, dp: [1, 2] },
  core: { si: 'MPa', us: 'psi', k: 145.0377, dp: [3, 1] },
  pressure: { si: 'kPa', us: 'psf', k: 20.88543, dp: [2, 1] },
  speed: { si: 'm/s', us: 'mph', k: 2.236936, dp: [1, 0] },
  density: { si: 'kg/m³', us: 'pcf', k: 0.0624280, dp: [0, 2] },
  force: { si: 'kN', us: 'lbf', k: 224.8089, dp: [2, 0] },
  perWidth: { si: '/m', us: '/ft', k: 1 / 3.28084, dp: [0, 2] },
  moment: { si: 'kN·m/m', us: 'lbf·ft/ft', k: 224.8089, dp: [2, 0] },
  reaction: { si: 'kN/m', us: 'lbf/ft', k: 68.5218, dp: [2, 0] },
  area: { si: 'm²', us: 'ft²', k: 10.76391, dp: [2, 1] },
  temp: { si: '°C', us: '°F', dp: [0, 0], to: (c) => (c * 9) / 5 + 32, from: (f) => ((f - 32) * 5) / 9 },
  alpha: { si: '×10⁻⁶/°C', us: '×10⁻⁶/°F', k: 1e6, kus: 1e6 / 1.8, dp: [1, 2] },
  rigidity: { si: 'kN·m²/m', us: 'kip·ft²/ft', k: 1, dp: [1, 1] },
};

const pickDp = (d, sys) => (Array.isArray(d.dp) ? d.dp[sys === 'us' ? 1 : 0] : d.dp);

export function toDisplay(v, dim, sys) {
  const d = DIMS[dim] || DIMS.none;
  if (v == null || Number.isNaN(v)) return v;
  if (d.to) return sys === 'us' ? d.to(v) : v;
  if (dim === 'alpha') return v * (sys === 'us' ? d.kus : d.k);
  if (dim === 'rigidity') return sys === 'us' ? v * 0.2248089 * 3.28084 * 3.28084 / 3.28084 : v;
  return sys === 'us' ? v * d.k : v;
}

export function fromDisplay(v, dim, sys) {
  const d = DIMS[dim] || DIMS.none;
  if (d.from) return sys === 'us' ? d.from(v) : v;
  if (dim === 'alpha') return v / (sys === 'us' ? d.kus : d.k);
  return sys === 'us' ? v / d.k : v;
}

export function unit(dim, sys) {
  const d = DIMS[dim] || DIMS.none;
  return sys === 'us' ? d.us : d.si;
}

export function fmt(v, dim, sys, dpOverride) {
  if (v == null || !isFinite(v)) return '—';
  const d = DIMS[dim] || DIMS.none;
  const x = toDisplay(v, dim, sys);
  const dp = dpOverride ?? pickDp(d, sys);
  const u = unit(dim, sys);
  const s = x.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  return u ? `${s} ${u}` : s;
}

export function round(v, dim, sys) {
  const d = DIMS[dim] || DIMS.none;
  const x = toDisplay(v, dim, sys);
  const dp = Math.max(pickDp(d, sys) + 1, 2);
  return Number(x.toFixed(dp));
}
