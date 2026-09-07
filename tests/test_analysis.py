"""Check the statistical functions behave the way the READMEs claim they do.

These tests use made up numbers rather than the real data, because the point is
to pin down the behaviour of the method itself. A funnel limit has to narrow as
population grows whatever data it is given, and a slope index has to be positive
when a rate rises with deprivation whether or not that is true in England.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import analysis


# --------------------------------------------------------------------------
# Funnel limits
# --------------------------------------------------------------------------


@pytest.mark.parametrize("confidence", [0.95, 0.998])
def test_funnel_limits_are_monotone_in_population(confidence):
    """Limits must close in on the national rate as the population grows.

    This is the whole point of a funnel plot. A rate measured over a small
    population moves around more, so its limits must be wider, and a rate
    measured over a large population must be held to a tighter standard.
    """
    population = np.array([1_000, 10_000, 50_000, 250_000, 1_000_000])
    lower, upper = analysis.poisson_funnel_limits(population, target_rate=1_500.0,
                                                  confidence=confidence)

    assert np.all(np.diff(upper) < 0), "upper limit must fall as population grows"
    assert np.all(np.diff(lower) > 0), "lower limit must rise as population grows"
    assert np.all(lower < 1_500.0) and np.all(upper > 1_500.0)


def test_outer_limits_are_wider_than_inner_limits():
    """The 99.8 per cent limits must sit outside the 95 per cent limits everywhere."""
    population = np.array([5_000, 50_000, 500_000])
    inner_low, inner_high = analysis.poisson_funnel_limits(population, 1_500.0, 0.95)
    outer_low, outer_high = analysis.poisson_funnel_limits(population, 1_500.0, 0.998)

    assert np.all(outer_high > inner_high)
    assert np.all(outer_low < inner_low)


def test_lower_limits_are_clipped_at_zero():
    """A rate cannot be negative, so the lower limit must never fall below zero."""
    population = np.array([50, 200, 1_000])
    lower, _ = analysis.poisson_funnel_limits(population, target_rate=100.0, confidence=0.998)
    assert np.all(lower >= 0.0)


def test_overdispersion_widens_the_limits_multiplicatively():
    """A dispersion ratio above one scales the distance from the target rate.

    The adjustment is multiplicative, so the gap between the limit and the
    national rate is multiplied by the square root of the ratio. A ratio of four
    should therefore double that gap.
    """
    population = np.array([20_000, 200_000])
    target = 1_500.0
    plain_low, plain_high = analysis.poisson_funnel_limits(population, target, 0.95, phi=1.0)
    wide_low, wide_high = analysis.poisson_funnel_limits(population, target, 0.95, phi=4.0)

    assert np.allclose(wide_high - target, 2.0 * (plain_high - target))
    assert np.allclose(target - wide_low, 2.0 * (target - plain_low))


def test_dispersion_ratio_is_one_when_counts_match_expectation():
    """Counts that behave like a Poisson process need no widening at all."""
    rng = np.random.default_rng(0)
    expected = np.full(200, 400.0)
    observed = rng.poisson(expected).astype(float)
    assert analysis.overdispersion_ratio(observed, expected) == pytest.approx(1.0)


def test_dispersion_ratio_rises_when_counts_are_spread_out():
    """Real variation between units must push the dispersion ratio above one."""
    expected = np.full(200, 400.0)
    observed = expected * np.linspace(0.5, 1.5, 200)
    assert analysis.overdispersion_ratio(observed, expected) > 1.0


def test_winsorising_stops_one_outlier_dominating():
    """A single extreme unit must not be allowed to set the dispersion ratio.

    Without winsorising, one authority far from the rest would inflate the ratio
    and widen the limits enough to hide itself.
    """
    rng = np.random.default_rng(1)
    expected = np.full(200, 400.0)
    observed = rng.poisson(expected).astype(float)
    with_outlier = observed.copy()
    with_outlier[0] = 4_000.0

    assert analysis.overdispersion_ratio(with_outlier, expected) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Slope and relative index of inequality
# --------------------------------------------------------------------------


def test_slope_index_is_positive_when_rate_rises_with_deprivation():
    """The sign convention: positive means a higher rate in more deprived areas.

    Every reading of the slope index in the READMEs depends on this, so it is
    pinned down here rather than left to be remembered.
    """
    deprivation = pd.Series([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    rate = pd.Series([100.0, 120.0, 140.0, 160.0, 180.0, 200.0])
    population = pd.Series([100_000.0] * 6)

    index = analysis.slope_index_of_inequality(rate, deprivation, population)
    assert index.sii > 0
    assert index.rii > 0
    assert index.sii_low < index.sii < index.sii_high


def test_slope_index_is_negative_when_rate_falls_with_deprivation():
    """The sign flips when the more deprived areas have the lower rate."""
    deprivation = pd.Series([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    rate = pd.Series([200.0, 180.0, 160.0, 140.0, 120.0, 100.0])
    population = pd.Series([100_000.0] * 6)

    index = analysis.slope_index_of_inequality(rate, deprivation, population)
    assert index.sii < 0
    assert index.rii < 0


def test_slope_index_is_about_zero_when_there_is_no_gradient():
    """A flat relationship must produce an interval that contains zero."""
    deprivation = pd.Series([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    rate = pd.Series([150.0, 149.0, 151.0, 150.0, 149.5, 150.5])
    population = pd.Series([100_000.0] * 6)

    index = analysis.slope_index_of_inequality(rate, deprivation, population)
    assert index.sii_low < 0 < index.sii_high


def test_slope_index_weights_by_population():
    """A large authority must pull the gradient more than a small one.

    Two datasets differ only in which end of the deprivation range carries the
    large population. The resulting slope indices must differ, which they cannot
    do if the weights are being ignored.
    """
    deprivation = pd.Series([5.0, 10.0, 15.0, 20.0])
    rate = pd.Series([100.0, 130.0, 140.0, 200.0])
    weighted_low = analysis.slope_index_of_inequality(
        rate, deprivation, pd.Series([1_000_000.0, 10_000.0, 10_000.0, 10_000.0])
    )
    weighted_high = analysis.slope_index_of_inequality(
        rate, deprivation, pd.Series([10_000.0, 10_000.0, 10_000.0, 1_000_000.0])
    )
    assert weighted_low.sii != pytest.approx(weighted_high.sii)


def test_relative_index_is_the_slope_over_the_mean():
    """The relative index must be the slope expressed against the average rate."""
    deprivation = pd.Series([5.0, 15.0, 25.0, 35.0])
    rate = pd.Series([100.0, 140.0, 180.0, 220.0])
    population = pd.Series([50_000.0, 200_000.0, 120_000.0, 90_000.0])

    index = analysis.slope_index_of_inequality(rate, deprivation, population)
    assert index.rii == pytest.approx(index.sii / index.mean_rate)


# --------------------------------------------------------------------------
# Negative binomial model
# --------------------------------------------------------------------------


def make_count_data(seed: int = 7, n: int = 250):
    """Build a small dataset whose counts really do depend on the covariates."""
    rng = np.random.default_rng(seed)
    population = rng.integers(20_000, 900_000, size=n).astype(float)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    rate = 0.015 * np.exp(0.20 * x1 - 0.10 * x2)
    mean = rate * population
    counts = rng.poisson(mean * rng.gamma(20.0, 1 / 20.0, size=n)).astype(float)
    index = pd.RangeIndex(n)
    return (
        pd.Series(counts, index=index),
        pd.Series(population, index=index),
        pd.DataFrame({"x1": x1, "x2": x2}, index=index),
    )


def test_incidence_rate_ratios_are_positive():
    """An incidence rate ratio is an exponentiated coefficient, so it is never negative.

    A ratio at or below zero would mean the model had produced something that
    cannot be read as a multiplier of a rate, which would make every statement in
    the README about it meaningless.
    """
    counts, population, covariates = make_count_data()
    model = analysis.negative_binomial_rate_model(counts, population, covariates)

    assert (model.irr["irr"] > 0).all()
    assert (model.irr["irr_low"] > 0).all()
    assert (model.irr["irr_high"] > 0).all()
    assert (model.irr["irr_low"] <= model.irr["irr"]).all()
    assert (model.irr["irr"] <= model.irr["irr_high"]).all()


def test_model_recovers_the_direction_of_each_covariate():
    """A covariate built to raise the rate must come back with a ratio above one."""
    counts, population, covariates = make_count_data()
    model = analysis.negative_binomial_rate_model(counts, population, covariates)

    assert model.irr.loc["x1", "irr"] > 1.0
    assert model.irr.loc["x2", "irr"] < 1.0


def test_dispersion_parameter_is_positive_and_deviance_explained_is_a_share():
    """Alpha must be usable by the negative binomial family and the fit must be a share."""
    counts, population, covariates = make_count_data()
    model = analysis.negative_binomial_rate_model(counts, population, covariates)

    assert model.alpha > 0
    assert 0.0 <= model.deviance_explained <= 1.0


def test_observed_expected_ratios_centre_on_one():
    """Observed divided by expected must average close to one across all units."""
    counts, population, covariates = make_count_data()
    model = analysis.negative_binomial_rate_model(counts, population, covariates)

    assert model.observed_expected.mean() == pytest.approx(1.0, abs=0.05)
    assert (model.observed_expected > 0).all()


def test_fixed_effects_add_indicator_terms():
    """Passing a region series must put region indicators into the model."""
    counts, population, covariates = make_count_data()
    regions = pd.Series(
        ["North", "South", "East", "West"] * (len(counts) // 4), index=counts.index[: (len(counts) // 4) * 4]
    ).reindex(counts.index, method="ffill")

    model = analysis.negative_binomial_rate_model(counts, population, covariates, regions)
    assert any(term.startswith("region_") for term in model.irr.index)


def test_cameron_trivedi_alpha_is_near_zero_for_poisson_counts():
    """Counts that are genuinely Poisson should need almost no extra dispersion."""
    import statsmodels.api as sm

    rng = np.random.default_rng(11)
    population = rng.integers(50_000, 500_000, size=400).astype(float)
    mean = 0.02 * population
    counts = rng.poisson(mean).astype(float)
    design = sm.add_constant(np.zeros((len(counts), 1)))
    fit = sm.GLM(
        counts, design, family=sm.families.Poisson(), offset=np.log(population)
    ).fit()

    assert analysis.cameron_trivedi_alpha(fit, counts) < 0.01
