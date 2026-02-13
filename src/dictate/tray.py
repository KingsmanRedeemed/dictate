"""System tray icon using AyatanaAppIndicator3."""

import signal
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3, GLib, Gtk

from dictate.daemon import Daemon

ICON_ACTIVE = "audio-input-microphone"
ICON_PAUSED = "audio-input-microphone-muted"


class TrayIcon:
    def __init__(self, daemon: Daemon):
        self.daemon = daemon

        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "dictate",
            ICON_ACTIVE,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        self._build_menu()

    def _build_menu(self):
        menu = Gtk.Menu()

        self.toggle_item = Gtk.CheckMenuItem(label="Dictation active")
        self.toggle_item.set_active(True)
        self.toggle_item.connect("toggled", self._on_toggle)
        menu.append(self.toggle_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def _on_toggle(self, item):
        if item.get_active():
            self.daemon.resume()
            self.indicator.set_icon_full(ICON_ACTIVE, "Dictate active")
        else:
            self.daemon.pause()
            self.indicator.set_icon_full(ICON_PAUSED, "Dictate paused")

    def _on_quit(self, _item):
        self.daemon.shutdown()
        Gtk.main_quit()

    def run(self):
        """Start daemon threads, then run GTK main loop (blocks)."""
        self.daemon.start()

        # Allow Ctrl+C to quit from terminal
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._sigint)

        print("dictate running (tray icon active)", file=sys.stderr)
        print("  Hold Right Ctrl to dictate", file=sys.stderr)
        Gtk.main()

    def _sigint(self):
        self._on_quit(None)
        return GLib.SOURCE_REMOVE
