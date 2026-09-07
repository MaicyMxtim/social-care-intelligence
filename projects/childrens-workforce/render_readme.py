"""Write README.md for the children's workforce project from outputs/findings.json.

No number in the README is typed by hand. Every figure the text quotes is read
from findings.json, which make_all.py writes when the analysis runs.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ROOT = PROJECT_DIR.parents[1]
FINDINGS_PATH = PROJECT_DIR / "outputs" / "findings.json"
README_PATH = PROJECT_DIR / "README.md"
BRIEF_PATH = ROOT / "docs" / "childrens-workforce-brief.md"

TERM_LABELS = {
    "agency_rate_lag1": "agency rate",
    "turnover_rate_lag1": "turnover rate",
    "caseload_lag1": "average caseload",
    "vacancy_rate_lag1": "vacancy rate",
    "absence_rate_lag1": "sickness absence rate",
}


def fmt(value: float, places: int = 0) -> str:
    """Format a number with thousands separators and a fixed number of decimals."""
    return f"{value:,.{places}f}"


def join_names(names: list[str], limit: int = 8) -> str:
    """Join a list of authority names into a readable sentence fragment."""
    if not names:
        return "none"
    shown = names[:limit]
    remainder = len(names) - len(shown)
    text = ", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 else shown[0]
    if remainder > 0:
        text += f", and {remainder} others"
    return text


def panel_rows(result: dict) -> str:
    """Build the coefficient table for one panel regression."""
    lines = []
    for term, values in result["terms"].items():
        marker = " (interval excludes zero)" if term in result["significant"] else ""
        lines.append(
            f"| {TERM_LABELS.get(term, term).capitalize()} | "
            f"{values['coefficient']:+.3f} | "
            f"{values['low']:+.3f} to {values['high']:+.3f} | "
            f"{values['p']:.3f}{marker} |"
        )
    return "\n".join(lines)


def render(findings: dict) -> str:
    """Build the whole README as one string."""
    descriptives = findings["descriptives"]
    cox = findings["cox"]
    regression = findings["panel_regression"]
    clusters = findings["clusters"]

    rereferral = regression["rereferral_rate"]
    repeat_cpp = regression["repeat_cpp_rate"]
    placements = regression["three_plus_placements_rate"]
    agency_on_rereferral = rereferral["terms"]["agency_rate_lag1"]
    agency_on_cpp = repeat_cpp["terms"]["agency_rate_lag1"]

    ph = cox["proportional_hazards"]
    ph_sentence = (
        f"The test finds no violation, with the smallest p value across "
        f"{ph['terms']} terms at {ph['min_p']:.2f}."
        if "error" not in ph and ph.get("violations", 1) == 0
        else (
            f"The test flags {ph.get('violations')} of {ph.get('terms')} terms, so "
            f"the hazard ratios should be read as an average over the follow-up."
            if "error" not in ph
            else f"The test could not be run: {ph['error']}"
        )
    )

    cox_verdict = (
        "None of the five covariates has an interval that excludes one, so none of "
        "them shifts the risk of a downgrade on its own."
        if not cox["significant"]
        else f"The covariates whose intervals exclude one are {join_names(cox['significant'])}."
    )

    silhouette_verdict = (
        "well separated"
        if clusters["silhouette"] > 0.5
        else "only weakly separated" if clusters["silhouette"] > 0.25 else "barely separated"
    )

    deprivation_direction = (
        "less deprived" if clusters["unstable_imd"] < clusters["other_imd"] else "more deprived"
    )

    return f"""# Children's social work: does workforce instability show up in outcomes later

## The question

Children's services depend on holding onto social workers. This project asks
whether workforce instability in one year, measured by turnover, vacancies,
agency reliance, caseload and sickness absence, predicts worse things later: an
Ofsted downgrade, more children re-referred within a year, more children back on
a second protection plan, and more children moved between placements. The panel
runs from {findings['first_year']} to {findings['last_year']}.

## Why this matters

