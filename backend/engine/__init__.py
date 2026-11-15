"""Panel Studio deterministic IMP engineering engine.

Pure functions only: no database, no I/O, no randomness. Every function returns
numeric results together with a trace (formula, substituted values, units,
reference) so that each number in a report can be re-derived by hand.

Units (SI, used consistently): m, kPa (= kN/m2), kN, kN*m, MPa only where noted.
"""
ENGINE_VERSION = "1.0.0"
