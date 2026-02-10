"""Analysis and visualization package for benchmark results."""

from bench.analysis.load import load_results
from bench.analysis.pareto import compute_pareto_frontier
from bench.analysis.report import generate_html_report

__all__ = ["load_results", "compute_pareto_frontier", "generate_html_report"]
