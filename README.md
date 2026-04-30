# SPC Analysis

**Statistical Process Control — Phase I retrospective baseline establishment**  
for Individual (I) and Moving Range (MR) charts.

---

## What this tool does

Establishes verified SPC control limits from historical process data by iteratively
identifying and removing out-of-control observations until only a stable, in-control
baseline remains. It then computes process capability indices (Cp, Cpk, Pp, Ppk) and
provides a full audit trail of every removal decision.

This is **Phase I SPC** — the foundation step before deploying Phase II (ongoing monitoring).

---

## Requirements

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) — dependency and environment manager

No other prerequisites. `uv` handles everything else.

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/spc-analysis.git
cd spc-analysis

# 2. Create environment and install dependencies (one command)
uv sync

# 3. Launch the application
uv run streamlit run app.py
```

The app opens automatically at `http://localhost:8501`.

---

## Development setup

```bash
# Install with dev extras (pytest, ruff)
uv sync --extra dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/spc --cov-report=term-missing

# Lint
uv run ruff check src/ tests/
```

---

## Project structure

```
spc-analysis/
├── app.py                  # Streamlit entry point
├── pyproject.toml          # Project metadata and dependencies (uv)
├── pages/
│   ├── 01_data_import.py   # Step 1 — upload CSV / Excel
│   ├── 02_phase_i.py       # Step 2 — iterative SPC loop
│   ├── 03_final_charts.py  # Step 3 — final I-MR charts
│   ├── 04_capability.py    # Step 4 — Cp, Cpk, Pp, Ppk
│   └── 05_audit_trail.py   # Step 5 — removal audit trail
├── src/spc/
│   ├── core/
│   │   ├── limits.py       # Control limit formulas (I-MR)
│   │   ├── rules.py        # Four SPC rule detectors
│   │   ├── capability.py   # Cp, Cpk, Pp, Ppk, RPI
│   │   ├── normality.py    # Shapiro-Wilk / Anderson-Darling pre-check
│   │   └── phase_i.py      # Iterative Phase I engine
│   └── charts/
│       └── imr.py          # Plotly I and MR chart builders
├── tests/
│   └── test_spc_core.py    # Unit tests for all core modules
├── data/examples/          # Example datasets (place CSV/Excel here)
└── docs/
    └── methodology.md      # Full methodology documentation
```

---

## Typical workflow

1. **Data Import** — Upload a CSV or Excel file. Select the measurement column.
2. **Phase I Study** — Configure rule thresholds and run the iterative loop.
3. **Final Charts** — Inspect the clean I-MR charts with verified limits.
4. **Capability** — Enter USL/LSL to get Cp, Cpk, Pp, Ppk, and RPI.
5. **Audit Trail** — Export the removal log for your QMS documentation.

---

## The four SPC rules

| Rule | Name | Condition (defaults) |
|------|------|----------------------|
| 1 | Action Limits | Any point outside UCL or LCL (±3σ) |
| 2 | Warning Zone | 2 of 3 consecutive points beyond ±2σ on the same side |
| 3 | Run | 8 or more consecutive points on the same side of the centre line |
| 4 | Trend | 6 or more consecutive points strictly rising or falling |

All thresholds are configurable in the UI.

---

## Capability indices

| Index | Measures |
|-------|---------|
| Cp | Potential capability — spread vs. tolerance (σ_within) |
| Cpk | Potential capability — spread AND centring |
| Pp | Actual performance — spread vs. tolerance (σ_overall) |
| Ppk | Actual performance — spread AND centring |
| RPI | Relative Precision Index = Cp |

Enterprise minimum: **Cpk ≥ 1.33**. Critical characteristics: Cpk ≥ 1.67.

---

## Enterprise / quality management notes

- Every removed data point is logged with the rule(s) that flagged it.
- Iteration is capped (default: 10) to prevent over-pruning.
- The audit trail CSV is suitable for attachment to a PPAP, control plan, or GMP record.
- A **normality pre-check** (Shapiro-Wilk) is run before interpreting limits.
- `uv.lock` ensures bit-for-bit reproducible installs on any machine.

---

## License

MIT
