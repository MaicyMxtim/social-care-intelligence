"""Write README.md for the adult variation project from outputs/findings.json.

No number in the README is typed by hand. Every figure the text quotes is read
from findings.json, which make_all.py writes when the analysis runs. If the data
changes, the README changes with it the next time make_all.py runs.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ROOT = PROJECT_DIR.parents[1]
FINDINGS_PATH = PROJECT_DIR / "outputs" / "findings.json"
README_PATH = PROJECT_DIR / "README.md"
BRIEF_PATH = ROOT / "docs" / "adult-variation-brief.md"


def fmt(value: float, places: int = 0) -> str:
    """Format a number with thousands separators and a fixed number of decimals."""
    return f"{value:,.{places}f}"


def join_names(names: list[str], limit: int = 6) -> str:
    """Join a list of authority names into a readable sentence fragment."""
    if not names:
        return "none"
    shown = names[:limit]
    remainder = len(names) - len(shown)
    text = ", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 else shown[0]
    if remainder > 0:
        text += f", and {remainder} others"
    return text


def render(findings: dict) -> str:
    """Build the whole README as one string."""
    funnel = findings["funnel"]["support"]
    assess = findings["funnel"]["assessments"]
    rates = findings["rate_summary"]
    inequality = findings["inequality"]
    model = findings["model"]
    panel = findings["panel"]
    coverage = findings["coverage"]

    irr = model["irr"]
    age = irr["Share of adults aged 65 and over"]
    imd = irr["Deprivation score"]
    vacancy = irr["Care workforce vacancy rate"]

    direction = "higher" if inequality["sii"] > 0 else "lower"
    significance = (
        "The interval does not cross zero, so the gradient is unlikely to be chance."
        if inequality["significant"]
        else "The interval crosses zero, so the gradient cannot be separated from chance."
    )

    vacancy_verdict = (
        "cannot be separated from no effect"
        if vacancy["low"] <= 1.0 <= vacancy["high"]
        else "changes the rate"
    )

    return f"""# Adult social care variation between local authorities

## Question

Local authorities in England support very different shares of their adult
population. Some of that difference is expected, because authorities differ in
how old their populations are, how deprived they are, and how easy it is to
recruit care workers locally. This project asks how much variation is left once
those three things are accounted for, and which authorities remain outliers when
they are.

## Context

Client level data is the first record-level national collection covering adult
social care in England. Councils have been required to submit it since April
2023, and it now feeds the Activity and Finance Report and six measures in the
Adult Social Care Outcomes Framework. That makes it the first dataset capable of
supporting this kind of comparison, and it means answers drawn from it will
increasingly shape how councils are judged.

The timing matters too. The Casey Commission timetable was accelerated during
2026, so questions about which councils are outliers and why are being asked
under pressure. Hospital discharge pressure pushes in the same direction,
because a council that cannot arrange long-term support quickly becomes a
constraint on the health service as well as on its own residents. A council
named as an outlier deserves to know whether the finding survives adjustment for
the things it cannot control.

## Data

Every file is downloaded by `scripts/download.py` from a published URL, and
`data/raw/MANIFEST.json` records the download date and a SHA256 hash for each
one. Nothing is edited by hand.

| Source | Publisher | What it provides |
| --- | --- | --- |
| Client level data, long-term support, to March 2026 | DHSC | Adults receiving long-term support, monthly, by council |
| Client level data, assessments, to March 2026 | DHSC | Assessments completed, monthly, by council |
| Client level data, September and December 2025 releases | DHSC | Earlier monthly snapshots for the panel |
| Mid-2024 population estimates, MYE2 | ONS | Population by single year of age |
| Indices of deprivation 2019, File 11 | MHCLG | Average deprivation score at upper tier |
| ASC-WDS local area estimates 2024/25 | Skills for Care | Care workforce vacancy rate |
| ASCOF 2024/25, Table 1a | DHSC | Measure 1A, social care related quality of life |
| Counties and unitary authorities, December 2023 | ONS Open Geography | Boundaries for the maps |

All of it is published under the Open Government Licence v3.0, except the Skills
for Care estimates, which are free to reuse with attribution.

