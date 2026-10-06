"""
Large Neighbourhood Search (LNS) with simulated-annealing acceptance for the
cost-minimising line planning problem (Model A / baseline MIP).

Solution = frequency vector y: line_id -> integer >= 0.
Feasible  <=>  for every edge e:  lo[e] <= sum_{l ∋ e} y[l] <= hi[e]
(lo/hi come from utils.effective_frequency_bounds, the same source the MIP and
validator use; hi = INF when the ceiling is not enforced).
"""
import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..parser import PTNInstance, Line
from ..utils import (
    effective_frequency_bounds,
    uncovered_required_edges,
    IncompletePoolError,
)

INF = 10**9
Freq = Dict[int, int]


@dataclass
class Problem:
    line_edges: Dict[int, Tuple[int, ...]]   # line_id -> edge ids
    line_cost: Dict[int, float]              # line_id -> cost per unit frequency
    lo: Dict[int, int]                       # edge_id -> required frequency
    hi: Dict[int, int]                       # edge_id -> max frequency (INF = none)
    weight: Dict[int, float]                 # edge_id -> demand weight for repair


def build_problem(ptn: PTNInstance, pool: Dict[int, Line]) -> Problem:
    """Mirror of the constraints built in models/cost_mip.py."""
    uncovered = uncovered_required_edges(ptn, pool)
    if uncovered:
        raise IncompletePoolError(uncovered)
    lo, hi, weight = {}, {}, {}
    for e_id, edge in ptn.edges.items():
        min_f, max_f = effective_frequency_bounds(edge, ptn.loads.get(e_id))
        lo[e_id] = min_f
        hi[e_id] = max_f if max_f > 0 else INF
        load = ptn.loads[e_id][0] if e_id in ptn.loads else 0.0
        weight[e_id] = 1.0 + load            # +1 so zero-load edges still count
    return Problem(
        line_edges={l: tuple(line.edges) for l, line in pool.items()},
        line_cost={l: line.cost for l, line in pool.items()},
        lo=lo, hi=hi, weight=weight,
    )


# ----------------------------------------------------------------- basics
def coverage(P: Problem, y: Freq) -> Dict[int, int]:
    cov = {e: 0 for e in P.lo}
    for l, v in y.items():
        for e in P.line_edges[l]:
            cov[e] += v
    return cov


def cost(P: Problem, y: Freq) -> float:
    return sum(P.line_cost[l] * v for l, v in y.items())


def feasible(P: Problem, y: Freq) -> bool:
    cov = coverage(P, y)
    return all(P.lo[e] <= cov[e] <= P.hi[e] for e in P.lo)


def _remove_unit(y: Freq, l: int) -> None:
    y[l] -= 1
    if y[l] == 0:
        del y[l]


# -------------------------------------------------------- destroy operators
def destroy_random(P: Problem, y: Freq, k: int, rng: random.Random) -> Freq:
    """Remove k uniformly random units of frequency."""
    y = dict(y)
    units = [l for l, v in y.items() for _ in range(v)]
    for l in rng.sample(units, min(k, len(units))):
        _remove_unit(y, l)
    return y


def destroy_costly(P: Problem, y: Freq, k: int, rng: random.Random) -> Freq:
    """Roulette-wheel removal, probability proportional to line cost
    (randomised so the same expensive line is not always removed)."""
    y = dict(y)
    for _ in range(k):
        if not y:
            break
        lines = list(y)
        l = rng.choices(lines, weights=[P.line_cost[x] for x in lines])[0]
        _remove_unit(y, l)
    return y


def destroy_related(P: Problem, y: Freq, k: int, rng: random.Random) -> Freq:
    """Pick a random active line and remove units from lines that share edges
    with it (a geographically coherent neighbourhood)."""
    y = dict(y)
    if not y:
        return y
    seed = rng.choice(list(y))
    seed_edges = set(P.line_edges[seed])
    related = [l for l in y if seed_edges & set(P.line_edges[l])]
    rng.shuffle(related)
    removed = 0
    while removed < k and related:
        for l in list(related):
            if removed >= k:
                break
            if l in y:
                _remove_unit(y, l)
                removed += 1
            if l not in y:
                related.remove(l)
    return y


