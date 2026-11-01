"""TOPSIS: rank alternatives by their closeness to an ideal solution.

Independent of FastAPI and the database. Steps:

1. Decision matrix: one row per alternative, one column per criterion.
2. Vector normalization: r_ij = x_ij / sqrt(sum_i x_ij^2), so criteria measured
   in different units (MDL, score, W) become comparable.
3. Weighting: v_ij = w_j * r_ij.
4. Ideal (A+) and anti-ideal (A-) solutions: per criterion, the best and worst
   weighted value; best is the maximum for benefit criteria and the minimum
   for cost criteria.
5. Euclidean distances D+ (to A+) and D- (to A-) for each alternative.
6. Closeness C = D- / (D+ + D-), between 0 and 1; higher ranks first.
"""
from dataclasses import dataclass
from math import isclose, sqrt


@dataclass(frozen=True)
class TopsisScore:
    index: int  # row in the decision matrix
    distance_best: float  # D+
    distance_worst: float  # D-
    closeness: float  # C


def topsis(matrix: list[list[float]], weights: list[float], maximize: list[bool]) -> list[TopsisScore]:
    """Score every row of `matrix`, best first; ties keep the original row order.

    `weights` must be non-negative and sum to 1. `maximize[j]` is True for a
    benefit criterion (performance) and False for a cost criterion (price, power).
    """
    if len(weights) != len(maximize):
        raise ValueError("Need one weight and one direction per criterion")
    if any(w < 0 for w in weights) or not isclose(sum(weights), 1.0, abs_tol=1e-9):
        raise ValueError("Weights must be non-negative and sum to 1")
    if any(len(row) != len(weights) for row in matrix):
        raise ValueError("Every alternative needs one value per criterion")
    if not matrix:
        return []

    criteria = range(len(weights))
    norms = [sqrt(sum(row[j] ** 2 for row in matrix)) for j in criteria]
    # An all-zero column cannot tell alternatives apart; it stays zero.
    weighted = [[weights[j] * (row[j] / norms[j] if norms[j] else 0.0) for j in criteria] for row in matrix]

    columns = [[row[j] for row in weighted] for j in criteria]
    best = [max(col) if maximize[j] else min(col) for j, col in enumerate(columns)]
    worst = [min(col) if maximize[j] else max(col) for j, col in enumerate(columns)]

    scores = []
    for i, row in enumerate(weighted):
        d_best = sqrt(sum((row[j] - best[j]) ** 2 for j in criteria))
        d_worst = sqrt(sum((row[j] - worst[j]) ** 2 for j in criteria))
        # D+ + D- = 0 only when every alternative is identical: all are equally good.
        closeness = d_worst / (d_best + d_worst) if d_best + d_worst else 1.0
        scores.append(TopsisScore(i, d_best, d_worst, closeness))
    return sorted(scores, key=lambda s: -s.closeness)
