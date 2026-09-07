"""Statistical methods shared by both projects.

The functions here are written to be read as much as run. Each one explains in
plain sentences what the method does and what its output means, because the
point of this repository is that the person who wrote it can pick it up again a
year later and still follow the argument.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


# --------------------------------------------------------------------------
# Funnel plots
# --------------------------------------------------------------------------


def overdispersion_ratio(observed: np.ndarray, expected: np.ndarray) -> float:
    """Return the dispersion ratio phi, using winsorised standardised residuals.

    A funnel plot assumes that the only reason two authorities differ is chance.
    In practice authorities differ for real reasons as well, so the spread of
    points is wider than chance alone would produce. The dispersion ratio
    measures how much wider.

    The ratio is the average squared standardised residual. Residuals are
    winsorised first, which means the most extreme ten per cent at each end are
    pulled back to the value at the tenth and ninetieth percentiles. Without
    that step a handful of genuine outliers would inflate the ratio and then
    widen the limits so much that they hid the very outliers that caused it.

    This follows Spiegelhalter (2005), which is the method the Office for Health
    Improvement and Disparities uses in Fingertips.

    A ratio of one means no more variation than chance. A ratio above one means
    there is extra variation between authorities.
    """
    observed = np.asarray(observed, dtype=float)
    expected = np.asarray(expected, dtype=float)
    usable = (expected > 0) & np.isfinite(observed) & np.isfinite(expected)
    observed, expected = observed[usable], expected[usable]
    if observed.size < 3:
        return 1.0

    z = (observed - expected) / np.sqrt(expected)
    low, high = np.percentile(z, [10, 90])
    z_winsorised = np.clip(z, low, high)
    phi = float(np.sum(z_winsorised**2) / z.size)

    # Spiegelhalter's test for whether the extra variation is worth adjusting
    # for. Below this threshold the spread is consistent with chance and the
    # limits are left alone.
    threshold = 1.0 + 2.0 * np.sqrt(2.0 / z.size)
    return phi if phi > threshold else 1.0


def poisson_funnel_limits(
    population: np.ndarray,
    target_rate: float,
    confidence: float,
    per: float = 100_000.0,
    phi: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the lower and upper funnel limits for a rate, at one confidence level.

    A funnel plot is a chart that shows each local authority as a point, with the
    size of its population along the horizontal axis and its rate up the vertical
    axis. Curved lines called control limits fan out from the national rate, wide
    where populations are small and narrow where they are large, because a rate
    measured over a small population bounces around more. An authority above the
    upper limit has a rate higher than chance alone explains.

    The limits are exact Poisson limits. For an expected count, the lower limit
    on the count is found from the chi-squared distribution with twice that
    count as its degrees of freedom, and the upper limit from the same
    distribution with twice the expected count plus one. Those count limits are
    then divided by the population to put them back on the rate scale.

    Where the dispersion ratio phi is greater than one, the distance between the
    limit and the national rate is multiplied by the square root of phi. This is
    the multiplicative adjustment, and it widens the limits by the same
    proportion everywhere rather than adding a fixed amount.

    Lower limits are clipped at zero, because a rate cannot be negative.

    Confidence is given as a proportion, so 0.95 for the inner limits and 0.998
    for the outer ones.
    """
    population = np.asarray(population, dtype=float)
    alpha = 1.0 - confidence
    expected = target_rate * population / per

    with np.errstate(divide="ignore", invalid="ignore"):
        lower_count = stats.chi2.ppf(alpha / 2.0, 2.0 * expected) / 2.0
        upper_count = stats.chi2.ppf(1.0 - alpha / 2.0, 2.0 * (expected + 1.0)) / 2.0

    lower_rate = lower_count / population * per
    upper_rate = upper_count / population * per
    lower_rate = np.nan_to_num(lower_rate, nan=0.0)

    if phi > 1.0:
        scale = np.sqrt(phi)
        lower_rate = target_rate + scale * (lower_rate - target_rate)
        upper_rate = target_rate + scale * (upper_rate - target_rate)

    return np.maximum(lower_rate, 0.0), upper_rate


