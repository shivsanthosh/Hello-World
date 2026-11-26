# Sandwich Panel Design Flow

An interactive React Flow diagram of the design procedure in *European Recommendations for Sandwich Panels, Part I: Design* (ECCS/CIB Report, CIB Publication 257, 2000). The load side is converted from Eurocode 1 to **ASCE/SEI 7-22**.

Every node in the graph is one step of the procedure and runs live: edit the inputs in the side panel and the loads, combinations, action effects and demand-to-capacity ratios update throughout the graph.

```
A Inputs ─▶ B Actions (ASCE 7-22) ─▶ C Combinations ─▶ D Analysis (CIB Ch. 3) ─▶ E Verification (CIB Ch. 4) ─▶ F Verdict
```

## Run

```bash
npm install
npm run dev        # local dev server
npm test           # engine unit tests (node:test)
npm run build      # static site in dist/
npm run artifact   # single self-contained HTML in dist-artifact/
```

## What changed from the CIB document

| CIB 257 (Eurocode basis) | This tool (ASCE 7-22) |
|---|---|
| §2.2 actions per EN 1991 | D (Ch. 3), L_r (Table 4.3-1, 20 psf / 300 lb), S (Ch. 7, p_s = C_s·0.7·C_e·C_t·p_g, risk-targeted p_g), W as components and cladding (Ch. 26/30) |
| Table 2.1 / 2.4: 1.35G + 1.5Q₁ + 1.5·ψ₀·Q_i | §2.3.1 LRFD: 1.4D; 1.2D + 1.6(L_r or S) + 0.5W; 1.2D + 1.0W + 0.5S; 0.9D + 1.0W |
| Temperature as variable action, ψ₀ = 0.6 | Self-straining load T (§2.3.4): 1.0 as companion, 1.2 when leading (C2.3.4 examples) |
| Characteristic (rare) combination for support stresses (Eq. 2.5) | §2.4.1 ASD combinations |
| Frequent combination for deflection (Eq. 2.6), ψ₁ | Service combinations (App. C), wind = 0.42 × C&C (IBC Table 1604.3 note f) |
| Deflection limits L/200 short, L/100 long | IBC Table 1604.3 defaults: L/180 roof (S or W), L/120 roof long term and walls. All editable |
| γ_M (Table 2.5) | φ = 1/γ_M, editable |

Unchanged from CIB: face temperatures by colour group (ASCE 7-22 has no cladding temperatures), creep coefficients, the sandwich beam analysis with shear-flexible core (§3.4), wrinkling stress (Eq. 4.11), support strength reductions (Eqs. 4.23–4.25), core crushing (Eq. 4.19) and the testing chapters.

## Scope and limits

- Flat or lightly profiled faces only (B_F = 0). Strongly profiled faces (CIB §3.5) need numerical analysis and are not computed.
- Single span or two equal spans, uniform load.
- Roof (GC_p) must be entered from ASCE 7-22 Fig. 30.3-2. Wall (GC_p) is computed from Fig. 30.3-1 for h ≤ 60 ft.
- Snow drift, unbalanced snow, seismic (§13.5) and transverse bending (CIB §4.3.8) are not computed.
- Default core properties are typical values. Replace them with tested values for the actual product.

The mapping of CIB combinations onto ASCE 7-22 is engineering judgment, not code text. Check it against the governing building code and the panel manufacturer's evaluation report (for example ICC-ES AC04) before using the results for design.

## Files

- `src/engine.js`: loads, combinations, analysis and checks (pure functions, SI units internally)
- `src/flow.js`: the node catalogue: CIB clause, ASCE 7-22 clause, inputs, results, equations
- `src/App.jsx`, `src/Inspector.jsx`, `src/nodes/`: React Flow UI
- `src/engine.test.js`: closed-form checks of the analysis and the ASCE coefficient functions
