"""Build every output for the children's social work workforce project.

Run this file from inside its own folder:

    python make_all.py

It reads only from data/raw, writes every chart, table and number to outputs,
and finishes by rendering the README from outputs/findings.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(ROOT))

from src import analysis, loaders, plots  # noqa: E402

OUTPUT_DIR = PROJECT_DIR / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
TABLE_DIR = OUTPUT_DIR / "tables"

FIRST_YEAR = 2017
LAST_YEAR = 2025
# Follow-up for the survival model ends at the date the Ofsted file was compiled.
FOLLOW_UP_END = pd.Timestamp("2026-03-31")

WORKFORCE_MEASURES = ["agency_rate", "turnover_rate", "caseload", "vacancy_rate", "absence_rate"]
CLUSTER_MEASURES = ["agency_rate", "turnover_rate", "caseload"]

SOURCE_NOTE = (
    "Source: DfE children's social work workforce 2017 to 2025; DfE children in "
    "need census; DfE children looked after; Ofsted local authority inspection "
    "outcomes to 31 March 2026; MHCLG indices of deprivation 2019; ONS mid-2024 "
    "population estimates. Open Government Licence v3.0."
)


def build_panel() -> pd.DataFrame:
    """Assemble one row per local authority per year from 2017 to 2025.

    Workforce measures, outcome measures, deprivation and child population are
    joined on the canonical authority code. Codes from before the local
    government reorganisations are translated first, which is what keeps
    Northamptonshire, Cumbria, Dorset, Buckinghamshire, Somerset and North
    Yorkshire in the panel across the years their boundaries changed.
    """
    workforce = loaders.load_csww_indicators()
    workforce = workforce[
        workforce["year"].between(FIRST_YEAR, LAST_YEAR)
    ].copy()

    panel = (
        workforce.merge(loaders.load_rereferrals(), on=["la_code", "year"], how="left")
        .merge(loaders.load_repeat_cpp(), on=["la_code", "year"], how="left")
        .merge(loaders.load_placement_stability(), on=["la_code", "year"], how="left")
        .merge(loaders.load_imd(), on="la_code", how="left")
        .merge(loaders.load_child_population(), on="la_code", how="left")
        .merge(loaders.load_region_lookup(), on="la_code", how="left")
    )
    panel["year"] = panel["year"].astype(int)
    panel["fte_per_10k_children"] = (
        panel["inpost_fte"] / panel["children_0_17"] * 10_000
    )

    # One-year lags of every workforce measure. Shifting inside each authority
    # means an authority's first year has no lag, which is correct, rather than
    # borrowing the previous authority's value.
    panel = panel.sort_values(["la_code", "year"])
    for measure in WORKFORCE_MEASURES:
        panel[f"{measure}_lag1"] = panel.groupby("la_code")[measure].shift(1)

    return panel.reset_index(drop=True)


def draw_descriptives(panel: pd.DataFrame, findings: dict) -> None:
    """Draw the regional trajectory plots and the turnover funnel plot."""
    by_region = (
        panel.dropna(subset=["region"])
        .groupby(["region", "year"], as_index=False)[["agency_rate", "turnover_rate"]]
        .mean()
    )

    first = by_region[by_region["year"] == FIRST_YEAR]
    latest = by_region[by_region["year"] == LAST_YEAR]
    england_agency = panel.groupby("year")["agency_rate"].mean()
    peak_year = int(england_agency.idxmax())
    england_peak = float(england_agency.max())
    england_last = float(england_agency.loc[LAST_YEAR])

    # The regional spread in the first and last year, so the title can say
    # whether regions converged rather than assuming it.
    spread_first = float(first["agency_rate"].max() - first["agency_rate"].min())
    spread_last = float(latest["agency_rate"].max() - latest["agency_rate"].min())
    spread_verb = "widened" if spread_last > spread_first else "narrowed"

    plots.trajectory_plot(
        by_region,
        x="year",
        y="agency_rate",
        group="region",
        title=(
            f"Agency use peaked in {peak_year} and has fallen since, while the gap "
            f"between regions {spread_verb}"
        ),
        subtitle=(
            f"Mean share of the children's social work workforce supplied by "
            f"agencies, by region. The spread between the highest and lowest region "
            f"went from {spread_first:.1f} to {spread_last:.1f} percentage points."
        ),
        y_label="Agency workers as a percentage of full time equivalent staff",
        x_label="Year",
        source=SOURCE_NOTE,
        path=CHART_DIR / "trajectory_agency_rate.png",
    )

    england_turnover = panel.groupby("year")["turnover_rate"].mean()
    turnover_peak_year = int(england_turnover.idxmax())
    peak_values = by_region[by_region["year"] == turnover_peak_year].set_index("region")
    last_values = latest.set_index("region")
    fell_everywhere = bool(
        (last_values["turnover_rate"] < peak_values["turnover_rate"]).all()
    )
    turnover_title = (
        f"Turnover fell after {turnover_peak_year} in every region, from very "
        f"different starting points"
        if fell_everywhere
        else f"Turnover peaked in {turnover_peak_year}, but has not fallen everywhere"
    )
    plots.trajectory_plot(
        by_region,
        x="year",
        y="turnover_rate",
        group="region",
        title=turnover_title,
        subtitle="Mean annual turnover of children's social workers, by region.",
        y_label="Leavers as a percentage of full time equivalent staff",
        x_label="Year",
        source=SOURCE_NOTE,
        path=CHART_DIR / "trajectory_turnover.png",
    )

    recent = panel[panel["year"] == LAST_YEAR].dropna(subset=["leavers_fte", "inpost_fte"])
    turnover_funnel = analysis.funnel_frame(
        recent.set_index("la_code")["leavers_fte"],
        recent.set_index("la_code")["inpost_fte"],
        per=100.0,
    )
    plots.funnel_plot(
        turnover_funnel,
        recent.set_index("la_code")["la_name"],
        title=(
            f"Turnover varies about {turnover_funnel['phi']:.0f} times more between "
            f"councils than chance would produce"
        ),
        subtitle=(
            f"Children's social workers leaving during {LAST_YEAR}, against the size "
            f"of the workforce. Limits are overdispersion adjusted."
        ),
        y_label="Leavers as a percentage of full time equivalent staff",
        x_label="Full time equivalent social workers in post (log scale)",
        source=SOURCE_NOTE,
        path=CHART_DIR / "funnel_turnover.png",
        flag_level="95",
    )

    findings["descriptives"] = {
        "agency_peak_year": peak_year,
        "agency_peak_mean": england_peak,
        "agency_last_mean": england_last,
        "agency_spread_first": spread_first,
        "agency_spread_last": spread_last,
        "turnover_peak_year": turnover_peak_year,
        "turnover_peak_mean": float(england_turnover.max()),
        "turnover_fell_everywhere": fell_everywhere,
        "turnover_last_mean": float(recent["turnover_rate"].mean()),
        "turnover_phi": turnover_funnel["phi"],
        "turnover_outside_95": int(turnover_funnel["points"]["outside_95"].sum()),
        "turnover_n": int(len(recent)),
        "region_high_agency": latest.nlargest(1, "agency_rate")["region"].iloc[0],
        "region_high_agency_value": float(latest.nlargest(1, "agency_rate")["agency_rate"].iloc[0]),
        "region_low_agency": latest.nsmallest(1, "agency_rate")["region"].iloc[0],
        "region_low_agency_value": float(
            latest.nsmallest(1, "agency_rate")["agency_rate"].iloc[0]
        ),
    }


def build_survival_frame(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Turn inspection history and the workforce panel into survival intervals.

    Each authority enters the analysis at its first ILACS inspection. The event
    is a downgrade, meaning a later inspection whose overall effectiveness grade
    is worse than the grade the authority held before it. An authority that is
    never downgraded is censored at the end of follow-up.

    The result is one row per authority per year of follow-up, holding the start
    and stop of that year measured from the authority's own entry, whether the
    downgrade happened in it, and the workforce measures from the year before.
    Splitting time this way is what lets covariates change while an authority is
    still at risk.
    """
    history = loaders.load_ilacs_history()
    history = history[history["inspection_type"].str.contains("ILACS", na=False)]

    rows = []
    summary = {"entered": 0, "downgraded": 0, "censored": 0}
    for code, inspections in history.groupby("la_code"):
        inspections = inspections.sort_values("inspection_date")
        if len(inspections) < 1:
            continue
        baseline = inspections.iloc[0]
        entry_date = baseline["inspection_date"]
        held_rank = baseline["grade_rank"]

        event_date = None
        for _, inspection in inspections.iloc[1:].iterrows():
            if inspection["grade_rank"] > held_rank:
                event_date = inspection["inspection_date"]
                break
            held_rank = inspection["grade_rank"]

        exit_date = event_date if event_date is not None else FOLLOW_UP_END
        if exit_date <= entry_date:
            continue
        summary["entered"] += 1
        if event_date is not None:
            summary["downgraded"] += 1
        else:
            summary["censored"] += 1

        total_years = (exit_date - entry_date).days / 365.25
        year_index = 0
        while year_index * 1.0 < total_years:
            start = float(year_index)
            stop = min(float(year_index + 1), total_years)
            calendar_year = entry_date.year + year_index
            rows.append(
                {
                    "la_code": code,
                    "start": start,
                    "stop": stop,
                    "event": int(event_date is not None and stop >= total_years - 1e-9),
                    "calendar_year": calendar_year,
                }
            )
            year_index += 1

    intervals = pd.DataFrame(rows)
    lagged = panel[["la_code", "year", "imd_score"] + [f"{m}_lag1" for m in WORKFORCE_MEASURES]]
    intervals = intervals.merge(
        lagged, left_on=["la_code", "calendar_year"], right_on=["la_code", "year"], how="left"
    )
    intervals = intervals.drop(columns=["year"])
    return intervals, summary


