# Social care intelligence

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

Across 153 councils the long-term support rate runs from
733 to 2,841 adults per 100,000, a
3.9-fold gap, and councils vary about
87 times more than chance alone would produce. A negative
binomial model with age structure, deprivation and region explains
64 per cent of that, the care workforce
vacancy rate adds nothing once the others are in, and
8 councils sit outside the limits in almost every one of
18 monthly snapshots rather than occasionally.

[![Funnel plot of long-term support rates](projects/adult-variation/outputs/charts/funnel_long_term_support.png)](projects/adult-variation/README.md)

[Read the full project](projects/adult-variation/README.md) ·
[One page brief for a Director of Adult Social Services](docs/adult-variation-brief.md)

---

## Project 2: children's social work workforce

**Does children's social work workforce instability predict later Ofsted
downgrades and worse child outcomes, 2017 to 2025?**

Across 151 councils and 24 Ofsted
downgrades, no measure of turnover, vacancies, agency use or caseload shifts the
risk of a downgrade, though with that few events this is weak evidence rather
than proof of no effect. Agency reliance does track re-referrals within
authorities over time, at 0.10 percentage points
per point of agency rate. 66 councils form a
persistently unstable group, and they are less deprived than the rest, so
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
date, size and SHA256 hash of all 17 source files, and a monthly
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
| Councils | 153 | 151 |
| Period | 31 March 2026 snapshot, 18 monthly snapshots for the panel | 2017 to 2025, 1349 authority years |
| Widest gap | 3.9-fold in support rates | 13.5 points between regions on agency use |
| Variation beyond chance | 87 times | 2.4 times on turnover |
| Explained by the model | 64 per cent of deviance | within R squared 0.025 |
| Deprivation gradient | slope index 547 per 100,000 | unstable group is the less deprived one |
| What does not explain it | care workforce vacancy rate | every workforce measure, for Ofsted downgrades |

## Tooling

The analysis, the method choices and the interpretation are mine. The code was
written with Claude Code as a pair programming tool.

## Licence

Code is released under the MIT licence. The source data stays under the licences
of its publishers, which are recorded for each file in `data/raw/MANIFEST.json`.
