"""Chart styling and the chart types both projects use.

Two rules run through this module. Every chart title states the finding rather
than naming the variable, so a reader who sees only the chart still learns
something. Every axis label carries its unit, so a number on the chart can be
read without going back to the text.

The palette is built from blues, teals, ambers and greys. It avoids rose and
pink entirely, and the outlier colour is chosen to stay distinguishable in
greyscale as well as in colour.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

mpl.use("Agg")

INK = "#1c2733"
MUTED = "#6b7683"
GRID = "#dfe4ea"
PRIMARY = "#1f4e79"
SECONDARY = "#2a7f7f"
ACCENT = "#c06a00"
OUTLIER_HIGH = "#a8480a"
OUTLIER_LOW = "#1b6a8a"
LIMIT_INNER = "#8c98a4"
LIMIT_OUTER = "#4a5561"

# A sequential ramp from pale sand to deep blue, for rates.
SEQUENTIAL = LinearSegmentedColormap.from_list(
    "care_sequential", ["#f4f1e8", "#c8d8e4", "#7fa8c4", "#3d6f96", "#1f4e79"]
)
# A diverging ramp from amber through near white to blue, for ratios centred on
# one. Neither end is rose or pink, and the midpoint is deliberately pale so
# that authorities close to expected recede.
DIVERGING = LinearSegmentedColormap.from_list(
    "care_diverging", ["#8a4b00", "#c78b3c", "#efe9df", "#6c9ec2", "#1f4e79"]
)

REGION_COLOURS = {
    "North East": "#1f4e79",
    "North West": "#2a7f7f",
    "Yorkshire and The Humber": "#5d7f4a",
    "East Midlands": "#8a7320",
    "West Midlands": "#c06a00",
    "East of England": "#3d6f96",
    "London": "#1c2733",
    "South East": "#7a6a55",
    "South West": "#4a8a8a",
}


def apply_house_style() -> None:
    """Set the matplotlib defaults used by every chart in this repository."""
    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.titlepad": 14,
            "axes.labelsize": 10,
            "axes.labelcolor": INK,
            "axes.edgecolor": GRID,
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "text.color": INK,
        }
    )


def finish(fig, axis, title: str, subtitle: str = "", source: str = "") -> None:
    """Add the title, an optional subtitle and a source note to a chart.

    The title carries the finding. The subtitle carries the detail that would
    make the title too long. The source note names the publications behind the
    chart so it can be checked.
    """
    axis.set_title(title)
    if subtitle:
        axis.text(
            0.0,
            1.02,
            subtitle,
            transform=axis.transAxes,
            fontsize=9.5,
            color=MUTED,
            va="bottom",
        )
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    if source:
        fig.text(0.0, -0.03, source, fontsize=8, color=MUTED, ha="left", va="top")


def save(fig, path: Path) -> Path:
    """Write a chart to disk, creating the folder if it is not there yet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path


def funnel_plot(
    funnel: dict,
    labels: pd.Series,
    title: str,
    subtitle: str,
    y_label: str,
    x_label: str,
    source: str,
    path: Path,
    label_count: int = 6,
) -> Path:
    """Draw a funnel plot of a rate against population size.

    Points inside the limits are drawn in grey, because they say nothing beyond
    what chance would produce. Points outside the outer limit are coloured, and
    the ones furthest outside are named.
    """
    points = funnel["points"].copy()
    points["label"] = labels.reindex(points.index)

    fig, axis = plt.subplots(figsize=(9, 5.6))

    grid = funnel["grid"]
    axis.plot(
        grid, funnel["curves"]["95"]["upper"], color=LIMIT_INNER, lw=1.0, ls="--", zorder=2
    )
    axis.plot(
        grid, funnel["curves"]["95"]["lower"], color=LIMIT_INNER, lw=1.0, ls="--", zorder=2,
        label="95% limits",
    )
    axis.plot(
        grid, funnel["curves"]["998"]["upper"], color=LIMIT_OUTER, lw=1.2, zorder=2
    )
    axis.plot(
        grid, funnel["curves"]["998"]["lower"], color=LIMIT_OUTER, lw=1.2, zorder=2,
        label="99.8% limits",
    )
    axis.axhline(
        funnel["target_rate"], color=ACCENT, lw=1.2, zorder=2, label="England rate"
    )

    inside = ~points["outside_998"]
    axis.scatter(
        points.loc[inside, "population"],
        points.loc[inside, "rate"],
        s=26,
        color=MUTED,
        alpha=0.55,
        linewidths=0,
        zorder=3,
    )
    high = points["outside_998"] & (points["rate"] > points["upper_998"])
    low = points["outside_998"] & (points["rate"] < points["lower_998"])
    axis.scatter(
        points.loc[high, "population"], points.loc[high, "rate"],
        s=42, color=OUTLIER_HIGH, linewidths=0, zorder=4, label="Above 99.8% limit",
    )
    axis.scatter(
        points.loc[low, "population"], points.loc[low, "rate"],
        s=42, color=OUTLIER_LOW, linewidths=0, zorder=4, label="Below 99.8% limit",
    )

    named = points.nlargest(label_count, "distance_outside")
    named = named[named["distance_outside"] > 0]
    for _, row in named.iterrows():
        axis.annotate(
            str(row["label"]),
            (row["population"], row["rate"]),
            textcoords="offset points",
            xytext=(7, 4),
            fontsize=8.5,
            color=INK,
        )

    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.set_xscale("log")
    axis.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axis.set_ylim(bottom=0)
    axis.legend(loc="upper right", ncols=2)
    finish(fig, axis, title, subtitle, source)
    return save(fig, path)


