# SPDX-License-Identifier: GPL-3.0-or-later
"""Row-prefix alpha counting under Blender image addressing modes."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .model import AddressMode, Coverage


def _prefix(values: Iterable[bool]) -> tuple[int, ...]:
    result = [0]
    total = 0
    for value in values:
        total += int(value)
        result.append(total)
    return tuple(result)


def _periodic_count(prefix: tuple[int, ...], start: int, stop: int) -> int:
    if stop <= start:
        return 0
    period = len(prefix) - 1
    if period <= 0:
        return 0
    remaining = stop - start
    position = start % period
    first = min(remaining, period - position)
    total = prefix[position + first] - prefix[position]
    remaining -= first
    if remaining:
        cycles, tail = divmod(remaining, period)
        total += cycles * prefix[-1] + prefix[tail]
    return total


@dataclass(slots=True)
class AlphaGrid:
    width: int
    height: int
    affected: tuple[bool, ...]
    _row_prefixes: tuple[tuple[int, ...], ...] = field(init=False, repr=False)
    _mirror_prefixes: tuple[tuple[int, ...], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.affected) != self.width * self.height:
            raise ValueError("affected mask length does not match dimensions")
        rows = tuple(
            self.affected[row * self.width : (row + 1) * self.width]
            for row in range(self.height)
        )
        self._row_prefixes = tuple(_prefix(row) for row in rows)
        self._mirror_prefixes = tuple(
            _prefix((*row, *reversed(row))) for row in rows
        )

    @classmethod
    def from_alpha_values(
        cls,
        width: int,
        height: int,
        values: Iterable[float],
        *,
        threshold: float = 0.999,
    ) -> "AlphaGrid":
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        affected = []
        for value in values:
            alpha = float(value)
            if not math.isfinite(alpha):
                raise ValueError("alpha values must be finite")
            affected.append(alpha < threshold)
        return cls(width, height, tuple(affected))

    @staticmethod
    def _mirror_index(value: int, size: int) -> int:
        position = value % (2 * size)
        return position if position < size else 2 * size - 1 - position

    def _resolved_row(self, row: int, mode: AddressMode) -> int | None:
        if mode is AddressMode.CLIP:
            return row if 0 <= row < self.height else None
        if mode is AddressMode.EXTEND:
            return min(max(row, 0), self.height - 1)
        if mode is AddressMode.REPEAT:
            return row % self.height
        return self._mirror_index(row, self.height)

    def count_run(self, row: int, start: int, stop: int, mode: AddressMode) -> int:
        """Count below-threshold virtual cells in one half-open run."""
        if stop <= start:
            return 0
        resolved_row = self._resolved_row(row, mode)
        if resolved_row is None:
            return stop - start

        prefix = self._row_prefixes[resolved_row]
        if mode is AddressMode.REPEAT:
            return _periodic_count(prefix, start, stop)
        if mode is AddressMode.MIRROR:
            return _periodic_count(self._mirror_prefixes[resolved_row], start, stop)
        if mode is AddressMode.CLIP:
            inside_start = max(start, 0)
            inside_stop = min(stop, self.width)
            inside = max(0, inside_stop - inside_start)
            outside = (stop - start) - inside
            return outside + (
                prefix[inside_stop] - prefix[inside_start] if inside else 0
            )

        total = 0
        if start < 0:
            left_stop = min(stop, 0)
            if left_stop > start and self.affected[resolved_row * self.width]:
                total += left_stop - start
        inside_start = max(start, 0)
        inside_stop = min(stop, self.width)
        if inside_start < inside_stop:
            total += prefix[inside_stop] - prefix[inside_start]
        if stop > self.width:
            right_start = max(start, self.width)
            if (
                stop > right_start
                and self.affected[resolved_row * self.width + self.width - 1]
            ):
                total += stop - right_start
        return total

    def count_coverage(self, coverage: Coverage, mode: AddressMode) -> int:
        return sum(
            self.count_run(row, start, stop, mode)
            for row, runs in coverage.rows.items()
            for start, stop in runs
        )
