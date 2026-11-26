// Sandwich panel design engine.
//
// Resistance model and analysis: ECCS/CIB "European Recommendations for Sandwich
// Panels, Part I: Design" (CIB Publication 257, 2000), Chapters 3 and 4.
// Loads and load combinations: ASCE/SEI 7-22 instead of Eurocode 1 / CIB Ch. 2.
//
// Internal units: N, mm, MPa (N/mm²), kPa (kN/m²), m for spans, °C.
// Results are per 1000 mm (1 m) panel width, so a line load q in N/mm is
// numerically equal to an area load in kPa.

export const B = 1000; // reference width, mm
const PSF_TO_KPA = 0.0478803;
const MPS_TO_MPH = 2.236936;
const M_TO_FT = 3.28084;

// ---------------------------------------------------------------------------
// Default (example) input set, SI.
// ---------------------------------------------------------------------------
export const CORE_PRESETS = {
  PIR: { label: 'PIR / PUR foam', Gc: 3.5, Ec: 4.0, fCv: 0.10, fCc: 0.10, rho: 40, kw: 0.5, kd: 0.5, phi2000: 2.4, phi100k: 7.0 },
  EPS: { label: 'EPS foam', Gc: 2.5, Ec: 3.5, fCv: 0.08, fCc: 0.08, rho: 20, kw: 0.5, kd: 0.5, phi2000: 2.4, phi100k: 7.0 },
  MW: { label: 'Mineral wool lamella', Gc: 4.5, Ec: 7.0, fCv: 0.06, fCc: 0.07, rho: 110, kw: 0.5, kd: 0.0, phi2000: 1.0, phi100k: 2.0 },
};

export const DEFAULT_INPUTS = {
  // A1 panel and scope
  app: 'roof', // 'roof' | 'wall'
  D: 150, // overall depth, mm
  t1: 0.60, // outer face design thickness, mm
  t2: 0.50, // inner face design thickness, mm
  bw: 1000, // panel cover width, mm
  // A2 materials
  EF: 203000, // face modulus, MPa (29,500 ksi)
  fy: 280, // face yield, MPa
  alpha: 12e-6, // face thermal expansion, 1/°C
  core: 'PIR',
  ...pick(CORE_PRESETS.PIR, ['Gc', 'Ec', 'fCv', 'fCc', 'rho', 'kw', 'kd', 'phi2000', 'phi100k']),
  // A3 static system
  spans: 2,
  L: 3.0, // m
  LsEnd: 60, // support width at end support, mm
  LsInt: 100, // support width at intermediate support, mm
  method: 'plastic', // 'elastic' | 'plastic' (ULS)
  nEnd: 4, // fasteners per m width, end support
  nInt: 4, // fasteners per m width, intermediate support
  NRk: 3.0, // characteristic tensile (pull-over) resistance per fastener, kN
  // B1 dead
  Dadd: 0.0, // superimposed dead load on panel, kPa
  // B2 roof live
  Lr: 0.96, // kPa (20 psf, ASCE 7-22 Table 4.3-1)
  // B3 snow
  pg: 1.44, // kPa (30 psf)
  Ce: 1.0,
  Ct: 1.1,
  Cs: 1.0,
  lowSlope: true,
  // B4 wind (components & cladding)
  V: 46.9, // m/s (105 mph)
  exposure: 'C',
  h: 7.6, // mean roof height, m (25 ft)
  Kzt: 1.0,
  Ke: 1.0,
  Kd: 0.85,
  enclosure: 'enclosed',
  zone: '4', // walls: '4' | '5'; roofs: user GCp
  GCpRoofPos: 0.3,
  GCpRoofNeg: -1.5,
  // B5 temperature
  colour: 'ii', // 'i' very light, 'ii' light, 'iii' dark
  T1winter: -20,
  T2summer: 25,
  T2winter: 20,
  // C factors
  gTprin: 1.2,
  gTcomp: 1.0,
  wSLS: 0.42,
  // E resistance factors (phi = 1/gamma_M, CIB Table 2.5)
  phiY: 0.91,
  phiWr: 0.80,
  phiWrSup: 0.80,
  phiV: 0.80,
  phiC: 0.80,
  phiF: 0.75,
  phiWrSupSLS: 0.91,
  // deflection limits (L / n)
  limRoofShort: 180,
  limRoofLong: 120,
  limWall: 120,
};

function pick(o, keys) {
  const r = {};
  keys.forEach((k) => (r[k] = o[k]));
  return r;
}