The analysis covers {findings['authorities']} upper tier councils, which is every
council in England responsible for adult social care.

## Method

### Authority table

One row per council, holding the count of adults receiving long-term support on
{findings['snapshot']}, the number of assessments completed over
{findings['assessment_window']}, the adult and older adult populations, the
deprivation score, the care workforce vacancy rate and ASCOF measure 1A.

### Funnel plots

A funnel plot is a chart that shows each council as a point, with the size of its
population along the horizontal axis and its rate up the vertical axis. Curved
control limits fan out from the national rate, wide where populations are small
and narrow where they are large, because a rate measured over a small population
moves around more. A council outside the limits has a rate that chance alone does
not explain.

The limits here are exact Poisson limits, widened for overdispersion.
Overdispersion is the tendency for real councils to vary more than chance
predicts. It is measured by the dispersion ratio, which is the average squared
standardised residual after the most extreme ten per cent at each end have been
pulled back to the tenth and ninetieth percentiles. That winsorising step stops a
few genuine outliers from widening the limits so far that they hide themselves.
The method follows Spiegelhalter (2005), which is what OHID uses in Fingertips.
Lower limits are clipped at zero.

Both the adjusted and the unadjusted limits are drawn. With counts this large the
adjustment is severe, and showing only the adjusted limits would hide how far the
councils are spread.

### Slope and relative index of inequality

The slope index of inequality is a number that describes the whole gap in a rate
between the most deprived end of a distribution and the least deprived end.
Councils are ranked by deprivation score and given a position from zero at the
least deprived end to one at the most deprived end. That position is a ridit
score, meaning it is the midpoint of the share of population the council
occupies once every council is lined up in deprivation order, so a large council
counts for more than a small one. The rate is then regressed on that position by
weighted least squares. A positive slope index means the rate is higher in more
deprived areas.

The relative index of inequality is the same gap expressed as a proportion of the
average rate, which makes it comparable between measures on different scales.

### Negative binomial model

A negative binomial model is a regression for counts that allows the counts to
vary more than a Poisson model permits. The population is entered as an offset,
which turns a model of the count into a model of the rate. The three covariates
are standardised, so each coefficient describes what happens when that covariate
rises by one standard deviation. Region indicators are included, so councils are
compared with their neighbours as well as with the country.

The dispersion parameter is estimated by the Cameron and Trivedi auxiliary
regression rather than assumed. A coefficient is reported as an incidence rate
ratio, which is the multiplier applied to the rate for a one standard deviation
rise. A ratio of 1.10 means a ten per cent higher rate, and a ratio of 1.00 means
no effect.

### Observed and expected

The observed to expected ratio divides the number of people a council actually
supports by the number the model predicts it would support given its population,
deprivation, vacancy rate and region. A ratio of 1.0 means a council supports
exactly as many people as predicted. The ratio is the measure of unexplained
variation, and it is what the second map shows.

### Monthly panel

The quarterly releases overlap, so stitching them together gives a run of
monthly snapshots. A funnel plot is fitted for each month separately. A council
is called persistent when it sits outside the 95 per cent limits in at least four
fifths of the months it appears in, and transient when it steps outside in some
months but not most. The inner limits are used because the adjusted outer limits
catch almost no council in any month, which would make every council look settled
whatever it did.

## Findings

### Scale of variation

Across the {rates['n']} councils, the long-term support rate runs from
{fmt(rates['min'])} to {fmt(rates['max'])} adults per 100,000, a
{fmt(rates['ratio_max_min'], 1)}-fold gap between the lowest and the highest. The
median is {fmt(rates['median'])} and the middle half of councils fall between
{fmt(rates['iqr_low'])} and {fmt(rates['iqr_high'])}. The England rate is
{fmt(funnel['target_rate'])} per 100,000.

Before any adjustment, {funnel['outside_unadjusted']} of {funnel['n']} councils
sit outside the 99.8 per cent Poisson limits. The differences between councils
are therefore not sampling noise. The dispersion ratio is
{fmt(funnel['phi'], 1)}, so councils vary roughly {fmt(funnel['phi'], 0)} times
more than chance alone would produce.

