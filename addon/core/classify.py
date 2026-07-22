# SPDX-License-Identifier: GPL-3.0-or-later
"""Face classification from exact polygon coverage and image alpha."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .alpha import AlphaGrid
from .model import (
    AddressMode,
    AnalysisSettings,
    ClassificationResult,
    FaceClass,
    InvalidRasterInput,
    RasterBudgetExceeded,
)
from .raster import Point, rasterize_polygon


def classify_polygon(
    triangles: Iterable[Sequence[Point]],
    alpha: AlphaGrid,
    *,
    address_mode: AddressMode = AddressMode.REPEAT,
    settings: AnalysisSettings = AnalysisSettings(),
) -> ClassificationResult:
    try:
        coverage = rasterize_polygon(
            triangles,
            margin_texels=settings.margin_texels,
            max_scanlines=settings.max_scanlines,
            max_run_emissions=settings.max_run_emissions,
        )
    except RasterBudgetExceeded as error:
        return ClassificationResult(
            classification=FaceClass.UNSUPPORTED,
            covered_texels=0,
            affected_texels=0,
            opaque_texels=0,
            affected_fraction=0.0,
            unsupported_reason=f"BUDGET_{error.budget.upper()}",
        )
    except InvalidRasterInput:
        return ClassificationResult(
            classification=FaceClass.UNSUPPORTED,
            covered_texels=0,
            affected_texels=0,
            opaque_texels=0,
            affected_fraction=0.0,
            unsupported_reason="INVALID_UV",
        )

    covered = coverage.stats.covered_texels
    if covered == 0:
        return ClassificationResult(
            classification=FaceClass.UNSUPPORTED,
            covered_texels=0,
            affected_texels=0,
            opaque_texels=0,
            affected_fraction=0.0,
            unsupported_reason="NO_POSITIVE_AREA_UV_COVERAGE",
            raster_stats=coverage.stats,
        )

    affected = alpha.count_coverage(coverage, address_mode)
    opaque = covered - affected
    fraction = affected / covered
    if affected == 0:
        return ClassificationResult(
            classification=FaceClass.OPAQUE,
            covered_texels=covered,
            affected_texels=0,
            opaque_texels=opaque,
            affected_fraction=0.0,
            raster_stats=coverage.stats,
        )

    shape = FaceClass.ALPHA_AFFECTED if opaque == 0 else FaceClass.MIXED
    failed: list[str] = []
    if settings.min_affected_texels > 0 and affected < settings.min_affected_texels:
        failed.append("MIN_AFFECTED_TEXELS")
    if (
        settings.min_affected_fraction > 0.0
        and fraction < settings.min_affected_fraction
    ):
        failed.append("MIN_AFFECTED_FRACTION")
    if failed:
        return ClassificationResult(
            classification=FaceClass.SUPPRESSED,
            covered_texels=covered,
            affected_texels=affected,
            opaque_texels=opaque,
            affected_fraction=fraction,
            failed_gates=tuple(failed),
            unsuppressed_shape=shape,
            raster_stats=coverage.stats,
        )
    return ClassificationResult(
        classification=shape,
        covered_texels=covered,
        affected_texels=affected,
        opaque_texels=opaque,
        affected_fraction=fraction,
        raster_stats=coverage.stats,
    )
