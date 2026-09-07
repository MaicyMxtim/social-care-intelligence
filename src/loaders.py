"""Read each raw source file and return a tidy table with predictable columns.

Every loader here does three things. It reads the published file exactly as it
was downloaded, it renames the publisher's column headings to the short names
used across this repository, and it returns one row per local authority (or per
local authority and year, where the source is a panel). Nothing is written back
to data/raw.

Suppressed values are a recurring feature of these publications. The Department
of Health and Social Care marks suppressed cells with [c], the Department for
Education uses markers such as z, c, x and : in its CSV extracts, and Ofsted
leaves cells empty. Every loader turns those markers into missing values rather
than into zeros, because a suppressed count is unknown, not absent.
"""
from __future__ import annotations

import json
import re
import warnings
import zipfile
from pathlib import Path

import pandas as pd

# The Skills for Care workbook carries Microsoft information protection labels
# that openpyxl does not recognise. The warning says nothing about the data, so
# it is silenced here to keep the run output readable.
warnings.filterwarnings(
    "ignore", message="Unknown type for .*", category=UserWarning, module="openpyxl.*"
)

from src.geography import canonicalise
from src.paths import raw

# Markers that publishers use in place of a number. Treating any of these as a
# number would silently invent data, so they all become missing values.
SUPPRESSION_MARKERS = {
    "[c]", "[x]", "[z]", "[w]", "[u]", "[low]", "c", "x", "z", "w", "u",
    ":", "..", ".", "-", "n/a", "na", "", "*",
}

# Adult social care and children's services are run by upper tier authorities.
# In ONS coding those are unitary authorities (E06), metropolitan districts
# (E08), London boroughs (E09) and county councils (E10). Together they are the
# 153 councils that appear in the client level data. Lower tier districts (E07)
# do not run social care and are excluded everywhere in this repository.
UPPER_TIER_PATTERN = r"^E(06|08|09|10)\d{6}$"

# The nine English regions, in the order used on charts so that the reading
# order is stable between plots.
REGION_ORDER = [
    "North East",
    "North West",
    "Yorkshire and The Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
]


def to_number(series: pd.Series) -> pd.Series:
    """Convert a column of published values to numbers, with suppression as missing.

    Published spreadsheets mix numbers with suppression markers and sometimes
    with thousands separators or percentage signs. This function strips those
    away, maps every recognised suppression marker to a missing value, and
    returns a numeric column.
    """
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
    )
    cleaned = cleaned.where(~cleaned.str.lower().isin(SUPPRESSION_MARKERS))
    return pd.to_numeric(cleaned, errors="coerce")


def _read_zip_member(archive_name: str, member_suffix: str) -> pd.DataFrame:
    """Read one CSV out of a Department for Education release zip.

    Release zips hold every file from a publication. The member is found by the
    end of its name rather than its full path, because the publisher changes the
    folder layout between releases more often than it changes file names.
    """
    with zipfile.ZipFile(raw(archive_name)) as archive:
        matches = [n for n in archive.namelist() if n.endswith(member_suffix)]
        if not matches:
            raise KeyError(
                f"{member_suffix} is not in {archive_name}. The publisher has "
                f"renamed it. Files present: {sorted(archive.namelist())[:40]}"
            )
        with archive.open(matches[0]) as handle:
            return pd.read_csv(handle, low_memory=False)


# --------------------------------------------------------------------------
# Adult social care client level data
# --------------------------------------------------------------------------

CLD_RELEASES = {
    "2025_09": (
        "cld_long_term_support_to_september_2025.ods",
        "cld_assessments_to_september_2025.ods",
    ),
    "2025_12": (
        "cld_long_term_support_to_december_2025.ods",
        "cld_assessments_to_december_2025.ods",
    ),
    "2026_03": (
        "cld_long_term_support_to_march_2026.ods",
        "cld_assessments_to_march_2026.ods",
    ),
}