COX_LABELS = {
    "agency_rate_lag1": "Agency rate, previous year",
    "turnover_rate_lag1": "Turnover rate, previous year",
    "caseload_lag1": "Average caseload, previous year",
    "vacancy_rate_lag1": "Vacancy rate, previous year",
    "imd_score": "Deprivation score",
}


def run_cox(panel: pd.DataFrame, findings: dict) -> None:
    """Fit a Cox model of the time until an Ofsted downgrade.

    A Cox proportional hazards model is a regression for how long something takes
    to happen. It does not model the shape of the risk over time, only how each
    covariate multiplies that risk. A hazard ratio of 1.05 means a five per cent
    higher risk of a downgrade at any moment for a one unit rise in the
    covariate, holding the others still.

    The proportional hazards assumption is that those multipliers stay the same
    over the whole follow-up. The test at the end of this function checks it, and
    the README reports the result whether it passes or not.
    """
    from lifelines import CoxTimeVaryingFitter
    from lifelines.statistics import proportional_hazard_test

    intervals, summary = build_survival_frame(panel)
    columns = list(COX_LABELS)
    usable = intervals.dropna(subset=columns + ["start", "stop", "event"]).copy()
    usable = usable[usable["stop"] > usable["start"]]
    usable["id"] = usable["la_code"].astype("category").cat.codes

    fitter = CoxTimeVaryingFitter(penalizer=0.05)
    fitter.fit(
        usable[["id", "start", "stop", "event"] + columns],
        id_col="id",
        event_col="event",
        start_col="start",
        stop_col="stop",
        show_progress=False,
    )

    hazard = pd.DataFrame(
        {
            "irr": np.exp(fitter.params_),
            "irr_low": np.exp(fitter.confidence_intervals_.iloc[:, 0]),
            "irr_high": np.exp(fitter.confidence_intervals_.iloc[:, 1]),
            "p_value": fitter.summary["p"],
        }
    ).rename(index=COX_LABELS)
    hazard.to_csv(TABLE_DIR / "cox_hazard_ratios.csv", index_label="term")

    plots.forest_plot(
        hazard,
        title="No workforce measure moves the risk of an Ofsted downgrade on its own",
        subtitle=(
            "Hazard ratios per one unit rise in the previous year's value, from a "
            "Cox model with time-varying covariates."
        ),
        x_label="Hazard ratio per one unit (1.0 means no change in risk)",
        source=SOURCE_NOTE,
        path=CHART_DIR / "forest_cox_hazard_ratios.png",
    )

    # The proportional hazards test needs a fixed covariate model, so it is run
    # on the last observation carried forward for each authority.
    last = usable.sort_values("stop").groupby("id", as_index=False).last()
    ph_result = None
    try:
        from lifelines import CoxPHFitter

        fixed = CoxPHFitter(penalizer=0.05)
        fixed.fit(
            last[columns + ["stop", "event"]], duration_col="stop", event_col="event"
        )
        test = proportional_hazard_test(fixed, last[columns + ["stop", "event"]])
        ph_result = {
            "min_p": float(test.summary["p"].min()),
            "violations": int((test.summary["p"] < 0.05).sum()),
            "terms": int(len(test.summary)),
        }
        test.summary.to_csv(TABLE_DIR / "cox_proportional_hazards_test.csv")
    except Exception as exc:  # noqa: BLE001 - reported, never silenced
        ph_result = {"error": f"{type(exc).__name__}: {exc}"}

    findings["cox"] = {
        "authorities": summary["entered"],
        "downgraded": summary["downgraded"],
        "censored": summary["censored"],
        "intervals": int(len(usable)),
        "events_modelled": int(usable["event"].sum()),
        "hazard": {
            label: {
                "hr": float(hazard.loc[label, "irr"]),
                "low": float(hazard.loc[label, "irr_low"]),
                "high": float(hazard.loc[label, "irr_high"]),
                "p": float(hazard.loc[label, "p_value"]),
            }
            for label in hazard.index
        },
        "significant": [
            label
            for label in hazard.index
            if hazard.loc[label, "irr_low"] > 1.0 or hazard.loc[label, "irr_high"] < 1.0
        ],
        "proportional_hazards": ph_result,
    }


