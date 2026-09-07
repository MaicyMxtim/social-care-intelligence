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


def canonicalise(frame: pd.DataFrame, code_column: str = "la_code") -> pd.DataFrame:
    """Translate old local authority codes into the current ones.

    Rows whose code has been recoded are relabelled in place. Rows whose
    authority was split are duplicated, once per successor authority, so that
    both successors carry the value recorded for their predecessor. Rows whose
    code needs no change pass through untouched.

    The function returns a new frame and never changes the one passed in.
    """
    working = frame.copy()
    working[code_column] = working[code_column].replace(RECODE_ONE_TO_ONE)

    split_rows = []
    for old_code, successors in SPLITS.items():
        matching = working[working[code_column] == old_code]
        for successor in successors:
            copied = matching.copy()
            copied[code_column] = successor
            split_rows.append(copied)
    working = working[~working[code_column].isin(SPLITS)]
    if split_rows:
        working = pd.concat([working, *split_rows], ignore_index=True)
    return working.reset_index(drop=True)


def deduplicate(frame: pd.DataFrame, keys: list[str], value_columns: list[str]) -> pd.DataFrame:
    """Collapse rows that now share a code after recoding, by averaging values.

    Two predecessor authorities can map to the same successor, as Bournemouth
    and Poole both do. Averaging their values is the honest summary available
    without the underlying counts, and the project READMEs record that these
    early years are approximate.
    """
    grouped = frame.groupby(keys, as_index=False)[value_columns].mean()
    return grouped