// ---------------------------------------------------------------------------
// B: ASCE 7-22 loads
// ---------------------------------------------------------------------------
const EXPOSURE = { B: { alpha: 7.0, zg: 1200 }, C: { alpha: 9.5, zg: 900 }, D: { alpha: 11.5, zg: 700 } };
export const GCPI = { enclosed: 0.18, partial: 0.55, partiallyOpen: 0.18, open: 0 };

export function kz(exposure, hM) {
  const { alpha, zg } = EXPOSURE[exposure];
  const z = Math.max(hM * M_TO_FT, 15);
  let k = 2.01 * Math.pow(z / zg, 2 / alpha);
  // Exposure B, C&C: Kz not taken below 0.70 (Table 26.10-1, Case 1 note)
  if (exposure === 'B' && z <= 30) k = Math.max(k, 0.7);
  return k;
}

// ASCE 7-22 Fig. 30.3-1 (walls, h <= 60 ft), log-linear in effective area.
export function wallGCp(zone, Aft2) {
  const A = Math.min(Math.max(Aft2, 10), 500);
  const s = Math.log10(A / 10) / Math.log10(50);
  const lerp = (a, b) => a + (b - a) * s;
  const pos = lerp(1.0, 0.7);
  const neg = zone === '5' ? lerp(-1.4, -0.8) : lerp(-1.1, -0.8);
  return { pos, neg };
}

export function loads(inp) {
  // Dead
  const gFaces = 78.5 * ((inp.t1 + inp.t2) / 1000); // kPa
  const gCore = (inp.rho * 9.81) / 1000 * (inp.D / 1000); // kPa
  const gPanel = gFaces + gCore;
  const Dtot = gPanel + inp.Dadd;
  const Dtrans = inp.app === 'roof' ? Dtot : 0; // transverse component

  // Snow (ASCE 7-22 Ch. 7)
  const pf = 0.7 * inp.Ce * inp.Ct * inp.pg;
  const ps = inp.Cs * pf;
  const pmCap = 20 * PSF_TO_KPA;
  const pm = inp.lowSlope ? Math.min(inp.pg, pmCap) : 0;
  const S = inp.app === 'roof' ? Math.max(ps, pm) : 0;
  const Lr = inp.app === 'roof' ? inp.Lr : 0;

  // Wind, components and cladding (ASCE 7-22 Ch. 26 & 30)
  const Vmph = inp.V * MPS_TO_MPH;
  const Kz = kz(inp.exposure, inp.h);
  const qhPsf = 0.00256 * Kz * inp.Kzt * inp.Ke * Vmph * Vmph;
  const qh = qhPsf * PSF_TO_KPA;
  const Lft = inp.L * M_TO_FT;
  const wft = (inp.bw / 1000) * M_TO_FT;
  const Aeff = Lft * Math.max(wft, Lft / 3); // ft²
  const GCp = inp.app === 'wall' ? wallGCp(inp.zone, Aeff) : { pos: inp.GCpRoofPos, neg: inp.GCpRoofNeg };
  const GCpi = GCPI[inp.enclosure];
  const pMin = 16 * PSF_TO_KPA;
  const pPosRaw = qh * inp.Kd * (GCp.pos + GCpi);
  const pNegRaw = qh * inp.Kd * (GCp.neg - GCpi);
  const Wp = Math.max(pPosRaw, pMin);
  const Wn = -Math.max(Math.abs(pNegRaw), pMin);

  // Temperature (CIB §2.2.2; ASCE 7-22 treats it as self-straining load T)
  const T1summerSLS = { i: 55, ii: 65, iii: 80 }[inp.colour];
  const temps = {
    summerU: { T1: 80, T2: inp.T2summer, label: 'Summer, T1 = 80 °C' },
    summerS: { T1: T1summerSLS, T2: inp.T2summer, label: `Summer, T1 = ${T1summerSLS} °C` },
    winter: { T1: inp.T1winter, T2: inp.T2winter, label: `Winter, T1 = ${inp.T1winter} °C` },
    snow: { T1: 0, T2: inp.T2winter, label: 'Winter under snow, T1 = 0 °C' },
  };

  return {
    gFaces, gCore, gPanel, Dtot, D: Dtrans, S, ps, pf, pm, Lr,
    Vmph, Kz, qhPsf, qh, Aeff, GCp, GCpi, pPosRaw, pNegRaw, Wp, Wn, pMin, temps,
  };
}

