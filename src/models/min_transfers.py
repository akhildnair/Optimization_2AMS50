"""RQ3: Maximize passenger demand served by direct lines."""

from typing import Dict
import gurobipy as gp
from gurobipy import GRB

from ..parser import PTNInstance, Line
from ..utils import effective_frequency_bounds


def solve_min_transfers(
    ptn: PTNInstance,
    pool: Dict[int, Line],
    time_limit: float = 60.0,
):
    """Maximize OD demand served directly by at least one selected line."""

    model = gp.Model("RQ3_MinTransfers")
    model.Params.TimeLimit = time_limit
    model.Params.OutputFlag = 0

    # Frequency of each candidate line and whether it is active.
    f = {
        l_id: model.addVar(
            vtype=GRB.INTEGER, lb=0, name=f"freq_{l_id}"
        )
        for l_id in pool
    }

    active = {
        l_id: model.addVar(
            vtype=GRB.BINARY, name=f"active_{l_id}"
        )
        for l_id in pool
    }

    # y[o,d] = 1 if at least one active line serves this OD pair directly.
    direct = {
        od: model.addVar(vtype=GRB.BINARY, name=f"direct_{od[0]}_{od[1]}")
        for od, demand in ptn.od_matrix.items()
        if demand > 0
    }

    # Link line frequency to line activation.
    for l_id in pool:
        model.addConstr(f[l_id] >= active[l_id])
        model.addConstr(f[l_id] <= len(ptn.edges) * active[l_id])

    # Satisfy edge-frequency bounds.
    for e_id, edge in ptn.edges.items():
        covering = [
            f[l_id] for l_id, line in pool.items()
            if e_id in line.edges
        ]
        min_f, max_f = effective_frequency_bounds(
             ptn.loads.get(e_id)
        )

        if covering:
            edge_freq = gp.quicksum(covering)
            if min_f > 0:
                model.addConstr(edge_freq >= min_f)
            if max_f > 0:
                model.addConstr(edge_freq <= max_f)
        elif min_f > 0:
            raise ValueError(
                f"Edge {e_id} requires frequency {min_f}, "
                "but no candidate line covers it."
            )

    # Link direct-service variables to active lines.
    for (origin, destination), y in direct.items():
        eligible = [
            active[l_id]
            for l_id, line in pool.items()
            if origin in line.nodes and destination in line.nodes
        ]

        if eligible:
            model.addConstr(y <= gp.quicksum(eligible))
        else:
            model.addConstr(y == 0)


    # Stage 1: Maximize the total demand served by direct lines.
    direct_demand_expr = gp.quicksum(
        ptn.od_matrix[od] * direct[od]
        for od in direct
    )

    model.setObjective(direct_demand_expr, GRB.MAXIMIZE)
    model.optimize()

    if model.SolCount == 0:
        return {
            "status": model.Status,
            "direct_passengers": None,
            "objective": None,
            "frequencies": {},
        }

    # Store the best direct-service level from Stage 1.
    best_direct_demand = model.ObjVal

    # Stage 2: Preserve the best service level and minimize cost.
    model.addConstr(
        direct_demand_expr >= best_direct_demand - 1e-6,
        name="preserve_best_direct_service",
    )

    total_cost_expr = gp.quicksum(
        pool[l_id].cost * f[l_id]
        for l_id in pool
    )

    model.setObjective(total_cost_expr, GRB.MINIMIZE)
    model.optimize()

    if model.SolCount == 0:
        return {
            "status": model.Status,
            "direct_passengers": best_direct_demand,
            "objective": None,
            "frequencies": {},
        }

    frequencies = {
        l_id: int(round(f[l_id].X))
        for l_id in pool
        if f[l_id].X > 0.5
    }

    return {
        "status": model.Status,
        "direct_passengers": sum(
            ptn.od_matrix[od] * direct[od].X
            for od in direct
        ),
        "objective": model.ObjVal,
        "total_cost": model.ObjVal,
        "frequencies": frequencies,
    }
