from __future__ import annotations

import unittest

from dictate.hotkey import (
    DEFAULT_PUSH_TO_TALK_COMBO,
    combo_is_active,
    format_hotkey_combo,
    key_event_names,
    normalize_push_to_talk_combo,
    parse_hotkey_combo,
)


class _FakeKey:
    def __init__(self, name: str | None = None, char: str | None = None):
        self.name = name
        self.char = char


class HotkeyTests(unittest.TestCase):
    def test_normalize_defaults_invalid_values(self) -> None:
        self.assertEqual(normalize_push_to_talk_combo(None), DEFAULT_PUSH_TO_TALK_COMBO)
        with self.assertRaises(ValueError):
            parse_hotkey_combo("bad-token-name")

    def test_parse_combo_orders_and_deduplicates(self) -> None:
        parsed = parse_hotkey_combo("space+ctrl+ctrl")
        self.assertEqual(parsed.combo, "ctrl+space")
        self.assertEqual(parsed.tokens, ("ctrl", "space"))

    def test_combo_is_active_with_generic_and_side_specific_aliases(self) -> None:
        self.assertTrue(combo_is_active({"ctrl", "space"}, "ctrl_r+space"))
        self.assertTrue(combo_is_active({"ctrl_l", "space"}, "ctrl+space"))
        self.assertFalse(combo_is_active({"ctrl"}, "ctrl+space"))

    def test_key_event_names_extracts_characters(self) -> None:
        self.assertEqual(key_event_names(_FakeKey(char="a")), {"a"})
        self.assertEqual(key_event_names(_FakeKey(name="space")), {"space"})

    def test_display_name_is_human_readable(self) -> None:
        self.assertEqual(format_hotkey_combo("ctrl_r"), "Right Ctrl")
        self.assertEqual(format_hotkey_combo("ctrl+space"), "Ctrl + Space")


if __name__ == "__main__":
    unittest.main()
