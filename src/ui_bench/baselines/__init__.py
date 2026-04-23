"""Non-LLM baselines used to validate that ui-bench is not trivial."""

from ui_bench.baselines.empty_baseline import EmptyProgramAdapter
from ui_bench.baselines.heuristic_baseline import HeuristicCVAdapter

__all__ = ["EmptyProgramAdapter", "HeuristicCVAdapter"]
