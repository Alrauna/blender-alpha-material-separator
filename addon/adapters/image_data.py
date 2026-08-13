# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded image-channel snapshots and authoritative content digests."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable

import bpy
import numpy

from ..core import AlphaGrid
from ..overrides import CHANNELS

# ponytail: allocation-by-failure, not a memory policy. An 8K RGBA float32
# source needs about 1.06 GiB of working buffers, so the bulk path is admitted
# up to 1.5 GiB and falls back only when an allocation actually raises. An OS
# may instead page, compress, overcommit, or fail later somewhere else. Replace
# with an explicit policy if measurement shows pathological paging.
MAX_BULK_WORKING_BYTES = 1536 * 1024 * 1024
MAX_BULK_TEXELS_PER_STEP = 65_536

CHANNEL_INDICES = {"RED": 0, "GREEN": 1, "BLUE": 2}

#: Accumulated extraction cost by phase; read as deltas by the analysis engine.
PHASE_SECONDS: dict[str, float] = {
    "read": 0.0,
    "select": 0.0,
    "digest": 0.0,
    "mask": 0.0,
}


class ImageReadError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ImageSnapshot:
    image: bpy.types.Image
    channel: str
    width: int
    height: int
    component_count: int
    digest: str
    grid: AlphaGrid


def _bulk_working_bytes(total_values: int, texel_count: int) -> int:
    """Float32 source buffer plus the retained one-byte-per-texel mask."""
    return total_values * 4 + texel_count


