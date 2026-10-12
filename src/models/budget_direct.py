
"""Budget-constrained line planning that maximizes direct-traveler demand."""

from math import floor

from pyscipopt import Model, quicksum

from src.utils import effective_frequency_bounds
from src.parser import PTNInstance, Line


def solve_budget_direct(
    ptn: PTNInstance,
    pool: dict[int, Line],
    budget: float,
    time_limit: float = 60.0,
):
    """Maximize directly served OD demand under a fixed operating budget."""

    if budget < 0:
        raise ValueError("Budget must be non-negative.")

    if not pool:
        raise ValueError("Candidate line pool cannot be empty.")

    # Each line needs a positive cost to calculate a budget-based
    # upper bound on its operating frequency.
    for line in pool.values():
        if line.cost <= 0:
            raise ValueError(
                f"Line {line.id} must have a positive operating cost."
            )

    model = Model("budget_direct")
    model.hideOutput()
    model.setRealParam("limits/time", time_limit)

    # Maximum possible frequency of each line under the budget.
    max_freq = {
        line_id: floor((budget + 1e-9) / line.cost)
        for line_id, line in pool.items()
    }

    # f_l: integer frequency; x_l: 1 if the line is active.
    f = {
        line_id: model.addVar(
            name=f"f_{line_id}",
            vtype="I",
            lb=0,
            ub=max_freq[line_id],
        )
        for line_id in pool
    }

    x = {
        line_id: model.addVar(
            name=f"x_{line_id}",
            vtype="B",
        )
        for line_id in pool
    }

    # A line is active exactly when its frequency is positive.
    for line_id in pool:
        model.addCons(x[line_id] <= f[line_id])
        model.addCons(
            f[line_id] <= max_freq[line_id] * x[line_id]
        )

    # Total operating cost cannot exceed the budget.
    model.addCons(
        quicksum(
            pool[line_id].cost * f[line_id]
            for line_id in pool
        ) <= budget
    )

    # Preserve all mandatory edge-frequency requirements.
    for edge_id in ptn.edges:
        min_f, max_f = effective_frequency_bounds(
            ptn.loads.get(edge_id)
        )

        covering_lines = [
            line_id
            for line_id, line in pool.items()
            if edge_id in line.edges
        ]

        if min_f > 0:
            model.addCons(
                quicksum(f[line_id] for line_id in covering_lines)
                >= min_f
            )

        # A maximum of 0 means there is no upper frequency bound.
        if max_f > 0:
            model.addCons(
                quicksum(f[line_id] for line_id in covering_lines)
                <= max_f
            )

    # Find candidate lines that directly serve each OD pair.
    direct_lines = {}
    demand = {}

    for (origin, destination), passengers in ptn.od_matrix.items():
        if passengers <= 0:
            continue

        candidates = [
            line_id
            for line_id, line in pool.items()
            if origin in line.nodes and destination in line.nodes
        ]

        if candidates:
            direct_lines[(origin, destination)] = candidates
            demand[(origin, destination)] = passengers

    # y_od = 1 if an active line provides direct service to the OD pair.
    y = {
        od: model.addVar(
            name=f"direct_{od[0]}_{od[1]}",
            vtype="B",
        )
        for od in direct_lines
    }

    for od, candidates in direct_lines.items():
        model.addCons(
            y[od] <= quicksum(x[line_id] for line_id in candidates)
        )

    # Maximize passenger demand served directly.
    model.setObjective(
        quicksum(demand[od] * y[od] for od in y),
        "maximize",
    )

    model.optimize()
    status = str(model.getStatus())

    result = {
        "status": status,
        "budget": budget,
        "objective": None,
        "frequencies": {},
        "active_lines": [],
    }

    if status == "optimal":
        frequencies = {
            line_id: int(round(model.getVal(var)))
            for line_id, var in f.items()
        }

        result["objective"] = model.getObjVal()
        result["frequencies"] = frequencies
        result["active_lines"] = [
            line_id for line_id, freq in frequencies.items() if freq > 0
        ]

    return result
