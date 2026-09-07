"""Put every source on one set of local authority codes.

England reorganised several areas of local government between 2017 and 2025,
and the Office for National Statistics also reissued codes for two metropolitan
districts. A panel that ignores this loses authorities in the years around each
change, so every code is translated here to the set of 153 upper tier codes used
by the mid-2024 population estimates.

Two kinds of change are handled. A merge or a straight recode maps one old code
to one new code. A split maps one old code to several new codes, and the value
recorded for the old authority is carried to each successor. Carrying a county
figure to both of its successors is an approximation, not a measurement, and the
project READMEs say so.

Every mapping in this module is listed in docs/DATA_NOTES.md with the date the
change took effect.
"""
from __future__ import annotations

import pandas as pd

# One old code to one new code. The comment on each line gives the year the
# change took effect.
RECODE_ONE_TO_ONE: dict[str, str] = {
    "E06000028": "E06000058",  # 2019, Bournemouth into Bournemouth, Christchurch and Poole
    "E06000029": "E06000058",  # 2019, Poole into Bournemouth, Christchurch and Poole
    "E10000009": "E06000059",  # 2019, Dorset county council into Dorset unitary authority
    "E10000002": "E06000060",  # 2020, Buckinghamshire county council into a unitary authority
    "E10000023": "E06000065",  # 2023, North Yorkshire county council into a unitary authority
    "E10000027": "E06000066",  # 2023, Somerset county council into a unitary authority
    "E08000038": "E08000016",  # ONS reissued the code for Barnsley
    "E08000039": "E08000019",  # ONS reissued the code for Sheffield
}

# One old code to several new codes. The old authority's value is carried to
# each successor.
SPLITS: dict[str, list[str]] = {
    # 2021, Northamptonshire county council split into two unitary authorities
    "E10000021": ["E06000061", "E06000062"],
    # 2023, Cumbria county council split into two unitary authorities
    "E10000006": ["E06000063", "E06000064"],
}

# Authorities that share a children's services arrangement and are reported by
# the Department for Education under one of their two codes. The region for the
# partner authority is filled in from the Ofsted file instead.
SHARED_SERVICES = {
    "E09000021": "Kingston upon Thames",
    "E09000027": "Richmond upon Thames",
}


# Column added by canonicalise to mark rows that were created by carrying a
# predecessor's value forward, so that collapse can prefer real observations.
SPLIT_FLAG = "_carried_from_predecessor"


def canonicalise(frame: pd.DataFrame, code_column: str = "la_code") -> pd.DataFrame:
    """Translate old local authority codes into the current ones.

    Rows whose code has been recoded are relabelled in place. Rows whose
    authority was split are duplicated, once per successor authority, so that
    both successors carry the value recorded for their predecessor. Rows whose
    code needs no change pass through untouched.

    Carried rows are marked in a column named by SPLIT_FLAG so that collapse can
    tell an authority's own measurement apart from a figure inherited from the
    council it replaced.

    The function returns a new frame and never changes the one passed in.
    """
    working = frame.copy()
    working[code_column] = working[code_column].replace(RECODE_ONE_TO_ONE)
    working[SPLIT_FLAG] = False

    split_rows = []
    for old_code, successors in SPLITS.items():
        matching = working[working[code_column] == old_code]
        for successor in successors:
            copied = matching.copy()
            copied[code_column] = successor
            copied[SPLIT_FLAG] = True
            split_rows.append(copied)
    working = working[~working[code_column].isin(SPLITS)]
    if split_rows:
        working = pd.concat([working, *split_rows], ignore_index=True)
    return working.reset_index(drop=True)


def collapse(
    frame: pd.DataFrame,
    keys: list[str],
    sum_columns: list[str] | None = None,
    weight_column: str | None = None,
) -> pd.DataFrame:
    """Reduce a canonicalised frame to one row per key, resolving the two collisions.

    Recoding creates collisions of two kinds, and they need opposite treatment.

    The first is a merge, where several predecessor councils became one. Both
    Bournemouth and Poole became Bournemouth, Christchurch and Poole, so both
    contribute a row for the years before 2019. Their values are combined: counts
    are added, and rates are averaged, weighted by the weight column when one is
    given so that the larger council counts for more.

    The second is a split, where one predecessor council became several. A row
    carried from the predecessor is only useful for years in which the successor
    has no figures of its own. Where the successor does have its own row, the
    carried row is dropped, because a real measurement always beats an inherited
    one.
    """
    working = frame.copy()
    if SPLIT_FLAG not in working.columns:
        working[SPLIT_FLAG] = False

    # Drop carried rows for any key that also has a real observation.
    has_real = working.groupby(keys)[SPLIT_FLAG].transform(lambda flags: (~flags).any())
    working = working[~(working[SPLIT_FLAG] & has_real)]

    sum_columns = sum_columns or []
    numeric = [
        column
        for column in working.columns
        if column not in keys
        and column != SPLIT_FLAG
        and pd.api.types.is_numeric_dtype(working[column])
    ]
    text = [
        column
        for column in working.columns
        if column not in keys and column != SPLIT_FLAG and column not in numeric
    ]

    pieces = []
    grouped = working.groupby(keys, sort=False)
    for column in numeric:
        if column in sum_columns:
            pieces.append(grouped[column].sum(min_count=1))
        elif weight_column and column != weight_column:
            pieces.append(
                grouped.apply(
                    lambda part, col=column: _weighted_mean(part, col, weight_column),
                    include_groups=False,
                ).rename(column)
            )
        else:
            pieces.append(grouped[column].mean())
    for column in text:
        pieces.append(grouped[column].first())

    result = pd.concat(pieces, axis=1).reset_index()
    return result


def _weighted_mean(part: pd.DataFrame, column: str, weight_column: str) -> float:
    """Return the weighted mean of one column, falling back to a plain mean.

    The fallback matters when every weight is missing, which happens for years
    where a council reported a rate but not a workforce size.
    """
    values = part[column]
    weights = part[weight_column] if weight_column in part else None
    usable = values.notna() & (weights.notna() if weights is not None else False)
    if weights is None or not usable.any() or weights[usable].sum() == 0:
        return values.mean()
    return float((values[usable] * weights[usable]).sum() / weights[usable].sum())
