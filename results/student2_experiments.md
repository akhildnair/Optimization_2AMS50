# Student 2 — Optimization Project Results

Dataset: Mandl
Candidate line pool: 154 lines

## 1. Baseline MIP and LP Relaxation

| Metric | Result |
|---|---:|
| LP relaxation objective | 1905.7911 |
| Integer MIP objective | 1933.32 |
| Absolute LP-IP gap | 27.5289 |
| Relative LP-IP gap | 1.42% |
| Baseline MIP status | Optimal |

## 2. RQ2 — Budget-Constrained Direct Service

| Budget | Actual Cost | Direct Passengers | Service |
|---:|---:|---:|---:|
| 1933.32 | 1933.32 | 13250 | 85.10% |
| 1940 | 1935.60 | 14800 | 95.05% |
| 1950 | 1936.65 | 14800 | 95.05% |
| 1960 | 1936.47 | 14800 | 95.05% |
| 1970 | 1935.66 | 14800 | 95.05% |
| 1980 | 1935.60 | 14800 | 95.05% |
| 1990 | 1985.88 | 15340 | 98.52% |
| 2000 | 1985.97 | 15340 | 98.52% |
| 2010 | 1986.69 | 15340 | 98.52% |
| 2020 | 1986.73 | 15340 | 98.52% |
| 2030 | 1986.34 | 15340 | 98.52% |
| 2040 | 2036.90 | 15530 | 99.74% |
| 2050 | 2036.90 | 15530 | 99.74% |
| 2060 | 2036.54 | 15530 | 99.74% |
| 2070 | 2036.96 | 15530 | 99.74% |
| 2080 | 2036.39 | 15530 | 99.74% |
| 2090 | 2088.27 | 15570 | 100.00% |
| 2100 | 2088.27 | 15570 | 100.00% |

Note: The model maximizes direct passenger service. Different solutions with
the same service level can have different costs because cost is not the
primary objective in the current formulation.

## 3. RQ3 — Direct-Service Optimization

| Metric | Result |
|---|---:|
| Candidate lines | 154 |
| Active lines | 24 |
| Total line frequencies | 41 |
| Direct passengers | 15570 / 15570 |
| Direct service | 100.00% |
| Operating cost | 2086.852 |
| Validation | FEASIBLE |

Method: First maximize direct passenger service, then minimize cost while
preserving the maximum service level.

Limitation: Direct service is a proxy for minimizing transfers. The model
does not explicitly count each passenger's transfers.

## 4. Standalone Greedy Heuristic

| Metric | Result |
|---|---:|
| Operating cost | 2387.47 |
| Active lines | 15 |
| Total line frequencies | 47 |
| Direct passengers | 14670 / 15570 |
| Direct service | 94.22% |
| Validation | FEASIBLE |
| Gap versus MIP | +23.50% |

## 5. Large Neighborhood Search (LNS)

Dataset: Mandl
Time limit: 10 seconds per run
Number of seeds: 5
Starting solution: Greedy

| Seed | Cost | Gap versus MIP | Iterations | Repair failures |
|---:|---:|---:|---:|---:|
| 0 | 1933.85 | +0.03% | 47605 | 0 |
| 1 | 1933.81 | +0.03% | 47442 | 0 |
| 2 | 1933.74 | +0.02% | 47130 | 0 |
| 3 | 1933.75 | +0.02% | 47011 | 0 |
| 4 | 1933.80 | +0.02% | 47449 | 0 |

| Summary | Result |
|---|---:|
| Exact MIP cost | 1933.32 |
| Mean LNS cost | 1933.79 |
| Best LNS cost | 1933.74 |
| Mean gap versus MIP | +0.02% |

The best LNS cost improved the standalone greedy cost by approximately 19.0%.
All five runs produced feasible solutions without repair failures.

## 6. Main Conclusions

- The Mandl baseline MIP is optimal with cost 1933.32.
- The LP relaxation has a relative gap of approximately 1.42%.
- RQ2 shows how the budget affects direct passenger service.
- RQ3 achieves 100% direct service at cost 2086.852 using 24 active lines.
- The standalone greedy solution is feasible but costs more than the MIP.
- LNS improves the greedy solution and obtains a best cost within 0.02%
  of the MIP optimum, based on the reported rounded gap.
