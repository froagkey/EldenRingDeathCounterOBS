from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from death_counter.save_parser import CharacterSlot
from death_counter.watcher import (
    CounterConfigurationError,
    read_stable_save,
    render_output,
    select_character,
    write_text_atomic,
)


def character(slot: int, name: str, deaths: int) -> CharacterSlot:
    return CharacterSlot(
        slot=slot,
        name=name,
        level=100,
        seconds_played=3600,
        deaths=deaths,
        hp=900,
        max_hp=1200,
        base_max_hp=1100,
    )


class WatcherTests(unittest.TestCase):
    def test_requires_selection_when_multiple_characters_exist(self) -> None:
        choices = [character(1, "Alpha", 10), character(3, "Beta", 20)]

        with self.assertRaisesRegex(
            CounterConfigurationError, "multiple active characters"
        ):
            select_character(choices)

    def test_selects_character_by_slot_or_case_insensitive_name(self) -> None:
        choices = [character(1, "Alpha", 10), character(3, "Beta", 20)]

        self.assertEqual(select_character(choices, slot=3).deaths, 20)
        self.assertEqual(select_character(choices, character="aLpHa").deaths, 10)

    def test_renders_and_atomically_replaces_obs_output(self) -> None:
        selected = character(2, "Tarnished", 42)
        rendered = render_output(
            "{name}: {deaths} deaths ({hp}/{max_hp} HP)", selected
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "obs" / "death_count.txt"
            write_text_atomic(output, rendered)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "Tarnished: 42 deaths (900/1200 HP)",
            )
            self.assertFalse(output.with_name(".death_count.txt.tmp").exists())

    def test_reads_a_stable_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.sl2"
            path.write_bytes(b"stable")
            self.assertEqual(read_stable_save(path), b"stable")


if __name__ == "__main__":
    unittest.main()