def funnel_frame(
    counts: pd.Series,
    populations: pd.Series,
    per: float = 100_000.0,
    grid_points: int = 300,
) -> dict:
    """Assemble everything needed to draw and interpret one funnel plot.

    The returned dictionary holds the national rate, the dispersion ratio, a
    smooth grid of populations with the limits evaluated on it for drawing the
    curves, and a table of authorities with each one's rate and whether it sits
    outside the limits.
    """
    counts = pd.Series(counts).astype(float)
    populations = pd.Series(populations).astype(float)
    usable = counts.notna() & populations.notna() & (populations > 0)
    counts, populations = counts[usable], populations[usable]

    target_rate = float(counts.sum() / populations.sum() * per)
    expected = target_rate * populations / per
    phi = overdispersion_ratio(counts.to_numpy(), expected.to_numpy())

    grid = np.linspace(populations.min() * 0.85, populations.max() * 1.05, grid_points)
    curves = {}
    for label, confidence in [("95", 0.95), ("998", 0.998)]:
        lower, upper = poisson_funnel_limits(grid, target_rate, confidence, per, phi)
        curves[label] = {"lower": lower, "upper": upper}
    # The unadjusted limits are kept as well. Showing both makes clear how much
    # of the spread between authorities is real rather than sampling noise.
    raw_lower, raw_upper = poisson_funnel_limits(grid, target_rate, 0.998, per, 1.0)
    curves["998_unadjusted"] = {"lower": raw_lower, "upper": raw_upper}

    point_rate = counts / populations * per
    flags = pd.DataFrame({"rate": point_rate, "population": populations})
    for label, confidence, dispersion in [
        ("95", 0.95, phi),
        ("998", 0.998, phi),
        ("998_unadjusted", 0.998, 1.0),
    ]:
        lower, upper = poisson_funnel_limits(
            populations.to_numpy(), target_rate, confidence, per, dispersion
        )
        flags[f"lower_{label}"] = lower
        flags[f"upper_{label}"] = upper
        flags[f"outside_{label}"] = (flags["rate"] < lower) | (flags["rate"] > upper)

    # How far outside each limit a point sits, used to pick which authorities to
    # label on the chart.
    for label in ["95", "998"]:
        flags[f"distance_outside_{label}"] = np.where(
            flags["rate"] > flags[f"upper_{label}"],
            flags["rate"] - flags[f"upper_{label}"],
            np.where(
                flags["rate"] < flags[f"lower_{label}"],
                flags[f"lower_{label}"] - flags["rate"],
                0.0,
            ),
        )

    return {
        "target_rate": target_rate,
        "phi": phi,
        "grid": grid,
        "curves": curves,
        "points": flags,
    }


# --------------------------------------------------------------------------
# Slope and relative index of inequality
# --------------------------------------------------------------------------


@dataclass
class InequalityIndex:
    """The result of fitting a slope and relative index of inequality.

    The slope index is the modelled difference in the rate between the most
    deprived end of the distribution and the least deprived end. It is measured
    in the same units as the rate. A positive slope index means the rate is
    higher in more deprived areas.

    The relative index expresses that same gap as a proportion of the average
    rate, so it can be compared between measures that are on different scales.
    """

    sii: float
    sii_low: float
    sii_high: float
    rii: float
    rii_low: float
    rii_high: float
    mean_rate: float


def slope_index_of_inequality(
    rate: pd.Series,
    deprivation_score: pd.Series,
    population: pd.Series,
    confidence: float = 0.95,
) -> InequalityIndex:
    """Fit the slope and relative index of inequality across local authorities.

    Authorities are ranked by their deprivation score and then given a position
    on a scale from zero to one. Zero is the least deprived end and one is the
    most deprived end. The position is a ridit score, meaning it is the midpoint
    of the share of the population that the authority occupies once every
    authority is lined up in order of deprivation. Using population shares rather
    than a plain rank stops a small authority from carrying the same weight as a
    large one.

    The rate is then regressed on that position by weighted least squares, with
    each authority weighted by its population. The slope of that line is the
    slope index of inequality, and because the position runs from zero to one the
    slope is the whole gap from one end of the distribution to the other.

    The relative index of inequality is the slope divided by the population
    weighted average rate.
    """
    frame = pd.DataFrame(
        {"rate": rate, "imd": deprivation_score, "population": population}
    ).dropna()
    frame = frame[frame["population"] > 0].sort_values("imd").reset_index(drop=True)
    if len(frame) < 3:
        raise ValueError("At least three authorities are needed to fit a slope index.")

    share = frame["population"] / frame["population"].sum()
    cumulative = share.cumsum()
    frame["ridit"] = cumulative - share / 2.0

    design = sm.add_constant(frame[["ridit"]])
    model = sm.WLS(frame["rate"], design, weights=frame["population"]).fit()

    sii = float(model.params["ridit"])
    low, high = model.conf_int(alpha=1.0 - confidence).loc["ridit"]
    mean_rate = float(np.average(frame["rate"], weights=frame["population"]))

    return InequalityIndex(
        sii=sii,
        sii_low=float(low),
        sii_high=float(high),
        rii=sii / mean_rate,
        rii_low=float(low) / mean_rate,
        rii_high=float(high) / mean_rate,
        mean_rate=mean_rate,
    )


# --------------------------------------------------------------------------
# Negative binomial regression
# --------------------------------------------------------------------------