PANEL_OUTCOMES = {
    "rereferral_rate": "Re-referrals within twelve months",
    "repeat_cpp_rate": "Repeat child protection plans",
    "three_plus_placements_rate": "Children with three or more placements",
}


def run_panel_regression(panel: pd.DataFrame, findings: dict) -> None:
    """Fit fixed effects panel regressions of outcomes on lagged workforce measures.

    A fixed effects panel regression compares an authority with itself over time
    rather than with other authorities. Authority effects absorb everything about
    a council that does not change across the period, such as its population and
    its history. Year effects absorb everything that moved nationally in a given
    year, such as a change in guidance. What is left is whether an authority's
    outcomes moved when its own workforce measures moved.

    Standard errors are clustered by authority, because observations from the
    same council in different years are not independent of each other.
    """
    from linearmodels.panel import PanelOLS

    lagged = [f"{m}_lag1" for m in WORKFORCE_MEASURES]
    results = {}
    for outcome, label in PANEL_OUTCOMES.items():
        frame = panel.dropna(subset=[outcome] + lagged).copy()
        frame = frame.set_index(["la_code", "year"])
        if frame.empty:
            continue
        model = PanelOLS(
            frame[outcome],
            frame[lagged],
            entity_effects=True,
            time_effects=True,
            drop_absorbed=True,
        )
        fitted = model.fit(cov_type="clustered", cluster_entity=True)

        table = pd.DataFrame(
            {
                "coefficient": fitted.params,
                "std_error": fitted.std_errors,
                "p_value": fitted.pvalues,
                "ci_low": fitted.conf_int()["lower"],
                "ci_high": fitted.conf_int()["upper"],
            }
        )
        table.to_csv(TABLE_DIR / f"panel_{outcome}.csv", index_label="term")

        results[outcome] = {
            "label": label,
            "n": int(fitted.nobs),
            "entities": int(frame.index.get_level_values(0).nunique()),
            "r_squared_within": float(fitted.rsquared_within),
            "terms": {
                term: {
                    "coefficient": float(table.loc[term, "coefficient"]),
                    "low": float(table.loc[term, "ci_low"]),
                    "high": float(table.loc[term, "ci_high"]),
                    "p": float(table.loc[term, "p_value"]),
                }
                for term in table.index
            },
            "significant": [
                term
                for term in table.index
                if table.loc[term, "ci_low"] > 0 or table.loc[term, "ci_high"] < 0
            ],
        }

    findings["panel_regression"] = results


