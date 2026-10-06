"""
Run the LNS heuristic on a LinTim instance and compare with the baseline MIP.
Usage: python scripts/run_lns.py mandl --time 10 --seeds 5 --start greedy
       --start in {greedy, bad, mip}
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.parser import load_ptn
from src.pool_generator import generate_line_pool
from src.validator import evaluate_line_plan
from src.models.cost_mip import solve_cost_mip
from src.heuristics.lns import build_problem, lns, random_start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--time", type=float, default=10.0)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--start", choices=["greedy", "bad", "mip"], default="greedy")
    ap.add_argument("--max-edges", type=int, default=6)
    ap.add_argument("--k-paths", type=int, default=2)
    args = ap.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    base = os.path.join(root, "data")
    ptn = load_ptn(os.path.join(base, args.dataset), os.path.join(base, "Global-Config.cnf"))
    # Same pool logic as run_baseline.py: given pool if present, else generate.
    # (For the final report, copy the exact pool settings from run_benchmarks.py.)
    pool = ptn.pool if ptn.pool else generate_line_pool(
        ptn, min_edges=2, max_edges=args.max_edges, k_paths_per_pair=args.k_paths)
    print(f"{ptn.name}: {ptn.num_stops} stops, {ptn.num_edges} edges, {len(pool)} lines")

    mip_freqs, mip_obj, mip_t, mip_status, mip_gap = solve_cost_mip(ptn, pool, integer=True)
    print(f"MIP: {mip_status}, cost {mip_obj:.2f}, {mip_t:.2f}s, gap {mip_gap:.2%}")

    P = build_problem(ptn, pool)
    rows, best_run = [], None
    for seed in range(args.seeds):
        #y0 = {"greedy": None, "bad": random_start(P, seed), "mip": dict(mip_freqs)}[args.start]
        if args.start == "greedy":
            y0 = None
        elif args.start == "bad":
            y0 = random_start(P, seed)
        else:
            y0 = dict(mip_freqs)
        best, hist, stats = lns(P, y0=y0, time_limit=args.time, seed=seed)
        rep = evaluate_line_plan(ptn, pool, best)        # validator = source of truth
        assert rep.is_feasible, f"seed {seed}: validator says INFEASIBLE"
        gap = (rep.total_cost - mip_obj) / mip_obj * 100
        rows.append(rep.total_cost)
        print(f"seed {seed}: cost {rep.total_cost:.2f}  gap vs MIP {gap:+.2f}%  "
              f"iters {stats['iters']}  repair_fail {stats['repair_fail']}  "
              f"direct {rep.direct_traveler_percentage:.1f}%")
        if best_run is None or rep.total_cost < best_run["cost"]:
            best_run = {"seed": seed, "cost": rep.total_cost, "history": hist,
                        "freqs": best, "stats": stats}

    mean = statistics.mean(rows)
    print(f"\nLNS mean {mean:.2f} | best {min(rows):.2f} | MIP {mip_obj:.2f} | "
          f"mean gap {(mean - mip_obj) / mip_obj * 100:+.2f}%")

    out = os.path.join(root, "results", f"lns_{ptn.name}_{args.start}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"dataset": ptn.name, "start": args.start, "time_limit": args.time,
                   "mip_obj": mip_obj, "mip_status": mip_status,
                   "lns_costs": rows, "best_run": best_run}, f, indent=2)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()