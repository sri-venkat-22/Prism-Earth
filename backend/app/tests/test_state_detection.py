"""State Detection Service tests (SRS §15.6, §15.7).

The hierarchy-assembly logic is tested with a fake session (no database). A live
PostGIS check is provided as an opt-in integration test guarded by
``PRISM_TEST_DATABASE_URL`` (a migrated + seeded database).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app.core.errors import ValidationAppError
from app.services.state_detection import StateDetectionService


class _Result:
    def __init__(self, obj: object | None) -> None:
        self._obj = obj

    def scalars(self) -> _Result:
        return self

    def first(self) -> object | None:
        return self._obj


class FakeSession:
    """Returns queued rows from successive ``execute`` calls (SRS §15.7 order)."""

    def __init__(self, queue: list[object | None]) -> None:
        self._queue = queue
        self.calls = 0

    async def execute(self, statement: object) -> _Result:
        obj = self._queue[self.calls] if self.calls < len(self._queue) else None
        self.calls += 1
        return _Result(obj)


def _unit(id_: int, name: str, code: str | None = None) -> SimpleNamespace:
    ns = SimpleNamespace(id=id_, name=name)
    if code is not None:
        ns.code = code
    return ns


@pytest.mark.parametrize("lat, lng", [(91.0, 78.0), (-91.0, 78.0), (17.0, 181.0), (17.0, -181.0)])
async def test_out_of_range_coordinate_raises(lat: float, lng: float) -> None:
    service = StateDetectionService(FakeSession([]))  # type: ignore[arg-type]
    with pytest.raises(ValidationAppError):
        await service.resolve(lat, lng)


async def test_full_hierarchy_assembled() -> None:
    queue = [
        _unit(1, "Telangana", "TG"),
        _unit(2, "Hyderabad", "HYD"),
        _unit(3, "Khairatabad", "KHB"),
        _unit(4, "Khairatabad", "KHB-V"),
        _unit(5, "Greater Hyderabad Municipal Corporation"),  # no code
        _unit(6, "Khairatabad Ward"),  # no code
    ]
    service = StateDetectionService(FakeSession(queue))  # type: ignore[arg-type]
    ctx = await service.resolve(17.385, 78.486)

    assert ctx.in_pilot_region is True
    assert ctx.resolved is True
    assert ctx.state and ctx.state.name == "Telangana" and ctx.state.code == "TG"
    assert ctx.district and ctx.district.name == "Hyderabad"
    assert ctx.mandal and ctx.mandal.name == "Khairatabad"
    assert ctx.village and ctx.village.name == "Khairatabad"
    assert ctx.municipality and ctx.municipality.code is None
    assert ctx.ward and ctx.ward.name == "Khairatabad Ward"


async def test_outside_region_is_flagged() -> None:
    service = StateDetectionService(FakeSession([None]))  # type: ignore[arg-type]
    ctx = await service.resolve(19.07, 72.87)
    assert ctx.in_pilot_region is False
    assert ctx.resolved is False
    assert ctx.state is None


async def test_partial_hierarchy_stops_at_state() -> None:
    """State found but no district seeded there — children are not queried."""
    session = FakeSession([_unit(1, "Telangana", "TG"), None])
    service = StateDetectionService(session)  # type: ignore[arg-type]
    ctx = await service.resolve(18.5, 79.5)

    assert ctx.state and ctx.state.name == "Telangana"
    assert ctx.district is None
    assert ctx.mandal is None and ctx.municipality is None
    # Only state + district were queried (district None short-circuits the rest).
    assert session.calls == 2


# --------------------------------------------------------------------------- #
# Opt-in integration test against a live, seeded PostGIS database.            #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not os.getenv("PRISM_TEST_DATABASE_URL"),
    reason="Set PRISM_TEST_DATABASE_URL to a migrated+seeded DB to run the live check.",
)
async def test_resolves_hyderabad_against_postgis() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(os.environ["PRISM_TEST_DATABASE_URL"])
    try:
        async with async_sessionmaker(engine)() as session:
            ctx = await StateDetectionService(session).resolve(17.385, 78.486)
        assert ctx.in_pilot_region is True
        assert ctx.state and ctx.state.name == "Telangana"
        assert ctx.district and ctx.district.name == "Hyderabad"
    finally:
        await engine.dispose()
