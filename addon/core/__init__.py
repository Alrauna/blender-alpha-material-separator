# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure-Python rasterization and classification package."""

from .alpha import AlphaGrid
from .classify import classify_counted, classify_coverage, classify_polygon
from .model import (
    AddressMode,
    AnalysisSettings,
    ClassificationResult,
    Coverage,
    FaceClass,
    InvalidRasterInput,
    RasterBudgetExceeded,
    RasterStats,
)
from .raster import rasterize_batch, rasterize_polygon, uv_to_texel_edge

__all__ = (
    "AddressMode",
    "AlphaGrid",
    "AnalysisSettings",
    "ClassificationResult",
    "Coverage",
    "FaceClass",
    "InvalidRasterInput",
    "RasterBudgetExceeded",
    "RasterStats",
    "classify_polygon",
    "classify_coverage",
    "classify_counted",
    "rasterize_batch",
    "rasterize_polygon",
    "uv_to_texel_edge",
)