Once the limits are widened by that amount, {funnel['outside_998']} council sits
outside the 99.8 per cent limits and {funnel['outside_95']} sit outside the 95 per
cent limits. The chart below shows both sets of limits. The overdispersion
adjustment asks whether a council is unusual compared with how much councils
actually differ, rather than compared with chance, and on that test almost none
is.

{funnel['highest_name']} has the highest rate at {fmt(funnel['highest_rate'])} per
100,000 and {funnel['lowest_name']} the lowest at {fmt(funnel['lowest_rate'])}.

![Funnel plot of long-term support rates](outputs/charts/funnel_long_term_support.png)

Assessments vary far more. The England assessment rate is
{fmt(assess['target_rate'])} per 100,000 adults over the year, and the dispersion
ratio is {fmt(assess['phi'], 0)}, which is several times the ratio for support.
A spread that wide is unlikely to describe need alone. Councils are probably not
yet recording an assessment in the same way as each other. Any assessment based
comparison between councils should wait until they are.

![Funnel plot of assessment rates](outputs/charts/funnel_assessments.png)

### Deprivation gradient

The slope index of inequality is {fmt(inequality['sii'])} per 100,000, with a 95
per cent interval from {fmt(inequality['sii_low'])} to
{fmt(inequality['sii_high'])}. The support rate is
{fmt(abs(inequality['sii']))} per 100,000 {direction} at the most deprived end of
the distribution than at the least deprived end. {significance} The relative
index is {fmt(inequality['rii'], 3)}, so the gap is
{fmt(abs(inequality['rii']) * 100, 1)} per cent of the average rate of
{fmt(inequality['mean_rate'])}.

### Model results

The negative binomial model fitted to {model['n']} councils has a dispersion
parameter of {fmt(model['alpha'], 4)} and explains
{fmt(model['deviance_explained'] * 100, 1)} per cent of the deviance.

| Covariate | Rate ratio per standard deviation | 95% interval |
| --- | --- | --- |
| Share of adults aged 65 and over | {fmt(age['irr'], 3)} | {fmt(age['low'], 3)} to {fmt(age['high'], 3)} |
| Deprivation score | {fmt(imd['irr'], 3)} | {fmt(imd['low'], 3)} to {fmt(imd['high'], 3)} |
| Care workforce vacancy rate | {fmt(vacancy['irr'], 3)} | {fmt(vacancy['low'], 3)} to {fmt(vacancy['high'], 3)} |

The care workforce vacancy rate {vacancy_verdict}. Vacancy pressure is often
offered as an explanation for why councils differ in how many people they
support. At this level of aggregation it does not carry that weight.

![Forest plot of incidence rate ratios](outputs/charts/forest_incidence_rate_ratios.png)

### Unexplained variation

Observed to expected ratios run from {fmt(model['oe_min'], 2)} to
{fmt(model['oe_max'], 2)}. {model['oe_top_name']} supports
{fmt(model['oe_top_value'], 2)} times as many adults as the model predicts, and
{model['oe_bottom_name']} supports {fmt(model['oe_bottom_value'], 2)} times as
many. {model['oe_above_1_2']} councils are more than a fifth above prediction and
{model['oe_below_0_8']} are more than a fifth below it.

![Councils furthest from their expected support level](outputs/charts/observed_expected_extremes.png)

The raw rate map shows a recognisable geography. The observed to expected map
does not.

![Map of raw support rates](outputs/charts/map_support_rate.png)

![Map of observed to expected ratios](outputs/charts/map_observed_expected.png)

### Persistence of outliers

Across {panel['months']} monthly snapshots from {panel['first_month']} to
{panel['last_month']}, {panel['persistent']} councils sit outside the 95 per cent
limits in at least four fifths of months, {panel['transient']} step outside in
some months but not most, and {panel['never']} never step outside at all. The
persistent group is {join_names(panel['persistent_names'])}.

![Councils outside the limits month after month](outputs/charts/panel_persistence.png)

## Limits

These statistics are official statistics in development, which means the
publisher has said they are not yet fully assured and may change.