# ---------------------------------------------------------------- repair
def repair_greedy(P: Problem, y: Freq, rng: random.Random,
                  noise: float = 0.1) -> Optional[Freq]:
    """
    Greedy demand-covering insertion: while some edge is below lo, add one unit
    of the line with best (demand weight of deficit edges covered) / cost,
    skipping lines that would push an edge above hi. Returns None on failure.
    """
    y = dict(y)
    cov = coverage(P, y)
    while True:
        deficit = {e for e in P.lo if cov[e] < P.lo[e]}
        if not deficit:
            return y
        best_l, best_score = None, 0.0
        for l, edges in P.line_edges.items():
            gain = 0.0
            ok = True
            for e in edges:
                if cov[e] + 1 > P.hi[e]:
                    ok = False
                    break
                if e in deficit:
                    gain += P.weight[e]
            if not ok or gain == 0.0:
                continue
            score = gain / P.line_cost[l] * (1.0 + noise * rng.random())
            if score > best_score:
                best_l, best_score = l, score
        if best_l is None:
            return None
        y[best_l] = y.get(best_l, 0) + 1
        for e in P.line_edges[best_l]:
            cov[e] += 1


def cleanup(P: Problem, y: Freq) -> Freq:
    """Drop redundant units (most expensive line first)."""
    y = dict(y)
    cov = coverage(P, y)
    for l in sorted(list(y), key=lambda x: -P.line_cost[x]):
        while y.get(l, 0) > 0 and all(cov[e] - 1 >= P.lo[e] for e in P.line_edges[l]):
            y[l] -= 1
            for e in P.line_edges[l]:
                cov[e] -= 1
        if y.get(l) == 0:
            del y[l]
    return y


def random_start(P: Problem, seed: int = 0) -> Freq:
    """Deliberately poor feasible solution (very noisy greedy, no cleanup),
    for testing whether LNS can recover towards the optimum."""
    y = repair_greedy(P, {}, random.Random(seed), noise=50.0)
    if y is None:
        raise RuntimeError("could not build a feasible random start")
    return y


# ------------------------------------------------------------------- LNS
def lns(P: Problem, y0: Optional[Freq] = None, time_limit: float = 30.0,
        seed: int = 0, T_start: float = 0.02, T_end: float = 0.0005,
        max_iters: Optional[int] = None,
        ) -> Tuple[Freq, List[Tuple[float, float]], Dict[str, int]]:
    """
    Returns (best_solution, history, stats).
    history = [(seconds, best_cost)] at each improvement (anytime curve).
    Temperature is relative to the start cost and cools geometrically over the
    *time budget* (T_start -> T_end), so it works for any instance size.
    """
    rng = random.Random(seed)
    cur = y0 if y0 is not None else repair_greedy(P, {}, rng, noise=0.0)
    if cur is None or not feasible(P, cur):
        raise RuntimeError("No feasible start; pass y0 (baseline MIP / Student 4)")
    cur = dict(cur)
    cur_cost = cost(P, cur)
    best, best_cost = dict(cur), cur_cost
    scale = cur_cost
    ops = [destroy_random, destroy_costly, destroy_related]

    t0 = time.perf_counter()
    history = [(0.0, best_cost)]
    stats = {"iters": 0, "repair_fail": 0, "accepted": 0, "improved": 0}

    while True:
        elapsed = time.perf_counter() - t0
        if elapsed >= time_limit or (max_iters and stats["iters"] >= max_iters):
            break
        stats["iters"] += 1
        T = scale * T_start * (T_end / T_start) ** (elapsed / time_limit)

        total = sum(cur.values())
        k = rng.randint(1, max(1, total // 4))
        partial = rng.choice(ops)(P, cur, k, rng)
        new = repair_greedy(P, partial, rng)
        if new is None:
            stats["repair_fail"] += 1
            continue
        new = cleanup(P, new)
        new_cost = cost(P, new)
        d = new_cost - cur_cost
        if d <= 0 or rng.random() < math.exp(-d / T):
            cur, cur_cost = new, new_cost
            stats["accepted"] += 1
            if cur_cost < best_cost - 1e-9:
                best, best_cost = dict(cur), cur_cost
                stats["improved"] += 1
                history.append((time.perf_counter() - t0, best_cost))
    history.append((time.perf_counter() - t0, best_cost))
    return best, history, stats