import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from engine.defaults import code_values


@pytest.fixture
def code():
    return code_values()


@pytest.fixture
def product():
    return {"name": "TEST-100", "thickness_mm": 100.0, "face_ext_mm": 0.5, "face_int_mm": 0.5, "E_face_MPa": 200000.0,
            "G_core_MPa": 3.5, "Mr_kNm_per_m": 4.0, "Vr_kN_per_m": 8.0, "fastener_Tr_kN": 2.0, "max_span_m": 3.5,
            "module_mm": 1000.0, "mass_kg_m2": 12.0}


@pytest.fixture
def section():
    return {"id": 1, "name": "Z203x1.9", "shape": "Z", "depth_mm": 203.0, "flange_mm": 70.0, "lip_mm": 20.0, "t_mm": 1.9, "Fy_MPa": 345.0}


@pytest.fixture
def wall_inp(code, product, section):
    return {"site": {"q50_kpa": 0.45, "importance": "Normal", "terrain": "Open", "ref_height_m": 9.0, "ct": 1.0,
                     "internal_category": "Category 2", "least_plan_dim_m": 30.0},
            "wall": {"length_m": 48.0, "height_m": 9.0, "max_bay_m": 8.0,
                     "openings": [{"offset_m": 4.0, "width_m": 3.6, "sill_m": 0.0, "height_m": 4.2}]},
            "design": {"n_spans": 4, "fasteners_per_support": 2}, "product": product, "section": section, "code": code}
