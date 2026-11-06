from __future__ import annotations

import unittest

from death_counter.save_parser import (
    HEADER_SIZE,
    SLOT_STRIDE,
    SaveFormatError,
    parse_save,
)
from tests.save_factory import make_save


class ParseSaveTests(unittest.TestCase):
    def test_parses_deaths_and_exact_hp_from_variable_layout(self) -> None:
        characters = parse_save(
            make_save(
                slot=2,
                name="Test Hero",
                level=87,
                seconds_played=98_765,
                deaths=456,
                hp=777,
                max_hp=1_642,
                base_max_hp=1_450,
                projectile_count=9,
                region_count=12,
                menu_size=31,
                tutorial_size=47,
            )
        )

        self.assertEqual(len(characters), 1)
        character = characters[0]
        self.assertEqual(character.slot, 2)
        self.assertEqual(character.name, "Test Hero")
        self.assertEqual(character.level, 87)
        self.assertEqual(character.seconds_played, 98_765)
        self.assertEqual(character.deaths, 456)
        self.assertEqual(character.hp, 777)
        self.assertEqual(character.max_hp, 1_642)
        self.assertEqual(character.base_max_hp, 1_450)

    def test_rejects_checksum_mismatch(self) -> None:
        data = bytearray(make_save())
        data[HEADER_SIZE + SLOT_STRIDE // 2] ^= 0xFF

        with self.assertRaisesRegex(SaveFormatError, "checksum does not match"):
            parse_save(bytes(data))

    def test_rejects_unknown_signature(self) -> None:
        data = bytearray(make_save())
        data[:4] = b"NOPE"

        with self.assertRaisesRegex(SaveFormatError, "unsupported save signature"):
            parse_save(bytes(data))


if __name__ == "__main__":
    unittest.main()