def forest_plot(
    irr: pd.DataFrame,
    title: str,
    subtitle: str,
    x_label: str,
    source: str,
    path: Path,
) -> Path:
    """Draw incidence rate ratios with their confidence intervals.

    Each row is one covariate. The dot is the ratio and the bar is its
    confidence interval. The vertical line at one marks no effect, so an
    interval that crosses it describes a covariate the data cannot separate
    from no effect at all.
    """
    frame = irr.copy().iloc[::-1]
    positions = np.arange(len(frame))

    fig, axis = plt.subplots(figsize=(8.4, 0.52 * len(frame) + 2.4))
    axis.axvline(1.0, color=MUTED, lw=1.0, ls="--", zorder=1)

    for position, (_, row) in zip(positions, frame.iterrows()):
        crosses_one = row["irr_low"] <= 1.0 <= row["irr_high"]
        colour = MUTED if crosses_one else PRIMARY
        axis.plot(
            [row["irr_low"], row["irr_high"]], [position, position],
            color=colour, lw=2.0, solid_capstyle="round", zorder=2,
        )
        axis.scatter([row["irr"]], [position], s=48, color=colour, zorder=3)

    axis.set_yticks(positions)
    axis.set_yticklabels(frame.index)
    axis.set_xlabel(x_label)
    axis.grid(axis="y", visible=False)
    finish(fig, axis, title, subtitle, source)
    return save(fig, path)


def choropleth(
    geo_frame,
    column: str,
    title: str,
    subtitle: str,
    legend_label: str,
    source: str,
    path: Path,
    diverging_at: float | None = None,
) -> Path:
    """Draw a map of English local authorities shaded by one column.

    Passing a value to diverging_at centres the colour scale on that value, which
    is how the observed to expected map is drawn so that authorities at exactly
    the expected level sit in the pale middle of the scale.
    """
    fig, axis = plt.subplots(figsize=(6.6, 8.2))

    if diverging_at is not None:
        values = geo_frame[column].dropna()
        spread = max(
            abs(values.max() - diverging_at), abs(diverging_at - values.min()), 1e-6
        )
        norm = TwoSlopeNorm(
            vmin=diverging_at - spread, vcenter=diverging_at, vmax=diverging_at + spread
        )
        colormap = DIVERGING
    else:
        norm = None
        colormap = SEQUENTIAL

    geo_frame.plot(
        column=column,
        ax=axis,
        cmap=colormap,
        norm=norm,
        linewidth=0.25,
        edgecolor="white",
        missing_kwds={"color": "#eceff1", "edgecolor": "white", "linewidth": 0.25},
        legend=True,
        legend_kwds={
            "label": legend_label,
            "orientation": "horizontal",
            "shrink": 0.62,
            "pad": 0.01,
            "aspect": 30,
        },
    )
    axis.set_axis_off()
    axis.set_title(title)
    if subtitle:
        axis.text(
            0.0, 1.01, subtitle, transform=axis.transAxes, fontsize=9.5,
            color=MUTED, va="bottom",
        )
    if source:
        fig.text(0.02, 0.02, source, fontsize=8, color=MUTED, ha="left")
    return save(fig, path)


def trajectory_plot(
    frame: pd.DataFrame,
    x: str,
    y: str,
    group: str,
    title: str,
    subtitle: str,
    y_label: str,
    x_label: str,
    source: str,
    path: Path,
    colours: dict | None = None,
) -> Path:
    """Draw one line per group over time, labelled at the right hand end.

    Labelling the lines at their end rather than in a legend means the eye does
    not have to travel between a key and the chart to work out which line is
    which.
    """
    fig, axis = plt.subplots(figsize=(9, 5.4))
    palette = colours or REGION_COLOURS

    for name, part in frame.groupby(group):
        part = part.sort_values(x)
        colour = palette.get(name, MUTED)
        axis.plot(part[x], part[y], color=colour, lw=1.8, zorder=3)
        last = part.dropna(subset=[y]).iloc[-1]
        axis.annotate(
            str(name),
            (last[x], last[y]),
            textcoords="offset points",
            xytext=(6, -3),
            fontsize=8.5,
            color=colour,
        )

    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.set_xlim(frame[x].min(), frame[x].max() + (frame[x].max() - frame[x].min()) * 0.26)
    finish(fig, axis, title, subtitle, source)
    return save(fig, path)


def ranked_bar(
    frame: pd.DataFrame,
    value: str,
    label: str,
    title: str,
    subtitle: str,
    x_label: str,
    source: str,
    path: Path,
    reference: float | None = None,
) -> Path:
    """Draw a horizontal bar chart of authorities ranked by one value."""
    ordered = frame.sort_values(value)
    positions = np.arange(len(ordered))

    fig, axis = plt.subplots(figsize=(8.4, 0.34 * len(ordered) + 2.2))
    if reference is not None:
        colours = [
            OUTLIER_HIGH if v > reference else OUTLIER_LOW for v in ordered[value]
        ]
    else:
        colours = [PRIMARY] * len(ordered)
    axis.barh(positions, ordered[value], color=colours, height=0.72)
    if reference is not None:
        axis.axvline(reference, color=MUTED, lw=1.0, ls="--")

    axis.set_yticks(positions)
    axis.set_yticklabels(ordered[label])
    axis.set_xlabel(x_label)
    axis.grid(axis="y", visible=False)
    finish(fig, axis, title, subtitle, source)
    return save(fig, path)
