import random
from typing import Iterator

import pytest
from wiring import Graph

from tomate.pomodoro import Bus, Config, Events, Session, SessionType, TimerPayload
from tomate.ui.testing import Q, create_session_payload


@pytest.fixture
def bus() -> Bus:
    return Bus()


@pytest.fixture
def graph() -> Graph:
    instance = Graph()
    instance.register_instance(Graph, instance)
    return instance


@pytest.fixture
def session(mocker):
    return mocker.Mock(spec=Session)


@pytest.fixture
def plugin(bus, graph, session):
    graph.providers.clear()
    graph.register_instance("tomate.bus", bus)
    graph.register_instance("tomate.config", Config(bus))
    graph.register_instance("tomate.session", session)

    import breakscreen_plugin

    instance = breakscreen_plugin.BreakScreenPlugin()
    instance.configure(bus, graph)
    return instance


@pytest.mark.parametrize("session_type", [SessionType.SHORT_BREAK, SessionType.LONG_BREAK])
def test_shows_screens_when_session_starts(session_type, bus, plugin):
    plugin.activate()

    payload = create_session_payload(type=session_type)
    bus.send(Events.SESSION_START, payload=payload)

    assert all([screen.widget.props.visible for screen in plugin.screens])
    assert label_text(payload.countdown, plugin)


@pytest.mark.parametrize("stop_event", [Events.SESSION_INTERRUPT, Events.SESSION_END])
def test_hides_screens_when_plugins_is_activated(stop_event, bus, plugin):
    plugin.activate()

    payload = create_session_payload(type=SessionType.SHORT_BREAK)
    bus.send(Events.SESSION_START, payload=payload)
    bus.send(stop_event, payload=payload)

    assert none([screen.widget.props.visible for screen in plugin.screens])


def test_do_no_show_screen_when_plugin_is_not_active(bus, plugin):
    plugin.activate()
    plugin.deactivate()

    payload = create_session_payload(type=SessionType.SHORT_BREAK)
    bus.send(Events.SESSION_START, payload=payload)

    assert none([screen.widget.props.visible for screen in plugin.screens])


def test_do_not_show_screen_when_session_is_pomodoro(bus, plugin):
    plugin.activate()

    payload = create_session_payload(type=SessionType.POMODORO)
    bus.send(Events.SESSION_START, payload=payload)

    assert none([screen.widget.props.visible for screen in plugin.screens])


def test_updates_screens_countdown(bus, plugin):
    plugin.activate()

    time_left = random.randint(1, 100)

    payload = TimerPayload(time_left=time_left, duration=150)
    bus.send(Events.TIMER_UPDATE, payload=payload)

    assert label_text(payload.countdown, plugin)


def none(values: Iterator) -> bool:
    return all([value is False for value in values])


def label_text(countdown: str, plugin) -> bool:
    return len(plugin.screens) > 0 and all(
        [Q.select(screen.widget, Q.props("name", "countdown")).get_text() == countdown for screen in plugin.screens]
    )
