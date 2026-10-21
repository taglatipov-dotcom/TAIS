"""Разбивка длины на пролёты стандартной длины.

Все размеры — в миллиметрах (целые числа), чтобы не ловить ошибки округления.
"""
from __future__ import annotations

# Пролёты, для которых есть ригель, стальной настил и бортик (см. catalog.py)
BAY_SIZES: tuple[int, ...] = (3000, 2500, 2000, 1500, 1000, 750)


class SplitError(ValueError):
    pass


def split_length(total: int, breakpoints: list[int] | None = None,
                 sizes: tuple[int, ...] = BAY_SIZES) -> list[int]:
    """Разбить отрезок [0, total] на пролёты из `sizes`.

    `breakpoints` — координаты, где обязательно должна стоять стойка
    (например, край пристроенного балкона). Каждый участок между соседними
    обязательными точками разбивается отдельно.

    Критерий выбора: меньше пролётов → меньше разных типоразмеров →
    крупные пролёты раньше мелких.
    """
    if total <= 0:
        raise SplitError("Длина должна быть больше нуля")
    points = sorted({0, total, *[p for p in (breakpoints or []) if 0 < p < total]})
    result: list[int] = []
    for a, b in zip(points, points[1:]):
        part = _best_split(b - a, sizes)
        if part is None:
            raise SplitError(
                f"Участок {(b - a) / 1000:g} м нельзя набрать из пролётов "
                f"{', '.join(f'{s / 1000:g}' for s in sizes)} м"
            )
        result.extend(part)
    return result


def _best_split(length: int, sizes: tuple[int, ...]) -> list[int] | None:
    """Минимальное число пролётов, затем минимум разных типоразмеров."""
    # 1) минимальное количество пролётов (задача о размене монет)
    inf = 10 ** 9
    best = [0] + [inf] * length
    step = 250  # все размеры кратны 250 мм
    if length % step or any(s % step for s in sizes):
        return None
    for v in range(step, length + 1, step):
        for s in sizes:
            if s <= v and best[v - s] + 1 < best[v]:
                best[v] = best[v - s] + 1
    k = best[length]
    if k >= inf:
        return None

    # 2) среди разбиений из k пролётов ищем с 1, 2, 3 типоразмерами
    ordered = sorted(sizes, reverse=True)
    for distinct in (1, 2, 3):
        found = _search(length, k, ordered, distinct)
        if found:
            return found

    # 3) запасной вариант — любое минимальное разбиение
    out: list[int] = []
    v = length
    while v:
        for s in ordered:
            if s <= v and best[v - s] == best[v] - 1:
                out.append(s)
                v -= s
                break
    return out


def _search(length: int, k: int, ordered: list[int], distinct: int) -> list[int] | None:
    from itertools import combinations

    candidates: list[list[int]] = []
    for combo in combinations(ordered, distinct):
        for counts in _compositions(k, distinct):
            if sum(c * s for c, s in zip(counts, combo)) == length:
                parts: list[int] = []
                for c, s in zip(counts, combo):
                    parts.extend([s] * c)
                candidates.append(sorted(parts, reverse=True))
    if not candidates:
        return None
    return min(candidates, key=lambda p: [-x for x in p])


def _compositions(total: int, parts: int):
    """Все способы записать total как сумму `parts` положительных чисел."""
    if parts == 1:
        yield (total,)
        return
    for first in range(1, total - parts + 2):
        for rest in _compositions(total - first, parts - 1):
            yield (first, *rest)


def cumulative(bays: list[int]) -> list[int]:
    """[2000, 2000] -> [0, 2000, 4000] — координаты стоек."""
    out = [0]
    for b in bays:
        out.append(out[-1] + b)
    return out