Coverage is incomplete in places. The care workforce vacancy rate is missing for
{coverage['vacancy_missing']} councils: {join_names(coverage['vacancy_missing_names'])}.
Those councils drop out of the model but stay in the funnel plots.

The January and April 2026 client level data releases were issued under
correction, and the September and December 2025 files used here are the corrected
July 2026 versions. Figures for recent months are marked provisional by the
publisher.

The main model is cross-sectional. It describes which councils differ from
prediction on one date, and it cannot say what caused the difference.

Eligibility policy is not modelled. Councils apply the Care Act eligibility
criteria with real local discretion, and a council that supports fewer people may
be applying a stricter threshold rather than meeting less need. Nothing in open
data measures that threshold.

The denominator lags the numerator. The support counts are from March 2026 and
the population estimates are mid-2024, so councils growing quickly will look as
though they support a slightly higher share of adults than they do.

Deprivation is measured in 2019. Five councils were created by reorganisation
after that, and they inherit the score of the county they replaced, which is an
approximation.

## Implications

Being an outlier on the raw rate is not by itself evidence of anything. Roughly a
third of the raw gap between councils survives adjustment for age structure,
deprivation and region.

The vacancy rate does not explain the residual. If a council supports far fewer
adults than prediction, workforce supply is unlikely to be the reason. The
eligibility threshold is the more probable explanation.

A council outside the limits in a single month may be a data artefact. A council
outside them in almost every month for over a year has a settled difference in
practice. Those councils are named above.

## Reproduce

From a fresh clone:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download.py
cd projects/adult-variation && python make_all.py
```

`make_all.py` writes every chart and table in `outputs/`, writes
`outputs/findings.json`, and regenerates this README from it. Run `pytest` from
the repository root to check the loaders and the statistical functions.

## Next steps

Model the eligibility threshold directly by pairing assessment counts with the
share of assessments leading to long-term support, which would separate councils
that assess few people from councils that assess many and support few.

Extend the panel as further quarterly releases appear, so that persistence can be
measured over several years rather than a single stretch of months.

Add unit costs from the Activity and Finance Report, so that the question becomes
how much support each council buys rather than how many people it supports.

Test whether the councils that remain outliers after adjustment differ on ASCOF
measure 1A, which would show whether unexplained variation in support levels
reaches the people using services.
"""


def render_brief(findings: dict) -> str:
    """Build the one page brief for a director of adult social services.

    The brief is held to about 150 words, on the view that a director reads the
    first paragraph and the recommendation and nothing else.
    """
    funnel = findings["funnel"]["support"]
    rates = findings["rate_summary"]
    model = findings["model"]
    panel = findings["panel"]
    vacancy = model["irr"]["Care workforce vacancy rate"]
    deprivation = model["irr"]["Deprivation score"]

    return f"""# Brief for a Director of Adult Social Services

**Local variation in long-term support, {findings['snapshot']}**

Long-term support rates across the {findings['authorities']} English councils run
from {fmt(rates['min'])} to {fmt(rates['max'])} per 100,000 adults, a
{fmt(rates['ratio_max_min'], 1)}-fold gap. Councils vary about
{fmt(funnel['phi'], 0)} times more than chance alone would produce, so raw
comparisons between councils are not measuring noise.

A negative binomial model with age structure, deprivation and region explains
{fmt(model['deviance_explained'] * 100, 0)} per cent of that variation.
Deprivation is the strongest single factor, at {fmt(deprivation['irr'], 2)} times
the rate per standard deviation. The care workforce vacancy rate adds nothing
once the others are in ({fmt(vacancy['irr'], 2)}, interval
{fmt(vacancy['low'], 2)} to {fmt(vacancy['high'], 2)}).

Unexplained variation remains wide, from {fmt(model['oe_min'], 2)} to
{fmt(model['oe_max'], 2)} times predicted. Over {panel['months']} monthly
snapshots, {panel['persistent']} councils sit outside the limits in almost every
month rather than occasionally.

**Recommendation.** Treat persistence, not a single month, as the trigger for
review, and look at eligibility thresholds rather than workforce supply when
explaining a low rate.
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
