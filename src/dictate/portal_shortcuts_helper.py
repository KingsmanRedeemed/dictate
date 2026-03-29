"""GTK4 helper that requests a portal-backed global shortcut on Wayland."""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from dictate.hotkey_backend import (
    APP_ID,
    PORTAL_BUS_NAME,
    PORTAL_INTERFACE,
    PORTAL_OBJECT_PATH,
    PORTAL_REGISTRY_INTERFACE,
    PORTAL_REQUEST_INTERFACE,
    _portal_trigger,
)

GTK_APP_ID = "io.github.dictate.PortalHelper"


def _token(prefix: str) -> str:
    return f"dictate_{prefix}_{uuid.uuid4().hex}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Request portal global shortcut authorization")
    parser.add_argument("--combo", required=True)
    args = parser.parse_args()

    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("GdkWayland", "4.0")
        gi.require_version("Gio", "2.0")
        gi.require_version("GLib", "2.0")
        from gi.repository import GdkWayland, Gio, GLib, Gtk
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"GTK4 portal helper unavailable: {exc}"}))
        return 2

    app = Gtk.Application(application_id=GTK_APP_ID)
    result: dict[str, object] = {"ok": False, "error": "portal request did not complete"}

    def on_activate(application: Gtk.Application) -> None:
        window = Gtk.ApplicationWindow(application=application)
        window.set_title("Authorize Dictate Shortcut")
        window.set_default_size(360, 120)
        window.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.append(
            Gtk.Label(
                label="GNOME needs to approve Dictate's global push-to-talk shortcut.",
                xalign=0.0,
                wrap=True,
            )
        )
        box.append(
            Gtk.Label(
                label=f"Requested shortcut: {args.combo}",
                xalign=0.0,
                wrap=True,
            )
        )
        window.set_child(box)
        window.present()

        def run_request() -> bool:
            surface = window.get_surface()
            if surface is None:
                return True

            def exported(_surface, handle: str, _user_data=None) -> None:
                parent_window = f"wayland:{handle}"
                try:
                    _request_shortcut(
                        parent_window=parent_window,
                        trigger=_portal_trigger(args.combo),
                        Gio=Gio,
                        GLib=GLib,
                    )
                except Exception as exc:  # noqa: BLE001
                    result["ok"] = False
                    result["error"] = str(exc)
                else:
                    result["ok"] = True
                finally:
                    try:
                        GdkWayland.WaylandToplevel.unexport_handle(surface)
                    except Exception:  # noqa: BLE001
                        pass
                    application.quit()

            if not GdkWayland.WaylandToplevel.export_handle(surface, exported, None):
                result["ok"] = False
                result["error"] = "failed to export Wayland parent window handle"
                application.quit()
            return False

        GLib.timeout_add(200, run_request)

    app.connect("activate", on_activate)
    exit_code = app.run([])
    print(json.dumps(result))
    if result.get("ok"):
        return 0
    return exit_code or 2


def _request_shortcut(*, parent_window: str, trigger: str, Gio, GLib) -> None:  # noqa: ANN001
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    try:
        connection.call_sync(
            PORTAL_BUS_NAME,
            PORTAL_OBJECT_PATH,
            PORTAL_REGISTRY_INTERFACE,
            "Register",
            GLib.Variant("(sa{sv})", (APP_ID, {})),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
    except Exception:  # noqa: BLE001
        pass

    context = GLib.MainContext.default()
    session_token = _token("session")
    session_results = _call_request_method(
        connection,
        Gio,
        GLib,
        context,
        method_name="CreateSession",
        parameters=GLib.Variant(
            "(a{sv})",
            (
                {
                    "handle_token": GLib.Variant("s", session_token),
                    "session_handle_token": GLib.Variant("s", session_token),
                },
            ),
        ),
        token=session_token,
    )
    session_handle = session_results.get("session_handle")
    if not isinstance(session_handle, str) or not session_handle:
        raise RuntimeError("portal CreateSession did not return a session handle")

    bind_token = _token("bind")
    try:
        _call_request_method(
            connection,
            Gio,
            GLib,
            context,
            method_name="BindShortcuts",
            parameters=GLib.Variant(
                "(oa(sa{sv})sa{sv})",
                (
                    session_handle,
                    [
                        (
                            "push-to-talk",
                            {
                                "description": GLib.Variant("s", "Push to talk"),
                                "preferred_trigger": GLib.Variant("s", trigger),
                            },
                        )
                    ],
                    parent_window,
                    {"handle_token": GLib.Variant("s", bind_token)},
                ),
            ),
            token=bind_token,
        )
    finally:
        try:
            connection.call_sync(
                PORTAL_BUS_NAME,
                session_handle,
                "org.freedesktop.portal.Session",
                "Close",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except Exception:  # noqa: BLE001
            pass


def _call_request_method(
    connection,  # noqa: ANN001
    Gio,  # noqa: ANN001
    GLib,  # noqa: ANN001
    context,  # noqa: ANN001
    *,
    method_name: str,
    parameters,
    token: str,
) -> dict:
    sender_path = connection.get_unique_name()[1:].replace(".", "_")
    expected_request_path = (
        f"/org/freedesktop/portal/desktop/request/{sender_path}/{token}"
    )
    result_holder: dict[str, object] = {"done": False}
    wait_loop = GLib.MainLoop.new(context, False)

    def on_response(_connection, _sender_name, _object_path, _interface_name, _signal_name, params):  # noqa: ANN001
        response_code, results = params.unpack()
        result_holder["done"] = True
        result_holder["response_code"] = response_code
        result_holder["results"] = results
        wait_loop.quit()

    subscription_id = connection.signal_subscribe(
        PORTAL_BUS_NAME,
        PORTAL_REQUEST_INTERFACE,
        "Response",
        expected_request_path,
        None,
        Gio.DBusSignalFlags.NONE,
        on_response,
    )
    try:
        connection.call_sync(
            PORTAL_BUS_NAME,
            PORTAL_OBJECT_PATH,
            PORTAL_INTERFACE,
            method_name,
            parameters,
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        while not result_holder["done"]:
            wait_loop.run()
    finally:
        connection.signal_unsubscribe(subscription_id)

    response_code = result_holder.get("response_code")
    if response_code != 0:
        raise RuntimeError(f"portal {method_name} failed with response code {response_code}")
    results = result_holder.get("results")
    if isinstance(results, dict):
        return results
    return {}


if __name__ == "__main__":
    raise SystemExit(main())
