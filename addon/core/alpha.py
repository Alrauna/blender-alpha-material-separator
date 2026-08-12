# SPDX-License-Identifier: GPL-3.0-or-later
"""Row-prefix alpha counting under Blender image addressing modes."""

from __future__ import annotations

import math
import time
from array import array
from dataclasses import dataclass, field
from typing import Iterable

import numpy

from .model import AddressMode, Coverage

#: Accumulated prefix-construction cost; read as deltas by the analysis engine.
#: Counting cost is the classification total minus this.
PHASE_SECONDS: dict[str, float] = {"prefix": 0.0}

# ponytail: uint32 accumulator rather than the int64 default. A prefix entry
# cannot exceed the row width because the mask holds one 0/1 byte per texel, so
# overflow needs a row of 4.29 billion texels. int64 would double the retained
# prefix cache against a tracked peak-working-set metric for no reachable gain.
_PREFIX_DTYPE = numpy.dtype(f"u{array('I').itemsize}")


def _prefix(values: bytes) -> array:
    """Inclusive prefix sums of a 0/1 mask row, with a leading zero.

    Returns `array("I")` rather than the numpy buffer so indexing still yields
    plain Python ints; numpy scalars would otherwise reach report metrics and
    the JSON benchmark output.
    """
    counts = numpy.cumsum(
        numpy.frombuffer(values, dtype=numpy.uint8), dtype=_PREFIX_DTYPE
    )
    result = array("I", (0,))
    result.frombytes(counts.tobytes())
    return result


def _periodic_count(prefix: array, start: int, stop: int) -> int:
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
    affected: bytes | bytearray | tuple[bool, ...]
    _row_prefixes: dict[int, array] = field(init=False, repr=False)
    _mirror_prefixes: dict[int, array] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.affected) != self.width * self.height:
            raise ValueError("affected mask length does not match dimensions")
        if not isinstance(self.affected, bytes):
            self.affected = bytes(self.affected)
        self._row_prefixes = {}
        self._mirror_prefixes = {}

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
        affected = bytearray()
        for value in values:
            alpha = float(value)
            if not math.isfinite(alpha):
                raise ValueError("alpha values must be finite")
            affected.append(alpha < threshold)
        return cls(width, height, bytes(affected))

    def _row_values(self, row: int) -> bytes:
        start = row * self.width
        return self.affected[start : start + self.width]

    def _row_prefix(self, row: int) -> array:
        prefix = self._row_prefixes.get(row)
        if prefix is None:
            started = time.perf_counter()
            prefix = _prefix(self._row_values(row))
            PHASE_SECONDS["prefix"] += time.perf_counter() - started
            self._row_prefixes[row] = prefix
        return prefix

    def _mirror_prefix(self, row: int) -> array:
        prefix = self._mirror_prefixes.get(row)
        if prefix is None:
            started = time.perf_counter()
            values = self._row_values(row)
            prefix = _prefix(values + values[::-1])
            PHASE_SECONDS["prefix"] += time.perf_counter() - started
            self._mirror_prefixes[row] = prefix
        return prefix

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

        prefix = self._row_prefix(resolved_row)
        if mode is AddressMode.REPEAT:
            return _periodic_count(prefix, start, stop)
        if mode is AddressMode.MIRROR:
            return _periodic_count(self._mirror_prefix(resolved_row), start, stop)
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
