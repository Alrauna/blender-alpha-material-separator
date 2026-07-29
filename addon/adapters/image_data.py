# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded image-channel snapshots and authoritative content digests."""

from __future__ import annotations

import hashlib
import math
from array import array
from dataclasses import dataclass
from typing import Callable

import bpy

from ..core import AlphaGrid
from ..overrides import CHANNELS

MAX_BULK_WORKING_BYTES = 384 * 1024 * 1024


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
        bulk_working_bytes = (
            total_values * array("f").itemsize
            + texel_count * (array("f").itemsize + 1)
        )
        self.use_bulk_read = (
            rows_per_chunk is None
            and bulk_working_bytes <= MAX_BULK_WORKING_BYTES
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
        self.affected = bytearray(texel_count)
        self.digest = hashlib.blake2b(digest_size=32)
        self.digest.update(
            f"AMS_IMAGE_CHANNEL_V1:{self.width}:{self.height}:{self.component_count}:{channel}".encode()
        )

    @property
    def complete(self) -> bool:
        return self.current_row >= self.height

    def step(self) -> int:
        if self.complete:
            return 0
        if self.use_bulk_read:
            try:
                pixels = array("f", [0.0]) * len(self.image.pixels)
                self.image.pixels.foreach_get(pixels)
            except (AttributeError, MemoryError, RuntimeError, TypeError, ValueError):
                self.use_bulk_read = False
                return self.step()
            values = _selected_values(
                pixels,
                self.component_count,
                self.channel,
            )
            del pixels
            self.digest.update(values.tobytes())
            for value in values:
                if not math.isfinite(value):
                    raise ImageReadError(
                        "image contains non-finite participating values"
                    )
                self.affected[self.destination] = value < self.threshold
                self.destination += 1
            self.current_row = self.height
            return self.height
        stop_row = min(self.height, self.current_row + self.rows_per_chunk)
        first_value = self.current_row * self.width * self.component_count
        stop_value = stop_row * self.width * self.component_count
        chunk = self.image.pixels[first_value:stop_value]
        values = _selected_values(chunk, self.component_count, self.channel)
        self.digest.update(values.tobytes())
        for value in values:
            if not math.isfinite(value):
                raise ImageReadError("image contains non-finite participating values")
            self.affected[self.destination] = value < self.threshold
            self.destination += 1
        processed = stop_row - self.current_row
        self.current_row = stop_row
        return processed

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
            grid=AlphaGrid(self.width, self.height, bytes(self.affected)),
        )


def _selected_values(
    pixels: list[float] | tuple[float, ...], component_count: int, channel: str
) -> array:
    if channel == "ALPHA":
        if component_count in {2, 4}:
            index = component_count - 1
            return array("f", pixels[index::component_count])
        return array("f", [1.0]) * (len(pixels) // component_count)

    indices = {"RED": 0, "GREEN": 1, "BLUE": 2}
    if channel in indices:
        index = indices[channel]
        if component_count <= index:
            raise ImageReadError(f"image does not contain a {channel.lower()} channel")
        return array("f", pixels[index::component_count])

    if channel == "LUMINANCE":
        if component_count < 3:
            raise ImageReadError("luminance requires RGB image data")
        values = array("f")
        for offset in range(0, len(pixels), component_count):
            values.append(
                0.2126 * pixels[offset]
                + 0.7152 * pixels[offset + 1]
                + 0.0722 * pixels[offset + 2]
            )
        return values
    raise ImageReadError(f"unsupported image channel: {channel}")


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