// ---------------------------------------------------------------------------
// C: ASCE 7-22 combinations
// ---------------------------------------------------------------------------
// Each term: D, Lr, S, W ('+' or '-' with factor), T (state + factor), longTerm.
export function combinations(inp) {
  const P = inp.gTprin;
  const C = inp.gTcomp;
  const w = inp.wSLS;
  const roof = inp.app === 'roof';
  const U = [];
  const S = [];
  const A = [];

  if (roof) {
    U.push(c('U1', '1.4D', { D: 1.4 }));
    U.push(c('U2', '1.2D + 1.6S + 0.5W + 1.0T', { D: 1.2, S: 1.6, W: 0.5, Wd: '+', T: 'snow', fT: C }, true));
    U.push(c('U3', '1.2D + 1.6Lr + 0.5W + 1.0T', { D: 1.2, Lr: 1.6, W: 0.5, Wd: '+', T: 'summerU', fT: C }));
    U.push(c('U4', '1.2D + 1.0W + 0.5S + 1.0T', { D: 1.2, S: 0.5, W: 1.0, Wd: '+', T: 'snow', fT: C }, true));
    U.push(c('U5', '0.9D + 1.0W(uplift) + 1.0T summer', { D: 0.9, W: 1.0, Wd: '-', T: 'summerU', fT: C }));
    U.push(c('U6', '0.9D + 1.0W(uplift) + 1.0T winter', { D: 0.9, W: 1.0, Wd: '-', T: 'winter', fT: C }));
    U.push(c('U7', '1.2D + 1.2T summer + 0.5Lr', { D: 1.2, Lr: 0.5, T: 'summerU', fT: P }));
    U.push(c('U8', '1.2D + 1.2T winter + 0.5S', { D: 1.2, S: 0.5, T: 'snow', fT: P }, true));
    U.push(c('U9', '0.9D + 1.2T winter', { D: 0.9, T: 'winter', fT: P }));
    U.push(c('U10', '0.9D + 1.2T summer', { D: 0.9, T: 'summerU', fT: P }));

    S.push(c('S1', 'D + S', { D: 1, S: 1 }));
    S.push(c('S2', 'D + Lr', { D: 1, Lr: 1 }));
    S.push(c('S3', `D + 0.75S + 1.0T snow`, { D: 1, S: 0.75, T: 'snow', fT: 1 }));
    S.push(c('S4', `D + ${w}W (pressure)`, { D: 1, W: w, Wd: '+' }));
    S.push(c('S5', `D + ${w}W (uplift)`, { D: 1, W: w, Wd: '-' }));
    S.push(c('S6', 'D + 1.0T winter', { D: 1, T: 'winter', fT: 1 }));
    S.push(c('S7', `D + 1.0T summer + 0.75·${w}W (uplift)`, { D: 1, T: 'summerS', fT: 1, W: 0.75 * w, Wd: '-' }));
    S.push(c('S8', 'D + S, long term (creep)', { D: 1, S: 1, long: true, lim: 'long' }));
    S.push(c('S9', 'D + 0.75S + 1.0T snow, long term', { D: 1, S: 0.75, T: 'snow', fT: 1, long: true, lim: 'long' }));

    A.push(c('A1', 'D + S + 1.0T snow', { D: 1, S: 1, T: 'snow', fT: 1 }));
    A.push(c('A2', 'D + 0.75S + 0.75(0.6W) + 0.75T', { D: 1, S: 0.75, W: 0.45, Wd: '+', T: 'snow', fT: 0.75 }));
    A.push(c('A3', 'D + 0.6W + 0.75T summer', { D: 1, W: 0.6, Wd: '+', T: 'summerS', fT: 0.75 }));
    A.push(c('A4', '0.6D + 0.6W(uplift) + 0.75T summer', { D: 0.6, W: 0.6, Wd: '-', T: 'summerS', fT: 0.75 }));
    A.push(c('A5', 'D + 1.0T summer', { D: 1, T: 'summerS', fT: 1 }));
    A.push(c('A6', 'D + 1.0T winter', { D: 1, T: 'winter', fT: 1 }));
    A.push(c('A7', 'D + S + 1.0T snow, long term', { D: 1, S: 1, T: 'snow', fT: 1, long: true }));
  } else {
    U.push(c('U1', '1.0W(pressure) + 1.0T winter', { W: 1, Wd: '+', T: 'winter', fT: C }));
    U.push(c('U2', '1.0W(pressure) + 1.0T summer', { W: 1, Wd: '+', T: 'summerU', fT: C }));
    U.push(c('U3', '1.0W(suction) + 1.0T summer', { W: 1, Wd: '-', T: 'summerU', fT: C }));
    U.push(c('U4', '1.0W(suction) + 1.0T winter', { W: 1, Wd: '-', T: 'winter', fT: C }));
    U.push(c('U5', '1.2T summer', { T: 'summerU', fT: P }));
    U.push(c('U6', '1.2T winter', { T: 'winter', fT: P }));

    S.push(c('S1', `${w}W (pressure)`, { W: w, Wd: '+' }));
    S.push(c('S2', `${w}W (suction)`, { W: w, Wd: '-' }));
    S.push(c('S3', `0.75·${w}W(pressure) + 1.0T winter`, { W: 0.75 * w, Wd: '+', T: 'winter', fT: 1 }));
    S.push(c('S4', `0.75·${w}W(suction) + 1.0T summer`, { W: 0.75 * w, Wd: '-', T: 'summerS', fT: 1 }));
    S.push(c('S5', '1.0T summer', { T: 'summerS', fT: 1 }));
    S.push(c('S6', '1.0T winter', { T: 'winter', fT: 1 }));

    A.push(c('A1', '0.6W(pressure) + 0.75T winter', { W: 0.6, Wd: '+', T: 'winter', fT: 0.75 }));
    A.push(c('A2', '0.6W(suction) + 0.75T summer', { W: 0.6, Wd: '-', T: 'summerS', fT: 0.75 }));
    A.push(c('A3', '1.0T summer', { T: 'summerS', fT: 1 }));
    A.push(c('A4', '1.0T winter', { T: 'winter', fT: 1 }));
  }
  return { U, S, A };
}