def _parse_cld_period(column: str) -> pd.Timestamp | None:
    """Turn a client level data column heading into a date.

    Long-term support columns are headed with a snapshot date such as
    "31 March 2026 [p]". Assessment columns are headed with a month such as
    "March 2026 [p]", which is read as the last day of that month. The [p]
    marker means provisional and carries no date information, so it is removed
    before parsing. Headings that are not periods return nothing.
    """
    text = re.sub(r"\s*\[[a-z]\]\s*$", "", str(column)).strip()
    if text.lower() in {"total", ""}:
        return None
    for fmt in ("%d %B %Y", "%B %Y"):
        try:
            stamp = pd.to_datetime(text, format=fmt)
        except (ValueError, TypeError):
            continue
        if fmt == "%B %Y":
            return stamp + pd.offsets.MonthEnd(0)
        return stamp
    return None


def load_long_term_support(release: str = "2026_03") -> pd.DataFrame:
    """Return monthly counts of adults receiving long-term support by authority.

    The published table is wide, with one column per monthly snapshot. This
    loader keeps the rows covering all support settings and all ages, which is
    the total number of adults aged 18 and over receiving long-term support, and
    reshapes the monthly columns into rows.

    Returns columns la_code, la_name, period and lts_count.
    """
    filename = CLD_RELEASES[release][0]
    frame = pd.read_excel(raw(filename), sheet_name="Table_1", engine="odf", header=2)
    frame = frame[
        (frame["Area unit"] == "Local Authority")
        & (frame["Support setting"] == "All")
        & (frame["Age group"] == "All")
    ]
    periods = {c: _parse_cld_period(c) for c in frame.columns}
    period_columns = {c: p for c, p in periods.items() if p is not None}
    if not period_columns:
        raise ValueError(
            f"No date columns were recognised in {filename}. The publisher has "
            f"changed the column headings. Headings found: {list(frame.columns)}"
        )
    long = frame.melt(
        id_vars=["Area", "Area code"],
        value_vars=list(period_columns),
        var_name="column",
        value_name="lts_count",
    )
    long["period"] = long["column"].map(period_columns)
    long["lts_count"] = to_number(long["lts_count"])
    long = long.rename(columns={"Area": "la_name", "Area code": "la_code"})
    return long[["la_code", "la_name", "period", "lts_count"]].sort_values(
        ["la_code", "period"], ignore_index=True
    )


def load_assessments(release: str = "2026_03") -> pd.DataFrame:
    """Return monthly counts of adults receiving an assessment by authority.

    The published table has one column per month plus a total column. The total
    column is dropped here so that callers can sum whichever months they want.

    Returns columns la_code, la_name, period and assess_count.
    """
    filename = CLD_RELEASES[release][1]
    frame = pd.read_excel(raw(filename), sheet_name="Table_1", engine="odf", header=2)
    frame = frame[(frame["Area unit"] == "Local Authority") & (frame["Age group"] == "All")]
    periods = {c: _parse_cld_period(c) for c in frame.columns}
    period_columns = {c: p for c, p in periods.items() if p is not None}
    if not period_columns:
        raise ValueError(
            f"No date columns were recognised in {filename}. The publisher has "
            f"changed the column headings. Headings found: {list(frame.columns)}"
        )
    long = frame.melt(
        id_vars=["Area", "Area code"],
        value_vars=list(period_columns),
        var_name="column",
        value_name="assess_count",
    )
    long["period"] = long["column"].map(period_columns)
    long["assess_count"] = to_number(long["assess_count"])
    long = long.rename(columns={"Area": "la_name", "Area code": "la_code"})
    return long[["la_code", "la_name", "period", "assess_count"]].sort_values(
        ["la_code", "period"], ignore_index=True
    )


def load_cld_panel() -> pd.DataFrame:
    """Return every monthly long-term support snapshot published so far.

    Each quarterly release carries a rolling window of monthly snapshots, and
    the windows overlap. Where a month appears in more than one release, the
    value from the most recent release wins, because later releases carry the
    publisher's corrections.

    Returns columns la_code, la_name, period and lts_count.
    """
    frames = []
    for release in ["2025_09", "2025_12", "2026_03"]:
        frame = load_long_term_support(release)
        frame["release"] = release
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("release")
    combined = combined.drop_duplicates(subset=["la_code", "period"], keep="last")
    return combined[["la_code", "la_name", "period", "lts_count"]].sort_values(
        ["la_code", "period"], ignore_index=True
    )


