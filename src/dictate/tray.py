"""System tray icon using AyatanaAppIndicator3."""

import signal
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3, GLib, Gtk

from dictate.config import load_config, set_stt_runtime_profile, set_stt_selection
from dictate.daemon import Daemon
from dictate.stt import create_speech_to_text

ICON_ACTIVE = "microphone-sensitivity-high-symbolic"
ICON_PAUSED = "microphone-disabled-symbolic"
MODEL_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("faster-whisper", "base", "faster-whisper / base"),
    ("faster-whisper", "turbo", "faster-whisper / turbo"),
    ("faster-whisper", "large-v3", "faster-whisper / large-v3"),
    ("nemo-canary", "nvidia/canary-1b-flash", "nemo-canary / canary-1b-flash"),
    ("nemo-canary", "nvidia/canary-1b-v2", "nemo-canary / canary-1b-v2"),
    ("nemo-canary", "nvidia/canary-1b", "nemo-canary / canary-1b"),
)
RUNTIME_PROFILES: tuple[tuple[str, str, str], ...] = (
    ("cuda", "int8", "cuda / int8 (recommended)"),
    ("cuda", "float16", "cuda / float16"),
    ("cpu", "int8", "cpu / int8"),
    ("auto", "int8", "auto / int8"),
)


class TrayIcon:
    def __init__(self, daemon: Daemon):
        self.daemon = daemon
        self._switch_in_progress = False
        self._syncing_model_menu = False
        self._syncing_profile_menu = False
        self._model_items: dict[tuple[str, str], Gtk.RadioMenuItem] = {}
        self._profile_items: dict[tuple[str, str], Gtk.RadioMenuItem] = {}

        self._active_backend, self._active_model = self.daemon.current_backend_model()
        self._stt_device, self._stt_compute_type = self.daemon.runtime_stt_options()

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

        models_item = Gtk.MenuItem(label="Speech Model")
        models_item.set_submenu(self._build_model_submenu())
        menu.append(models_item)

        runtime_item = Gtk.MenuItem(label="Runtime Profile")
        runtime_item.set_submenu(self._build_runtime_submenu())
        menu.append(runtime_item)

        hotwords_item = Gtk.MenuItem(label="Manage Hotwords...")
        hotwords_item.connect("activate", self._on_manage_hotwords)
        menu.append(hotwords_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def _build_model_submenu(self) -> Gtk.Menu:
        submenu = Gtk.Menu()
        presets = list(MODEL_PRESETS)
        active_key = (self._active_backend, self._active_model)
        if active_key not in {(backend, model) for backend, model, _label in MODEL_PRESETS}:
            presets.insert(
                0,
                (
                    self._active_backend,
                    self._active_model,
                    f"current / {self._active_backend} / {self._active_model}",
                ),
            )

        radio_group: Gtk.RadioMenuItem | None = None
        for backend, model, label in presets:
            if radio_group is None:
                item = Gtk.RadioMenuItem.new_with_label(None, label)
                radio_group = item
            else:
                item = Gtk.RadioMenuItem.new_with_label_from_widget(radio_group, label)
            item.connect("toggled", self._on_model_selected, backend, model)
            self._model_items[(backend, model)] = item
            submenu.append(item)

        self._set_active_model_menu_item(self._active_backend, self._active_model)
        return submenu

    def _build_runtime_submenu(self) -> Gtk.Menu:
        submenu = Gtk.Menu()
        profiles = list(RUNTIME_PROFILES)
        active_key = (self._stt_device, self._stt_compute_type)
        known_profiles = {
            (device, compute_type)
            for device, compute_type, _label in RUNTIME_PROFILES
        }
        if active_key not in known_profiles:
            profiles.insert(
                0,
                (
                    self._stt_device,
                    self._stt_compute_type,
                    f"current / {self._stt_device} / {self._stt_compute_type}",
                ),
            )

        radio_group: Gtk.RadioMenuItem | None = None
        for device, compute_type, label in profiles:
            if radio_group is None:
                item = Gtk.RadioMenuItem.new_with_label(None, label)
                radio_group = item
            else:
                item = Gtk.RadioMenuItem.new_with_label_from_widget(radio_group, label)
            item.connect("toggled", self._on_profile_selected, device, compute_type)
            self._profile_items[(device, compute_type)] = item
            submenu.append(item)

        self._set_active_profile_menu_item(self._stt_device, self._stt_compute_type)
        return submenu

    def _on_toggle(self, item):
        if item.get_active():
            self.daemon.resume()
            self.indicator.set_icon_full(ICON_ACTIVE, "Dictate active")
        else:
            self.daemon.pause()
            self.indicator.set_icon_full(ICON_PAUSED, "Dictate paused")

    def _on_manage_hotwords(self, _item):
        from dictate.hotwords_dialog import HotwordsDialog

        dialog = HotwordsDialog()
        dialog.run()
        dialog.destroy()

        # Live-reload: update engine hotwords from saved config
        self.daemon.set_hotwords(load_config().hotwords_str)

    def _on_model_selected(self, item, backend: str, model: str) -> None:
        if self._syncing_model_menu:
            return
        if not item.get_active():
            return
        if self._switch_in_progress:
            return
        if (backend, model) == (self._active_backend, self._active_model):
            return

        self._start_switch(
            backend=backend,
            model=model,
            device=self._stt_device,
            compute_type=self._stt_compute_type,
        )

    def _on_profile_selected(self, item, device: str, compute_type: str) -> None:
        if self._syncing_profile_menu:
            return
        if not item.get_active():
            return
        if self._switch_in_progress:
            return
        if (device, compute_type) == (self._stt_device, self._stt_compute_type):
            return

        self._start_switch(
            backend=self._active_backend,
            model=self._active_model,
            device=device,
            compute_type=compute_type,
        )

    def _start_switch(
        self,
        *,
        backend: str,
        model: str,
        device: str,
        compute_type: str,
    ) -> None:
        self._switch_in_progress = True
        self._set_switch_menu_sensitive(False)
        threading.Thread(
            target=self._switch_worker,
            args=(backend, model, device, compute_type),
            daemon=True,
        ).start()

    def _switch_worker(self, backend: str, model: str, device: str, compute_type: str) -> None:
        print(
            f"Switching STT to {backend} / {model} on {device} ({compute_type})...",
            file=sys.stderr,
        )
        try:
            stt = create_speech_to_text(
                backend=backend,  # type: ignore[arg-type]
                model=model,
                device=device,  # type: ignore[arg-type]
                compute_type=compute_type,  # type: ignore[arg-type]
            )
            _ = stt.model
            self.daemon.switch_speech_to_text(stt, hotwords=load_config().hotwords_str)
            set_stt_selection(backend=backend, model=model)
            set_stt_runtime_profile(device=device, compute_type=compute_type)
        except Exception as exc:  # noqa: BLE001
            GLib.idle_add(
                self._finalize_switch,
                False,
                backend,
                model,
                device,
                compute_type,
                str(exc),
            )
            return

        GLib.idle_add(self._finalize_switch, True, backend, model, device, compute_type, "")

    def _finalize_switch(
        self,
        ok: bool,
        backend: str,
        model: str,
        device: str,
        compute_type: str,
        error_message: str,
    ) -> bool:
        if ok:
            self._active_backend = backend
            self._active_model = model
            self._stt_device = device
            self._stt_compute_type = compute_type
            print(
                f"STT switched to {backend} / {model} on {device} ({compute_type})",
                file=sys.stderr,
            )
            self._set_active_model_menu_item(backend, model)
            self._set_active_profile_menu_item(device, compute_type)
        else:
            print(
                f"STT switch failed ({backend}/{model} {device}/{compute_type}): {error_message}",
                file=sys.stderr,
            )
            self._set_active_model_menu_item(self._active_backend, self._active_model)
            self._set_active_profile_menu_item(self._stt_device, self._stt_compute_type)
            dialog = Gtk.MessageDialog(
                transient_for=None,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"Failed to switch to {backend} / {model} ({device}, {compute_type})",
            )
            dialog.format_secondary_text(error_message)
            dialog.run()
            dialog.destroy()

        self._switch_in_progress = False
        self._set_switch_menu_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _set_switch_menu_sensitive(self, sensitive: bool) -> None:
        for item in self._model_items.values():
            item.set_sensitive(sensitive)
        for item in self._profile_items.values():
            item.set_sensitive(sensitive)

    def _set_active_model_menu_item(self, backend: str, model: str) -> None:
        item = self._model_items.get((backend, model))
        if item is None:
            return
        self._syncing_model_menu = True
        try:
            item.set_active(True)
        finally:
            self._syncing_model_menu = False

    def _set_active_profile_menu_item(self, device: str, compute_type: str) -> None:
        item = self._profile_items.get((device, compute_type))
        if item is None:
            return
        self._syncing_profile_menu = True
        try:
            item.set_active(True)
        finally:
            self._syncing_profile_menu = False

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
