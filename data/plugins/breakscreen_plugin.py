import logging
from collections import namedtuple
from locale import gettext as _

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk, GLib
import tomate.pomodoro.plugin as plugin
from tomate.pomodoro import (
    Config,
    Events,
    Session,
    Subscriber,
    on,
    suppress_errors,
    SessionPayload,
    SessionEndPayload,
    SessionType,
    TimerPayload,
    ConfigPayload,
)

logger = logging.getLogger(__name__)

SECTION_NAME = "break_screen"
SKIP_BREAK_OPTION = "skip_break"
AUTO_START_OPTION = "auto_start"


class Monitor(namedtuple("Monitor", "number geometry")):
    @property
    def x(self) -> int:
        return self.geometry.x

    @property
    def y(self) -> int:
        return self.geometry.y

    @property
    def width(self) -> int:
        return self.geometry.width

    @property
    def height(self) -> int:
        return self.geometry.height


class BreakScreen(Subscriber):
    def __init__(self, monitor: Monitor, session: Session, config: Config):
        logger.debug("action=init_screen monitor=%s", monitor)

        self.monitor = monitor
        self.session = session
        self.options = self.create_options(config)
        self.countdown = self.create_countdown()
        box = Gtk.Box()
        box.pack_start(self.countdown, True, True, 0)
        self.widget = self.create_window(self.monitor)
        self.widget.add(box)

    def create_options(self, config):
        return {
            SKIP_BREAK_OPTION: config.get_bool(SECTION_NAME, SKIP_BREAK_OPTION, fallback=False),
            AUTO_START_OPTION: config.get_bool(SECTION_NAME, AUTO_START_OPTION, fallback=False),
        }

    def create_countdown(self):
        return Gtk.Label(
            "00:00",
            name="countdown",
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )

    def create_window(self, monitor):
        window = Gtk.Window(
            can_focus=False,
            decorated=False,
            deletable=False,
            focus_on_map=False,
            gravity=Gdk.Gravity.CENTER,
            name="breakscreen",
            opacity=0.9,
            skip_taskbar_hint=True,
            urgency_hint=True,
        )
        window.set_visual(window.get_screen().get_rgba_visual())
        window.stick()
        window.set_keep_above(True)
        window.fullscreen()
        window.move(monitor.x, monitor.y)
        window.resize(monitor.width, monitor.height)
        return window

    @on(Events.SESSION_START)
    def on_session_start(self, *_, payload=SessionPayload) -> None:
        logger.debug("action=session_start monitor=%d session=%s", self.monitor.number, payload.type)

        if payload.type != SessionType.POMODORO:
            self.countdown.set_text(payload.countdown)
            self.widget.show_all()

    @on(Events.SESSION_INTERRUPT)
    def on_session_interrupt(self, *_, **__) -> None:
        logger.debug("action=session_start monitor=%d", self.monitor.number)
        self.widget.hide()

    @on(Events.SESSION_END)
    def on_session_end(self, _, payload: SessionEndPayload) -> None:
        logger.debug(
            "action=session_end monitor=%d auto_start=%s session_type=%s",
            self.monitor.number,
            self.auto_start,
            payload.type,
        )

        if payload.type != SessionType.POMODORO and self.auto_start:
            GLib.timeout_add_seconds(0, self.start_session)
        else:
            self.widget.hide()

    def start_session(self) -> bool:
        self.session.start()
        return False

    @property
    def auto_start(self) -> bool:
        return self.options[AUTO_START_OPTION]

    @on(Events.TIMER_UPDATE)
    def on_timer_update(self, _, payload: TimerPayload) -> None:
        logger.debug("action=update_countdown countdown=%s", payload.countdown)
        self.countdown.set_text(payload.countdown)

    @on(Events.CONFIG_CHANGE)
    def on_settings_change(self, _, payload: ConfigPayload) -> None:
        if payload.section == SECTION_NAME:
            logger.debug("action=change_option action=%s option=%s", payload.action, payload.option)
            self.options[payload.option] = payload.action == "set"


class SettingsDialog:
    def __init__(self, config: Config, toplevel):
        self.options = {SKIP_BREAK_OPTION: False, AUTO_START_OPTION: False}
        self.config = config
        self.widget = self.create_dialog(toplevel)

    def create_dialog(self, toplevel) -> Gtk.Dialog:
        dialog = Gtk.Dialog(
            border_width=12,
            modal=True,
            resizable=False,
            title=_("Preferences"),
            transient_for=toplevel,
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
        )
        dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda widget, _: widget.destroy())
        dialog.set_size_request(350, -1)
        dialog.get_content_area().add(self.create_options())
        return dialog

    def create_options(self):
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin_bottom=12, margin_top=12)
        self.create_option(grid, 0, _("Auto start:"), AUTO_START_OPTION)
        self.create_option(grid, 1, _("Skip break:"), SKIP_BREAK_OPTION)
        return grid

    def run(self):
        self.widget.show_all()
        return self.widget

    def create_option(self, grid: Gtk.Grid, row: int, label: str, option):
        active = self.config.get_bool(SECTION_NAME, option, fallback=False)
        self.options[option] = active

        label = Gtk.Label(label=_(label), hexpand=True, halign=Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)

        switch = Gtk.Switch(hexpand=True, halign=Gtk.Align.START, name=option, active=active)
        switch.connect("notify::active", self.on_option_change, option)
        grid.attach_next_to(switch, label, Gtk.PositionType.RIGHT, 1, 1)

    def on_option_change(self, switch: Gtk.Switch, _, option: str):
        self.options[option] = switch.props.active

        if switch.props.active:
            self.config.set(SECTION_NAME, option, "true")
        else:
            logger.debug("action=remove_option name=%s", option)
            self.config.remove(SECTION_NAME, option)


class BreakScreenPlugin(plugin.Plugin):
    has_settings = True

    @suppress_errors
    def __init__(self, display=Gdk.Display.get_default()):
        super().__init__()
        self.display = display
        self.screens = []
        self.configure_style()

    def configure_style(self):
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(b"#countdown { font-size: 10em; }")
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    @suppress_errors
    def activate(self):
        super().activate()

        for monitor in range(self.display.get_n_monitors()):
            geometry = self.display.get_monitor(monitor).get_geometry()
            screen = BreakScreen(
                Monitor(monitor, geometry), self.graph.get("tomate.session"), self.graph.get("tomate.config")
            )
            screen.connect(self.bus)
            self.screens.append(screen)

    @suppress_errors
    def deactivate(self):
        super().deactivate()

        for screen in self.screens:
            screen.disconnect(self.bus)
            screen.widget.destroy()

        del self.screens[:]

    def settings_window(self, toplevel) -> SettingsDialog:
        return SettingsDialog(self.graph.get("tomate.config"), toplevel)
