"""Continuous beam under uniform load, with optional shear flexibility (sandwich panels).

Three-moment (Clapeyron) equation extended with the shear term 1/(L*GA):

  M[i-1](L_i/6EI - 1/(L_i GA)) + M[i](L_i/3EI + 1/(L_i GA) + L_j/3EI + 1/(L_j GA))
      + M[i+1](L_j/6EI - 1/(L_j GA)) = -w (L_i^3 + L_j^3) / (24 EI)        (j = i+1)

End supports are simple (M = 0). Sign convention: sagging moment positive, load and
deflection positive in the direction of loading. With GA = None the classic
Euler-Bernoulli result is recovered.
"""
from __future__ import annotations
import numpy as np


def continuous_beam(spans: list[float], w: float, EI: float, GA: float | None = None, n_pts: int = 201) -> dict:
    if not spans or any(L <= 0 for L in spans):
        raise ValueError("spans must be a non-empty list of positive lengths")
    if EI <= 0:
        raise ValueError("EI must be positive")
    if GA is not None and GA <= 0:
        raise ValueError("GA must be positive when given")
    if w < 0:
        raise ValueError("w must be non-negative (apply direction by load case)")
    n = len(spans)
    sh = (lambda L: 1.0 / (L * GA)) if GA else (lambda L: 0.0)
    M = np.zeros(n + 1)
    if n > 1:
        A = np.zeros((n - 1, n - 1)); b = np.zeros(n - 1)
        for k in range(1, n):
            Li, Lj = spans[k - 1], spans[k]
            A[k - 1, k - 1] = Li / (3 * EI) + sh(Li) + Lj / (3 * EI) + sh(Lj)
            if k > 1:
                A[k - 1, k - 2] = Li / (6 * EI) - sh(Li)
            if k < n - 1:
                A[k - 1, k] = Lj / (6 * EI) - sh(Lj)
            b[k - 1] = -w * (Li ** 3 + Lj ** 3) / (24 * EI)
        M[1:n] = np.linalg.solve(A, b)
    span_out = []; reactions = np.zeros(n + 1)
    for i, L in enumerate(spans):
        Ml, Mr = M[i], M[i + 1]
        Vl = w * L / 2 + (Mr - Ml) / L
        Vr = Vl - w * L
        reactions[i] += Vl
        reactions[i + 1] += -Vr
        x0 = Vl / w if w > 0 else L / 2
        m_sag = Ml + Vl * x0 - w * x0 ** 2 / 2 if 0 <= x0 <= L else max(Ml, Mr)
        x = np.linspace(0, L, n_pts)
        d_b = (w * x * (L ** 3 - 2 * L * x ** 2 + x ** 3) / (24 * EI)
               + Ml * x * (L - x) * (2 * L - x) / (6 * EI * L)
               + Mr * x * (L ** 2 - x ** 2) / (6 * EI * L))
        Mx = Ml + Vl * x - w * x ** 2 / 2
        d_s = (Mx - Ml - (Mr - Ml) * x / L) / GA if GA else np.zeros_like(x)
        d = d_b + d_s
        j = int(np.argmax(np.abs(d)))
        span_out.append({"L": L, "M_left": float(Ml), "M_right": float(Mr), "V_left": float(Vl),
                         "V_right": float(Vr), "M_sag_max": float(max(m_sag, 0.0)),
                         "defl_max": float(abs(d[j])), "defl_bending": float(abs(d_b[j])),
                         "defl_shear": float(abs(d_s[j])), "x_defl_max": float(x[j])})
    return {"support_moments": [float(v) for v in M], "reactions": [float(v) for v in reactions],
            "spans": span_out,
            "M_sag_max": max(s["M_sag_max"] for s in span_out),
            "M_hog_max": float(max(0.0, -M.min())),
            "V_max": max(max(abs(s["V_left"]), abs(s["V_right"])) for s in span_out),
            "R_max": float(reactions.max()),
            "R_max_interior": float(reactions[1:-1].max()) if n > 1 else float(reactions.max()),
            "defl_max": max(s["defl_max"] for s in span_out),
            "governing_span": max(span_out, key=lambda s: s["defl_max"])}
