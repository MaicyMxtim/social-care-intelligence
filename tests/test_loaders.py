"""Check that every loader returns the columns the analysis scripts expect.

These tests read the real downloaded files rather than fixtures, because the
thing most likely to break this repository is a publisher changing a spreadsheet
layout, and a fixture would never notice that.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src import loaders
from src.paths import RAW_DIR

pytestmark = pytest.mark.skipif(
    not (RAW_DIR / "MANIFEST.json").exists(),
    reason="raw data has not been downloaded, run python scripts/download.py",
)

# The number of upper tier councils in England, which every authority level
# source should line up with once codes are canonicalised.
UPPER_TIER_COUNT = 153


def assert_columns(frame: pd.DataFrame, expected: set[str]) -> None:
    """Fail with a readable message when a loader loses or renames a column."""
    missing = expected - set(frame.columns)
    assert not missing, f"loader is missing {sorted(missing)}; it returned {sorted(frame.columns)}"


def test_long_term_support_columns():
    """The long-term support loader returns one row per authority and month."""
    frame = loaders.load_long_term_support()
    assert_columns(frame, {"la_code", "la_name", "period", "lts_count"})
    assert frame["la_code"].nunique() == UPPER_TIER_COUNT
    assert pd.api.types.is_datetime64_any_dtype(frame["period"])
    assert not frame.duplicated(["la_code", "period"]).any()


def test_assessments_columns():
    """The assessments loader returns one row per authority and month."""
    frame = loaders.load_assessments()
    assert_columns(frame, {"la_code", "la_name", "period", "assess_count"})
    assert frame["la_code"].nunique() == UPPER_TIER_COUNT


def test_cld_panel_has_no_duplicate_months():
    """Stitching the overlapping releases leaves one value per authority and month."""
    frame = loaders.load_cld_panel()
    assert not frame.duplicated(["la_code", "period"]).any()
    assert frame["period"].nunique() > 12


def test_population_covers_every_authority():
    """Population is available for all 153 councils and the shares are proportions."""
    frame = loaders.load_population()
    assert_columns(
        frame, {"la_code", "la_name", "adults_18plus", "adults_65plus", "share_65plus"}
    )
    assert len(frame) == UPPER_TIER_COUNT
    assert frame["adults_18plus"].gt(0).all()
    assert frame["share_65plus"].between(0, 1).all()


def test_imd_covers_every_authority_after_recoding():
    """Deprivation scores reach every current council, including the new unitaries."""
    frame = loaders.load_imd()
    assert_columns(frame, {"la_code", "imd_score"})
    assert len(frame) == UPPER_TIER_COUNT
    assert frame["imd_score"].gt(0).all()


def test_ascof_and_vacancy_columns():
    """The two authority level measures return the columns the model needs.

    Missing values are expected in both. ASCOF 1A is suppressed for councils
    whose survey response was too small to publish, and Skills for Care does not
    cover every council. What matters is that the values that are present are on
    the scale the analysis assumes, and that suppression came through as missing
    rather than as zero.
    """
    ascof = loaders.load_ascof_1a()
    assert_columns(ascof, {"la_code", "ascof_1a"})
    present = ascof["ascof_1a"].dropna()
    assert len(present) > 140, "almost every council should have a published score"
    # Measure 1A is an average score out of 24 built from eight survey questions.
    assert present.between(0, 24).all()

    vacancy = loaders.load_workforce_vacancy()
    assert_columns(vacancy, {"la_code", "vacancy_rate"})
    rates = vacancy["vacancy_rate"].dropna()
    # Skills for Care publishes proportions and the loader converts to percent.
    assert rates.between(0, 100).all()
    assert rates.median() > 1, "rates still look like proportions, not percentages"


def test_region_lookup_is_complete_and_uses_ons_regions():
    """Every council has one region, and London is not split into inner and outer."""
    frame = loaders.load_region_lookup()
    assert_columns(frame, {"la_code", "region"})
    assert len(frame) == UPPER_TIER_COUNT
    assert not frame.duplicated("la_code").any()
    assert "Inner London" not in set(frame["region"])
    assert set(frame["region"]) <= set(loaders.REGION_ORDER)


def test_csww_panel_columns_and_shape():
    """The workforce panel carries every measure and one row per authority and year."""
    frame = loaders.load_csww_indicators()
    assert_columns(
        frame,
        {
            "la_code", "la_name", "year", "turnover_rate", "vacancy_rate",
            "agency_rate", "caseload", "absence_rate", "inpost_fte", "leavers_fte",
        },
    )
    assert not frame.duplicated(["la_code", "year"]).any()
    assert frame["year"].between(2017, 2025).all()


@pytest.mark.parametrize(
    "loader, column",
    [
        (loaders.load_rereferrals, "rereferral_rate"),
        (loaders.load_repeat_cpp, "repeat_cpp_rate"),
        (loaders.load_placement_stability, "three_plus_placements_rate"),
    ],
)
def test_outcome_panels(loader, column):
    """Each outcome loader returns one percentage per authority and year."""
    frame = loader()
    assert_columns(frame, {"la_code", "year", column})
    assert not frame.duplicated(["la_code", "year"]).any()
    assert frame[column].dropna().between(0, 100).all()


def test_ilacs_history_grades_are_ranked_worst_highest():
    """Grades map to ranks where a bigger number is a worse judgement."""
    frame = loaders.load_ilacs_history()
    assert_columns(
        frame,
        {"la_code", "la_name", "inspection_date", "inspection_type", "grade", "grade_rank"},
    )
    assert frame["grade_rank"].between(1, 4).all()
    assert loaders.GRADE_RANK["Outstanding"] < loaders.GRADE_RANK["Good"]
    assert loaders.GRADE_RANK["Good"] < loaders.GRADE_RANK["Inadequate"]


def test_suppression_markers_become_missing_not_zero():
    """A suppressed cell is unknown, so it must never be read as a count of zero."""
    values = pd.Series(["[c]", "1,234", "5", "x", ":", "12.5%", ""])
    converted = loaders.to_number(values)
    assert converted.isna().tolist() == [True, False, False, True, True, False, True]
    assert converted.dropna().tolist() == [1234.0, 5.0, 12.5]


def test_boundaries_cover_every_english_authority():
    """The upper tier boundary file has a shape for all 153 councils."""
    frame = loaders.load_boundaries()
    english = frame[frame["la_code"].str.match(loaders.UPPER_TIER_PATTERN, na=False)]
    assert len(english) == UPPER_TIER_COUNT
