// Node catalogue for the design-procedure graph.
// Each step maps a CIB Publication 257 clause to its ASCE 7-22 counterpart
// (where the load side changed) and declares its inputs, live results and
// the equations it applies.

import { CORE_PRESETS, GCPI } from './engine.js';
import { fmt } from './units.js';

export const LANES = [
  { id: 'A', title: 'Inputs', sub: 'Panel, materials, static system', x: 0 },
  { id: 'B', title: 'Actions', sub: 'ASCE 7-22 loads', x: 1 },
  { id: 'C', title: 'Combinations', sub: 'ASCE 7-22 §2.3 / §2.4 / App. C', x: 2 },
  { id: 'D', title: 'Analysis', sub: 'CIB Chapter 3', x: 3 },
  { id: 'E', title: 'Verification', sub: 'CIB Chapter 4, φ = 1/γM', x: 4 },
  { id: 'F', title: 'Outcome', sub: 'Governing check', x: 5 },
];

// Field catalogue: key -> { label, dim, type, options, help }
export const FIELDS = {
  app: { label: 'Application', type: 'select', options: [['roof', 'Roof / ceiling'], ['wall', 'Wall']] },
  D: { label: 'Panel depth D', dim: 'mm' },
  t1: { label: 'Outer face t₁ (design)', dim: 'thk', help: 'CIB §3.2: t = t_nom − t_zinc − 0.5·t_tol' },
  t2: { label: 'Inner face t₂ (design)', dim: 'thk' },
  bw: { label: 'Panel cover width', dim: 'mm' },
  EF: { label: 'Face modulus E_F', dim: 'modulus' },
  fy: { label: 'Face yield f_y', dim: 'stress' },
  alpha: { label: 'Face expansion α', dim: 'alpha' },
  core: { label: 'Core material', type: 'select', options: Object.entries(CORE_PRESETS).map(([k, v]) => [k, v.label]), help: 'Choosing a material loads its typical properties. Replace them with tested values (CIB §5.2).' },
  Gc: { label: 'Core shear modulus G_C', dim: 'core' },
  Ec: { label: 'Core modulus E_C', dim: 'core' },
  fCv: { label: 'Core shear strength f_Cv', dim: 'core' },
  fCc: { label: 'Core compression f_Cc', dim: 'core' },
  rho: { label: 'Core density', dim: 'density' },
  kw: { label: 'Wrinkling coefficient k', dim: 'ratio', help: '0.5 general; up to 0.65 for good-quality continuous PUR (CIB §4.3.2.2)' },
  kd: { label: 'Support dispersion k', dim: 'ratio', help: '0.5 rigid foam, 0 mineral wool unless tested (CIB §4.3.5)' },
  phi2000: { label: 'Creep φ_t, snow duration', dim: 'ratio', help: 'CIB uses 2000 h for Central European snow. Adjust for local snow persistence.' },
  phi100k: { label: 'Creep φ_t, permanent', dim: 'ratio', help: '100 000 h' },
  spans: { label: 'Spans', type: 'select', options: [[1, 'Single span'], [2, 'Two equal spans']], numeric: true },
  L: { label: 'Span L', dim: 'span' },
  LsEnd: { label: 'End support width', dim: 'mm' },
  LsInt: { label: 'Intermediate support width', dim: 'mm' },
  method: { label: 'ULS analysis', type: 'select', options: [['elastic', 'Elastic'], ['plastic', 'Plastic (hinge at support)']], help: 'CIB §3.3. Plastic: ULS on simple spans; support wrinkling becomes a service check.' },
  nEnd: { label: 'Fasteners at end support', dim: 'perWidth', help: 'per unit width' },
  nInt: { label: 'Fasteners at intermediate support', dim: 'perWidth' },
  NRk: { label: 'Fastener tension N_Rk (tested)', dim: 'force' },
  Dadd: { label: 'Superimposed dead load', dim: 'pressure' },
  Lr: { label: 'Roof live load L_r', dim: 'pressure', help: 'ASCE 7-22 Table 4.3-1: 20 psf ordinary roofs' },
  pg: { label: 'Ground snow p_g', dim: 'pressure', help: 'ASCE 7-22 maps are risk-targeted; read p_g for your Risk Category from the ASCE Hazard Tool.' },
  Ce: { label: 'Exposure factor C_e', dim: 'ratio' },
  Ct: { label: 'Thermal factor C_t', dim: 'ratio', help: 'ASCE 7-22 Table 7.3-2 ties C_t to roof thermal resistance R. Well-insulated sandwich roofs often land above 1.0.' },
  Cs: { label: 'Slope factor C_s', dim: 'ratio' },
  lowSlope: { label: 'Low-slope minimum p_m', type: 'bool', help: 'ASCE 7-22 §7.3.4' },
  V: { label: 'Basic wind speed V', dim: 'speed', help: 'Risk-Category specific map (ASCE 7-22 Fig. 26.5-1)' },
  exposure: { label: 'Exposure', type: 'select', options: [['B', 'B'], ['C', 'C'], ['D', 'D']] },
  h: { label: 'Mean roof height h', dim: 'height' },
  Kzt: { label: 'Topographic K_zt', dim: 'ratio' },
  Ke: { label: 'Ground elevation K_e', dim: 'ratio' },
  Kd: { label: 'Directionality K_d', dim: 'ratio' },
  enclosure: { label: 'Enclosure', type: 'select', options: [['enclosed', 'Enclosed (±0.18)'], ['partial', 'Partially enclosed (±0.55)'], ['partiallyOpen', 'Partially open (±0.18)'], ['open', 'Open (0)']] },
  zone: { label: 'Wall zone', type: 'select', options: [['4', 'Zone 4 (field)'], ['5', 'Zone 5 (corner)']] },
  GCpRoofPos: { label: 'Roof (GC_p) positive', dim: 'ratio', help: 'Read from ASCE 7-22 Fig. 30.3-2A–I for the zone and effective area shown.' },
  GCpRoofNeg: { label: 'Roof (GC_p) negative', dim: 'ratio' },
  colour: { label: 'Outer face colour', type: 'select', options: [['i', 'Very light, R_G 75–90'], ['ii', 'Light, R_G 40–74'], ['iii', 'Dark, R_G 8–39']] },
  T1winter: { label: 'Winter outer face T₁', dim: 'temp', help: 'Use the ASHRAE 99.6% heating dry-bulb for the site.' },
  T2summer: { label: 'Summer inside T₂', dim: 'temp' },
  T2winter: { label: 'Winter inside T₂', dim: 'temp' },
  gTprin: { label: 'γ_T when temperature leads', dim: 'ratio', help: 'ASCE 7-22 C2.3.4 examples use 1.2' },
  gTcomp: { label: 'γ_T as companion', dim: 'ratio', help: 'ASCE 7-22 §2.3.4: not less than 1.0' },
  wSLS: { label: 'Service wind factor', dim: 'ratio', help: 'IBC Table 1604.3 note f: 0.42 × C&C wind for deflection' },
  phiY: { label: 'φ yielding (1/1.1)', dim: 'ratio' },
  phiWr: { label: 'φ wrinkling, span (1/1.25)', dim: 'ratio' },
  phiWrSup: { label: 'φ wrinkling, support ULS', dim: 'ratio' },
  phiWrSupSLS: { label: 'φ wrinkling, support SLS (1/1.1)', dim: 'ratio' },
  phiV: { label: 'φ core shear (1/1.25)', dim: 'ratio' },
  phiC: { label: 'φ core crushing (1/1.25)', dim: 'ratio' },
  phiF: { label: 'φ fastener (1/1.33)', dim: 'ratio' },
  limRoofShort: { label: 'Roof, short term L /', dim: 'int' },
  limRoofLong: { label: 'Roof, long term L /', dim: 'int' },
  limWall: { label: 'Wall L /', dim: 'int' },
};