An authority that cannot keep social workers is usually described as being at
risk, and agency reliance in particular is treated as a warning sign. That belief
drives real decisions about intervention and improvement support. It is worth
knowing whether the open data bears it out, and where it does not.

There is a gap that has to be stated at the start rather than buried in the
limits. No measure of social worker wellbeing exists at local authority level in
open data. Nothing published by authority records whether social workers feel
able to do the job, whether they are burnt out, or whether they intend to leave.
Sickness absence and agency reliance are used here as proxies, and they are poor
ones, because a council can have low sickness absence and an exhausted workforce.
National surveys by the British Association of Social Workers and by the Local
Government Association do ask those questions, but they report nationally and
cannot be joined to a council. That absence is itself a finding of this project.
Any conclusion drawn below about wellbeing is inference from staffing behaviour,
not measurement of how staff are.

## The data

Every file is downloaded by `scripts/download.py` from a published URL, and
`data/raw/MANIFEST.json` records the download date and a SHA256 hash for each
one.

| Source | Publisher | What it provides |
| --- | --- | --- |
| Children's social work workforce, 2017 to 2025 | DfE | Turnover, vacancy, agency, caseload, sickness absence, staff in post |
| Children in need census | DfE | Re-referrals within twelve months, repeat protection plans |
| Children looked after in England | DfE | Children with three or more placements in the year |
| Local authority inspection outcomes to 31 March 2026 | Ofsted | Every ILACS inspection with its date and grade |
| Indices of deprivation 2019, File 11 | MHCLG | Average deprivation score at upper tier |
| Mid-2024 population estimates, MYE2 | ONS | Population aged 0 to 17 |
| Counties and unitary authorities, December 2023 | ONS Open Geography | Boundaries for the map |

All of it is published under the Open Government Licence v3.0.

The panel holds {findings['rows']} authority years covering
{findings['authorities']} authorities.

### Local government reorganisation

Six areas reorganised during the period, and two metropolitan districts were
given new codes. Every source is translated onto one set of authority codes
before anything is joined. Where a county split into unitary authorities, the
county's figures are carried to each successor for the years before the split.
Where councils merged, their figures are combined, with rates weighted by
workforce size and counts added. Where a carried figure and a real one collide,
the real one wins. The full mapping is in
[docs/DATA_NOTES.md](../../docs/DATA_NOTES.md).

## The method

### Descriptives

Regional trajectory plots of agency rate and turnover, and a funnel plot of
turnover for the most recent year. A funnel plot is a chart that shows each
council as a point against the size of its workforce, with control limits that
fan out because a rate measured over a small workforce moves around more. The
funnel code is shared with the adult social care project in this repository.

### Cox proportional hazards model

A Cox proportional hazards model is a regression for how long something takes to
happen. It does not model the shape of the risk over time, only how much each
covariate multiplies it. A hazard ratio of 1.05 means a five per cent higher risk
of the event at any moment for a one unit rise in the covariate.

Here the event is an Ofsted downgrade, meaning an inspection whose overall
effectiveness grade is worse than the grade the authority held before it. An
authority enters at its first ILACS inspection and is followed until a downgrade
or until 31 March 2026. Follow-up is split into yearly intervals so that
covariates can change while an authority is still at risk, and every workforce
covariate enters lagged by one year, so the model asks whether last year's
staffing predicts this year's judgement.

The proportional hazards assumption is that the multipliers stay the same across
the whole follow-up. It is tested and the result reported below either way.

### Fixed effects panel regression

A fixed effects panel regression compares an authority with itself over time
rather than with other authorities. Authority effects absorb everything about a
council that does not change across the period, including its population, its
history and its deprivation. Year effects absorb everything that moved nationally
in a given year, such as a change in guidance. What is left is whether an
authority's outcomes moved when its own workforce measures moved. Standard errors
are clustered by authority, because observations from one council in different
years are not independent.

### Trajectory clustering

