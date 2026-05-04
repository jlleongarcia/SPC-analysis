"""Core package exports."""

from spc.core.limits import compute_limits, compute_moving_range
from spc.core.rules import apply_all_rules, apply_mr_rule1, apply_mr_rules
from spc.core.capability import compute_capability
from spc.core.normality import normality_check
from spc.core.phase_i import run_phase_i_pass, PassResult, PhaseIResult

__all__ = [
    "compute_limits",
    "compute_moving_range",
    "apply_all_rules",
    "apply_mr_rule1",
    "apply_mr_rules",
    "compute_capability",
    "normality_check",
    "run_phase_i_pass",
    "PassResult",
    "PhaseIResult",
]
