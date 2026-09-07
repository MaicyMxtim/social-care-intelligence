"""Write the portfolio index README from both projects' findings.json files.

The top level README quotes headline numbers from each project. Like the project
READMEs, none of those numbers is typed by hand. Run this after both projects
have run, or run scripts/make_all.py which does everything in order.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADULT = ROOT / "projects" / "adult-variation" / "outputs" / "findings.json"
CHILDREN = ROOT / "projects" / "childrens-workforce" / "outputs" / "findings.json"
README_PATH = ROOT / "README.md"


def fmt(value: float, places: int = 0) -> str:
    """Format a number with thousands separators and a fixed number of decimals."""
    return f"{value:,.{places}f}"


def render(adult: dict, children: dict) -> str:
    """Build the portfolio index as one string."""
    rates = adult["rate_summary"]
    funnel = adult["funnel"]["support"]
    model = adult["model"]
    panel = adult["panel"]
    inequality = adult["inequality"]

    descriptives = children["descriptives"]
    cox = children["cox"]
    clusters = children["clusters"]
    agency = children["panel_regression"]["rereferral_rate"]["terms"]["agency_rate_lag1"]

    manifest_count = len(adult.get("sources", {}))
    # The direction of the deprivation contrast is read from the data rather than
    # written in, so the sentence cannot end up saying the opposite of the table.
    unstable_direction = (
        "less deprived" if clusters["unstable_imd"] < clusters["other_imd"] else "more deprived"
    )
    vacancy = adult["model"]["irr"]["Care workforce vacancy rate"]
    vacancy_verdict = (
        "adds nothing once the others are in"
        if vacancy["low"] <= 1.0 <= vacancy["high"]
        else f"still moves the rate, at {vacancy['irr']:.2f} times per standard deviation"
    )

    return f"""# Social care intelligence

Two reproducible analyses of English social care, built only from open data.
Each one runs end to end from a single command and writes its own README from
the numbers it produced.

Both projects measure how far local authorities differ from one another, and how
much of that difference remains once the standard explanations are accounted
for.

---

## Project 1: adult social care variation

**How much do local authority long-term adult social care support rates vary once
age structure, deprivation and care workforce supply are accounted for, and which
authorities remain outliers?**

Across {adult['authorities']} councils the long-term support rate runs from
{fmt(rates['min'])} to {fmt(rates['max'])} adults per 100,000, a
{fmt(rates['ratio_max_min'], 1)}-fold gap, and councils vary about
{fmt(funnel['phi'], 0)} times more than chance alone would produce. A negative
binomial model with age structure, deprivation and region explains
{fmt(model['deviance_explained'] * 100, 0)} per cent of that, the care workforce
vacancy rate {vacancy_verdict}, and
{panel['persistent']} councils sit outside the limits in almost every one of
{panel['months']} monthly snapshots rather than occasionally.

[![Funnel plot of long-term support rates](projects/adult-variation/outputs/charts/funnel_long_term_support.png)](projects/adult-variation/README.md)

[Read the full project](projects/adult-variation/README.md) ·
[One page brief for a Director of Adult Social Services](docs/adult-variation-brief.md)

---

## Project 2: children's social work workforce

**Does children's social work workforce instability predict later Ofsted
downgrades and worse child outcomes, 2017 to 2025?**

Across {children['authorities']} councils and {cox['downgraded']} Ofsted
downgrades, no measure of turnover, vacancies, agency use or caseload shifts the
risk of a downgrade, though with that few events this is weak evidence rather
than proof of no effect. Agency reliance does track re-referrals within
authorities over time, at {fmt(abs(agency['coefficient']), 2)} percentage points
per point of agency rate. {clusters['unstable_size']} councils form a
persistently unstable group, and they are {unstable_direction} than the rest, so
instability is not a deprivation story.

[![Agency rate by region](projects/childrens-workforce/outputs/charts/trajectory_agency_rate.png)](projects/childrens-workforce/README.md)