export function statusFor(dcr) {
  if (dcr == null) return { kind: 'info', text: 'n/a' };
  if (dcr > 1) return { kind: 'fail', text: `DCR ${dcr.toFixed(2)}` };
  if (dcr > 0.9) return { kind: 'warn', text: `DCR ${dcr.toFixed(2)}` };
  return { kind: 'ok', text: `DCR ${dcr.toFixed(2)}` };
}

const env = (r, id) => r.envelope[id];
const checkStatus = (id) => (r) => (env(r, id) ? statusFor(env(r, id).dcr) : { kind: 'info', text: 'not applicable' });
const checkMetrics = (id, dim) => (r, u) => {
  const e = env(r, id);
  if (!e) return [['Status', 'Not applicable for this system']];
  return [
    ['Demand', fmt(e.demand, dim, u)],
    ['Capacity', fmt(e.cap, dim, u)],
    ['Governs', `${e.combo}${e.note ? ' · ' + e.note : ''}`],
  ];
};

export const STEPS = [
  // ---------------- A: inputs
  {
    id: 'A1', lane: 'A', row: 0, title: 'Panel & scope', cib: '§1.1, §3.2',
    fields: ['app', 'D', 't1', 't2', 'bw'],
    about: 'Metal faces 0.5–2.0 mm, panel depth 30–300 mm, faces fully bonded to the core. Flat or lightly profiled faces, so face bending stiffness is neglected (B_F = 0).',
    metrics: (r, u) => [['Use', r.inp.app === 'roof' ? 'Roof' : 'Wall'], ['Depth', fmt(r.inp.D, 'mm', u)], ['Faces', `${fmt(r.inp.t1, 'thk', u)} / ${fmt(r.inp.t2, 'thk', u)}`]],
    status: (r) => {
      const ok = r.inp.D >= 30 && r.inp.D <= 300 && Math.min(r.inp.t1, r.inp.t2) >= 0.4 && Math.max(r.inp.t1, r.inp.t2) <= 2.0;
      return ok ? { kind: 'ok', text: 'In scope' } : { kind: 'warn', text: 'Outside CIB range' };
    },
    eqs: ['e = D − (t₁ + t₂)/2', 't_d = t_nom − t_zinc − 0.5·t_tol'],
  },
  {
    id: 'A2', lane: 'A', row: 1, title: 'Materials', cib: '§4.1, §5.2',
    fields: ['core', 'EF', 'fy', 'alpha', 'Gc', 'Ec', 'fCv', 'fCc', 'rho', 'kw', 'kd'],
    about: 'Core properties come from tests on the actual product: shear (§5.2.4), compression (§5.2.3), tension (§5.2.2). Face yield is the guaranteed minimum for the steel grade, for example ASTM A653 SS Grade 40 in place of EN 10147.',
    change: 'Face steel: cite ASTM A653 / A792 grades instead of EN 10147. Core values are still product-specific test values.',
    metrics: (r, u) => [['Core', CORE_PRESETS[r.inp.core]?.label ?? r.inp.core], ['G_C', fmt(r.inp.Gc, 'core', u)], ['f_y', fmt(r.inp.fy, 'stress', u)]],
    status: () => ({ kind: 'info', text: 'Test values' }),
  },
  {
    id: 'A3', lane: 'A', row: 2, title: 'Static system', cib: '§3.2, §3.3',
    fields: ['spans', 'L', 'LsEnd', 'LsInt', 'method', 'nEnd', 'nInt', 'NRk'],
    about: 'Simple supports, free rotation and axial movement. Elastic analysis is always used for serviceability. Plastic analysis may replace a continuous panel with simple spans at the ultimate limit state.',
    metrics: (r, u) => [['System', r.inp.spans === 2 ? `2 × ${fmt(r.inp.L, 'span', u)}` : `1 × ${fmt(r.inp.L, 'span', u)}`], ['ULS method', r.inp.method === 'plastic' && r.inp.spans === 2 ? 'Plastic' : 'Elastic'], ['Fasteners', `${fmt(r.inp.nEnd, 'perWidth', u)} end, ${fmt(r.inp.nInt, 'perWidth', u)} int.`]],
    status: () => ({ kind: 'info', text: 'Set' }),
  },
  {
    id: 'A4', lane: 'A', row: 3, title: 'Testing & QC', cib: 'Ch. 5, Ch. 6',
    fields: [],
    about: 'Characteristic values from tests (5% fractile, 75% confidence), ageing, creep (§5.2.7), support reaction capacity (§5.2.10), walkability (§5.2.11), impact (§5.2.17) and fastener tests (§5.2.18). Design by full-scale testing (Ch. 6) is an alternative route that this tool does not compute.',
    change: 'Unchanged by ASCE 7-22, which covers loads only. In the US, product evaluation reports typically reference ICC-ES AC04 for sandwich panels.',
    metrics: () => [['Walkability', 'by test §4.5'], ['Impact', 'by test §4.6'], ['Fasteners', 'by test §5.2.18']],
    status: () => ({ kind: 'info', text: 'By test' }),
  },

  // ---------------- B: actions
  {
    id: 'B1', lane: 'B', row: 0, title: 'Dead load D', cib: '§2.2.1', asce: 'Ch. 3',
    fields: ['Dadd'],
    about: 'Self-weight of faces and core plus any permanent components carried by the panel. For walls, self-weight acts in-plane and adds no transverse load.',
    change: 'Eurocode G_k → ASCE 7-22 D.',
    metrics: (r, u) => [['Panel', fmt(r.ld.gPanel, 'pressure', u)], ['Transverse D', fmt(r.ld.D, 'pressure', u)]],
    status: () => ({ kind: 'info', text: 'D' }),
    eqs: ['g = 78.5 kN/m³ · (t₁ + t₂) + ρ_c·g·D'],
  },
  {
    id: 'B2', lane: 'B', row: 1, title: 'Roof live load Lr', cib: '§2.2.2 note 2', asce: '§4.8, Table 4.3-1',
    fields: ['Lr'],
    about: 'Access for construction and maintenance. CIB suggests q_k = 0.25 kN/m² and F_k = 1.2 kN for ceilings. ASCE 7-22 uses 20 psf for ordinary roofs and a 300 lb concentrated load for roofs accessed by maintenance workers.',
    change: 'q_k = 0.25 kN/m² → L_r = 20 psf (0.96 kPa). The 300 lb point load is covered by the walkability test (§4.5).',
    metrics: (r, u) => [['L_r', r.inp.app === 'roof' ? fmt(r.ld.Lr, 'pressure', u) : 'n/a (wall)'], ['Point load', u === 'us' ? '300 lbf' : '1.33 kN']],
    status: (r) => ({ kind: 'info', text: r.inp.app === 'roof' ? 'Lr' : 'n/a' }),
  },
  {
    id: 'B3', lane: 'B', row: 2, title: 'Snow S', cib: '§2.2.2', asce: 'Ch. 7',
    fields: ['pg', 'Ce', 'Ct', 'Cs', 'lowSlope'],
    about: 'Flat-roof snow from ground snow, then slope, with the low-slope minimum. Drifts and unbalanced loads are not computed here. Check them where panels sit next to parapets or higher roofs.',
    change: 'EN 1991-1-3 s_k·μ_i → ASCE 7-22 p_s = C_s·0.7·C_e·C_t·p_g. The 7-22 maps are risk-targeted, so there is no separate importance factor.',
    metrics: (r, u) => [['p_f', fmt(r.ld.pf, 'pressure', u)], ['p_m', fmt(r.ld.pm, 'pressure', u)], ['S used', r.inp.app === 'roof' ? fmt(r.ld.S, 'pressure', u) : 'n/a (wall)']],
    status: (r) => ({ kind: 'info', text: r.inp.app === 'roof' ? 'S' : 'n/a' }),
    eqs: ['p_f = 0.7·C_e·C_t·p_g', 'p_s = C_s·p_f', 'p_m = p_g ≤ 20 psf (low slope)'],
  },
  {
    id: 'B4', lane: 'B', row: 3, title: 'Wind W (C&C)', cib: '§2.2.2', asce: 'Ch. 26, Ch. 30',
    fields: ['V', 'exposure', 'h', 'Kzt', 'Ke', 'Kd', 'enclosure', 'zone', 'GCpRoofPos', 'GCpRoofNeg'],
    fieldsFilter: (inp) => (k) => (inp.app === 'wall' ? !k.startsWith('GCpRoof') : k !== 'zone'),
    about: 'Sandwich panels are components and cladding. The effective wind area is span × max(width, span/3). Wall (GC_p) is read from Fig. 30.3-1 (h ≤ 60 ft). For roofs, enter (GC_p) from Fig. 30.3-2 for the zone. Net pressures are not taken below 16 psf.',
    change: 'EN 1991-1-4 q_p·(c_pe − c_pi) → ASCE 7-22 p = q_h·K_d·[(GC_p) − (GC_pi)], strength-level wind.',
    metrics: (r, u) => [['q_h', fmt(r.ld.qh, 'pressure', u)], ['A_eff', fmt(r.ld.Aeff / 10.76391, 'area', u)], ['p⁺ / p⁻', `${fmt(r.ld.Wp, 'pressure', u)} / ${fmt(r.ld.Wn, 'pressure', u)}`]],
    status: () => ({ kind: 'info', text: 'W' }),
    eqs: ['K_z = 2.01·(z/z_g)^(2/α), z ≥ 15 ft', 'q_h = 0.00256·K_z·K_zt·K_e·V²  (psf, mph)', 'p = q_h·K_d·[(GC_p) − (GC_pi)]', 'A_eff = L · max(b, L/3)'],
  },
  {
    id: 'B5', lane: 'B', row: 4, title: 'Temperature T', cib: '§2.2.2', asce: '§2.3.4 (self-straining)',
    fields: ['colour', 'T1winter', 'T2summer', 'T2winter'],
    about: 'A face temperature difference curves the panel. On a single span this gives deflection only. On a continuous panel it also gives support moments and reactions. ASCE 7-22 gives no cladding temperatures, so the CIB colour-group values are kept.',
    change: 'ASCE 7-22 treats this as a self-straining load T with a load factor ≥ 1.0. Temperatures stay as in CIB §2.2.2. In hot US climates outer faces can exceed 80 °C.',
    metrics: (r, u) => [['Summer T₁', `${fmt(r.ld.temps.summerS.T1, 'temp', u)} SLS / ${fmt(80, 'temp', u)} ULS`], ['Winter T₁', fmt(r.inp.T1winter, 'temp', u)], ['Under snow T₁', fmt(0, 'temp', u)]],
    status: () => ({ kind: 'info', text: 'T' }),
    eqs: ['θ = α·(T₂ − T₁)/e', 'T₁ = 55 / 65 / 80 °C by colour group'],
  },
  {
    id: 'B6', lane: 'B', row: 5, title: 'Core creep', cib: '§2.2.3, §3.6',
    fields: ['phi2000', 'phi100k'],
    about: 'Shear creep of the core lowers its effective shear modulus under long-term load. This raises deflection and moves moment from the support into the span. Creep can be neglected when φ_t < 0.5.',
    change: 'Durations follow CIB (2000 h snow, 100 000 h permanent). Lengthen the snow duration for climates where snow stays on the roof longer.',
    metrics: (r, u) => [['G_C,t snow', fmt(r.sec.Gt2000, 'core', u)], ['G_C,t perm.', fmt(r.sec.Gt100k, 'core', u)]],
    status: () => ({ kind: 'info', text: 'Long term' }),
    eqs: ['G_C,t = G_C / (1 + φ_t)'],
  },

  // ---------------- C: combinations
  {
    id: 'C1', lane: 'C', row: 0, title: 'Strength (LRFD)', cib: '§2.4.1, Tables 2.1, 2.4', asce: '§2.3.1, §2.3.4',
    fields: ['gTprin', 'gTcomp'],
    combos: 'U',
    about: 'Replaces S_d = 1.35G + 1.5Q₁ + 1.5ψ₀Q_i. Snow combinations are also run with crept core properties (marked t = ∞) on continuous panels, as CIB requires creep in both limit states.',
    change: 'γ_G = 1.35 / γ_Q = 1.5 / ψ₀ = 0.6 → ASCE 7-22 1.2D + 1.6S, 1.0W at strength level, 0.9D for uplift. T is added at 1.0 as companion and 1.2 when it leads.',
    metrics: (r) => [['Combinations', `${r.combos.U.length}`], ['Governs', r.governingU ? r.governingU : '—']],
    status: () => ({ kind: 'info', text: 'LRFD' }),
  },
  {
    id: 'C2', lane: 'C', row: 1, title: 'Serviceability', cib: '§2.4.2, Table 2.3', asce: 'App. C; IBC Table 1604.3',
    fields: ['wSLS', 'limRoofShort', 'limRoofLong', 'limWall'],
    combos: 'S',
    about: 'Deflection combinations, short term and long term with creep. The frequent-combination ψ₁ = 0.75 is kept for snow when temperature acts with it.',
    change: 'CIB L/200 short, L/100 long → IBC Table 1604.3 defaults L/180 (roof S or W), L/120 (roof D + S long term, walls with flexible finishes). Wind is taken as 0.42 × C&C pressure.',
    metrics: (r) => [['Combinations', `${r.combos.S.length}`], ['Limits', r.inp.app === 'roof' ? `L/${r.inp.limRoofShort}, L/${r.inp.limRoofLong}` : `L/${r.inp.limWall}`]],
    status: () => ({ kind: 'info', text: 'Service' }),
  },
  {
    id: 'C3', lane: 'C', row: 2, title: 'Support stresses (ASD)', cib: '§2.4.2 Eq. 2.5, §4.4', asce: '§2.4.1',
    fields: [],
    combos: 'A',
    about: 'CIB checks wrinkling, core shear and crushing at intermediate supports under the characteristic (rare) combination. Nominal ASD combinations serve that role here. They run only for continuous panels.',
    change: 'Characteristic combination G + Q₁ + ψ₀Q_i → ASCE 7-22 ASD: D + S, D + 0.75S + 0.75(0.6W), 0.6D + 0.6W.',
    metrics: (r) => [['Combinations', r.inp.spans === 2 ? `${r.combos.A.length}` : 'n/a (single span)']],
    status: (r) => ({ kind: 'info', text: r.inp.spans === 2 ? 'ASD' : 'n/a' }),
  },

  // ---------------- D: analysis
  {
    id: 'D1', lane: 'D', row: 0, title: 'Section properties', cib: '§3.4.1',
    fields: [],
    about: 'For flat or lightly profiled faces, the faces carry the bending moment as axial forces and the core carries all the shear.',
    metrics: (r, u) => [['e', fmt(r.sec.e, 'mm', u)], ['B_S', fmt(r.sec.Bs / 1e9, 'rigidity', u)], ['k', r.sec.k.toFixed(3)], ['σ_w', fmt(r.sec.sigW, 'stress', u)]],
    status: () => ({ kind: 'info', text: 'Computed' }),
    eqs: ['B_S = E_F1A_F1·E_F2A_F2/(E_F1A_F1 + E_F2A_F2)·e²', 'A_S = e', 'k = 3B_S/(L²·G_C·A_S)', 'σ_w = k·(E_F·E_C·G_C)^(1/3)   (Eq. 4.11)'],
  },
  {
    id: 'D2', lane: 'D', row: 1, title: 'Elastic / plastic analysis', cib: '§3.3, §3.4.2',
    fields: [],
    about: 'Stress resultants per unit width, with shear deformation of the core included. On two spans, the support moment combines load and temperature terms. The load terms use a crept G_C for the long-term parts.',
    metrics: (r, u) => {
      const g = r.maxRow;
      return g ? [['M span', fmt(g.a.Mmax / 1e6, 'moment', u)], ['M support', fmt(g.a.MB / 1e6, 'moment', u)], ['V max', fmt(g.a.Vmax / 1000, 'reaction', u)]] : [];
    },
    status: (r) => ({ kind: 'info', text: r.plastic ? 'Plastic ULS' : 'Elastic' }),
    eqs: ['M_B = −qL²/[8(1+k)] − 3B_Sθ/[2(1+k)]', 'R_B = qL − 2M_B/L', 'w = 5qL⁴/384B_S + qL²/8G_CA_S + θL²/8 + M_BL²/16B_S', 'Single span: thermal curvature gives deflection only'],
  },

  // ---------------- E: checks
  { id: 'E1', lane: 'E', row: 0, title: 'Face yielding', cib: '§4.3.1', check: 'yield', fields: ['phiY'], dim: 'stress', about: 'Tension face stress σ = M/(e·t) against φ·f_y.', eqs: ['σ_F = M/(e·A_F) ≤ φ·f_y'] },
  { id: 'E2', lane: 'E', row: 1, title: 'Wrinkling in span', cib: '§4.3.2.2', check: 'wrSpan', fields: ['phiWr'], dim: 'stress', about: 'Compressed flat face against the wrinkling stress, capped at yield. Full-scale tests (§5.2.6) usually give higher values than Eq. 4.11.', eqs: ['σ_F,c ≤ φ·min(σ_w, f_y)'] },
  { id: 'E3', lane: 'E', row: 2, title: 'Wrinkling at support', cib: '§4.3.2.3, §4.4.1', check: 'wrSup', fields: ['phiWrSup', 'phiWrSupSLS'], dim: 'stress', about: 'At an intermediate support, a bearing reaction reduces the compressed-face strength by 10%. An uplift reaction through the screws reduces it by 20%, or more when there are more than 3 screws per metre. With plastic ULS analysis this becomes a service (ASD) check.', eqs: ['f_sup = 0.9·σ_w   (R > 0)', 'f_sup = 0.8·σ_w, n ≤ 3;  0.125(11 − n)·0.8·σ_w, n > 3   (R < 0)'] },
  { id: 'E4', lane: 'E', row: 3, title: 'Core shear', cib: '§4.3.3', check: 'shear', fields: ['phiV'], dim: 'core', about: 'Average core shear at the section of maximum shear. Long-term loading lowers f_Cv (§5.2.4.3).', eqs: ['τ_C = V/(e·B) ≤ φ·f_Cv'] },
  { id: 'E5', lane: 'E', row: 4, title: 'Core crushing', cib: '§4.3.5, Eq. 4.24', check: 'crush', fields: ['phiC'], dim: 'core', about: 'Reaction spread over L_s + k·e at mid-depth, with e ≤ 100 mm. At an intermediate support under elastic analysis, the ×0.71 factor accounts for interaction with face compression.', eqs: ['σ_C = F/[B(L_s + k·e)]   (intermediate)', 'σ_C = F/[B(L_s + 0.5k·e)]   (end)', 'σ_C ≤ 0.71·φ·f_Cc at intermediate supports'] },
  { id: 'E6', lane: 'E', row: 5, title: 'Fastener tension', cib: '§4.3.6, Ch. 7', check: 'fast', fields: ['phiF'], dim: 'force', about: 'Uplift reactions from suction and temperature are shared by the screws at each support. N_Rk comes from pull-over and pull-out tests on the actual panel (§5.2.18).', change: 'With AISI S100 screw equations instead of panel tests, use φ = 0.5 for pull-over and pull-out.', eqs: ['N = |R|/n ≤ φ·N_Rk'] },
  { id: 'E7', lane: 'E', row: 6, title: 'Deflection', cib: '§2.3.2, §4.4.4', asce: 'App. C', check: 'defl', fields: [], dim: 'defl', about: 'Elastic deflection including core shear deformation, temperature curvature and creep.', eqs: ['|w| ≤ L/n'] },

  // ---------------- F
  { id: 'F1', lane: 'F', row: 0, title: 'Design verdict', cib: 'Eq. 2.1', asce: '§2.3, §2.4', summary: true, fields: [], about: 'The design passes when every demand-to-capacity ratio is at or below 1.0.' },
];

