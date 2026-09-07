"""Build every output for the adult social care variation project.

Run this file from inside its own folder:

    python make_all.py

It reads only from data/raw, writes every chart, table and number to outputs,
and finishes by rendering the README from outputs/findings.json. Nothing in this
script asks a question or waits for input, so it can run unattended.
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

SNAPSHOT = pd.Timestamp("2026-03-31")
YEAR_START = pd.Timestamp("2025-04-30")
YEAR_END = pd.Timestamp("2026-03-31")
PER = 100_000.0

SOURCE_NOTE = (
    "Source: DHSC adult social care client level data to March 2026; ONS mid-2024 "
    "population estimates; MHCLG indices of deprivation 2019; Skills for Care "
    "ASC-WDS 2024/25; DHSC ASCOF 2024/25. Open Government Licence v3.0."
)


def build_table() -> pd.DataFrame:
    """Assemble one row for each of the 153 upper tier local authorities.

    The row carries the count of adults receiving long-term support on the
    snapshot date, the count of assessments over the twelve months to that date,
    the population denominators, and the three explanatory measures used later.
    """
    lts = loaders.load_long_term_support()
    snapshot = lts[lts["period"] == SNAPSHOT][["la_code", "la_name", "lts_count"]]
    if snapshot.empty:
        raise ValueError(
            f"No long-term support figures were found for {SNAPSHOT.date()}. The "
            f"periods available are {sorted(lts['period'].unique())}."
        )

    assessments = loaders.load_assessments()
    window = assessments[
        (assessments["period"] >= YEAR_START) & (assessments["period"] <= YEAR_END)
    ]
    yearly = (
        window.groupby("la_code", as_index=False)["assess_count"]
        .sum(min_count=1)
        .rename(columns={"assess_count": "assess_count"})
    )

    table = (
        snapshot.merge(loaders.load_population(), on="la_code", how="left", suffixes=("", "_pop"))
        .merge(yearly, on="la_code", how="left")
        .merge(loaders.load_region_lookup(), on="la_code", how="left")
        .merge(loaders.load_imd(), on="la_code", how="left")
        .merge(loaders.load_workforce_vacancy(), on="la_code", how="left")
        .merge(loaders.load_ascof_1a(), on="la_code", how="left")
    )
    table = table.drop(columns=[c for c in table.columns if c.endswith("_pop")])

    table["lts_rate"] = table["lts_count"] / table["adults_18plus"] * PER
    table["assess_rate"] = table["assess_count"] / table["adults_18plus"] * PER
    return table.sort_values("la_name", ignore_index=True)


def draw_funnels(table: pd.DataFrame, findings: dict) -> None:
    """Draw the two funnel plots and record what falls outside the limits."""
    support = analysis.funnel_frame(
        table.set_index("la_code")["lts_count"],
        table.set_index("la_code")["adults_18plus"],
    )
    names = table.set_index("la_code")["la_name"]
    points = support["points"]
    outside = int(points["outside_95"].sum())
    unadjusted = int(points["outside_998_unadjusted"].sum())
    highest = points["rate"].idxmax()
    lowest = points["rate"].idxmin()

    plots.funnel_plot(
        support,
        names,
        title=(
            f"Councils vary about {support['phi']:.0f} times more than chance alone "
            f"would produce"
        ),
        subtitle=(
            f"Adults receiving long-term support on 31 March 2026, against the adult "
            f"population. {unadjusted} of {len(table)} councils fall outside the "
            f"unadjusted limits; {outside} remain outside once the limits are widened "
            f"for that extra variation."
        ),
        y_label="Adults receiving long-term support per 100,000 adults aged 18 and over",
        x_label="Population aged 18 and over (log scale)",
        source=SOURCE_NOTE,
        path=CHART_DIR / "funnel_long_term_support.png",
        flag_level="95",
    )

    assessment = analysis.funnel_frame(
        table.set_index("la_code")["assess_count"],
        table.set_index("la_code")["adults_18plus"],
    )
    plots.funnel_plot(
        assessment,
        names,
        title=(
            f"Assessment counts vary about {assessment['phi']:.0f} times more than "
            f"chance, far more than support counts do"
        ),
        subtitle=(
            "Assessments completed April 2025 to March 2026, against the adult "
            "population. A spread this wide points to differences in how councils "
            "record an assessment, not only to differences in what they do."
        ),
        y_label="Assessments per 100,000 adults aged 18 and over",
        x_label="Population aged 18 and over (log scale)",
        source=SOURCE_NOTE,
        path=CHART_DIR / "funnel_assessments.png",
        flag_level="95",
    )

    findings["funnel"] = {
        "support": {
            "target_rate": support["target_rate"],
            "phi": support["phi"],
            "outside_998": int(points["outside_998"].sum()),
            "outside_95": outside,
            "outside_unadjusted": unadjusted,
            "n": int(len(points)),
            "highest_name": names[highest],
            "highest_rate": float(points.loc[highest, "rate"]),
            "lowest_name": names[lowest],
            "lowest_rate": float(points.loc[lowest, "rate"]),
        },
        "assessments": {
            "target_rate": assessment["target_rate"],
            "phi": assessment["phi"],
            "outside_95": int(assessment["points"]["outside_95"].sum()),
            "outside_998": int(assessment["points"]["outside_998"].sum()),
            "outside_unadjusted": int(
                assessment["points"]["outside_998_unadjusted"].sum()
            ),
            "n": int(len(assessment["points"])),
        },
    }

    named = points.nlargest(6, "distance_outside_95")
    named = named[named["distance_outside_95"] > 0]
    named.assign(la_name=names.reindex(named.index)).to_csv(
        TABLE_DIR / "funnel_outliers.csv", index_label="la_code"
    )


def run_inequality(table: pd.DataFrame, findings: dict) -> None:
    """Fit the slope and relative index of inequality and record the result."""
    index = analysis.slope_index_of_inequality(
        table["lts_rate"], table["imd_score"], table["adults_18plus"]
    )
    findings["inequality"] = {
        "sii": index.sii,
        "sii_low": index.sii_low,
        "sii_high": index.sii_high,
        "rii": index.rii,
        "rii_low": index.rii_low,
        "rii_high": index.rii_high,
        "mean_rate": index.mean_rate,
        "significant": bool(index.sii_low > 0 or index.sii_high < 0),
    }


COVARIATE_LABELS = {
    "share_65plus": "Share of adults aged 65 and over",
    "imd_score": "Deprivation score",
    "vacancy_rate": "Care workforce vacancy rate",
}


def run_model(table: pd.DataFrame, findings: dict) -> pd.DataFrame:
    """Fit the negative binomial model, draw the forest plot, rank the residuals."""
    covariates = table.set_index("la_code")[list(COVARIATE_LABELS)]
    model = analysis.negative_binomial_rate_model(
        counts=table.set_index("la_code")["lts_count"],
        exposure=table.set_index("la_code")["adults_18plus"],
        covariates=covariates,
        fixed_effects=table.set_index("la_code")["region"],
    )

    covariate_rows = model.irr.loc[list(COVARIATE_LABELS)].rename(index=COVARIATE_LABELS)
    plots.forest_plot(
        covariate_rows,
        title="Deprivation and age structure move the support rate; vacancies do not",
        subtitle=(
            "Incidence rate ratios per one standard deviation, from a negative "
            "binomial model with a population offset and region fixed effects."
        ),
        x_label="Incidence rate ratio per one standard deviation (1.0 means no effect)",
        source=SOURCE_NOTE,
        path=CHART_DIR / "forest_incidence_rate_ratios.png",
    )
    model.irr.to_csv(TABLE_DIR / "negative_binomial_irr.csv", index_label="term")

    ratios = model.observed_expected.rename("observed_expected")
    table = table.merge(ratios, left_on="la_code", right_index=True, how="left")

    ranked = table[["la_code", "la_name", "region", "lts_rate", "observed_expected"]].dropna(
        subset=["observed_expected"]
    )
    ranked = ranked.sort_values("observed_expected", ascending=False)
    ranked.to_csv(TABLE_DIR / "observed_expected_ranked.csv", index=False)

    top = ranked.head(10)
    bottom = ranked.tail(10).sort_values("observed_expected")
    plots.ranked_bar(
        pd.concat([bottom, top]),
        value="observed_expected",
        label="la_name",
        title="Ten councils support far more adults than their population predicts, ten far fewer",
        subtitle=(
            "Observed divided by expected support, after age structure, deprivation, "
            "vacancy rate and region are accounted for. A value of 1.0 is as expected."
        ),
        x_label="Observed support divided by expected support",
        source=SOURCE_NOTE,
        path=CHART_DIR / "observed_expected_extremes.png",
        reference=1.0,
    )

    findings["model"] = {
        "alpha": model.alpha,
        "deviance_explained": model.deviance_explained,
        "n": int(model.result.nobs),
        "irr": {
            label: {
                "irr": float(covariate_rows.loc[label, "irr"]),
                "low": float(covariate_rows.loc[label, "irr_low"]),
                "high": float(covariate_rows.loc[label, "irr_high"]),
                "p": float(covariate_rows.loc[label, "p_value"]),
            }
            for label in covariate_rows.index
        },
        "oe_min": float(ranked["observed_expected"].min()),
        "oe_max": float(ranked["observed_expected"].max()),
        "oe_top_name": ranked.iloc[0]["la_name"],
        "oe_top_value": float(ranked.iloc[0]["observed_expected"]),
        "oe_bottom_name": ranked.iloc[-1]["la_name"],
        "oe_bottom_value": float(ranked.iloc[-1]["observed_expected"]),
        "oe_above_1_2": int((ranked["observed_expected"] > 1.2).sum()),
        "oe_below_0_8": int((ranked["observed_expected"] < 0.8).sum()),
    }
    return table


def draw_maps(table: pd.DataFrame) -> None:
    """Draw the raw rate map and the observed to expected map."""
    boundaries = loaders.load_boundaries()
    geo = boundaries.merge(table, on="la_code", how="inner", suffixes=("", "_table"))
    geo = geo[geo["la_code"].str.startswith("E")]

    plots.choropleth(
        geo,
        column="lts_rate",
        title="Long-term support rates are highest in the north east and parts of London",
        subtitle="Adults receiving long-term support on 31 March 2026, per 100,000 adults.",
        legend_label="Adults supported per 100,000 adults aged 18 and over",
        source=SOURCE_NOTE,
        path=CHART_DIR / "map_support_rate.png",
    )
    plots.choropleth(
        geo,
        column="observed_expected",
        title="Once population and deprivation are accounted for, the pattern breaks up",
        subtitle=(
            "Observed divided by expected support. Blue is more support than "
            "predicted, amber is less."
        ),
        legend_label="Observed support divided by expected support",
        source=SOURCE_NOTE,
        path=CHART_DIR / "map_observed_expected.png",
        diverging_at=1.0,
    )


def run_panel(table: pd.DataFrame, findings: dict) -> None:
    """Ask which authorities stay outside the funnel limits month after month.

    The client level data releases overlap, so stitching them together gives a
    run of monthly snapshots. A funnel plot is fitted for each month separately,
    and an authority is called persistent when it sits outside the 95 per cent
    limits in at least four fifths of the months it appears in.

    The inner limits are used rather than the outer ones because the
    overdispersion adjustment widens the outer limits so far that they catch
    almost no council in any month, which would make every council look settled
    whatever it did.
    """
    panel = loaders.load_cld_panel()
    population = table.set_index("la_code")["adults_18plus"]
    names = table.set_index("la_code")["la_name"]

    records = []
    for period, month in panel.groupby("period"):
        month = month.set_index("la_code")
        counts = month["lts_count"].reindex(population.index)
        funnel = analysis.funnel_frame(counts, population)
        flags = funnel["points"]["outside_95"]
        for code, outside in flags.items():
            records.append({"la_code": code, "period": period, "outside": bool(outside)})

    monthly = pd.DataFrame(records)
    summary = (
        monthly.groupby("la_code")
        .agg(months=("outside", "size"), months_outside=("outside", "sum"))
        .reset_index()
    )
    summary["share_outside"] = summary["months_outside"] / summary["months"]
    summary["la_name"] = summary["la_code"].map(names)
    summary["status"] = np.where(
        summary["share_outside"] >= 0.8,
        "persistent",
        np.where(summary["share_outside"] > 0, "transient", "never outside"),
    )
    summary.sort_values("share_outside", ascending=False).to_csv(
        TABLE_DIR / "panel_persistence.csv", index=False
    )

    periods = sorted(panel["period"].unique())
    findings["panel"] = {
        "months": len(periods),
        "first_month": pd.Timestamp(periods[0]).strftime("%B %Y"),
        "last_month": pd.Timestamp(periods[-1]).strftime("%B %Y"),
        "persistent": int((summary["status"] == "persistent").sum()),
        "transient": int((summary["status"] == "transient").sum()),
        "never": int((summary["status"] == "never outside").sum()),
        "persistent_names": sorted(
            summary.loc[summary["status"] == "persistent", "la_name"].dropna().tolist()
        ),
    }

    persistent = summary[summary["status"] != "never outside"].nlargest(20, "share_outside")
    plots.ranked_bar(
        persistent,
        value="share_outside",
        label="la_name",
        title=(
            f"{findings['panel']['persistent']} councils sit outside the limits in "
            f"almost every month, not just one"
        ),
        subtitle=(
            f"Share of the {len(periods)} monthly snapshots from "
            f"{findings['panel']['first_month']} to {findings['panel']['last_month']} "
            f"in which the council was outside the overdispersion adjusted 95 per "
            f"cent limits."
        ),
        x_label="Share of months outside the 95 per cent limits",
        source=SOURCE_NOTE,
        path=CHART_DIR / "panel_persistence.png",
        reference=0.8,
    )


def main() -> int:
    """Run the whole project and render the README."""
    plots.apply_house_style()
    for folder in (CHART_DIR, TABLE_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    print("Building the authority table ...")
    table = build_table()
    table.to_csv(TABLE_DIR / "authority_table.csv", index=False)

    findings: dict = {
        "authorities": int(len(table)),
        "snapshot": SNAPSHOT.strftime("%d %B %Y"),
        "assessment_window": "April 2025 to March 2026",
        "coverage": {
            "vacancy_missing": int(table["vacancy_rate"].isna().sum()),
            "vacancy_missing_names": sorted(
                table.loc[table["vacancy_rate"].isna(), "la_name"].tolist()
            ),
            "ascof_missing": int(table["ascof_1a"].isna().sum()),
        },
        "rate_summary": analysis.summarise_series(table["lts_rate"]),
        "assess_summary": analysis.summarise_series(table["assess_rate"]),
    }

    print("Drawing funnel plots ...")
    draw_funnels(table, findings)

    print("Fitting the slope index of inequality ...")
    run_inequality(table, findings)

    print("Fitting the negative binomial model ...")
    table = run_model(table, findings)
    table.to_csv(TABLE_DIR / "authority_table.csv", index=False)

    print("Drawing maps ...")
    draw_maps(table)

    print("Running the monthly panel ...")
    run_panel(table, findings)

    findings["sources"] = {
        key: {"downloaded": entry["downloaded"], "sha256": entry["sha256"][:12]}
        for key, entry in loaders.read_manifest().items()
    }

    (OUTPUT_DIR / "findings.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT_DIR / 'findings.json'}")

    print("Rendering the README ...")
    subprocess.run([sys.executable, str(PROJECT_DIR / "render_readme.py")], check=True)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
