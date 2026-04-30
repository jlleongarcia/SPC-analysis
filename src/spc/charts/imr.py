"""Plotly chart builders for Individual (I) and Moving Range (MR) charts.

All charts return a ``plotly.graph_objects.Figure`` so they integrate
seamlessly with ``st.plotly_chart()`` in Streamlit and can also be exported
to HTML / PNG for reports.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Colour palette (accessible, works on white backgrounds)
COLORS = {
    "data": "#1f77b4",          # blue — normal points
    "violation": "#d62728",     # red  — violated points
    "removed": "#aec7e8",       # light blue — previously removed (ghost)
    "cl": "#2ca02c",            # green — centre line
    "warning": "#ff7f0e",       # orange — warning lines
    "action": "#d62728",        # red — action/control limits
    "fill_warn": "rgba(255,127,14,0.08)",
    "fill_action": "rgba(214,39,40,0.06)",
}


def _limit_trace(y: float, x_range: list, name: str, color: str, dash: str = "dash") -> go.Scatter:
    return go.Scatter(
        x=x_range, y=[y, y],
        mode="lines",
        name=name,
        line={"color": color, "dash": dash, "width": 1.5},
        showlegend=True,
        hoverinfo="skip",
    )


def build_individuals_chart(
    values: pd.Series,
    limits: dict[str, float],
    violations: pd.DataFrame | None = None,
    removed_values: pd.Series | None = None,
    title: str = "Individuals (I) Chart",
) -> go.Figure:
    """Build an Individuals control chart.

    Parameters
    ----------
    values:
        Retained measurements (clean set for this iteration).
    limits:
        Dict from :func:`spc.core.limits.compute_limits`.
    violations:
        Optional DataFrame from :func:`spc.core.rules.apply_all_rules`.
        Violated points are highlighted in red.
    removed_values:
        Optional series of points removed in *previous* iterations.
        Displayed as faded markers for context.
    title:
        Chart title string.
    """
    fig = go.Figure()
    x = list(values.index)
    x_range = [x[0], x[-1]] if x else [0, 1]

    # ── Shaded zones ────────────────────────────────────────────────────────
    # Action zone (UCL / LCL fill)
    fig.add_hrect(y0=limits["i_uwl"], y1=limits["i_ucl"],
                  fillcolor=COLORS["fill_action"], line_width=0, layer="below")
    fig.add_hrect(y0=limits["i_lcl"], y1=limits["i_lwl"],
                  fillcolor=COLORS["fill_action"], line_width=0, layer="below")
    # Warning zone fill
    fig.add_hrect(y0=limits["i_cl"], y1=limits["i_uwl"],
                  fillcolor=COLORS["fill_warn"], line_width=0, layer="below")
    fig.add_hrect(y0=limits["i_lwl"], y1=limits["i_cl"],
                  fillcolor=COLORS["fill_warn"], line_width=0, layer="below")

    # ── Control lines ────────────────────────────────────────────────────────
    for y, name, color, dash in [
        (limits["i_ucl"], "UCL (Action)", COLORS["action"], "dash"),
        (limits["i_uwl"], "UWL (Warning)", COLORS["warning"], "dot"),
        (limits["i_cl"],  "CL (Mean)",    COLORS["cl"],      "solid"),
        (limits["i_lwl"], "LWL (Warning)", COLORS["warning"], "dot"),
        (limits["i_lcl"], "LCL (Action)", COLORS["action"], "dash"),
    ]:
        fig.add_trace(_limit_trace(y, x_range, name, color, dash))

    # ── Ghost points (previously removed) ────────────────────────────────────
    if removed_values is not None and not removed_values.empty:
        fig.add_trace(go.Scatter(
            x=list(removed_values.index),
            y=list(removed_values.values),
            mode="markers",
            name="Previously removed",
            marker={"color": COLORS["removed"], "size": 7, "symbol": "x"},
            opacity=0.5,
        ))

    # ── Data points ──────────────────────────────────────────────────────────
    if violations is not None:
        ok_mask = ~violations["any_violation"]
        viol_mask = violations["any_violation"]

        fig.add_trace(go.Scatter(
            x=list(values.index[ok_mask]),
            y=list(values.values[ok_mask]),
            mode="lines+markers",
            name="In control",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": COLORS["data"], "size": 7},
        ))
        if viol_mask.any():
            # Build hover text explaining which rules fired
            hover = []
            for idx in values.index[viol_mask]:
                rules = [r for r in ["rule1","rule2","rule3","rule4"]
                         if violations.loc[idx, r]]
                hover.append(f"Value: {values.loc[idx]:.4g}<br>Rules: {', '.join(rules)}")
            fig.add_trace(go.Scatter(
                x=list(values.index[viol_mask]),
                y=list(values.values[viol_mask]),
                mode="markers",
                name="Violation",
                marker={"color": COLORS["violation"], "size": 10, "symbol": "circle-open",
                        "line": {"width": 2, "color": COLORS["violation"]}},
                hovertext=hover,
                hoverinfo="text",
            ))
    else:
        fig.add_trace(go.Scatter(
            x=x, y=list(values.values),
            mode="lines+markers",
            name="Measurements",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": COLORS["data"], "size": 7},
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Observation",
        yaxis_title="Value",
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.3},
    )
    return fig


def build_mr_chart(
    mr_values: pd.Series,
    limits: dict[str, float],
    mr_violations: pd.Series | None = None,
    title: str = "Moving Range (MR) Chart",
) -> go.Figure:
    """Build a Moving Range control chart.

    Parameters
    ----------
    mr_values:
        Moving range series (first value is NaN by construction).
    limits:
        Dict from :func:`spc.core.limits.compute_limits`.
    mr_violations:
        Optional boolean Series where True marks MR > UCL.
    """
    fig = go.Figure()
    mr_clean = mr_values.dropna()
    x = list(mr_clean.index)
    x_range = [x[0], x[-1]] if x else [0, 1]

    # Action zone shading
    fig.add_hrect(y0=limits["mr_ucl"] * 0.9, y1=limits["mr_ucl"] * 1.1,
                  fillcolor=COLORS["fill_action"], line_width=0, layer="below")

    # Control lines
    fig.add_trace(_limit_trace(limits["mr_ucl"], x_range, "UCL (Action)", COLORS["action"]))
    fig.add_trace(_limit_trace(limits["mr_cl"],  x_range, "MR-bar (CL)", COLORS["cl"], "solid"))

    # Data
    if mr_violations is not None:
        viol = mr_violations.reindex(mr_clean.index).fillna(False)
        ok_mask = ~viol
        fig.add_trace(go.Scatter(
            x=list(mr_clean.index[ok_mask]),
            y=list(mr_clean.values[ok_mask]),
            mode="lines+markers",
            name="Moving Range",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": COLORS["data"], "size": 7},
        ))
        if viol.any():
            fig.add_trace(go.Scatter(
                x=list(mr_clean.index[viol]),
                y=list(mr_clean.values[viol]),
                mode="markers",
                name="MR Violation (Rule 1)",
                marker={"color": COLORS["violation"], "size": 10, "symbol": "circle-open",
                        "line": {"width": 2, "color": COLORS["violation"]}},
            ))
    else:
        fig.add_trace(go.Scatter(
            x=x, y=list(mr_clean.values),
            mode="lines+markers", name="Moving Range",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": COLORS["data"], "size": 7},
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Observation",
        yaxis_title="Moving Range",
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.3},
    )
    return fig


def build_imr_panel(
    values: pd.Series,
    mr_values: pd.Series,
    limits: dict[str, float],
    violations: pd.DataFrame | None = None,
    mr_violations: pd.Series | None = None,
    removed_values: pd.Series | None = None,
    title: str = "I-MR Chart",
) -> go.Figure:
    """Combine I and MR charts into a single stacked figure (2 rows)."""
    i_fig = build_individuals_chart(values, limits, violations, removed_values,
                                    title=f"{title} — Individuals")
    mr_fig = build_mr_chart(mr_values, limits, mr_violations,
                             title=f"{title} — Moving Range")

    combined = make_subplots(
        rows=2, cols=1,
        subplot_titles=[f"{title} — Individuals", f"{title} — Moving Range"],
        vertical_spacing=0.12,
        shared_xaxes=True,
    )

    for trace in i_fig.data:
        combined.add_trace(trace, row=1, col=1)
    for trace in mr_fig.data:
        combined.add_trace(trace, row=2, col=1)

    # Add shapes (hrect) from both figures
    shapes = []
    for shape in list(i_fig.layout.shapes or []):
        s = shape.to_plotly_json()
        s["yref"] = "y"
        s["xref"] = "x"
        shapes.append(s)
    for shape in list(mr_fig.layout.shapes or []):
        s = shape.to_plotly_json()
        s["yref"] = "y2"
        s["xref"] = "x2"
        shapes.append(s)
    combined.update_layout(shapes=shapes)

    combined.update_layout(
        template="plotly_white",
        hovermode="x unified",
        height=700,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25},
    )
    combined.update_yaxes(title_text="Value", row=1, col=1)
    combined.update_yaxes(title_text="Moving Range", row=2, col=1)
    combined.update_xaxes(title_text="Observation", row=2, col=1)
    return combined