// fill check metrics/status
for (const s of STEPS) {
  if (s.check) {
    s.metrics = checkMetrics(s.check, s.dim);
    s.status = checkStatus(s.check);
  }
}

export const EDGES = [
  ['A1', 'D1'], ['A2', 'D1'], ['A1', 'B1'], ['A2', 'B6'], ['A3', 'D2'], ['A4', 'A2'],
  ['B1', 'C1'], ['B1', 'C2'], ['B1', 'C3'], ['B2', 'C1'], ['B2', 'C2'],
  ['B3', 'C1'], ['B3', 'C2'], ['B3', 'C3'], ['B4', 'C1'], ['B4', 'C2'], ['B4', 'C3'],
  ['B5', 'C1'], ['B5', 'C2'], ['B5', 'C3'], ['B6', 'D2'],
  ['C1', 'D2'], ['C2', 'D2'], ['C3', 'D2'], ['D1', 'D2'],
  ['D2', 'E1'], ['D2', 'E2'], ['D2', 'E3'], ['D2', 'E4'], ['D2', 'E5'], ['D2', 'E6'], ['D2', 'E7'],
  ['E1', 'F1'], ['E2', 'F1'], ['E3', 'F1'], ['E4', 'F1'], ['E5', 'F1'], ['E6', 'F1'], ['E7', 'F1'],
];

export { GCPI };
