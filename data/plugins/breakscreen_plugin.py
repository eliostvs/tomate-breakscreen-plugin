import logging

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk
import tomate.pomodoro.plugin as plugin
from tomate.pomodoro import Events, Subscriber, on, suppress_errors, SessionPayload, SessionType, TimerPayload

logger = logging.getLogger(__name__)


class BreakScreen(Subscriber):
    def __init__(self, monitor: int, geometry: Gdk.Rectangle):
        logger.debug(
            "action=init_screen monitor=%d x=%d y=%d width=%d height=%d",
            monitor,
            geometry.x,
            geometry.y,
            geometry.width,
            geometry.height,
        )
        self.monitor = monitor
        countdown = Gtk.Label(
            "00:00",
            name="countdown",
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        box = Gtk.Box()
        box.pack_start(countdown, True, True, 0)
        window = Gtk.Window(
            can_focus=False,
            decorated=False,
            deletable=False,
            focus_on_map=False,
            gravity=Gdk.Gravity.CENTER,
            name="breakscreen",
            opacity=0.8,
            skip_taskbar_hint=True,
            urgency_hint=True,
        )
        window.set_visual(window.get_screen().get_rgba_visual())
        window.stick()
        window.set_keep_above(True)
        window.fullscreen()
        window.move(geometry.x, geometry.y)
        window.resize(geometry.width, geometry.height)
        window.add(box)

        self.widget = window
        self.countdown = countdown

    @on(Events.SESSION_START)
    def _on_session_start(self, *_, payload=SessionPayload):
        logger.debug("action=session_start monitor=%d session=%s", self.monitor, payload.type)
        if payload.type != SessionType.POMODORO:
            self.countdown.set_text(payload.countdown)
            self.widget.show_all()

    @on(Events.SESSION_INTERRUPT, Events.SESSION_END)
    def _on_session_stops(self, *_, **__):
        logger.debug("action=session_start monitor=%d", self.monitor)
        self.widget.hide()

    @on(Events.TIMER_UPDATE)
    def _on_timer_update(self, _, payload: TimerPayload) -> None:
        self.countdown.set_text(payload.countdown)


class BreakScreenPlugin(plugin.Plugin):
    @suppress_errors
    def __init__(self, display=Gdk.Display.get_default()):
        super().__init__()
        self.display = display
        self.screens = []

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
            screen = BreakScreen(monitor, geometry)
            screen.connect(self.bus)
            self.screens.append(screen)

    @suppress_errors
    def deactivate(self):
        super().deactivate()

        for screen in self.screens:
            screen.disconnect(self.bus)
            screen.widget.destroy()

        del self.screens[:]
