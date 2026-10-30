"""CMR reference intervals transcribed from the supplied reference documents."""

from typing import Any


def _ranges(
    *,
    lv: dict[str, tuple[float, float]],
    rv: dict[str, tuple[float, float]],
    lv_mass: tuple[float, float] | None = None,
    lv_mass_bsa: tuple[float, float] | None = None,
) -> dict[str, Any]:
    return {
        "lv": lv,
        "rv": rv,
        "lv_mass": lv_mass,
        "lv_mass_bsa": lv_mass_bsa,
    }

REFERENCE_PROFILES: dict[str, dict[str, Any]] = {
    "female_8_17": _ranges(
        lv={
            "edv_bsa": (55, 95),
            "esv_bsa": (15, 35),
            "sv_bsa": (34, 66),
            "ejection_fraction_pct": (51, 75),
            "ci": (2.7, 5.1),
        },
        rv={
            "edv_bsa": (58, 94),
            "esv_bsa": (17, 37),
            "sv_bsa": (35, 63),
            "ejection_fraction_pct": (55, 71),
        },
        lv_mass_bsa=(35, 71),
    ),
    "male_8_17": _ranges(
        lv={
            "edv_bsa": (56, 104),
            "esv_bsa": (16, 40),
            "sv_bsa": (36, 72),
            "ejection_fraction_pct": (56, 76),
        },
        rv={
            "edv_bsa": (60, 108),
            "esv_bsa": (18, 46),
            "sv_bsa": (36, 68),
            "ejection_fraction_pct": (54, 70),
        },
        lv_mass_bsa=(38, 86),
    ),
    "female_under_60": _ranges(
        lv={
            "edv": (90, 174),
            "edv_bsa": (61, 95),
            "esv": (25, 63),
            "sv": (60, 116),
            "ejection_fraction_pct": (58, 76),
        },
        rv={
            "edv": (89, 177),
            "edv_bsa": (60, 96),
            "esv": (23, 75),
            "sv": (59, 111),
            "ejection_fraction_pct": (52, 76),
        },
        lv_mass=(70, 142),
        lv_mass_bsa=(47, 77),
    ),
    "male_under_60": _ranges(
        lv={
            "edv": (119, 203),
            "edv_bsa": (64, 100),
            "esv": (33, 77),
            "sv": (78, 134),
            "ejection_fraction_pct": (57, 75),
        },
        rv={
            "edv": (119, 219),
            "edv_bsa": (63, 111),
            "esv": (32, 92),
            "sv": (73, 141),
            "ejection_fraction_pct": (50, 78),
        },
        lv_mass=(107, 187),
        lv_mass_bsa=(57, 91),
    ),
    "female_60_plus": _ranges(
        lv={
            "edv": (78, 162),
            "edv_bsa": (52, 86),
            "esv": (19, 57),
            "sv": (54, 110),
            "ejection_fraction_pct": (60, 78),
        },
        rv={
            "edv": (70, 158),
            "edv_bsa": (48, 84),
            "esv": (9, 61),
            "sv": (54, 106),
            "ejection_fraction_pct": (58, 82),
        },
        lv_mass=(74, 146),
        lv_mass_bsa=(48, 78),
    ),
    "male_60_plus": _ranges(
        lv={
            "edv": (106, 190),
            "edv_bsa": (58, 94),
            "esv": (26, 70),
            "sv": (72, 128),
            "ejection_fraction_pct": (59, 77),
        },
        rv={
            "edv": (103, 203),
            "edv_bsa": (53, 101),
            "esv": (18, 78),
            "sv": (71, 139),
            "ejection_fraction_pct": (55, 83),
        },
        lv_mass=(105, 185),
        lv_mass_bsa=(56, 90),
    ),
    "female_chinese": _ranges(
        lv={
            "edv": (69, 153),
            "edv_bsa": (49, 93),
            "esv": (22, 62),
            "esv_bsa": (15, 39),
            "sv": (43, 95),
            "ejection_fraction_pct": (52, 72),
            "co": (2.7, 6.3),
            "ci": (1.9, 3.9),
        },
        rv={
            "edv": (75, 163),
            "edv_bsa": (53, 101),
            "esv": (25, 77),
            "sv": (42, 94),
            "ejection_fraction_pct": (46, 70),
        },
        lv_mass=(38, 78),
        lv_mass_bsa=(28, 48),
    ),
    "male_chinese": _ranges(
        lv={
            "edv": (99, 191),
            "edv_bsa": (57, 101),
            "esv": (36, 84),
            "esv_bsa": (21, 45),
            "sv": (53, 117),
            "ejection_fraction_pct": (48, 68),
            "co": (3.4, 7.8),
            "ci": (1.8, 4.2),
        },
        rv={
            "edv": (112, 224),
            "edv_bsa": (63, 119),
            "esv": (47, 119),
            "sv": (55, 115),
            "ejection_fraction_pct": (41, 61),
        },
        lv_mass=(61, 125),
        lv_mass_bsa=(36, 64),
    ),
}


