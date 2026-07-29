from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from geotarget.engine import ChampionSubprocessEngine
from geotarget.models import SolveOptions, WorkCheckpoint
from geotarget.runtime_broker import ProductRuntimeBroker


def test_parent_owned_hp_pool_is_warm_across_sessions_and_retired_on_cancel(
    monkeypatch, tmp_path: Path
) -> None:
    class FakePool:
        instances: list[FakePool] = []

        def __init__(self, cpus, worker, environment):
            del worker, environment
            self.cpus = tuple(cpus)
            self.directory = tmp_path / f"pool-{len(self.instances)}"
            self.directory.mkdir()
            self.processes = {}
            self.closed = False
            self.instances.append(self)

        def ensure(self):
            self.processes = {cpu: object() for cpu in self.cpus}

        def close(self):
            self.closed = True
            self.processes.clear()

    monkeypatch.setattr("geotarget.runtime_broker.PersistentHpPool", FakePool)
    with ProductRuntimeBroker(cpus=(0,), hp_worker=tmp_path / "worker.py") as broker:
        first = broker.begin_session((0,))
        assert broker.session_metadata(first)["hp_preloader_warm"] is False
        broker.end_session(first)
        second = broker.begin_session((0,))
        assert broker.session_metadata(second)["hp_preloader_warm"] is True
        assert len(FakePool.instances) == 1
        broker.cancel_session(second)
        assert FakePool.instances[0].closed
        broker.end_session(second)
        third = broker.begin_session((0,))
        assert broker.session_metadata(third)["hp_preloader_warm"] is False
        assert len(FakePool.instances) == 2


def test_optimized_engine_sessions_are_unique_and_reference_bypasses_broker(
    monkeypatch,
) -> None:
    class FakeBroker:
        def __init__(self):
            self.tokens = []
            self.ended = []

        def begin_session(self, cpus):
            token = f"session-{len(self.tokens)}"
            self.tokens.append((token, tuple(cpus)))
            return token

        def session_environment(self, token):
            return {"BROKER_TEST_SESSION": token}

        def session_metadata(self, token):
            return {
                "solve_generation": len(self.tokens),
                "hp_preloader_warm": len(self.tokens) > 1,
            }

        def end_session(self, token):
            self.ended.append(token)

        def cancel_session(self, token):
            pass

    class RecordingEngine(ChampionSubprocessEngine):
        def __init__(self):
            super().__init__()
            self.inputs = []

        def _execute(self, problem, options, reservation):
            self.inputs.append((dict(problem), options.seed, dict(self._runtime_environment)))
            return {"status": "TEST"}, 0.1, WorkCheckpoint(), []

    broker = FakeBroker()
    monkeypatch.setattr("geotarget.engine._product_runtime_broker", lambda: broker)
    reservation = SimpleNamespace(physical_cpus=(0,))
    engine = RecordingEngine()
    first, *_ = engine.execute(
        {"id": "one"}, SolveOptions.model_construct(engine="optimized", seed=11), reservation
    )
    second, *_ = engine.execute(
        {"id": "two"}, SolveOptions.model_construct(engine="optimized", seed=29), reservation
    )
    assert broker.tokens == [("session-0", (0,)), ("session-1", (0,))]
    assert broker.ended == ["session-0", "session-1"]
    assert engine.inputs == [
        ({"id": "one"}, 11, {"BROKER_TEST_SESSION": "session-0"}),
        ({"id": "two"}, 29, {"BROKER_TEST_SESSION": "session-1"}),
    ]
    assert first["geotarget_product"]["runtime_cache"]["hp_preloader_warm"] is False
    assert second["geotarget_product"]["runtime_cache"]["hp_preloader_warm"] is True

    reference = RecordingEngine()
    reference.execute(
        {"id": "reference"},
        SolveOptions(
            engine="reference",
            run_mode="fixed_time",
            max_time_seconds=180,
            cores=1,
            seed=7,
        ),
        reservation,
    )
    assert len(broker.tokens) == 2
    assert reference.inputs[-1][2] == {}
