# SPDX-License-Identifier: GPL-3.0-or-later
"""Row-prefix alpha counting under Blender image addressing modes."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy

from .model import AddressMode, Coverage

#: Accumulated prefix-construction cost; read as deltas by the analysis engine.
#: Counting cost is the classification total minus this.
PHASE_SECONDS: dict[str, float] = {"prefix": 0.0}

# ponytail: uint32 accumulator rather than the int64 default. A prefix entry
# cannot exceed the row width because the mask holds one 0/1 byte per texel, so
# overflow needs a row of 4.29 billion texels. int64 would double the retained
# prefix cache against a tracked peak-working-set metric for no reachable gain.
_PREFIX_DTYPE = numpy.uint32


def _prefix_rows(block: numpy.ndarray) -> numpy.ndarray:
    """Inclusive prefix sums of 0/1 mask rows, each with a leading zero.

    Whole rows at a time so a batch of runs can gather `prefix[row, x]` in one
    indexing operation; a dict of one-dimensional rows cannot be gathered from.
    """
    result = numpy.zeros((block.shape[0], block.shape[1] + 1), dtype=_PREFIX_DTYPE)
    if block.shape[1]:
        numpy.cumsum(block, axis=1, dtype=_PREFIX_DTYPE, out=result[:, 1:])
    return result


def _periodic_count(prefix: numpy.ndarray, start: int, stop: int) -> int:
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
    _plane: numpy.ndarray = field(init=False, repr=False)
    _prefixes: numpy.ndarray | None = field(init=False, repr=False)
    _prefix_built: numpy.ndarray | None = field(init=False, repr=False)
    _mirrors: numpy.ndarray | None = field(init=False, repr=False)
    _mirror_built: numpy.ndarray | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.affected) != self.width * self.height:
            raise ValueError("affected mask length does not match dimensions")
        if not isinstance(self.affected, bytes):
            self.affected = bytes(self.affected)
        self._plane = numpy.frombuffer(self.affected, dtype=numpy.uint8).reshape(
            self.height, self.width
        )
        self._prefixes = None
        self._prefix_built = None
        self._mirrors = None
        self._mirror_built = None

    def _ensure_prefixes(self, rows: numpy.ndarray) -> numpy.ndarray:
        """Build the prefix rows this batch touches, and only those.

        The buffer is allocated whole but written lazily, so rows a mesh never
        samples are never faulted in and stay out of the working set.
        """
        if self._prefixes is None:
            self._prefixes = numpy.empty(
                (self.height, self.width + 1), dtype=_PREFIX_DTYPE
            )
            self._prefix_built = numpy.zeros(self.height, dtype=bool)
        missing = numpy.unique(rows[~self._prefix_built[rows]])
        if missing.size:
            started = time.perf_counter()
            self._prefixes[missing] = _prefix_rows(self._plane[missing])
            self._prefix_built[missing] = True
            PHASE_SECONDS["prefix"] += time.perf_counter() - started
        return self._prefixes

    def _ensure_mirrors(self, rows: numpy.ndarray) -> numpy.ndarray:
        if self._mirrors is None:
            self._mirrors = numpy.empty(
                (self.height, 2 * self.width + 1), dtype=_PREFIX_DTYPE
            )
            self._mirror_built = numpy.zeros(self.height, dtype=bool)
        missing = numpy.unique(rows[~self._mirror_built[rows]])
        if missing.size:
            started = time.perf_counter()
            block = self._plane[missing]
            self._mirrors[missing] = _prefix_rows(
                numpy.concatenate((block, block[:, ::-1]), axis=1)
            )
            self._mirror_built[missing] = True
            PHASE_SECONDS["prefix"] += time.perf_counter() - started
        return self._mirrors

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

    def _row_prefix(self, row: int) -> numpy.ndarray:
        return self._ensure_prefixes(numpy.asarray((row,)))[row]

    def _mirror_prefix(self, row: int) -> numpy.ndarray:
        return self._ensure_mirrors(numpy.asarray((row,)))[row]

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
        """Count below-threshold virtual cells in one half-open run.

        Reference implementation for a single run. `count_batch` is the form the
        analysis engine uses; the two are cross-checked against each other and
        against a cell-by-cell oracle in the unit suite.
        """
        # Prefix rows are numpy buffers, so cast back before a count can reach
        # report metrics or the JSON benchmark output as a numpy scalar.
        return int(self._count_run(row, start, stop, mode))

    def _count_run(self, row: int, start: int, stop: int, mode: AddressMode) -> int:
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
            self.count_run(int(row), int(start), int(stop), mode)
            for row, start, stop in zip(
                coverage.rows, coverage.starts, coverage.stops
            )
        )

    def _resolve_rows(self, rows: numpy.ndarray, mode: AddressMode):
        """Resolved row per run, plus which runs fall outside a clipped image."""
        if mode is AddressMode.REPEAT:
            return rows % self.height, None
        if mode is AddressMode.EXTEND:
            return numpy.clip(rows, 0, self.height - 1), None
        if mode is AddressMode.CLIP:
            outside = (rows < 0) | (rows >= self.height)
            return numpy.clip(rows, 0, self.height - 1), outside
        position = rows % (2 * self.height)
        return (
            numpy.where(position < self.height, position,
                        2 * self.height - 1 - position),
            None,
        )

    def _periodic_counts(self, prefixes, rows, starts, stops, period):
        """`_periodic_count` for a whole batch, same closed form."""
        remaining = stops - starts
        position = starts % period
        first = numpy.minimum(remaining, period - position)
        total = prefixes[rows, position + first].astype(numpy.int64)
        total -= prefixes[rows, position]
        remaining -= first
        cycles, tail = numpy.divmod(remaining, period)
        total += cycles * prefixes[rows, period]
        total += prefixes[rows, tail]
        return total

    def count_batch(
        self, coverages: Sequence[Coverage], mode: AddressMode
    ) -> list[int]:
        """Affected virtual cells per polygon, counting a whole batch at once.

        One gather across every run in the batch instead of a Python call per
        run. A polygon with no positive-area coverage keeps its slot and counts
        zero, so results stay aligned with the input order.
        """
        coverages = tuple(coverages)
        if not coverages:
            return []
        spans = numpy.concatenate([one.spans for one in coverages], axis=1)
        rows, starts = spans[0], spans[1]
        # A zero-length run has to contribute nothing, and clamping here makes
        # every branch below produce that without a separate mask.
        stops = numpy.maximum(spans[2], starts)

        resolved, outside = self._resolve_rows(rows, mode)
        if mode is AddressMode.MIRROR:
            counts = self._periodic_counts(
                self._ensure_mirrors(resolved), resolved, starts, stops,
                2 * self.width,
            )
        elif mode is AddressMode.REPEAT:
            counts = self._periodic_counts(
                self._ensure_prefixes(resolved), resolved, starts, stops,
                self.width,
            )
        else:
            prefixes = self._ensure_prefixes(resolved)
            inside_start = numpy.clip(starts, 0, self.width)
            inside_stop = numpy.clip(stops, 0, self.width)
            inside = numpy.maximum(inside_stop - inside_start, 0)
            counts = numpy.where(
                inside > 0,
                prefixes[resolved, inside_stop].astype(numpy.int64)
                - prefixes[resolved, inside_start],
                0,
            )
            if mode is AddressMode.CLIP:
                # Outside a clipped image every cell is transparent.
                counts += (stops - starts) - inside
                counts = numpy.where(outside, stops - starts, counts)
            else:
                # EXTEND repeats the edge texel, so a run's overhang counts only
                # when that edge texel is itself affected.
                edges = self._plane[resolved]
                counts += numpy.where(
                    edges[:, 0] != 0, numpy.minimum(stops, 0) - numpy.minimum(starts, 0), 0
                )
                counts += numpy.where(
                    edges[:, -1] != 0,
                    numpy.maximum(stops, self.width) - numpy.maximum(starts, self.width),
                    0,
                )

        lengths = numpy.fromiter(
            (one.spans.shape[1] for one in coverages),
            dtype=numpy.int64,
            count=len(coverages),
        )
        bounds = numpy.concatenate(((0,), numpy.cumsum(lengths)))
        running = numpy.concatenate(((0,), numpy.cumsum(counts, dtype=numpy.int64)))
        return (running[bounds[1:]] - running[bounds[:-1]]).tolist()
