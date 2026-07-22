# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest

from addon.overrides import (
    OverrideConfigError,
    dumps_material_overrides,
    parse_material_overrides_json,
)


class MaterialOverrideTests(unittest.TestCase):
    def test_round_trip_and_defaults(self) -> None:
        overrides = parse_material_overrides_json(
            '[{"material_name":"Body","image_name":"Mask","image_channel":"RED"}]'
        )
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0].uv_map_name, "")
        self.assertEqual(overrides[0].address_mode, "AUTO")
        self.assertEqual(
            dumps_material_overrides(overrides),
            '[{"address_mode":"AUTO","image_channel":"RED","image_name":"Mask","material_name":"Body","uv_map_name":""}]',
        )

    def test_duplicate_target_is_rejected(self) -> None:
        with self.assertRaises(OverrideConfigError) as caught:
            parse_material_overrides_json(
                '[{"material_name":"Body"},{"material_name":"Body"}]'
            )
        self.assertEqual(caught.exception.code, "DUPLICATE_MATERIAL_OVERRIDE")

    def test_non_alpha_channel_requires_image(self) -> None:
        with self.assertRaises(OverrideConfigError) as caught:
            parse_material_overrides_json(
                '[{"material_name":"Body","image_channel":"GREEN"}]'
            )
        self.assertEqual(caught.exception.code, "CHANNEL_REQUIRES_IMAGE_OVERRIDE")

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(OverrideConfigError) as caught:
            parse_material_overrides_json(
                '[{"material_name":"Body","guess":true}]'
            )
        self.assertEqual(caught.exception.code, "INVALID_MATERIAL_OVERRIDES")


if __name__ == "__main__":
    unittest.main()
