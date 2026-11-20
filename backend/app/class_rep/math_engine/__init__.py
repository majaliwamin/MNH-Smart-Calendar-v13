"""Deterministic mathematics, statistics and biostatistics engine for CRARA.

This package is additive to the existing conversational pipeline. It returns
structured, verified computation records that the language layer may explain,
but never invents numerical results itself.
"""
from .results import MathResult, blocked_result
from .engine import solve, detect_math_request, capabilities

__all__ = ["MathResult", "blocked_result", "solve", "detect_math_request", "capabilities"]