def select_reference_profile(study_info: dict[str, Any]) -> str | None:
    """Select only a profile whose sex, age, and optional ethnicity are known."""
    sex_value = str(study_info.get("sex", "")).strip().lower()
    sex = "female" if sex_value in {"f", "female", "woman"} else (
        "male" if sex_value in {"m", "male", "man"} else None
    )
    age = study_info.get("age")
    if sex is None or not isinstance(age, int) or isinstance(age, bool):
        return None

    ethnicity = str(study_info.get("ethnicity", "")).strip().lower()
    if "chinese" in ethnicity and "non-chinese" not in ethnicity:
        if age < 18:
            return None
        return f"{sex}_chinese"
    if 8 <= age <= 17:
        return f"{sex}_8_17"
    if 18 <= age < 60:
        return f"{sex}_under_60"
    if age >= 60:
        return f"{sex}_60_plus"
    return None


def reference_profile(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return a selected reference profile, or None when profile is unsupported."""
    name = select_reference_profile(data.get("study_info", {}))
    return REFERENCE_PROFILES.get(name) if name else None


def atrial_reference_interval(
    *,
    chamber: str,
    view: str,
    sex: str | None,
    age: int | None,
    indexed: bool = False,
) -> tuple[float, float] | None:
    """Return a supplied adult atrial area interval for a known view and profile."""
    normalized_sex = (sex or "").strip().lower()
    if normalized_sex not in {"f", "female", "woman", "m", "male", "man"}:
        return None
    if age is None or not 20 <= age <= 80:
        return None
    sex_key = "female" if normalized_sex in {"f", "female", "woman"} else "male"
    view_key = view.lower().replace(" ", "").replace("-", "")
    suffix = "_bsa" if indexed else ""
    key = f"area{suffix}"
    image_ranges = {
        ("female", "2ch"): {"area": (10, 28), "area_bsa": (6.2, 15.8)},
        ("female", "3ch"): {"area": (10, 24), "area_bsa": (6.4, 13.6)},
        ("female", "4ch"): {"area": (13, 27), "area_bsa": (8.4, 15.6)},
        ("male", "2ch"): {"area": (12, 30), "area_bsa": (6.2, 15.8)},
        ("male", "3ch"): {"area": (12, 26), "area_bsa": (6.4, 13.6)},
        ("male", "4ch"): {"area": (15, 29), "area_bsa": (7.4, 14.6)},
    }
    if chamber.lower() == "la":
        return image_ranges.get((sex_key, view_key), {}).get(key)
    return None


def atrial_max_volume_interval(
    sex: str | None,
    age: int | None,
    *,
    indexed: bool = False,
) -> tuple[float, float] | None:
    """Return the supplied adult max LA volume interval within its age limits."""
    normalized_sex = (sex or "").strip().lower()
    if normalized_sex not in {"f", "female", "woman", "m", "male", "man"}:
        return None
    if age is None or not 20 <= age <= 80:
        return None
    ranges = {
        "female": {"volume": (38, 98), "volume_bsa": (27, 53)},
        "male": {"volume": (47, 107), "volume_bsa": (26, 52)},
    }
    sex_key = "female" if normalized_sex in {"f", "female", "woman"} else "male"
    return ranges[sex_key]["volume_bsa" if indexed else "volume"]
