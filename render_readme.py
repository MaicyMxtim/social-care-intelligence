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
        "has no measurable effect"
        if vacancy["low"] <= 1.0 <= vacancy["high"]
        else f"still moves the rate, at {vacancy['irr']:.2f} times per standard deviation"
    )

    return f"""# Social care intelligence

This repository holds two analyses of English social care data.

The first measures how much adult social care support rates vary between local
authorities, and how much of that variation is explained by age structure,
deprivation and care workforce vacancies.

The second tests whether instability in the children's social work workforce
predicts later Ofsted downgrades and worse outcomes for children.

All the data is open and published by government departments. Each project
downloads its own data and runs from a single command.

---

## Project 1: adult social care variation

Support rates across the {adult['authorities']} councils run from
{fmt(rates['min'])} to {fmt(rates['max'])} adults per 100,000, a
{fmt(rates['ratio_max_min'], 1)}-fold gap. Councils vary about
{fmt(funnel['phi'], 0)} times more than chance would produce. A negative binomial
model using age structure, deprivation and region explains
{fmt(model['deviance_explained'] * 100, 0)} per cent of the variation. The care
workforce vacancy rate {vacancy_verdict}. {panel['persistent']} councils sit
outside the funnel limits in almost every one of {panel['months']} monthly
snapshots.

[![Funnel plot of long-term support rates](projects/adult-variation/outputs/charts/funnel_long_term_support.png)](projects/adult-variation/README.md)

[Read the full project](projects/adult-variation/README.md) ·
[One page brief for a Director of Adult Social Services](docs/adult-variation-brief.md)

---

## Project 2: children's social work workforce

There were {cox['downgraded']} Ofsted downgrades across
{children['authorities']} councils between {children['first_year']} and
{children['last_year']}. No measure of turnover, vacancies, agency use or
caseload shifts the risk of a downgrade. With that few events the result carries
little statistical weight. Agency reliance tracks re-referrals within
councils over time, at {fmt(abs(agency['coefficient']), 2)} percentage points per
point of agency rate. {clusters['unstable_size']} councils form a persistently
unstable group, and that group is {unstable_direction} than the rest.

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

`scripts/download.py` downloads every dataset from a published URL. Raw files
stay as downloaded. `data/raw/MANIFEST.json` records the download date, size and
SHA256 hash of all {manifest_count} source files. A monthly GitHub Actions job
re-downloads them and opens an issue if a publisher reissues one under
correction.

Each project runs from `python make_all.py` inside its own folder, starting from
a fresh clone.

The numbers quoted in each README come from that project's
`outputs/findings.json`, through its `render_readme.py`.

Chart titles state the finding. Axis labels carry units.

Where a published file did not match what a loader expected, the loader was
changed and the change recorded in [docs/DATA_NOTES.md](docs/DATA_NOTES.md).

## Data sources

Every source is open. All are published under the Open Government Licence v3.0,
except the Skills for Care estimates, which are free to reuse with
attribution.

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
