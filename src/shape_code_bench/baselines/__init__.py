"""Non-LLM baselines used to validate that ShapeCodeBench is not trivial."""

from shape_code_bench.baselines.empty_baseline import EmptyProgramAdapter
from shape_code_bench.baselines.heuristic_baseline import HeuristicCVAdapter

__all__ = ["EmptyProgramAdapter", "HeuristicCVAdapter"]
