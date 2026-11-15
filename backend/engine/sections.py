"""Gross section properties of lipped cold-formed C and Z girts (thin-wall centreline, square corners)."""
from __future__ import annotations


def lipped_section(shape: str, depth_mm: float, flange_mm: float, lip_mm: float, t_mm: float,
                   density_kg_m3: float = 7850.0) -> dict:
    """Properties about the horizontal centroidal axis x-x (the bending axis for wind on a girt).

    Centreline dimensions: h = D - t, b = B - t, c = C - t/2.
    A  = t (h + 2b + 2c)
    Ix = t h^3/12 + 2 [b t (h/2)^2 + b t^3/12] + 2 [t c^3/12 + c t (h/2 - c/2)^2]
    Sx = Ix / (D/2)
    C (mirror-symmetric) and Z (point-symmetric) share the same A and Ix.
    """
    if shape not in ("C", "Z"):
        raise ValueError("shape must be 'C' or 'Z'")
    if min(depth_mm, flange_mm, t_mm) <= 0 or lip_mm < 0:
        raise ValueError("section dimensions must be positive")
    if t_mm >= min(depth_mm, flange_mm) / 2:
        raise ValueError("thickness is not thin relative to the section")
    h = depth_mm - t_mm
    b = flange_mm - t_mm
    c = max(lip_mm - t_mm / 2.0, 0.0)
    if 2 * c > h:
        raise ValueError("lips overlap")
    A = t_mm * (h + 2 * b + 2 * c)
    Ix = (t_mm * h ** 3 / 12.0
          + 2 * (b * t_mm * (h / 2) ** 2 + b * t_mm ** 3 / 12.0)
          + 2 * (t_mm * c ** 3 / 12.0 + c * t_mm * (h / 2 - c / 2) ** 2))
    Sx = Ix / (depth_mm / 2.0)
    return {"A_mm2": A, "Ix_mm4": Ix, "Sx_mm3": Sx, "mass_kg_per_m": A * 1e-6 * density_kg_m3,
            "web_flat_mm": depth_mm - 2 * t_mm, "h_over_t": (depth_mm - 2 * t_mm) / t_mm}
