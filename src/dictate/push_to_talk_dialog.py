"""GTK 3 dialog for configuring the push-to-talk combo."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from dictate.hotkey import HotkeyParseError, format_hotkey_combo, normalize_push_to_talk_combo

PRESET_COMBOS: tuple[tuple[str, str], ...] = (
    ("Right Ctrl", "ctrl_r"),
    ("Left Ctrl", "ctrl_l"),
    ("Ctrl + Space", "ctrl+space"),
    ("Ctrl + Shift", "ctrl+shift"),
    ("Left Ctrl + Space", "ctrl_l+space"),
    ("Right Alt", "alt_r"),
    ("Left Alt", "alt_l"),
)


class PushToTalkDialog(Gtk.Dialog):
    """Modal dialog to edit and validate the push-to-talk combo."""

    def __init__(self, current_combo: str, parent: Gtk.Window | None = None):
        super().__init__(
            title="Push-to-Talk Settings",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(420, 220)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)

        self.result_combo = normalize_push_to_talk_combo(current_combo)

        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        info = Gtk.Label(
            label="Use a holdable combo such as ctrl_r, ctrl_l, ctrl+space, or ctrl+shift.",
            xalign=0.0,
        )
        info.set_line_wrap(True)
        content.pack_start(info, False, False, 0)

        preset_label = Gtk.Label(label="Preset", xalign=0.0)
        content.pack_start(preset_label, False, False, 0)

        self.preset_combo = Gtk.ComboBoxText()
        self.preset_combo.append("custom", "Custom")
        current_preset = "custom"
        for label, combo in PRESET_COMBOS:
            self.preset_combo.append(combo, f"{label} ({format_hotkey_combo(combo)})")
            if combo == self.result_combo:
                current_preset = combo
        self.preset_combo.set_active_id(current_preset)
        self.preset_combo.connect("changed", self._on_preset_changed)
        content.pack_start(self.preset_combo, False, False, 0)

        entry_label = Gtk.Label(label="Combo", xalign=0.0)
        content.pack_start(entry_label, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_text(self.result_combo)
        self.entry.set_placeholder_text("ctrl_r or ctrl+space")
        self.entry.set_hexpand(True)
        content.pack_start(self.entry, False, False, 0)

        examples = Gtk.Label(
            label="Supported tokens include ctrl, ctrl_l, ctrl_r, shift, alt, super, space, enter, tab, esc, and single letters or digits.",
            xalign=0.0,
        )
        examples.set_line_wrap(True)
        content.pack_start(examples, False, False, 0)

        self.show_all()

    def run(self) -> int:
        while True:
            response = super().run()
            if response != Gtk.ResponseType.OK:
                return response
            try:
                self.result_combo = normalize_push_to_talk_combo(self.entry.get_text())
                return response
            except HotkeyParseError as exc:
                self._show_error(str(exc))

    def _on_preset_changed(self, widget: Gtk.ComboBoxText) -> None:
        active_id = widget.get_active_id()
        if active_id and active_id != "custom":
            self.entry.set_text(active_id)

    def _show_error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Invalid push-to-talk combo",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