function c(id, name, terms, alsoLong = false) {
  return { id, name, ...terms, alsoLong };
}

// ---------------------------------------------------------------------------
// D: section properties and analysis (CIB §3.4)
// ---------------------------------------------------------------------------
export function section(inp) {
  const e = inp.D - (inp.t1 + inp.t2) / 2; // centroid distance, mm
  const A1 = inp.t1 * B;
  const A2 = inp.t2 * B;
  const Bs = ((inp.EF * A1 * inp.EF * A2) / (inp.EF * A1 + inp.EF * A2)) * e * e; // N·mm²
  const GA = inp.Gc * e * B; // N
  const Lmm = inp.L * 1000;
  const k = (3 * Bs) / (Lmm * Lmm * GA);
  const Gt2000 = inp.Gc / (1 + inp.phi2000);
  const Gt100k = inp.Gc / (1 + inp.phi100k);
  const sigW = inp.kw * Math.cbrt(inp.EF * inp.Ec * inp.Gc); // CIB Eq. 4.11
  const ePrime = Math.min(e, 100);
  return { e, A1, A2, Bs, GA, k, Lmm, Gt2000, Gt100k, sigW, ePrime };
}

// Moment at the intermediate support of an equal two-span panel, per load part.
function supportMoment(q, theta, G, sec, inp, continuous) {
  if (!continuous) return 0;
  const L = sec.Lmm;
  const GA = G * sec.e * B;
  const kk = (3 * sec.Bs) / (L * L * GA);
  return -(q * L * L) / (8 * (1 + kk)) - (3 * sec.Bs * theta) / (2 * (1 + kk));
}

function midDeflection(q, theta, G, MB, sec) {
  const L = sec.Lmm;
  const GA = G * sec.e * B;
  return (5 * q * L ** 4) / (384 * sec.Bs) + (q * L * L) / (8 * GA) + (theta * L * L) / 8 + (MB * L * L) / (16 * sec.Bs);
}