def cameron_trivedi_alpha(poisson_result, endog: np.ndarray) -> float:
    """Estimate the negative binomial dispersion parameter from a Poisson fit.

    A Poisson model assumes the variance of a count equals its mean. Counts of
    people receiving social care are more variable than that, which makes the
    standard errors from a Poisson model too small. The negative binomial model
    allows the variance to be the mean plus alpha times the mean squared, and
    alpha has to be estimated.

    Cameron and Trivedi estimate it with an auxiliary regression. For each
    authority the quantity ((observed minus fitted) squared, minus observed),
    divided by the fitted value, has an expected value of alpha times the fitted
    value. Regressing the first quantity on the fitted value through the origin
    therefore gives alpha as the slope.

    An alpha at or below zero means the counts are not overdispersed, and a
    small positive floor is returned so that the negative binomial fit stays
    well defined.
    """
    fitted = np.asarray(poisson_result.mu, dtype=float)
    observed = np.asarray(endog, dtype=float)
    response = ((observed - fitted) ** 2 - observed) / fitted
    auxiliary = sm.OLS(response, fitted).fit()
    alpha = float(auxiliary.params[0])
    return max(alpha, 1e-6)


@dataclass
class CountModel:
    """A fitted negative binomial model together with the parts reports need."""

    result: object
    alpha: float
    irr: pd.DataFrame
    deviance_explained: float
    observed_expected: pd.Series


def negative_binomial_rate_model(
    counts: pd.Series,
    exposure: pd.Series,
    covariates: pd.DataFrame,
    fixed_effects: pd.Series | None = None,
) -> CountModel:
    """Fit a negative binomial model of a count with a population offset.

    The model explains the number of people receiving support in each authority.
    The population is entered as an offset, meaning its coefficient is fixed at
    one, which turns the model into a model of the rate rather than the count.

    Continuous covariates are standardised before fitting, so each one is
    measured in standard deviations away from the national average. A coefficient
    is reported as an incidence rate ratio, which is the multiplier applied to the
    rate when that covariate rises by one standard deviation. A ratio of 1.10
    means a ten per cent higher rate.

    Fixed effects for region are added as indicator columns when a region series
    is supplied, so that comparisons are made between authorities within the same
    part of the country as well as across the country as a whole.

    Deviance explained compares the deviance of the fitted model with the
    deviance of a model containing only an intercept. It is the share of the
    explainable variation that the covariates account for.
    """
    frame = pd.concat([counts.rename("y"), exposure.rename("exposure"), covariates], axis=1)
    if fixed_effects is not None:
        frame = pd.concat([frame, fixed_effects.rename("fixed_effect")], axis=1)
    frame = frame.dropna()

    design_parts = []
    standardised = frame[covariates.columns].apply(
        lambda column: (column - column.mean()) / column.std(ddof=0)
    )
    design_parts.append(standardised)

    if fixed_effects is not None:
        indicators = pd.get_dummies(frame["fixed_effect"], prefix="region", drop_first=True)
        design_parts.append(indicators.astype(float))

    design = sm.add_constant(pd.concat(design_parts, axis=1))
    offset = np.log(frame["exposure"].to_numpy(dtype=float))
    endog = frame["y"].to_numpy(dtype=float)

    poisson_fit = sm.GLM(
        endog, design, family=sm.families.Poisson(), offset=offset
    ).fit()
    alpha = cameron_trivedi_alpha(poisson_fit, endog)

    negative_binomial = sm.GLM(
        endog, design, family=sm.families.NegativeBinomial(alpha=alpha), offset=offset
    ).fit()

    confidence = negative_binomial.conf_int()
    irr = pd.DataFrame(
        {
            "irr": np.exp(negative_binomial.params),
            "irr_low": np.exp(confidence[0]),
            "irr_high": np.exp(confidence[1]),
            "p_value": negative_binomial.pvalues,
        }
    )

    intercept_only = sm.GLM(
        endog,
        np.ones((len(endog), 1)),
        family=sm.families.NegativeBinomial(alpha=alpha),
        offset=offset,
    ).fit()
    deviance_explained = float(
        1.0 - negative_binomial.deviance / intercept_only.deviance
    )

    observed_expected = pd.Series(
        endog / negative_binomial.fittedvalues, index=frame.index, name="observed_expected"
    )

    return CountModel(
        result=negative_binomial,
        alpha=alpha,
        irr=irr,
        deviance_explained=deviance_explained,
        observed_expected=observed_expected,
    )


def summarise_series(values: pd.Series) -> dict:
    """Return the summary numbers that the READMEs quote for a distribution."""
    clean = pd.Series(values).dropna()
    return {
        "n": int(clean.size),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "median": float(clean.median()),
        "mean": float(clean.mean()),
        "ratio_max_min": float(clean.max() / clean.min()) if clean.min() > 0 else float("nan"),
        "iqr_low": float(clean.quantile(0.25)),
        "iqr_high": float(clean.quantile(0.75)),
    }
