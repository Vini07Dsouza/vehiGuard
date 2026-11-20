"""Near-miss plate matching for POSSIBLE_MATCH review items (FR-PLT-08)."""

from collections.abc import Iterable


def edit_distance(a: str, b: str, limit: int | None = None) -> int:
    """Levenshtein distance (insert, delete, replace = 1 each).

    With limit, stops early and returns limit + 1 once it is exceeded.
    """
    if a == b:
        return 0
    if limit is not None and abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        if limit is not None and min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def near_misses(plate: str, candidates: Iterable[str], max_distance: int) -> list[str]:
    """Candidates within max_distance of plate, but not equal to it."""
    return sorted(
        c
        for c in set(candidates)
        if c != plate and edit_distance(plate, c, max_distance) <= max_distance
    )