// Evaluate one combination. Returns action effects (N, mm units, per 1 m width).
export function analyse(combo, inp, ld, sec, opts = {}) {
  const { long = false, plastic = false } = opts;
  const continuous = inp.spans === 2 && !plastic;
  const t = combo.T ? ld.temps[combo.T] : null;
  const theta = t ? ((inp.alpha * (t.T2 - t.T1)) / sec.e) * (combo.fT ?? 1) : 0;
  const qW = combo.W ? combo.W * (combo.Wd === '-' ? ld.Wn : ld.Wp) : 0;
  const parts = [
    { q: (combo.D || 0) * ld.D, th: 0, G: long ? sec.Gt100k : inp.Gc },
    { q: (combo.S || 0) * ld.S, th: 0, G: long ? sec.Gt2000 : inp.Gc },
    { q: (combo.Lr || 0) * ld.Lr + qW, th: plastic && inp.spans === 2 ? 0 : theta, G: inp.Gc },
  ];
  const q = parts.reduce((s, p) => s + p.q, 0);
  const L = sec.Lmm;
  let MB = 0;
  let w = 0;
  for (const p of parts) {
    const m = supportMoment(p.q, p.th, p.G, sec, inp, continuous);
    MB += m;
    w += midDeflection(p.q, p.th, p.G, continuous ? m : 0, sec);
  }
  // single span: temperature gives deflection only
  const RA = (q * L) / 2 + (continuous ? MB / L : 0);
  const RB = continuous ? q * L - (2 * MB) / L : null;
  let Mmax = 0;
  let Mmin = 0;
  const N = 200;
  for (let i = 0; i <= N; i++) {
    const x = (L * i) / N;
    const M = RA * x - (q * x * x) / 2;
    if (M > Mmax) Mmax = M;
    if (M < Mmin) Mmin = M;
  }
  const Vmax = Math.max(Math.abs(RA), Math.abs(RA - q * L));
  return { q, theta, MB: continuous ? MB : 0, RA, RB, Mmax, Mmin, Vmax, w, continuous };
}

// ---------------------------------------------------------------------------
// E: resistances and checks (CIB §4.3, §4.4)
// ---------------------------------------------------------------------------
function supportReduction(R, n) {
  if (R >= 0) return 0.9; // CIB Eq. 4.23 (positive support reaction)
  return n <= 3 ? 0.8 : Math.max(0.125 * (11 - n) * 0.8, 0); // CIB Eq. 4.25
}

export const CHECKS = [
  { id: 'yield', node: 'E1', label: 'Face yielding' },
  { id: 'wrSpan', node: 'E2', label: 'Face wrinkling in span' },
  { id: 'wrSup', node: 'E3', label: 'Wrinkling at intermediate support' },
  { id: 'shear', node: 'E4', label: 'Core shear' },
  { id: 'crush', node: 'E5', label: 'Core crushing at supports' },
  { id: 'fast', node: 'E6', label: 'Fastener tension' },
  { id: 'defl', node: 'E7', label: 'Deflection' },
];

function checkStress(a, inp, sec, phi, isSLS) {
  const out = {};
  const sigW = sec.sigW;
  const fy = inp.fy;
  const compRes = (phiW) => (sigW < fy ? phiW * sigW : phi.y * fy);
  const s1pos = Math.max(a.Mmax, 0) / (sec.e * sec.A1); // face 1 compression (sagging)
  const s2pos = Math.max(a.Mmax, 0) / (sec.e * sec.A2); // face 2 tension
  const s1neg = Math.max(-a.Mmin, 0) / (sec.e * sec.A1); // face 1 tension (hogging)
  const s2neg = Math.max(-a.Mmin, 0) / (sec.e * sec.A2); // face 2 compression
  const tens = Math.max(s2pos, s1neg);
  out.yield = { dcr: tens / (phi.y * fy), demand: tens, cap: phi.y * fy, unit: 'MPa', note: 'tension face' };
  const comp = Math.max(s1pos, s2neg);
  // envelope over the whole span (unreduced strength); the support check adds the CIB 4.4.1 reduction
  out.wrSpan = { dcr: comp / compRes(phi.wr), demand: comp, cap: compRes(phi.wr), unit: 'MPa', note: s1pos >= s2neg ? 'outer face' : 'inner face' };

  if (a.continuous) {
    const RB = a.RB;
    const red = supportReduction(RB, inp.nInt);
    const faceArea = a.MB < 0 ? sec.A2 : sec.A1;
    const sig = Math.abs(a.MB) / (sec.e * faceArea);
    const cap = red * compRes(isSLS ? phi.wrSupSLS : phi.wrSup);
    out.wrSup = { dcr: sig / cap, demand: sig, cap, unit: 'MPa', note: `${a.MB < 0 ? 'inner' : 'outer'} face, ×${red.toFixed(2)} for ${RB >= 0 ? 'bearing' : 'uplift'} reaction` };
  }

  const tau = a.Vmax / (sec.e * B);
  out.shear = { dcr: tau / (phi.v * inp.fCv), demand: tau, cap: phi.v * inp.fCv, unit: 'MPa' };

  const kd = inp.kd;
  const crushList = [];
  if (a.RA > 0) {
    const s = a.RA / (B * (inp.LsEnd + 0.5 * kd * sec.ePrime));
    crushList.push({ s, cap: phi.c * inp.fCc, where: 'end support' });
  }
  if (a.continuous && a.RB > 0) {
    const s = a.RB / (B * (inp.LsInt + kd * sec.ePrime));
    crushList.push({ s, cap: 0.71 * phi.c * inp.fCc, where: 'intermediate support (×0.71 interaction)' });
  }
  if (crushList.length) {
    const g = crushList.reduce((m, x) => (x.s / x.cap > m.s / m.cap ? x : m));
    out.crush = { dcr: g.s / g.cap, demand: g.s, cap: g.cap, unit: 'MPa', note: g.where };
  } else out.crush = { dcr: 0, demand: 0, cap: phi.c * inp.fCc, unit: 'MPa', note: 'no bearing reaction' };

  const fl = [];
  if (a.RA < 0) fl.push({ N: -a.RA / inp.nEnd, where: 'end support' });
  if (a.continuous && a.RB < 0) fl.push({ N: -a.RB / inp.nInt, where: 'intermediate support' });
  const NRd = phi.f * inp.NRk * 1000;
  if (fl.length) {
    const g = fl.reduce((m, x) => (x.N > m.N ? x : m));
    out.fast = { dcr: g.N / NRd, demand: g.N / 1000, cap: NRd / 1000, unit: 'kN', note: g.where };
  } else out.fast = { dcr: 0, demand: 0, cap: NRd / 1000, unit: 'kN', note: 'no uplift reaction' };
  return out;
}