[Read the full project](projects/childrens-workforce/README.md) ·
[One page brief for a Director of Children's Services](docs/childrens-workforce-brief.md)

---

## Repository layout

```
scripts/download.py          every dataset, from documented URLs, with a hash manifest
scripts/make_all.py          runs both projects and rebuilds this page
src/loaders.py               one loader per source, returning tidy tables
src/geography.py             local government reorganisation code mapping
src/analysis.py              funnel limits, inequality indices, negative binomial models
src/plots.py                 chart styling and the chart types both projects use
projects/adult-variation/    project 1
projects/childrens-workforce/ project 2
tests/                       loader contracts and statistical behaviour
docs/DATA_NOTES.md           every decision made about a source file
```

## Conventions

Every dataset is downloaded by `scripts/download.py` from a published URL. Raw
files are never edited by hand. `data/raw/MANIFEST.json` records the download
date, size and SHA256 hash of all {manifest_count} source files, and a monthly
GitHub Actions job re-downloads them and opens an issue when a publisher reissues
one under correction.

Every project runs end to end from `python make_all.py` inside its own folder. If
it does not run clean from a fresh clone, it is not done.

Every number in every README is generated from that project's
`outputs/findings.json` by its `render_readme.py`. None is typed by hand, so the
prose cannot drift away from the analysis.

Chart titles state the finding rather than naming the variable, and axis labels
carry their units.

Where a published file did not match what a loader expected, the loader was
fixed and the change written down in [docs/DATA_NOTES.md](docs/DATA_NOTES.md).
Nothing is silenced with a bare `try` and `except`.

## Data sources

All open, all published under the Open Government Licence v3.0 except the Skills
for Care estimates, which are free to reuse with attribution.

| Source | Publisher |
| --- | --- |
| Adult social care client level data, long-term support and assessments | Department of Health and Social Care |
| Measures from the Adult Social Care Outcomes Framework 2024/25 | Department of Health and Social Care |
| ASC-WDS local authority area workforce estimates 2024/25 | Skills for Care |
| Children's social work workforce statistics 2017 to 2025 | Department for Education |
| Children in need census | Department for Education |
| Children looked after in England including adoptions | Department for Education |
| Local authority inspection outcomes as at 31 March 2026 | Ofsted |
| English indices of deprivation 2019 | Ministry of Housing, Communities and Local Government |
| Mid-2024 population estimates | Office for National Statistics |
| Local authority and upper tier boundaries | ONS Open Geography Portal |

## Reproduce

```bash
git clone https://github.com/MaicyMxtim/social-care-intelligence.git
cd social-care-intelligence
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download.py
python scripts/make_all.py
```

`scripts/make_all.py` runs both projects and rebuilds this page. To run one
project on its own, change into its folder and run `python make_all.py`. To check
the loaders and the statistical functions, run `pytest` from the repository root.

## Headline numbers

| | Adult social care | Children's workforce |
| --- | --- | --- |
| Councils | {adult['authorities']} | {children['authorities']} |
| Period | {adult['snapshot']} snapshot, {panel['months']} monthly snapshots for the panel | {children['first_year']} to {children['last_year']}, {children['rows']} authority years |
| Widest gap | {fmt(rates['ratio_max_min'], 1)}-fold in support rates | {fmt(descriptives['agency_spread_last'], 1)} points between regions on agency use |
| Variation beyond chance | {fmt(funnel['phi'], 0)} times | {fmt(descriptives['turnover_phi'], 1)} times on turnover |
| Explained by the model | {fmt(model['deviance_explained'] * 100, 0)} per cent of deviance | within R squared {fmt(children['panel_regression']['rereferral_rate']['r_squared_within'], 3)} |
| Deprivation gradient | slope index {fmt(inequality['sii'])} per 100,000 | unstable group is the {unstable_direction} one |
| What does not explain it | care workforce vacancy rate | every workforce measure, for Ofsted downgrades |

## Tooling

The analysis, the method choices and the interpretation are mine. The code was
written with Claude Code as a pair programming tool.

## Licence

Code is released under the MIT licence. The source data stays under the licences
of its publishers, which are recorded for each file in `data/raw/MANIFEST.json`.
"""


def main() -> int:
    """Read both findings files and write the portfolio index."""
    for path in (ADULT, CHILDREN):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run both projects first, or run "
                f"python scripts/make_all.py which does everything in order."
            )
    adult = json.loads(ADULT.read_text(encoding="utf-8"))
    children = json.loads(CHILDREN.read_text(encoding="utf-8"))
    README_PATH.write_text(render(adult, children), encoding="utf-8")
    print(f"Wrote {README_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