def _selected_channel(values, component_count: int, channel: str):
    """One participating channel of interleaved texels as canonical float32.

    `values` is a numpy array of either float32 (native bulk transfer) or
    float64 (Python slice fallback); both hold exact float32 image values, so
    the narrowed results are identical.
    """
    if channel == "ALPHA":
        if component_count in {2, 4}:
            return numpy.ascontiguousarray(
                values[component_count - 1 :: component_count], dtype=numpy.float32
            )
        return numpy.ones(values.size // component_count, dtype=numpy.float32)

    index = CHANNEL_INDICES.get(channel)
    if index is not None:
        if component_count <= index:
            raise ImageReadError(f"image does not contain a {channel.lower()} channel")
        return numpy.ascontiguousarray(
            values[index::component_count], dtype=numpy.float32
        )

    if channel == "LUMINANCE":
        if component_count < 3:
            raise ImageReadError("luminance requires RGB image data")
        # The digest depends on this exact form: float64 operands, canonical
        # coefficient order, and a single narrowing to float32 at the end.
        red = values[0::component_count].astype(numpy.float64)
        green = values[1::component_count].astype(numpy.float64)
        blue = values[2::component_count].astype(numpy.float64)
        return (0.2126 * red + 0.7152 * green + 0.0722 * blue).astype(numpy.float32)

    raise ImageReadError(f"unsupported image channel: {channel}")


class ImageSnapshotBuilder:
    """Incrementally read and hash one participating image channel."""

    def __init__(
        self,
        image: bpy.types.Image,
        *,
        channel: str,
        threshold: float,
        rows_per_chunk: int | None = None,
    ) -> None:
        if channel not in CHANNELS:
            raise ImageReadError(f"unsupported image channel: {channel}")
        self.image = image
        self.channel = channel
        self.threshold = threshold
        # A numpy scalar keeps the comparison in float64; a bare Python float
        # would be narrowed to float32 under NEP 50 weak promotion.
        self._threshold = numpy.float64(threshold)
        self.width, self.height = (int(image.size[0]), int(image.size[1]))
        if self.width <= 0 or self.height <= 0:
            raise ImageReadError("image has no readable pixels")
        total_values = len(image.pixels)
        texel_count = self.width * self.height
        if total_values <= 0 or total_values % texel_count:
            raise ImageReadError("image pixel storage does not match its dimensions")
        self.component_count = total_values // texel_count
        if self.component_count not in {1, 2, 3, 4}:
            raise ImageReadError("unsupported image component count")
        self.use_bulk_read = (
            rows_per_chunk is None
            and _bulk_working_bytes(total_values, texel_count)
            <= MAX_BULK_WORKING_BYTES
        )
        self.rows_per_chunk = rows_per_chunk or max(
            1,
            min(
                self.height,
                1_048_576 // (self.width * self.component_count),
            ),
        )
        self.current_row = 0
        self.destination = 0
        self._bulk_pixels = None
        self.affected = numpy.zeros(texel_count, dtype=numpy.uint8)
        self.digest = hashlib.blake2b(digest_size=32)
        self.digest.update(
            f"AMS_IMAGE_CHANNEL_V1:{self.width}:{self.height}:{self.component_count}:{channel}".encode()
        )

    @property
    def complete(self) -> bool:
        return self.current_row >= self.height

    def _consume(self, values) -> None:
        started = time.perf_counter()
        selected = _selected_channel(values, self.component_count, self.channel)
        selected_at = time.perf_counter()
        self.digest.update(selected.tobytes())
        digested_at = time.perf_counter()
        if not numpy.isfinite(selected).all():
            raise ImageReadError("image contains non-finite participating values")
        stop = self.destination + selected.size
        self.affected[self.destination : stop] = selected < self._threshold
        self.destination = stop
        finished_at = time.perf_counter()
        PHASE_SECONDS["select"] += selected_at - started
        PHASE_SECONDS["digest"] += digested_at - selected_at
        PHASE_SECONDS["mask"] += finished_at - digested_at

    def step(self) -> int:
        if self.complete:
            return 0
        if self.use_bulk_read:
            if self._bulk_pixels is None:
                started = time.perf_counter()
                try:
                    self._bulk_pixels = numpy.empty(
                        len(self.image.pixels), dtype=numpy.float32
                    )
                    self.image.pixels.foreach_get(self._bulk_pixels)
                except (
                    AttributeError,
                    MemoryError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ):
                    self._bulk_pixels = None
                    self.use_bulk_read = False
                    return self.step()
                finally:
                    PHASE_SECONDS["read"] += time.perf_counter() - started
            start_texel = self.destination
            stop_texel = min(
                self.width * self.height,
                start_texel + MAX_BULK_TEXELS_PER_STEP,
            )
            try:
                self._consume(
                    self._bulk_pixels[
                        start_texel
                        * self.component_count : stop_texel
                        * self.component_count
                    ]
                )
            except Exception:
                self.close()
                raise
            previous_row = self.current_row
            self.current_row = min(self.height, self.destination // self.width)
            if self.destination == self.width * self.height:
                self.current_row = self.height
                self.close()
            return self.current_row - previous_row
        stop_row = min(self.height, self.current_row + self.rows_per_chunk)
        first_value = self.current_row * self.width * self.component_count
        stop_value = stop_row * self.width * self.component_count
        started = time.perf_counter()
        # `foreach_get` is all-or-nothing, so the low-memory path keeps bounded
        # Python slices and vectorizes each bounded chunk instead.
        chunk = numpy.array(
            self.image.pixels[first_value:stop_value], dtype=numpy.float64
        )
        PHASE_SECONDS["read"] += time.perf_counter() - started
        self._consume(chunk)
        processed = stop_row - self.current_row
        self.current_row = stop_row
        return processed

    def close(self) -> None:
        self._bulk_pixels = None

    def finish(self) -> ImageSnapshot:
        if not self.complete or self.destination != self.width * self.height:
            raise ImageReadError("incomplete image channel read")
        return ImageSnapshot(
            image=self.image,
            channel=self.channel,
            width=self.width,
            height=self.height,
            component_count=self.component_count,
            digest=self.digest.hexdigest(),
            grid=AlphaGrid(self.width, self.height, self.affected.tobytes()),
        )


def read_image_snapshot(
    image: bpy.types.Image,
    *,
    channel: str,
    threshold: float,
    rows_per_chunk: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> ImageSnapshot:
    """Read one participating channel through bounded native or row chunks."""
    builder = ImageSnapshotBuilder(
        image,
        channel=channel,
        threshold=threshold,
        rows_per_chunk=rows_per_chunk,
    )
    while not builder.complete:
        builder.step()
        if progress is not None:
            progress(builder.current_row, builder.height)
    return builder.finish()
