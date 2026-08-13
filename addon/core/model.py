# SPDX-License-Identifier: GPL-3.0-or-later
"""Data-only contracts for rasterization and alpha classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy


class AddressMode(str, Enum):
    REPEAT = "REPEAT"
    EXTEND = "EXTEND"
    CLIP = "CLIP"
    MIRROR = "MIRROR"


class FaceClass(str, Enum):
    OPAQUE = "OPAQUE"
    ALPHA_AFFECTED = "ALPHA_AFFECTED"
    MIXED = "MIXED"
    SUPPRESSED = "SUPPRESSED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    alpha_threshold: float = 0.999
    min_affected_texels: int = 1
    min_affected_fraction: float = 0.0
    margin_texels: int = 0
    max_scanlines: int = 1_000_000
    max_run_emissions: int = 2_000_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.alpha_threshold <= 1.0:
            raise ValueError("alpha_threshold must be between 0 and 1")
        if self.min_affected_texels < 0:
            raise ValueError("min_affected_texels cannot be negative")
        if not 0.0 <= self.min_affected_fraction <= 1.0:
            raise ValueError("min_affected_fraction must be between 0 and 1")
        if self.margin_texels < 0:
            raise ValueError("margin_texels cannot be negative")
        if self.max_scanlines <= 0 or self.max_run_emissions <= 0:
            raise ValueError("raster budgets must be positive")


@dataclass(frozen=True, slots=True)
class RasterStats:
    triangles: int
    degenerate_triangles: int
    scanlines: int
    emitted_runs: int
    union_runs: int
    covered_texels: int


# eq=False because a generated `__eq__` would compare the span arrays with
# `==`, which returns an array rather than a bool. Compare `spans` explicitly.
@dataclass(frozen=True, slots=True, eq=False)
class Coverage:
    """Unioned half-open x spans as one flat array, ordered by virtual row.

    `spans` is `(3, run_count)` of int64: virtual row, start, half-open stop.
    Flat rather than a mapping of tuples so a whole step chunk of polygons can
    be counted in one gather; int64 because a virtual coordinate is a UV value
    times an image dimension, which the adversarial suite pushes past int32.
    """

    spans: numpy.ndarray
    stats: RasterStats

    @property
    def rows(self) -> numpy.ndarray:
        return self.spans[0]

    @property
    def starts(self) -> numpy.ndarray:
        return self.spans[1]

    @property
    def stops(self) -> numpy.ndarray:
        return self.spans[2]


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    classification: FaceClass
    covered_texels: int
    affected_texels: int
    opaque_texels: int
    affected_fraction: float
    failed_gates: tuple[str, ...] = ()
    unsuppressed_shape: FaceClass | None = None
    unsupported_reason: str | None = None
    raster_stats: RasterStats | None = None


class RasterBudgetExceeded(RuntimeError):
    """Raised instead of returning an approximate coverage result."""

    def __init__(self, budget: str, limit: int) -> None:
        super().__init__(f"{budget} budget exceeded ({limit})")
        self.budget = budget
        self.limit = limit


class InvalidRasterInput(ValueError):
    """Raised for non-finite or malformed UV input."""
