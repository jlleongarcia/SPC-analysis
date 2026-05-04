"""Plotly chart builders for Individual (I) and Moving Range (MR) charts.

All charts return a ``plotly.graph_objects.Figure`` so they integrate
seamlessly with ``st.plotly_chart()`` in Streamlit and can also be exported
to HTML / PNG for reports.
"""

from __future__ import annotations

import numpy as np
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
    "fill_ctrl": "rgba(44,160,44,0.08)",    # green  — control zone  (CL ↔ WL)
    "fill_warn": "rgba(255,127,14,0.10)",   # orange — warning zone  (WL ↔ AL)
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
    n_points: int | None = None,
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

    # ── Stats legend entries ────────────────────────────────────────────────
    _n = n_points if n_points is not None else int(values.notna().sum())
    _s = float(values.dropna().std(ddof=1))
    for _name in [
        f"n = {_n}",
        f"X̄ = {limits['i_cl']:.4f}",
        f"s = {_s:.4f}",
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker={"opacity": 0, "size": 1},
            showlegend=True, name=_name,
        ))

    x = list(values.index)
    x_range = [x[0], x[-1]] if x else [0, 1]

    # ── Shaded zones ────────────────────────────────────────────────────────
    # Warning zone (between WL and AL) — orange
    fig.add_hrect(y0=limits["i_uwl"], y1=limits["i_ucl"],
                  fillcolor=COLORS["fill_warn"], line_width=0, layer="below")
    fig.add_hrect(y0=limits["i_lcl"], y1=limits["i_lwl"],
                  fillcolor=COLORS["fill_warn"], line_width=0, layer="below")
    # Control zone (between CL and WL) — green
    fig.add_hrect(y0=limits["i_cl"], y1=limits["i_uwl"],
                  fillcolor=COLORS["fill_ctrl"], line_width=0, layer="below")
    fig.add_hrect(y0=limits["i_lwl"], y1=limits["i_cl"],
                  fillcolor=COLORS["fill_ctrl"], line_width=0, layer="below")

    # ── Control lines ────────────────────────────────────────────────────────
    for y, name, color, dash in [
        (limits["i_ucl"], f"UAL = {limits['i_ucl']:.4f}",              COLORS["action"],  "dash"),
        (limits["i_uwl"], f"UWL = {limits['i_uwl']:.4f}",              COLORS["warning"], "dot"),
        (limits["i_cl"],  f"CL = X̄ = {limits['i_cl']:.4f}",           COLORS["cl"],      "solid"),
        (limits["i_lwl"], f"LWL = {limits['i_lwl']:.4f}",              COLORS["warning"], "dot"),
        (limits["i_lcl"], f"LAL = {limits['i_lcl']:.4f}",              COLORS["action"],  "dash"),
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
    # Always draw one continuous line through ALL points in order so the
    # chronological sequence is preserved regardless of violation status.
    if violations is not None:
        viol_mask = violations["any_violation"].to_numpy(dtype=bool)

        # Continuous line + all markers (coloured per status)
        marker_colors = [
            COLORS["violation"] if v else COLORS["data"] for v in viol_mask
        ]
        fig.add_trace(go.Scatter(
            x=x,
            y=list(values.values),
            mode="lines+markers",
            name="In control",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": marker_colors, "size": 7},
        ))

        # Overlay open-circle violation markers with hover text
        if viol_mask.any():
            rule_cols = ["rule1", "rule2", "rule3", "rule4"]
            viol_arr = violations[rule_cols].to_numpy()
            vals_arr = values.to_numpy()
            viol_x, viol_y, hover = [], [], []
            for pos, is_viol in enumerate(viol_mask):
                if not is_viol:
                    continue
                viol_x.append(x[pos])
                viol_y.append(float(vals_arr[pos]))
                rules = [rule_cols[j] for j in range(4) if bool(viol_arr[pos, j])]
                hover.append(f"Value: {vals_arr[pos]:.4g}<br>Rules: {', '.join(rules)}")
            fig.add_trace(go.Scatter(
                x=viol_x,
                y=viol_y,
                mode="markers",
                name="Violation",
                marker={"color": COLORS["violation"], "size": 12, "symbol": "circle-open",
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
        xaxis=dict(
            title="Observation",
            type="category",
            categoryorder="array",
            categoryarray=x,
            tickangle=-45,
            nticks=20,
            automargin=True,
        ),
        yaxis_title="Value",
        hovermode="x unified",
        template="plotly_white",
        legend={
            "orientation": "v",
            "xanchor": "left", "x": 1.02,
            "yanchor": "top", "y": 1.0,
        },
        margin={"r": 200},
    )
    return fig


def build_mr_chart(
    mr_values: pd.Series,
    limits: dict[str, float],
    mr_violations: pd.Series | None = None,
    title: str = "Moving Range (MR) Chart",
    n_points: int | None = None,
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

    # ── Stats legend entries ────────────────────────────────────────────────
    _n_mr = n_points if n_points is not None else int(mr_values.notna().sum())
    for _name in [
        f"n = {_n_mr}",
        f"MR̄ = {limits['mr_cl']:.4f}",
        f"σ̂ within = {limits['sigma_within']:.4f}",
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker={"opacity": 0, "size": 1},
            showlegend=True, name=_name,
        ))

    mr_clean = mr_values.dropna()
    x = list(mr_clean.index)
    x_range = [x[0], x[-1]] if x else [0, 1]

    # Action zone shading (above UWL to UCL — capped at UAL)
    fig.add_hrect(y0=limits["mr_uwl"], y1=limits["mr_ucl"],
                  fillcolor=COLORS["fill_warn"], line_width=0, layer="below")
    # Control zone shading (CL to UWL) — green
    fig.add_hrect(y0=limits["mr_cl"], y1=limits["mr_uwl"],
                  fillcolor=COLORS["fill_ctrl"], line_width=0, layer="below")

    # Control lines
    fig.add_trace(_limit_trace(limits["mr_ucl"], x_range, f"UAL = {limits['mr_ucl']:.4f}", COLORS["action"]))
    fig.add_trace(_limit_trace(limits["mr_uwl"], x_range, f"UWL = {limits['mr_uwl']:.4f}", COLORS["warning"], "dot"))
    fig.add_trace(_limit_trace(limits["mr_cl"],  x_range, f"CL = MR̄ = {limits['mr_cl']:.4f}", COLORS["cl"], "solid"))

    # Data
    if mr_violations is not None:
        # Align violations to mr_clean (dropna removes the first NaN by construction).
        valid_pos = mr_values.notna().to_numpy()
        viol_full = mr_violations.to_numpy(dtype=bool)
        viol_np = viol_full[valid_pos] if len(viol_full) == len(valid_pos) else np.zeros(len(mr_clean), dtype=bool)

        # One continuous line through all MR points in order
        marker_colors = [
            COLORS["violation"] if v else COLORS["data"] for v in viol_np
        ]
        fig.add_trace(go.Scatter(
            x=x,
            y=list(mr_clean.values),
            mode="lines+markers",
            name="Moving Range",
            line={"color": COLORS["data"], "width": 1.5},
            marker={"color": marker_colors, "size": 7},
        ))
        if viol_np.any():
            viol_x = [x[i] for i, v in enumerate(viol_np) if v]
            viol_y = [float(mr_clean.iloc[i]) for i, v in enumerate(viol_np) if v]
            fig.add_trace(go.Scatter(
                x=viol_x,
                y=viol_y,
                mode="markers",
                name="MR Violation (Rules 1/2)",
                marker={"color": COLORS["violation"], "size": 12, "symbol": "circle-open",
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
        xaxis=dict(
            title="Observation",
            type="category",
            categoryorder="array",
            categoryarray=x,
            tickangle=-45,
            nticks=20,
            automargin=True,
        ),
        yaxis_title="Moving Range",
        hovermode="x unified",
        template="plotly_white",
        legend={
            "orientation": "v",
            "xanchor": "left", "x": 1.02,
            "yanchor": "top", "y": 1.0,
        },
        margin={"r": 200},
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
    combined.update_xaxes(
        title_text="Observation",
        type="category",
        tickangle=-45,
        nticks=20,
        automargin=True,
        row=2, col=1,
    )
    combined.update_xaxes(
        type="category",
        tickangle=-45,
        nticks=20,
        automargin=True,
        row=1, col=1,
    )
    return combined