export function design(inp) {
  const ld = loads(inp);
  const sec = section(inp);
  const combos = combinations(inp);
  const phiU = { y: inp.phiY, wr: inp.phiWr, wrSup: inp.phiWrSup, v: inp.phiV, c: inp.phiC, f: inp.phiF };
  const phiS = { y: 1, wr: 1, wrSup: inp.phiWrSupSLS, wrSupSLS: inp.phiWrSupSLS, v: 1, c: 1, f: 1 / 1.02 };
  const plastic = inp.method === 'plastic' && inp.spans === 2;
  const rows = []; // {combo, set, long, a, checks}

  for (const cb of combos.U) {
    const variants = [false];
    if (cb.alsoLong && inp.spans === 2 && !plastic) variants.push(true);
    for (const long of variants) {
      const a = analyse(cb, inp, ld, sec, { long, plastic });
      const checks = checkStress(a, inp, sec, phiU, false);
      if (plastic) delete checks.wrSup;
      rows.push({ set: 'U', id: cb.id + (long ? 'ᴸ' : ''), name: cb.name + (long ? ' (t = ∞)' : ''), a, checks });
    }
  }
  // Support stresses at SLS (ASD combinations) for continuous panels.
  if (inp.spans === 2) {
    for (const cb of combos.A) {
      const a = analyse(cb, inp, ld, sec, { long: !!cb.long });
      const all = checkStress(a, inp, sec, phiS, true);
      const checks = { wrSup: all.wrSup, shear: all.shear, crush: all.crush };
      rows.push({ set: 'A', id: cb.id, name: cb.name, a, checks });
    }
  }
  // Deflections
  for (const cb of combos.S) {
    const a = analyse(cb, inp, ld, sec, { long: !!cb.long });
    const n = inp.app === 'wall' ? inp.limWall : cb.lim === 'long' ? inp.limRoofLong : inp.limRoofShort;
    const lim = sec.Lmm / n;
    rows.push({ set: 'S', id: cb.id, name: cb.name, a, checks: { defl: { dcr: Math.abs(a.w) / lim, demand: Math.abs(a.w), cap: lim, unit: 'mm', note: `L/${n}` } } });
  }

  // Envelope per check
  const envelope = {};
  for (const ch of CHECKS) {
    let best = null;
    for (const r of rows) {
      const x = r.checks[ch.id];
      if (!x || !isFinite(x.dcr)) continue;
      if (!best || x.dcr > best.dcr) best = { ...x, combo: r.id, comboName: r.name, set: r.set };
    }
    envelope[ch.id] = best;
  }
  const governing = Object.entries(envelope)
    .filter(([, v]) => v)
    .reduce((m, [k, v]) => (!m || v.dcr > m.dcr ? { check: k, ...v } : m), null);

  return { inp, ld, sec, combos, rows, envelope, governing, plastic };
}