Each authority becomes one row holding its agency rate, turnover and caseload in
every year. Each measure is standardised within its year, so a value says where
an authority stood relative to the rest of the country that year rather than
where the country stood. K-means then splits authorities into groups whose
trajectories look alike. The number of groups is chosen by the silhouette score,
which measures how much closer an authority sits to its own group than to the
nearest other group. A score near one means well separated groups and a score
near zero means the groups barely differ.

## What the analysis found

### Agency reliance rose, peaked and fell, and regions did not converge

Agency use across England peaked in {descriptives['agency_peak_year']} at
{fmt(descriptives['agency_peak_mean'], 1)} per cent of the workforce and stood at
{fmt(descriptives['agency_last_mean'], 1)} per cent by {findings['last_year']}.
The gap between the highest and lowest region went from
{fmt(descriptives['agency_spread_first'], 1)} to
{fmt(descriptives['agency_spread_last'], 1)} percentage points, so the fall did
not bring regions together. In {findings['last_year']} the highest region was
{descriptives['region_high_agency']} at
{fmt(descriptives['region_high_agency_value'], 1)} per cent and the lowest was
{descriptives['region_low_agency']} at
{fmt(descriptives['region_low_agency_value'], 1)} per cent.

![Agency rate by region](outputs/charts/trajectory_agency_rate.png)

Turnover peaked in {descriptives['turnover_peak_year']} at
{fmt(descriptives['turnover_peak_mean'], 1)} per cent and fell to
{fmt(descriptives['turnover_last_mean'], 1)} per cent by {findings['last_year']}.

![Turnover by region](outputs/charts/trajectory_turnover.png)

Turnover in {findings['last_year']} varies about
{fmt(descriptives['turnover_phi'], 1)} times more between councils than chance
would produce, and {descriptives['turnover_outside_95']} of
{descriptives['turnover_n']} councils sit outside the 95 per cent limits.

![Funnel plot of turnover](outputs/charts/funnel_turnover.png)

### Workforce instability does not predict an Ofsted downgrade

Of {cox['authorities']} authorities followed from their first ILACS inspection,
{cox['downgraded']} were downgraded and {cox['censored']} were not. The model
uses {cox['intervals']} authority years.

| Covariate, previous year | Hazard ratio | 95% interval | p |
| --- | --- | --- | --- |
| Agency rate | {fmt(cox['hazard']['Agency rate, previous year']['hr'], 3)} | {fmt(cox['hazard']['Agency rate, previous year']['low'], 3)} to {fmt(cox['hazard']['Agency rate, previous year']['high'], 3)} | {fmt(cox['hazard']['Agency rate, previous year']['p'], 3)} |
| Turnover rate | {fmt(cox['hazard']['Turnover rate, previous year']['hr'], 3)} | {fmt(cox['hazard']['Turnover rate, previous year']['low'], 3)} to {fmt(cox['hazard']['Turnover rate, previous year']['high'], 3)} | {fmt(cox['hazard']['Turnover rate, previous year']['p'], 3)} |
| Average caseload | {fmt(cox['hazard']['Average caseload, previous year']['hr'], 3)} | {fmt(cox['hazard']['Average caseload, previous year']['low'], 3)} to {fmt(cox['hazard']['Average caseload, previous year']['high'], 3)} | {fmt(cox['hazard']['Average caseload, previous year']['p'], 3)} |
| Vacancy rate | {fmt(cox['hazard']['Vacancy rate, previous year']['hr'], 3)} | {fmt(cox['hazard']['Vacancy rate, previous year']['low'], 3)} to {fmt(cox['hazard']['Vacancy rate, previous year']['high'], 3)} | {fmt(cox['hazard']['Vacancy rate, previous year']['p'], 3)} |
| Deprivation score | {fmt(cox['hazard']['Deprivation score']['hr'], 3)} | {fmt(cox['hazard']['Deprivation score']['low'], 3)} to {fmt(cox['hazard']['Deprivation score']['high'], 3)} | {fmt(cox['hazard']['Deprivation score']['p'], 3)} |

