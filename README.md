# Social care intelligence

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

Support rates across the 153 councils run from
733 to 2,841 adults per 100,000, a
3.9-fold gap. Councils vary about
87 times more than chance would produce. A negative binomial
model using age structure, deprivation and region explains
64 per cent of the variation. The care
workforce vacancy rate has no measurable effect. 8 councils sit
outside the funnel limits in almost every one of 18 monthly
snapshots.

[![Funnel plot of long-term support rates](projects/adult-variation/outputs/charts/funnel_long_term_support.png)](projects/adult-variation/README.md)

[Read the full project](projects/adult-variation/README.md) ·
[One page brief for a Director of Adult Social Services](docs/adult-variation-brief.md)

---

## Project 2: children's social work workforce

There were 24 Ofsted downgrades across
151 councils between 2017 and
2025. No measure of turnover, vacancies, agency use or
caseload shifts the risk of a downgrade. With that few events the result carries
little statistical weight. Agency reliance tracks re-referrals within
councils over time, at 0.10 percentage points per
point of agency rate. 66 councils form a persistently
unstable group, and that group is less deprived than the rest.

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
SHA256 hash of all 17 source files. A monthly GitHub Actions job
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
| Councils | 153 | 151 |
| Period | 31 March 2026 snapshot, 18 monthly snapshots for the panel | 2017 to 2025, 1349 authority years |
| Widest gap | 3.9-fold in support rates | 13.5 points between regions on agency use |
| Variation beyond chance | 87 times | 2.4 times on turnover |
| Explained by the model | 64 per cent of deviance | within R squared 0.025 |
| Deprivation gradient | slope index 547 per 100,000 | unstable group is the less deprived one |
| What does not explain it | care workforce vacancy rate | every workforce measure, for Ofsted downgrades |

## Licence

Code is released under the MIT licence. The source data stays under the licences
of its publishers, which are recorded for each file in `data/raw/MANIFEST.json`.
