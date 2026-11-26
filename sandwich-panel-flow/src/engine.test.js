import test from 'node:test';
import assert from 'node:assert/strict';
import { analyse, section, loads, design, kz, wallGCp, DEFAULT_INPUTS } from './engine.js';

const near = (a, b, tol = 1e-3) => assert.ok(Math.abs(a - b) <= tol * Math.max(1, Math.abs(b)), `${a} vs ${b}`);

test('single span UDL: M = qL²/8, V = qL/2, Timoshenko deflection', () => {
  const inp = { ...DEFAULT_INPUTS, spans: 1, app: 'roof' };
  const sec = section(inp);
  const ld = { ...loads(inp), D: 1, S: 0, Lr: 0 };
  const a = analyse({ D: 1 }, inp, ld, sec);
  const L = sec.Lmm;
  near(a.Mmax, (1 * L * L) / 8);
  near(a.Vmax, L / 2);
  near(a.w, (5 * L ** 4) / (384 * sec.Bs) + (L * L) / (8 * sec.GA));
});

test('two span UDL: support moment = -qL²/8/(1+k), tends to -qL²/8 for a rigid core', () => {
  const inp = { ...DEFAULT_INPUTS, spans: 2, app: 'roof' };
  const sec = section(inp);
  const ld = { ...loads(inp), D: 1, S: 0, Lr: 0 };
  const a = analyse({ D: 1 }, inp, ld, sec);
  near(a.MB, -(sec.Lmm ** 2) / 8 / (1 + sec.k));
  const stiff = { ...inp, Gc: 1e9 };
  const a2 = analyse({ D: 1 }, stiff, ld, section(stiff));
  near(a2.MB, -(sec.Lmm ** 2) / 8, 1e-4);
  near(a2.RB, 1.25 * sec.Lmm, 1e-4);
});

test('two span temperature: M_B = -3 Bs θ / (2(1+k)); single span has no thermal moment', () => {
  const inp = { ...DEFAULT_INPUTS, spans: 2, app: 'wall' };
  const sec = section(inp);
  const ld = loads(inp);
  const a = analyse({ T: 'winter', fT: 1 }, inp, ld, sec);
  const t = ld.temps.winter;
  const theta = (inp.alpha * (t.T2 - t.T1)) / sec.e;
  near(a.MB, (-3 * sec.Bs * theta) / (2 * (1 + sec.k)));
  const a1 = analyse({ T: 'winter', fT: 1 }, { ...inp, spans: 1 }, ld, sec);
  near(a1.Mmax, 0);
  near(a1.w, (theta * sec.Lmm ** 2) / 8);
});

test('ASCE 7-22 Kz and wall GCp end points', () => {
  near(kz('C', 15 / 3.28084), 0.849, 2e-3);
  near(kz('B', 3), 0.70);
  const s = wallGCp('5', 10);
  near(s.pos, 1.0); near(s.neg, -1.4);
  const l = wallGCp('4', 500);
  near(l.pos, 0.7); near(l.neg, -0.8);
});

test('default example produces an envelope for every check', () => {
  const r = design(DEFAULT_INPUTS);
  for (const k of ['yield', 'wrSpan', 'wrSup', 'shear', 'crush', 'fast', 'defl']) assert.ok(r.envelope[k], k);
  assert.ok(r.governing.dcr < 1);
});
