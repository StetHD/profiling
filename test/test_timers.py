# -*- coding: utf-8 -*-
import sys
import time

import pytest

from profiling.__main__ import spawn_thread
from profiling.tracing import TracingProfiler
from profiling.tracing.timers import ThreadTimer, YappiTimer, GreenletTimer
from utils import factorial, find_stats


# is it running on pypy?
try:
    import __pypy__
except ImportError:
    PYPY = False
else:
    PYPY = True
    del __pypy__


def _test_contextual_timer(timer, sleep, spawn, join=lambda x: x.join()):
    def light():
        factorial(10)
        sleep(0.1)
        factorial(10)
    def heavy():
        factorial(10000)
    def profile(profiler):
        with profiler:
            c1 = spawn(light)
            c2 = spawn(heavy)
            for c in [c1, c2]:
                join(c)
        stat1 = find_stats(profiler.stats, 'light')
        stat2 = find_stats(profiler.stats, 'heavy')
        return (stat1, stat2)
    # using the default timer.
    # light() ends later than heavy().  its total time includes heavy's also.
    normal_profiler = TracingProfiler(top_frame=sys._getframe())
    stat1, stat2 = profile(normal_profiler)
    assert stat1.deep_time >= stat2.deep_time
    # using the given timer.
    # light() ends later than heavy() like the above case.  but the total time
    # doesn't include heavy's.  each contexts should have isolated cpu time.
    contextual_profiler = TracingProfiler(top_frame=sys._getframe(),
                                          timer=timer)
    stat1, stat2 = profile(contextual_profiler)
    assert stat1.deep_time < stat2.deep_time


@pytest.mark.xfail(sys.version_info < (3, 3),
                   reason='ThreadTimer requires Python 3.3 or later.')
def test_thread_timer():
    _test_contextual_timer(ThreadTimer(), time.sleep, spawn_thread)


def test_yappi_timer():
    pytest.importorskip('yappi')
    _test_contextual_timer(YappiTimer(), time.sleep, spawn_thread)


@pytest.mark.xfail(PYPY, reason='greenlet.settrace() not available on PyPy.')
def test_greenlet_timer_with_gevent():
    try:
        gevent = pytest.importorskip('gevent', '1')
    except ValueError:
        # gevent Alpha versions doesn't respect Semantic Versioning.
        gevent = pytest.importorskip('gevent')
        assert gevent.__version__.startswith('1.1a')
    _test_contextual_timer(GreenletTimer(), gevent.sleep, gevent.spawn)


@pytest.mark.xfail(PYPY, reason='greenlet.settrace() not available on PyPy.')
def test_greenlet_timer_with_eventlet():
    eventlet = pytest.importorskip('eventlet', '0.15')
    _test_contextual_timer(GreenletTimer(), eventlet.sleep, eventlet.spawn,
                           eventlet.greenthread.GreenThread.wait)


@pytest.mark.xfail(sys.version_info >= (3, 3),
                   reason='ThreadTimer works well on Python 3.3 or later.')
def test_thread_timer_runtime_error():
    with pytest.raises(RuntimeError):
        ThreadTimer()
