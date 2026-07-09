"""Bounded offloading of blocking data-source calls (SRS §15.12, §7.1).

The Earth Engine SDK is synchronous, so GEE-backed sources run via a worker
thread. Bare ``asyncio.to_thread`` admits unlimited concurrent calls into the
interpreter's *shared* default thread pool — one slow GEE region could occupy
every worker thread and pin unrelated request handling. Every blocking source
call goes through :func:`run_blocking` instead, which admits at most
``settings.gee_max_concurrency`` calls at a time; the excess queue on the event
loop (cheap) rather than in the thread pool (scarce).

The semaphore is created lazily per event loop: an ``asyncio.Semaphore`` binds
to the loop that first awaits it, and the test suite runs each test on a fresh
loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from weakref import WeakKeyDictionary

from app.core.config import get_settings

_semaphores: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    semaphore = _semaphores.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(get_settings().gee_max_concurrency)
        _semaphores[loop] = semaphore
    return semaphore


async def run_blocking[T](fn: Callable[..., T], /, *args: object) -> T:
    """Run a blocking source call in a worker thread, bounded by the semaphore."""
    async with _semaphore():
        return await asyncio.to_thread(fn, *args)