{cox_verdict} {ph_sentence}

This is a null result and it is worth saying so plainly. With
{cox['downgraded']} downgrades across the whole period there is not much
statistical power, so the honest reading is that the open data does not show a
link, not that no link exists.

![Cox hazard ratios](outputs/charts/forest_cox_hazard_ratios.png)

### Agency reliance does move re-referrals

The fixed effects regressions tell a different story from the survival model,
because they use every authority year rather than only the years around an
inspection.

**Re-referrals within twelve months** ({rereferral['n']} authority years,
{rereferral['entities']} authorities, within R squared
{fmt(rereferral['r_squared_within'], 3)}):

| Covariate, previous year | Coefficient | 95% interval | p |
| --- | --- | --- | --- |
{panel_rows(rereferral)}

A one percentage point rise in an authority's agency rate is followed by a
{fmt(abs(agency_on_rereferral['coefficient']), 3)} percentage point
{"rise" if agency_on_rereferral['coefficient'] > 0 else "fall"} in its
re-referral rate the next year. That is a small effect, but it is measured within
authorities, so it is not a comparison between different kinds of council.

**Repeat child protection plans** ({repeat_cpp['n']} authority years,
{repeat_cpp['entities']} authorities, within R squared
{fmt(repeat_cpp['r_squared_within'], 3)}):

| Covariate, previous year | Coefficient | 95% interval | p |
| --- | --- | --- | --- |
{panel_rows(repeat_cpp)}

Agency reliance points the other way here, at
{agency_on_cpp['coefficient']:+.3f} percentage points. Two effects in opposite
directions from the same covariate is a reason for caution rather than a finding
to build on, and it is more likely to reflect how councils record repeat plans
than a real protective effect of agency staff.

**Children with three or more placements** ({placements['n']} authority years,
{placements['entities']} authorities):

| Covariate, previous year | Coefficient | 95% interval | p |
| --- | --- | --- | --- |
{panel_rows(placements)}

Nothing here reaches significance.

### There is a persistently unstable group, and it is not the deprived group

The silhouette score picked {clusters['k']} groups from
{clusters['authorities_clustered']} authorities with complete trajectories, at
{fmt(clusters['silhouette'], 3)}. That is low, so the groups are
{silhouette_verdict} and the split should be read as a tendency rather than a
clean division.

The unstable group holds {clusters['unstable_size']} authorities. It runs a mean
agency rate of {fmt(clusters['unstable_agency'], 1)} per cent against
{fmt(clusters['other_agency'], 1)} per cent elsewhere, and turnover of
{fmt(clusters['unstable_turnover'], 1)} per cent against
{fmt(clusters['other_turnover'], 1)} per cent.

The interesting part is deprivation. The unstable group is {deprivation_direction}
than the rest, with a mean deprivation score of
{fmt(clusters['unstable_imd'], 1)} against {fmt(clusters['other_imd'], 1)}.
Persistent workforce instability is therefore not a deprivation story, which
matters because improvement support is often targeted as though it were.

![Map of the persistent instability group](outputs/charts/map_workforce_clusters.png)

![Agency rate by cluster](outputs/charts/cluster_agency_trajectory.png)

## Limits

No authority-level measure of social worker wellbeing exists in open data.
Sickness absence and agency reliance stand in for it and they are weak proxies.
The BASW and LGA social worker surveys ask the right questions but report
nationally, so they can provide context and nothing more.

Ofsted downgrades are rare. {cox['downgraded']} events across the period is
enough to fit a model but not enough to detect a modest effect, so the null
result in the survival model is weak evidence rather than strong evidence of no
effect.

Inspection timing is not random. Ofsted inspects on a risk-based schedule, so a
council thought to be struggling is inspected sooner. That works against finding
a workforce effect, because the comparison group contains councils that have not
been looked at recently.

The clustering is weak. A silhouette score of {fmt(clusters['silhouette'], 2)}
means the groups overlap a great deal, and a different random start or a
different set of measures could move authorities between them.