def load_ascof_1a() -> pd.DataFrame:
    """Return ASCOF measure 1A, social care related quality of life, by authority.

    Measure 1A is an average score out of 24 built from eight questions in the
    Adult Social Care Survey. The loader keeps the total across all age and
    gender groups, which is the headline figure for each council.

    Returns columns la_code and ascof_1a.
    """
    frame = pd.read_excel(
        raw("ascof_england_2024_to_2025_outcome_and_demographic.ods"),
        sheet_name="Table_1a",
        engine="odf",
        header=5,
    )
    frame = frame[
        (frame["Area unit"] == "Local Authority")
        & (frame["Demographic"] == "Total")
        & (frame["Group"] == "Total")
    ]
    result = pd.DataFrame(
        {
            "la_code": frame["ONS Area Code"].astype(str).str.strip(),
            "ascof_1a": to_number(frame["Outcome (Score out of 24)"]),
        }
    )
    return result.dropna(subset=["la_code"]).drop_duplicates("la_code", ignore_index=True)


def load_workforce_vacancy() -> pd.DataFrame:
    """Return the adult social care vacancy rate for each local authority area.

    Skills for Care publishes one row for every combination of sector, service
    and job role. The loader keeps the whole-area total, meaning all sectors,
    all services and all job roles, so the vacancy rate describes the care
    workforce available across the authority rather than one part of it.

    Skills for Care publishes the vacancy rate as a proportion, so 0.062 means
    6.2 per cent. It is multiplied by 100 here so that every rate in this
    repository is on the same percentage scale.

    Returns columns la_code and vacancy_rate, where the rate is a percentage.
    """
    frame = pd.read_excel(
        raw("skills_for_care_local_area_2024_25.xlsx"),
        sheet_name="Local authority area 2024-25",
        header=0,
    )
    frame = frame[
        (frame["Area Level"] == "Local authority")
        & (frame["Sector"] == "All sectors - LA, IND and DPR")
        & (frame["Service"] == "All services")
        & (frame["Job role group"] == "All job roles")
    ]
    if frame.empty:
        raise ValueError(
            "No whole-area rows were found in the Skills for Care file. The "
            "filter values in the Sector, Service or Job role group columns "
            "have changed."
        )
    result = pd.DataFrame(
        {
            "la_code": frame["Area code"].astype(str).str.strip(),
            "vacancy_rate": to_number(frame["Vacancy rate"]) * 100,
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = canonicalise(result)
    return result.groupby("la_code", as_index=False)["vacancy_rate"].mean()


# --------------------------------------------------------------------------
# Population, deprivation and geography
# --------------------------------------------------------------------------


def load_population(min_age: int = 18) -> pd.DataFrame:
    """Return mid-2024 population by authority for adults and for older adults.

    The MYE2 sheet holds one column per single year of age, with a final column
    for people aged 90 and over. This loader sums those columns into the two
    denominators used across the adult project, the population aged 18 and over
    and the population aged 65 and over.

    Returns columns la_code, la_name, adults_18plus, adults_65plus and
    share_65plus.
    """
    frame = pd.read_excel(
        raw("ons_mid_2024_population_estimates.xlsx"),
        sheet_name="MYE2 - Persons",
        header=7,
    )
    frame = frame[frame["Code"].astype(str).str.match(UPPER_TIER_PATTERN, na=False)]

    def age_columns(lower: int) -> list:
        """Return the single-year-of-age columns at or above a given age."""
        chosen = []
        for column in frame.columns:
            label = str(column).strip()
            if label == "90+":
                if lower <= 90:
                    chosen.append(column)
                continue
            try:
                age = int(float(label))
            except (TypeError, ValueError):
                continue
            if age >= lower:
                chosen.append(column)
        return chosen

    adults = frame[age_columns(min_age)].apply(to_number).sum(axis=1)
    older = frame[age_columns(65)].apply(to_number).sum(axis=1)
    result = pd.DataFrame(
        {
            "la_code": frame["Code"].astype(str).str.strip(),
            "la_name": frame["Name"].astype(str).str.strip(),
            "adults_18plus": adults.values,
            "adults_65plus": older.values,
        }
    )
    result["share_65plus"] = result["adults_65plus"] / result["adults_18plus"]
    return result.reset_index(drop=True)


def load_child_population() -> pd.DataFrame:
    """Return the mid-2024 population aged 0 to 17 for each local authority.

    This is the denominator for the children's project. It is a single year of
    estimates applied to every panel year, which is noted as a limit in the
    project README.

    Returns columns la_code and children_0_17.
    """
    frame = pd.read_excel(
        raw("ons_mid_2024_population_estimates.xlsx"),
        sheet_name="MYE2 - Persons",
        header=7,
    )
    frame = frame[frame["Code"].astype(str).str.match(UPPER_TIER_PATTERN, na=False)]
    child_columns = []
    for column in frame.columns:
        label = str(column).strip()
        try:
            age = int(float(label))
        except (TypeError, ValueError):
            continue
        if 0 <= age <= 17:
            child_columns.append(column)
    result = pd.DataFrame(
        {
            "la_code": frame["Code"].astype(str).str.strip(),
            "children_0_17": frame[child_columns].apply(to_number).sum(axis=1).values,
        }
    )
    return result.reset_index(drop=True)


def load_imd() -> pd.DataFrame:
    """Return the 2019 average index of multiple deprivation score by authority.

    The index of multiple deprivation is a measure that ranks every small area
    in England from most to least deprived using seven domains, among them
    income, employment and health. The average score summarises the deprivation
    of all the small areas inside an authority, and a higher score means more
    deprivation.

    File 11 is used rather than File 10 because File 11 is published at upper
    tier, which is the geography social care is run at, so no aggregation from
    districts to counties is needed.

    Returns columns la_code and imd_score.
    """
    frame = pd.read_excel(
        raw("imd_2019_file_11_upper_tier_summaries.xlsx"), sheet_name="IMD", header=0
    )
    code_column = next(c for c in frame.columns if "code" in str(c).lower())
    score_column = next(
        c
        for c in frame.columns
        if "average score" in str(c).lower() and "rank" not in str(c).lower()
    )
    result = pd.DataFrame(
        {
            "la_code": frame[code_column].astype(str).str.strip(),
            "imd_score": to_number(frame[score_column]),
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    # The 2019 indices predate five reorganisations, so county scores are
    # carried to the unitary authorities that replaced those counties.
    result = canonicalise(result)
    return result.groupby("la_code", as_index=False)["imd_score"].mean()


def load_boundaries(upper_tier: bool = True):
    """Return local authority boundaries as a GeoDataFrame.

    By default this returns the December 2023 county and unitary authority
    boundaries, which match the geography social care is run at. Passing
    upper_tier as false returns the May 2024 local authority district
    boundaries instead.

    The import of geopandas happens inside the function so that the rest of this
    module can be used, and tested, on a machine where the geospatial stack is
    not installed.

    Returns columns la_code, la_name and geometry.
    """
    import geopandas as gpd

    if upper_tier:
        frame = gpd.read_file(raw("ctyua_december_2023_boundaries_buc.geojson"))
        frame = frame.rename(columns={"CTYUA23CD": "la_code", "CTYUA23NM": "la_name"})
    else:
        frame = gpd.read_file(raw("lad_may_2024_boundaries_buc.geojson"))
        frame = frame.rename(columns={"LAD24CD": "la_code", "LAD24NM": "la_name"})
    return frame[["la_code", "la_name", "geometry"]]


# Ofsted publishes eight inspection regions rather than the nine statistical
# regions, because it runs the North East together with Yorkshire and the
# Humber. The mapping below is used only to fill gaps left by the Department for
# Education file, and none of the authorities it fills sit in the combined
# region, so no authority is placed in the wrong statistical region.
OFSTED_REGION_TO_ONS = {
    "London": "London",
    "North West": "North West",
    "East Midlands": "East Midlands",
    "West Midlands": "West Midlands",
    "East of England": "East of England",
    "South East": "South East",
    "South West": "South West",
}


def load_region_lookup() -> pd.DataFrame:
    """Return the English region each upper tier local authority sits in.

    The lookup comes mainly from the Department for Education workforce file,
    which carries a region for every authority that runs children's services.
    That department splits London into an inner and an outer part, and those two
    are combined here into the single London region used by the Office for
    National Statistics.

    A small number of authorities are missing from that file, either because
    they were created by reorganisation or because they share a children's
    services arrangement with a neighbour and are reported under one code. Their
    region is filled in from the Ofsted inspection file.

    Returns columns la_code and region.
    """
    frame = _read_zip_member(
        "dfe_childrens_social_work_workforce.zip", "csww_indicators_2017_to_2025.csv"
    )
    frame = frame[frame["geographic_level"] == "Local authority"]
    result = pd.DataFrame(
        {
            "la_code": frame["new_la_code"].astype(str).str.strip(),
            "region": frame["region_name"].astype(str).str.strip(),
            "year": to_number(frame["time_period"]),
        }
    )
    result["region"] = result["region"].replace(
        {"Inner London": "London", "Outer London": "London"}
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = result.sort_values("year")
    result = canonicalise(result).sort_values("year")
    primary = result.drop_duplicates("la_code", keep="last")[["la_code", "region"]]

    ofsted = pd.read_excel(
        raw("ofsted_la_inspection_outcomes_2026.ods"),
        sheet_name="Inspections_as_at_31_March",
        engine="odf",
        header=2,
    )
    fallback = pd.DataFrame(
        {
            "la_code": ofsted["Local authority area code"].astype(str).str.strip(),
            "region": ofsted["Ofsted region"].astype(str).str.strip().map(OFSTED_REGION_TO_ONS),
        }
    ).dropna(subset=["region"])
    fallback = fallback[~fallback["la_code"].isin(primary["la_code"])]

    combined = pd.concat([primary, fallback], ignore_index=True)
    combined = combined[combined["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    return combined.drop_duplicates("la_code", ignore_index=True)


# --------------------------------------------------------------------------
# Children's social care
# --------------------------------------------------------------------------


def load_csww_indicators() -> pd.DataFrame:
    """Return the children's social work workforce panel for 2017 to 2025.

    The Department for Education publishes one row per authority per year with
    the workforce measures used in this project. The loader keeps the local
    authority rows and renames the measures to short names.

    Returns columns la_code, la_name, year, turnover_rate, vacancy_rate,
    agency_rate, caseload, absence_rate and inpost_fte.
    """
    frame = _read_zip_member(
        "dfe_childrens_social_work_workforce.zip", "csww_indicators_2017_to_2025.csv"
    )
    frame = frame[frame["geographic_level"] == "Local authority"]
    result = pd.DataFrame(
        {
            "la_code": frame["new_la_code"].astype(str).str.strip(),
            "la_name": frame["la_name"].astype(str).str.strip(),
            "year": to_number(frame["time_period"]).astype("Int64"),
            "turnover_rate": to_number(frame["turnover_rate_fte"]),
            "vacancy_rate": to_number(frame["vacancy_rate_fte"]),
            "agency_rate": to_number(frame["agency_rate_fte"]),
            "caseload": to_number(frame["caseload_fte"]),
            "absence_rate": to_number(frame["absence_rate_fte"]),
            "inpost_fte": to_number(frame["inpost_fte"]),
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    return canonicalise(result).reset_index(drop=True)


def load_rereferrals() -> pd.DataFrame:
    """Return the percentage of referrals that were re-referrals, by authority and year.

    A re-referral is a referral to children's social care for a child who was
    already referred within the previous twelve months. A higher percentage
    means more children coming back into the system soon after a previous
    contact.

    Returns columns la_code, year and rereferral_rate.
    """
    frame = _read_zip_member(
        "dfe_children_in_need.zip",
        "c1_children_in_need_referrals_and_rereferrals_2013_to_2025.csv",
    )
    frame = frame[frame["geographic_level"] == "Local authority"]
    result = pd.DataFrame(
        {
            "la_code": frame["new_la_code"].astype(str).str.strip(),
            "year": to_number(frame["time_period"]).astype("Int64"),
            "rereferral_rate": to_number(frame["rereferral_percent"]),
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = canonicalise(result.dropna(subset=["year"]))
    return result.reset_index(drop=True)


def load_repeat_cpp() -> pd.DataFrame:
    """Return the percentage of child protection plans that were repeat plans.

    A repeat plan is a child protection plan that is the second or a later plan
    for the same child. A higher percentage means more children returning to a
    protection plan after an earlier one ended.

    Returns columns la_code, year and repeat_cpp_rate.
    """
    frame = _read_zip_member(
        "dfe_children_in_need.zip", "d3_cpps_subsequent_plan_2013_to_2025.csv"
    )
    frame = frame[frame["geographic_level"] == "Local authority"]
    result = pd.DataFrame(
        {
            "la_code": frame["new_la_code"].astype(str).str.strip(),
            "year": to_number(frame["time_period"]).astype("Int64"),
            "repeat_cpp_rate": to_number(frame["CPP_subsequent_percent"]),
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = canonicalise(result.dropna(subset=["year"]))
    return result.reset_index(drop=True)


def load_placement_stability() -> pd.DataFrame:
    """Return the percentage of looked after children with three or more placements.

    Placement instability is measured here as the share of children looked after
    during the year who had three or more placements in that year. A higher
    share means more children moving between homes.

    Returns columns la_code, year and three_plus_placements_rate.
    """
    frame = _read_zip_member(
        "dfe_children_looked_after.zip", "LA_CLA_placement_stability.csv"
    )
    frame.columns = [str(c).lstrip("﻿") for c in frame.columns]
    frame = frame[frame["geographic_level"] == "Local authority"]
    # The file holds two instability measures. The one wanted here counts moves
    # within a single year, not moves across the previous two years.
    wanted = frame[
        frame["placement_stability"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("with 3 or more placements during the year")
    ]
    if wanted.empty:
        raise ValueError(
            "No rows describing three or more placements were found. The "
            "placement_stability labels are now: "
            f"{sorted(frame['placement_stability'].dropna().unique())}"
        )
    result = pd.DataFrame(
        {
            "la_code": wanted["new_la_code"].astype(str).str.strip(),
            "year": to_number(wanted["time_period"]).astype("Int64"),
            "three_plus_placements_rate": to_number(wanted["children_percent"]),
        }
    )
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = canonicalise(result.dropna(subset=["year"]))
    return result.reset_index(drop=True)


# Ofsted grades, ordered from best to worst. The numeric rank makes a downgrade
# easy to detect, because a downgrade is any move to a higher rank.
GRADE_RANK = {
    "Outstanding": 1,
    "Good": 2,
    "Requires improvement to be good": 3,
    "Requires improvement": 3,
    "Inadequate": 4,
}


def load_ilacs_history() -> pd.DataFrame:
    """Return every ILACS inspection from 2018 onwards with its date and grade.

    ILACS stands for the inspection of local authority children's services. Each
    row is one inspection of one authority. The overall effectiveness grade is
    converted to a rank from one for outstanding to four for inadequate, so that
    a fall in quality between two inspections is a rise in rank.

    Returns columns la_code, la_name, region, inspection_date, inspection_type,
    grade and grade_rank.
    """
    frame = pd.read_excel(
        raw("ofsted_la_inspection_outcomes_2026.ods"),
        sheet_name="ILACS_inspection_history",
        engine="odf",
        header=2,
    )
    result = pd.DataFrame(
        {
            "la_code": frame["Local authority area code"].astype(str).str.strip(),
            "la_name": frame["Local authority name"].astype(str).str.strip(),
            "region": frame["Ofsted region"].astype(str).str.strip(),
            "inspection_date": pd.to_datetime(frame["Inspection date"], errors="coerce"),
            "inspection_type": frame["Inspection type"].astype(str).str.strip(),
            "grade": frame["Overall effectiveness"].astype(str).str.strip(),
        }
    )
    result["grade_rank"] = result["grade"].map(GRADE_RANK)
    result = result[result["la_code"].str.match(UPPER_TIER_PATTERN, na=False)]
    result = canonicalise(result.dropna(subset=["inspection_date", "grade_rank"]))
    return result.sort_values(["la_code", "inspection_date"], ignore_index=True)


def read_manifest() -> dict:
    """Return the download manifest so that reports can cite source dates and hashes."""
    path = Path(raw("MANIFEST.json"))
    return json.loads(path.read_text(encoding="utf-8"))
