"""GTK 3 dialog showing recent dictation history with copy-to-clipboard."""

from __future__ import annotations

from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from dictate.history import HistoryEntry, HistoryStore
from dictate.outputs import ClipboardOutput, OutputError


class RecentHistoryDialog(Gtk.Dialog):
    """Modal dialog listing recent dictations with a Copy action."""

    def __init__(self, store: HistoryStore, parent: Gtk.Window | None = None):
        super().__init__(
            title="Recent History",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(420, 300)
        self.add_button("Close", Gtk.ResponseType.CLOSE)

        self._store = store
        self._entries = store.load()

        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        if not self._entries:
            empty_label = Gtk.Label(label="No recent dictations.")
            empty_label.set_xalign(0.0)
            content.pack_start(empty_label, False, False, 0)
        else:
            for idx, entry in enumerate(self._entries, start=1):
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                info_box.set_hexpand(True)

                timestamp = _format_timestamp(entry.created_at)
                header_label = Gtk.Label(label=f"{idx}. {timestamp}")
                header_label.set_xalign(0.0)
                header_label.set_markup(f"<b>{idx}.</b> {timestamp}")
                info_box.pack_start(header_label, False, False, 0)

                preview = _truncate(entry.text, max_chars=80)
                preview_label = Gtk.Label(label=preview)
                preview_label.set_xalign(0.0)
                preview_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
                preview_label.set_max_width_chars(60)
                info_box.pack_start(preview_label, False, False, 0)

                row_box.pack_start(info_box, True, True, 0)

                copy_btn = Gtk.Button(label="Copy")
                copy_btn.connect("clicked", self._on_copy, entry)
                row_box.pack_start(copy_btn, False, False, 0)

                content.pack_start(row_box, False, False, 4)

        self.show_all()

    def _on_copy(self, _button: Gtk.Button, entry: HistoryEntry) -> None:
        try:
            ClipboardOutput().send(entry.text)
        except OutputError as exc:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text="Clipboard copy failed",
            )
            dialog.format_secondary_text(
                f"{exc}\n\nMake sure a clipboard backend is installed (xclip or pyperclip)."
            )
            dialog.run()
            dialog.destroy()


def _format_timestamp(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:  # noqa: BLE001
        return iso_str


def _truncate(text: str, *, max_chars: int = 80) -> str:
    single_line = text.replace("\n", " ").strip()
    if len(single_line) <= max_chars:
        return single_line
    return single_line[: max_chars - 1] + "\u2026"
