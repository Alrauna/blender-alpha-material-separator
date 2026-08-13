# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical image-channel extraction contracts across both read paths."""

from __future__ import annotations

import hashlib
import math
import random
from array import array

import bpy
import numpy

from addon.adapters import image_data
from addon.adapters.image_data import (
    ImageReadError,
    ImageSnapshotBuilder,
    read_image_snapshot,
)

CHANNEL_INDICES = {"RED": 0, "GREEN": 1, "BLUE": 2}
THRESHOLD = 0.999


class _StubPixels:
    """Minimal stand-in for `Image.pixels`: length, bounded slices, foreach_get.

    Blender images are always four-component, so component counts 1/2/3 can only
    be exercised against a stand-in. Slices return lists of Python floats and
    `foreach_get` fills a caller-provided buffer, exactly as Blender does.
    """

    def __init__(self, values: array) -> None:
        self._values = values

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, item):
        return list(self._values[item])

    def foreach_get(self, target) -> None:
        target[:] = self._values


class _StubImage:
    def __init__(self, width: int, height: int, values: array) -> None:
        self.size = (width, height)
        self.pixels = _StubPixels(values)


def _reference(
    width: int,
    height: int,
    component_count: int,
    values: array,
    channel: str,
    threshold: float,
) -> tuple[str, bytes]:
    """Scalar oracle: the canonical semantics the fast paths must reproduce."""
    digest = hashlib.blake2b(digest_size=32)
    digest.update(
        f"AMS_IMAGE_CHANNEL_V1:{width}:{height}:{component_count}:{channel}".encode()
    )
    if channel == "ALPHA":
        if component_count in {2, 4}:
            selected = array("f", values[component_count - 1 :: component_count])
        else:
            selected = array("f", [1.0]) * (len(values) // component_count)
    elif channel in CHANNEL_INDICES:
        index = CHANNEL_INDICES[channel]
        if component_count <= index:
            raise ImageReadError(f"image does not contain a {channel.lower()} channel")
        selected = array("f", values[index::component_count])
    elif channel == "LUMINANCE":
        if component_count < 3:
            raise ImageReadError("luminance requires RGB image data")
        selected = array("f")
        for offset in range(0, len(values), component_count):
            selected.append(
                0.2126 * values[offset]
                + 0.7152 * values[offset + 1]
                + 0.0722 * values[offset + 2]
            )
    else:
        raise ImageReadError(f"unsupported image channel: {channel}")
    digest.update(selected.tobytes())
    affected = bytearray()
    for value in selected:
        if not math.isfinite(value):
            raise ImageReadError("image contains non-finite participating values")
        affected.append(value < threshold)
    return digest.hexdigest(), bytes(affected)


def _read(image, *, channel, threshold, rows_per_chunk):
    builder = ImageSnapshotBuilder(
        image,
        channel=channel,
        threshold=threshold,
        rows_per_chunk=rows_per_chunk,
    )
    while not builder.complete:
        builder.step()
    return builder, builder.finish()


def _boundary_pool(threshold: float) -> tuple[float, ...]:
    """Exact float32 values straddling the threshold plus ordinary extremes."""
    exact = numpy.float32(threshold)
    below = numpy.nextafter(exact, numpy.float32(0.0))
    above = numpy.nextafter(exact, numpy.float32(2.0))
    return (
        0.0,
        1.0,
        0.5,
        float(exact),
        float(below),
        float(above),
        float(numpy.float32(threshold - 1e-6)),
        1.401298464324817e-45,
        -0.0,
        2.5,
        -1.25,
    )


def _case_values(component_count: int, texels: int, seed: int, threshold: float) -> array:
    generator = random.Random(seed)
    pool = _boundary_pool(threshold)
    return array(
        "f",
        [
            pool[generator.randrange(len(pool))]
            for _ in range(texels * component_count)
        ],
    )


def _assert_agrees(
    width: int,
    height: int,
    component_count: int,
    values: array,
    channel: str,
    threshold: float,
    rows_per_chunk: int | None,
    expect_bulk: bool,
) -> str:
    image = _StubImage(width, height, values)
    expected_digest, expected_mask = _reference(
        width, height, component_count, values, channel, threshold
    )
    builder, snapshot = _read(
        image, channel=channel, threshold=threshold, rows_per_chunk=rows_per_chunk
    )
    label = f"{component_count}c/{channel}/chunk={rows_per_chunk}"
    assert builder.use_bulk_read is expect_bulk, label
    assert snapshot.digest == expected_digest, label
    assert snapshot.grid.affected == expected_mask, label
    assert snapshot.width == width and snapshot.height == height, label
    assert snapshot.component_count == component_count, label
    assert snapshot.channel == channel, label
    assert snapshot.image is image, label
    assert snapshot.grid.width == width and snapshot.grid.height == height, label
    return expected_digest


def _assert_raises(callable_, message: str, label: str) -> None:
    try:
        callable_()
    except ImageReadError as error:
        assert message in str(error), f"{label}: {error}"
        return
    raise AssertionError(f"{label}: expected ImageReadError {message!r}")


def run_matrix() -> dict[str, str]:
    """Both read paths reproduce the scalar oracle for every supported case."""
    digests: dict[str, str] = {}
    # 300x250 crosses MAX_BULK_TEXELS_PER_STEP on a non-row-aligned boundary.
    width, height = 300, 250
    texels = width * height
    for component_count in (1, 2, 3, 4):
        values = _case_values(component_count, texels, 7 + component_count, THRESHOLD)
        for channel in ("ALPHA", "RED", "GREEN", "BLUE", "LUMINANCE"):
            supported = (
                channel == "ALPHA"
                or (channel in CHANNEL_INDICES and component_count > CHANNEL_INDICES[channel])
                or (channel == "LUMINANCE" and component_count >= 3)
            )
            image = _StubImage(width, height, values)
            if not supported:
                expected = (
                    "luminance requires RGB image data"
                    if channel == "LUMINANCE"
                    else f"image does not contain a {channel.lower()} channel"
                )
                for rows_per_chunk in (None, 37):
                    _assert_raises(
                        lambda rows=rows_per_chunk: _read(
                            image,
                            channel=channel,
                            threshold=THRESHOLD,
                            rows_per_chunk=rows,
                        ),
                        expected,
                        f"{component_count}c/{channel}",
                    )
                continue
            bulk = _assert_agrees(
                width, height, component_count, values, channel, THRESHOLD, None, True
            )
            chunked = _assert_agrees(
                width, height, component_count, values, channel, THRESHOLD, 37, False
            )
            assert bulk == chunked, f"{component_count}c/{channel} path disagreement"
            digests[f"{component_count}:{channel}"] = bulk
    return digests


def run_thresholds() -> None:
    """Threshold comparison stays a float64 comparison of float32 values.

    `float32(0.999)` is above `float64(0.999)`, so a float32-narrowed threshold
    would flip the exact-boundary texel on some thresholds.
    """
    exact = float(numpy.float32(THRESHOLD))
    below = float(numpy.nextafter(numpy.float32(THRESHOLD), numpy.float32(0.0)))
    above = float(numpy.nextafter(numpy.float32(THRESHOLD), numpy.float32(2.0)))
    single = array("f", [exact, below, above, 0.0, 1.0, -0.0])
    rgba = array("f", [value for value in single for _ in range(4)])
    # Thresholds that a float32-narrowed comparison would answer differently.
    traps = (0.5 + 1e-9, exact + 1e-9)
    for value, threshold in ((0.5, traps[0]), (exact, traps[1])):
        assert (value < threshold) is True, (value, threshold)
        assert bool(numpy.float32(value) < numpy.float32(threshold)) is False, (
            value,
            threshold,
        )
    for threshold in (0.0, 1.0, THRESHOLD, exact, below, above, 0.5, 1e-45, *traps):
        for rows_per_chunk in (None, 1):
            bulk = rows_per_chunk is None
            _assert_agrees(
                len(single), 1, 1, single, "RED", threshold, rows_per_chunk, bulk
            )
            _assert_agrees(
                len(single), 1, 4, rgba, "ALPHA", threshold, rows_per_chunk, bulk
            )


def run_non_finite() -> None:
    """NaN and both infinities are rejected on either path and every channel."""
    for bad in (math.nan, math.inf, -math.inf):
        for component_count in (1, 2, 3, 4):
            for channel in ("ALPHA", "RED", "GREEN", "BLUE", "LUMINANCE"):
                if channel in CHANNEL_INDICES and component_count <= CHANNEL_INDICES[channel]:
                    continue
                if channel == "LUMINANCE" and component_count < 3:
                    continue
                if channel == "ALPHA" and component_count in {1, 3}:
                    continue  # synthesized opaque alpha is always finite
                values = array("f", [0.25] * (4 * component_count))
                index = (
                    component_count - 1
                    if channel == "ALPHA"
                    else CHANNEL_INDICES.get(channel, 0)
                )
                values[2 * component_count + index] = bad
                label = f"{component_count}c/{channel}/{bad}"
                _assert_raises(
                    lambda: _reference(4, 1, component_count, values, channel, THRESHOLD),
                    "non-finite participating values",
                    f"oracle {label}",
                )
                for rows_per_chunk in (None, 1):
                    image = _StubImage(4, 1, values)
                    _assert_raises(
                        lambda rows=rows_per_chunk: _read(
                            image,
                            channel=channel,
                            threshold=THRESHOLD,
                            rows_per_chunk=rows,
                        ),
                        "non-finite participating values",
                        label,
                    )


def run_input_errors() -> None:
    values = array("f", [0.5] * 16)
    _assert_raises(
        lambda: ImageSnapshotBuilder(
            _StubImage(2, 2, values), channel="MAGENTA", threshold=THRESHOLD
        ),
        "unsupported image channel",
        "channel",
    )
    _assert_raises(
        lambda: ImageSnapshotBuilder(
            _StubImage(0, 2, values), channel="ALPHA", threshold=THRESHOLD
        ),
        "image has no readable pixels",
        "width",
    )
    _assert_raises(
        lambda: ImageSnapshotBuilder(
            _StubImage(3, 3, values), channel="ALPHA", threshold=THRESHOLD
        ),
        "image pixel storage does not match its dimensions",
        "dimensions",
    )
    _assert_raises(
        lambda: ImageSnapshotBuilder(
            _StubImage(2, 1, array("f", [0.5] * 10)),
            channel="ALPHA",
            threshold=THRESHOLD,
        ),
        "unsupported image component count",
        "components",
    )
    builder = ImageSnapshotBuilder(
        _StubImage(2, 2, values), channel="ALPHA", threshold=THRESHOLD, rows_per_chunk=1
    )
    builder.step()
    _assert_raises(
        builder.finish, "incomplete image channel read", "incomplete"
    )


def run_memory_policy() -> None:
    """8K RGBA float32 sources take the vectorized bulk path; 16K does not."""
    for size, expected in ((4096, True), (8192, True), (16384, False)):
        texels = size * size
        working = image_data._bulk_working_bytes(texels * 4, texels)
        assert (
            working <= image_data.MAX_BULK_WORKING_BYTES
        ) is expected, (size, working)


def run_blender_image() -> None:
    """A real Blender image agrees with the oracle on both paths."""
    size = 48
    image = bpy.data.images.new("AMS_TEST_IMAGE_DATA", width=size, height=size, alpha=True)
    try:
        values = _case_values(4, size * size, 991, THRESHOLD)
        image.pixels.foreach_set(numpy.asarray(values, dtype=numpy.float32))
        stored = array("f", [0.0]) * (size * size * 4)
        image.pixels.foreach_get(stored)
        for channel in ("ALPHA", "RED", "GREEN", "BLUE", "LUMINANCE"):
            expected_digest, expected_mask = _reference(
                size, size, 4, stored, channel, THRESHOLD
            )
            for rows_per_chunk in (None, 5):
                builder, snapshot = _read(
                    image,
                    channel=channel,
                    threshold=THRESHOLD,
                    rows_per_chunk=rows_per_chunk,
                )
                assert builder.use_bulk_read is (rows_per_chunk is None), channel
                assert snapshot.digest == expected_digest, channel
                assert snapshot.grid.affected == expected_mask, channel
            direct = read_image_snapshot(image, channel=channel, threshold=THRESHOLD)
            assert direct.digest == expected_digest, channel
    finally:
        bpy.data.images.remove(image)


GOLDEN_DIGESTS = {
    "1:ALPHA": "8d240eb4c378d4e3e5052e372ee2b16eca739490e05a85cb6e9582b0b85b3971",
    "1:RED": "c18fcf66f3d95640cf81971e70e2f33866b780e16039ba1f698f4710eb5a6fad",
    "2:ALPHA": "ca50281f486ace1595488e61fa707da089c90281bae725b6a4285ddfd2d17f9f",
    "2:GREEN": "d307b4a6e433ce0e485654582978506f8e3ba41211ed1564d4a1048b9cd0f889",
    "2:RED": "d6da5400ef036c6ceb9cbe676eba5d7d47f170ac21d8c0e3a3555d7e505f15ff",
    "3:ALPHA": "0ca8569eef077869e09b787ac16bdfaee0c01c6cc3e32ff81dbb4251ee53458e",
    "3:BLUE": "281896fd9a08bfd756ff907cde4b6eac59ae954e8694b1bd7e2fdc6d65f31134",
    "3:GREEN": "a05346b5bce20f1206d587a6f02325420533bba7bdf791107be1cae21dcf5320",
    "3:LUMINANCE": "379afbe34b825282934df46966e806ab3b2164730c13842a1ba025dc0dbd646f",
    "3:RED": "bec68819f5ed754a6aa5189362c1ef5f7d3b33999a0d46927fb0b6652e3502fe",
    "4:ALPHA": "b339c5e52f55eec0264d8c40f993332e3e2b874cf1944ac28dc9e46847fb7be6",
    "4:BLUE": "41a1701eee834e7a58fc842a4af94efdd53cf5dad7e9ea30f7c466aeee75eb2f",
    "4:GREEN": "636fba9cb4ed4fbe8ad528f1ad13333d845c0fb029f6993a1ba7d8f1cb27e937",
    "4:LUMINANCE": "0a487b8883bad323f34644c4cf15859c1a088667b1a8fdb2f90ea250a962b86b",
    "4:RED": "089754693b4347e2eec4d99f69d0aa64050b4117f6da9c18bc51efd5dab7e625",
}


def run_goldens(digests: dict[str, str]) -> None:
    """Committed canonical digests catch both implementations drifting together."""
    assert digests.keys() == GOLDEN_DIGESTS.keys(), sorted(digests)
    for key, expected in GOLDEN_DIGESTS.items():
        assert digests[key] == expected, (key, digests[key])


def run() -> None:
    digests = run_matrix()
    run_thresholds()
    run_non_finite()
    run_input_errors()
    run_memory_policy()
    run_blender_image()
    run_goldens(digests)
    print("ALPHA_MATERIAL_SEPARATOR_IMAGE_DATA_OK")


if __name__ == "__main__":
    run()
