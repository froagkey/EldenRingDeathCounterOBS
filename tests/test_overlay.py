from __future__ import annotations

import json
import unittest
from urllib.request import urlopen

from death_counter.overlay import OverlayServer, OverlayState
from death_counter.save_parser import CharacterSlot


class OverlayServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = OverlayState()
        self.server = OverlayServer(self.state, port=0)
        self.server.start()

    def tearDown(self) -> None:
        self.server.close()

    def test_serves_transparent_overlay(self) -> None:
        with urlopen(self.server.url, timeout=2) as response:
            html = response.read().decode("utf-8")

        self.assertIn("background: transparent", html)
        self.assertIn("/api/status", html)
        self.assertIn('<span id="label">Deaths:</span>', html)
        self.assertIn("white-space: nowrap", html)
        self.assertNotIn("#label {", html)

    def test_serves_updated_character_state(self) -> None:
        self.state.update_character(
            CharacterSlot(
                slot=2,
                name="Tarnished",
                level=150,
                seconds_played=100,
                deaths=42,
                hp=1_900,
                max_hp=1_900,
                base_max_hp=1_900,
            )
        )

        with urlopen(
            f"http://127.0.0.1:{self.server.port}/api/status", timeout=2
        ) as response:
            payload = json.load(response)

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["deaths"], 42)
        self.assertEqual(payload["name"], "Tarnished")
        self.assertEqual(payload["slot"], 2)


if __name__ == "__main__":
    unittest.main()
