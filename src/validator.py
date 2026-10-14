
"""
Solution Validator and Evaluation Engine for Line Planning.
Evaluates line plans on edge coverage, capacity constraints, operating cost,
and passenger direct-connectivity service levels.
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass

from .parser import PTNInstance, Line
from .utils import effective_frequency_bounds, resolve_line_nodes


@dataclass
class ValidationReport:
    is_feasible: bool
    total_cost: float
    num_active_lines: int
    total_line_frequencies: int
    min_frequency_violations: List[Tuple[int, int, int]]
    max_frequency_violations: List[Tuple[int, int, int]]
    direct_travelers: float
    total_demand: float
    direct_traveler_percentage: float

    def summary(self) -> str:
        status = "FEASIBLE" if self.is_feasible else "INFEASIBLE"
        lines = [
            f"=== Line Plan Evaluation ({status}) ===",
            f"  Total Cost:                 {self.total_cost:.2f}",
            f"  Active Lines:               {self.num_active_lines}",
            f"  Total Line Frequencies:     {self.total_line_frequencies}",
            (
                f"  Direct Travelers:           "
                f"{self.direct_travelers:.1f} / {self.total_demand:.1f} "
                f"({self.direct_traveler_percentage:.2f}%)"
            ),
        ]

        if self.min_frequency_violations:
            lines.append(
                f"  [!] Under-served Edges "
                f"({len(self.min_frequency_violations)}): "
                f"{self.min_frequency_violations[:5]}..."
            )

        if self.max_frequency_violations:
            lines.append(
                f"  [!] Over-capacity Edges "
                f"({len(self.max_frequency_violations)}): "
                f"{self.max_frequency_violations[:5]}..."
            )

        return "\n".join(lines)


def evaluate_line_plan(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    frequencies: Dict[int, int],
    enforce_upper_bounds: bool = True,
) -> ValidationReport:
    """
    Evaluates a line plan given as line_id -> integer frequency.

    Active lines must consist of valid, contiguous edges and must not
    visit any stop more than once. Raises ValueError for invalid lines.
    """

    # 1. Check that every referenced line exists in the supplied pool.
    unknown = sorted(set(frequencies) - set(pool))

    if unknown:
        shown = unknown[:10]
        suffix = "..." if len(unknown) > len(shown) else ""
        raise ValueError(
            f"frequencies reference {len(unknown)} line id(s) "
            f"not in the supplied pool: {shown}{suffix}"
        )

    # 2. Validate every active line as a simple path.
    for l_id, frequency in frequencies.items():
        if frequency <= 0:
            continue

        line = pool[l_id]

        # Reject empty lines and references to nonexistent edges.
        if not line.edges or any(e_id not in ptn.edges for e_id in line.edges):
            raise ValueError(
                f"Line {l_id} contains invalid or empty edges"
            )

        # Resolve the ordered edges into their traversed node sequence.
        nodes = resolve_line_nodes(line.edges, ptn)

        if not nodes:
            raise ValueError(
                f"Line {l_id} is not a valid contiguous path"
            )

        # A simple path cannot visit the same stop more than once.
        if len(nodes) != len(set(nodes)):
            raise ValueError(
                f"Line {l_id} is not a simple path: repeated stops"
            )

    active_lines = {
        l_id: frequency
        for l_id, frequency in frequencies.items()
        if frequency > 0
    }

    total_cost = sum(
        pool[l_id].cost * frequency
        for l_id, frequency in active_lines.items()
    )
    total_freq = sum(active_lines.values())

    # 3. Calculate edge frequencies from active lines.
    edge_freq: Dict[int, int] = {
        e_id: 0 for e_id in ptn.edges
    }

    for l_id, frequency in active_lines.items():
        for e_id in pool[l_id].edges:
            edge_freq[e_id] += frequency

    min_violations = []
    max_violations = []

    for e_id in ptn.edges:
        actual_frequency = edge_freq[e_id]
        min_f, max_f = effective_frequency_bounds(
            ptn.loads.get(e_id)
        )

        if actual_frequency < min_f:
            min_violations.append(
                (e_id, actual_frequency, min_f)
            )

        if (
            enforce_upper_bounds
            and max_f > 0
            and actual_frequency > max_f
        ):
            max_violations.append(
                (e_id, actual_frequency, max_f)
            )

    is_feasible = (
        not min_violations and not max_violations
    )

    # 4. Calculate direct-traveler demand using the connectivity proxy.
    # Both stops must appear on the same active line.
    active_line_nodes = [
        set(resolve_line_nodes(pool[l_id].edges, ptn))
        for l_id in active_lines
    ]

    direct_demand = 0.0
    total_demand = ptn.total_demand

    for (orig, dest), demand in ptn.od_matrix.items():
        if demand <= 0:
            continue

        if any(
            orig in node_set and dest in node_set
            for node_set in active_line_nodes
        ):
            direct_demand += demand

    percentage = (
        direct_demand / total_demand * 100.0
        if total_demand > 0
        else 0.0
    )

    return ValidationReport(
        is_feasible=is_feasible,
        total_cost=total_cost,
        num_active_lines=len(active_lines),
        total_line_frequencies=total_freq,
        min_frequency_violations=min_violations,
        max_frequency_violations=max_violations,
        direct_travelers=direct_demand,
        total_demand=total_demand,
        direct_traveler_percentage=percentage,
    )