def run_clustering(panel: pd.DataFrame, findings: dict) -> None:
    """Group authorities by the shape of their workforce trajectories.

    Each authority becomes one long row holding its agency rate, turnover and
    caseload in every year from 2017 to 2025. Each measure is standardised across
    authorities within its year, so a value describes where an authority stood
    relative to the rest of the country that year rather than the national level.

    K-means then splits authorities into groups whose trajectories look alike.
    The number of groups is chosen by the silhouette score, which measures how
    much closer an authority sits to its own group than to the nearest other
    group. A score near one means well separated groups and a score near zero
    means the groups barely differ.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    wide = panel.pivot_table(
        index="la_code", columns="year", values=CLUSTER_MEASURES, aggfunc="first"
    )
    # Standardise within each measure and year, then drop authorities with gaps
    # rather than filling them, because an invented trajectory would be clustered
    # as though it were observed.
    standardised = wide.apply(lambda column: (column - column.mean()) / column.std(ddof=0))
    standardised = standardised.dropna()

    scores = {}
    for k in range(2, 7):
        model = KMeans(n_clusters=k, n_init=25, random_state=0)
        labels = model.fit_predict(standardised)
        scores[k] = float(silhouette_score(standardised, labels))
    best_k = max(scores, key=scores.get)

    model = KMeans(n_clusters=best_k, n_init=25, random_state=0)
    assignment = pd.Series(
        model.fit_predict(standardised), index=standardised.index, name="cluster"
    )

    clustered = panel.merge(assignment, left_on="la_code", right_index=True, how="inner")
    profile = (
        clustered.groupby("cluster")[CLUSTER_MEASURES + ["imd_score", "rereferral_rate"]]
        .mean()
        .round(2)
    )
    counts = assignment.value_counts().sort_index()
    profile["authorities"] = counts

    # Name the cluster with the highest combined agency use and turnover, which
    # is the persistent instability group the project set out to find.
    instability = (
        profile["agency_rate"] / profile["agency_rate"].mean()
        + profile["turnover_rate"] / profile["turnover_rate"].mean()
    )
    unstable = int(instability.idxmax())
    profile.to_csv(TABLE_DIR / "cluster_profile.csv", index_label="cluster")

    members = (
        clustered[clustered["year"] == LAST_YEAR][["la_code", "la_name", "region", "cluster"]]
        .drop_duplicates("la_code")
        .sort_values(["cluster", "la_name"])
    )
    members.to_csv(TABLE_DIR / "cluster_membership.csv", index=False)

    boundaries = loaders.load_boundaries()
    names = {
        cluster: (
            "Persistent instability" if cluster == unstable else f"Group {cluster + 1}"
        )
        for cluster in sorted(assignment.unique())
    }
    geo = boundaries.merge(
        assignment.rename("cluster").reset_index(), on="la_code", how="inner"
    )
    geo["group"] = np.where(geo["cluster"] == unstable, "unstable", "rest")

    plots.choropleth(
        geo,
        column="group",
        title=(
            f"The {counts[unstable]} councils with persistently unstable workforces "
            f"are spread across England"
        ),
        subtitle=(
            f"Cluster membership from agency use, turnover and caseload across "
            f"{FIRST_YEAR} to {LAST_YEAR}."
        ),
        legend_label="",
        source=SOURCE_NOTE,
        path=CHART_DIR / "map_workforce_clusters.png",
        categories={
            "unstable": "Persistent instability",
            "rest": "Every other council",
        },
    )

    unstable_trajectory = (
        clustered.groupby(["cluster", "year"], as_index=False)[CLUSTER_MEASURES].mean()
    )
    unstable_trajectory["cluster_name"] = unstable_trajectory["cluster"].map(names)
    palette = {
        name: (plots.OUTLIER_HIGH if name == "Persistent instability" else plots.MUTED)
        for name in names.values()
    }
    plots.trajectory_plot(
        unstable_trajectory,
        x="year",
        y="agency_rate",
        group="cluster_name",
        title=(
            "The unstable group has relied on agency staff more than the rest "
            "throughout the period"
        ),
        subtitle=f"Mean agency rate by cluster, {FIRST_YEAR} to {LAST_YEAR}.",
        y_label="Agency workers as a percentage of full time equivalent staff",
        x_label="Year",
        source=SOURCE_NOTE,
        path=CHART_DIR / "cluster_agency_trajectory.png",
        colours=palette,
    )

    findings["clusters"] = {
        "k": best_k,
        "silhouette": scores[best_k],
        "silhouette_by_k": scores,
        "authorities_clustered": int(len(standardised)),
        "unstable_cluster": unstable,
        "unstable_size": int(counts[unstable]),
        "unstable_agency": float(profile.loc[unstable, "agency_rate"]),
        "unstable_turnover": float(profile.loc[unstable, "turnover_rate"]),
        "unstable_caseload": float(profile.loc[unstable, "caseload"]),
        "unstable_imd": float(profile.loc[unstable, "imd_score"]),
        "unstable_rereferral": float(profile.loc[unstable, "rereferral_rate"]),
        "other_agency": float(profile.drop(index=unstable)["agency_rate"].mean()),
        "other_turnover": float(profile.drop(index=unstable)["turnover_rate"].mean()),
        "other_imd": float(profile.drop(index=unstable)["imd_score"].mean()),
        "other_rereferral": float(profile.drop(index=unstable)["rereferral_rate"].mean()),
        "unstable_names": sorted(
            members.loc[members["cluster"] == unstable, "la_name"].tolist()
        ),
    }


def main() -> int:
    """Run the whole project and render the README."""
    plots.apply_house_style()
    for folder in (CHART_DIR, TABLE_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    print("Building the panel ...")
    panel = build_panel()
    panel.to_csv(TABLE_DIR / "authority_year_panel.csv", index=False)

    findings: dict = {
        "first_year": FIRST_YEAR,
        "last_year": LAST_YEAR,
        "rows": int(len(panel)),
        "authorities": int(panel["la_code"].nunique()),
        "coverage": {
            measure: int(panel[measure].notna().sum()) for measure in WORKFORCE_MEASURES
        },
        "authorities_per_year": {
            str(year): int(part["la_code"].nunique())
            for year, part in panel.groupby("year")
        },
    }

    print("Drawing descriptive charts ...")
    draw_descriptives(panel, findings)

    print("Fitting the Cox model ...")
    run_cox(panel, findings)

    print("Fitting the panel regressions ...")
    run_panel_regression(panel, findings)

    print("Clustering trajectories ...")
    run_clustering(panel, findings)

    findings["sources"] = {
        key: {"downloaded": entry["downloaded"], "sha256": entry["sha256"][:12]}
        for key, entry in loaders.read_manifest().items()
    }

    (OUTPUT_DIR / "findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT_DIR / 'findings.json'}")

    print("Rendering the README ...")
    subprocess.run([sys.executable, str(PROJECT_DIR / "render_readme.py")], check=True)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
