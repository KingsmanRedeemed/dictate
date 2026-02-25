from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dictate.history import HistoryStore, MAX_ENTRIES


class HistoryStoreTests(unittest.TestCase):
    def test_append_stores_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(path=Path(tmp) / "h.json")
            store.append("first")
            store.append("second")
            entries = store.load()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].text, "second")
            self.assertEqual(entries[1].text, "first")

    def test_trims_to_max_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(path=Path(tmp) / "h.json")
            for i in range(MAX_ENTRIES + 2):
                store.append(f"text-{i}")
            entries = store.load()
            self.assertEqual(len(entries), MAX_ENTRIES)
            # Newest is first.
            self.assertEqual(entries[0].text, f"text-{MAX_ENTRIES + 1}")

    def test_corrupted_file_recovers_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            path.write_text("NOT VALID JSON!!!")
            store = HistoryStore(path=path)
            entries = store.load()
            self.assertEqual(entries, [])
            # Append still works after corrupt file.
            store.append("recovery")
            entries = store.load()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].text, "recovery")

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(path=Path(tmp) / "does-not-exist.json")
            self.assertEqual(store.load(), [])

    def test_empty_json_object_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            path.write_text("{}")
            store = HistoryStore(path=path)
            self.assertEqual(store.load(), [])

    def test_preserves_duplicate_texts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(path=Path(tmp) / "h.json")
            store.append("same")
            store.append("same")
            entries = store.load()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].text, "same")
            self.assertEqual(entries[1].text, "same")
            # Separate events have different IDs.
            self.assertNotEqual(entries[0].id, entries[1].id)

    def test_entries_have_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            store = HistoryStore(path=path)
            store.append("hello world")
            raw = json.loads(path.read_text())
            self.assertEqual(raw["version"], 1)
            entry = raw["entries"][0]
            self.assertIn("id", entry)
            self.assertIn("created_at", entry)
            self.assertEqual(entry["text"], "hello world")

    def test_ignores_entries_with_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            path.write_text(json.dumps({
                "version": 1,
                "entries": [
                    {"id": "a", "created_at": "b"},  # missing text
                    {"id": "c", "created_at": "d", "text": "good"},
                ],
            }))
            store = HistoryStore(path=path)
            entries = store.load()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].text, "good")


if __name__ == "__main__":
    unittest.main()