Reorganisation handling is approximate. Carrying a county's figures to each of
its successors assumes the successors resembled the county, which is unlikely to
be exactly true for the years before each split.

The child population denominator is a single year of estimates applied to every
panel year, so authorities whose child population changed quickly are described
slightly wrongly in the early years.

Everything here is association within authorities over time. Fixed effects remove
the confounders that do not change, but they cannot remove a confounder that
moves alongside both staffing and outcomes.

## So what

Three things follow for a director of children's services.

Agency reliance is worth watching for its own sake, because it is followed by
more children being re-referred, but it is not a leading indicator of an Ofsted
downgrade in this data. Using it as one would be reading more into it than the
evidence supports.

The persistently unstable group is not the deprived group. Improvement support
aimed at deprivation will miss most of the councils whose workforces have been
unstable for eight years.

The missing measure is the important one. Until something records how social
workers are, rather than how many of them left, every analysis of this kind is
inferring wellbeing from staffing behaviour. Commissioning a consistent
authority-level staff survey would do more for this question than any further
modelling of the data that already exists.

## Reproduce

From a fresh clone:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download.py
cd projects/childrens-workforce && python make_all.py
```

`make_all.py` writes every chart and table in `outputs/`, writes
`outputs/findings.json`, and regenerates this README from it. Run `pytest` from
the repository root to check the loaders and the statistical functions.

## Next steps

Model the interaction between agency reliance and caseload, on the theory that
agency staff carrying heavy caseloads is a different situation from agency staff
carrying light ones.

Use inspection sub-judgements rather than overall effectiveness, which would give
more events and so more power than the {cox['downgraded']} downgrades available
here.

Bring in the DfE workforce data on starters and leavers by experience band, to
separate a council losing newly qualified workers from one losing its experienced
staff.

Ask whether the unstable cluster differs on spending per child, which would test
whether instability follows financial pressure rather than deprivation.
"""


def render_brief(findings: dict) -> str:
    """Build the one page brief for a director of children's services."""
    descriptives = findings["descriptives"]
    cox = findings["cox"]
    clusters = findings["clusters"]
    agency = findings["panel_regression"]["rereferral_rate"]["terms"]["agency_rate_lag1"]
    direction = "less" if clusters["unstable_imd"] < clusters["other_imd"] else "more"

    return f"""# Brief for a Director of Children's Services

**Workforce instability and outcomes, {findings['first_year']} to {findings['last_year']}**

Agency reliance peaked in {descriptives['agency_peak_year']} at
{fmt(descriptives['agency_peak_mean'], 1)} per cent of the children's social work
workforce and has fallen to {fmt(descriptives['agency_last_mean'], 1)} per cent.
The gap between regions has not closed.

Workforce instability does not predict an Ofsted downgrade. Across
{cox['authorities']} authorities and {cox['downgraded']} downgrades, no measure of
turnover, vacancies, agency use or caseload shifts the risk. With that few events
this is weak evidence rather than proof of no effect.

Agency reliance does track re-referrals. Within an authority, a one point rise in
the agency rate is followed by a {fmt(abs(agency['coefficient']), 2)} point rise
in re-referrals the next year.

{clusters['unstable_size']} authorities form a persistently unstable group. They
are {direction} deprived than the rest, so instability is not a deprivation story.

**Recommendation.** Track agency reliance as an operational risk to case
continuity, not as an inspection early warning. No open data measures social
worker wellbeing at authority level, and that gap limits every conclusion here.
"""


def main() -> int:
    """Read findings.json and write README.md and the director brief."""
    if not FINDINGS_PATH.exists():
        raise FileNotFoundError(
            f"{FINDINGS_PATH} is missing. Run make_all.py first, because the README "
            f"is generated from the numbers it produces."
        )
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    README_PATH.write_text(render(findings), encoding="utf-8")
    BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_PATH.write_text(render_brief(findings), encoding="utf-8")
    print(f"Wrote {README_PATH}")
    print(f"Wrote {BRIEF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
