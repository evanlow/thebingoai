"""Tests for `runner._run_chunks` — best-effort chunked dlt runs for new-model
(schedule) pipeline runs. Verifies chunk boundaries, byte summing, and that a
failing chunk is isolated (later chunks still run; run marked failed).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from backend.pipelines.runner import _run_chunks, _CHUNK_SIZE


def _specs(n):
    return [{"source_table": f"t{i}", "target_table": f"tgt{i}"} for i in range(n)]


def _bytes(load_info):
    """Test stub: dlt_pipeline.run returns the byte count directly."""
    return load_info


def test_chunk_boundaries_and_call_count():
    specs = _specs(25)  # 25 / 10 → chunks of 10, 10, 5
    captured = []
    dlt_pipeline = MagicMock()
    dlt_pipeline.run.return_value = 0

    def source_fn(conn, ec):
        captured.append(list(ec["table_specs"]))
        return object()

    _run_chunks(specs, {"k": "v"}, dlt_pipeline, source_fn, "conn",
                "p1", "s1", _bytes)

    assert dlt_pipeline.run.call_count == 3
    assert [len(c) for c in captured] == [10, 10, 5]
    # order preserved, no overlap
    assert captured[0][0]["source_table"] == "t0"
    assert captured[2][-1]["source_table"] == "t24"


def test_bytes_summed_across_chunks():
    specs = _specs(15)  # 2 chunks
    dlt_pipeline = MagicMock()
    dlt_pipeline.run.side_effect = [100, 50]  # _bytes returns these
    total, err = _run_chunks(specs, {}, dlt_pipeline,
                             lambda c, ec: object(), "conn", "p1", "s1", _bytes)
    assert total == 150
    assert err is None


def test_failing_chunk_isolated_later_chunks_run():
    specs = _specs(25)  # 3 chunks; middle one fails
    dlt_pipeline = MagicMock()
    dlt_pipeline.run.side_effect = [100, RuntimeError("boom"), 30]
    total, err = _run_chunks(specs, {}, dlt_pipeline,
                             lambda c, ec: object(), "conn", "p1", "s1", _bytes)
    assert dlt_pipeline.run.call_count == 3      # all chunks attempted
    assert total == 130                          # good chunks still counted
    assert err is not None
    assert "boom" in err
    assert "tgt10" in err                        # failing chunk's target tables


def test_all_success_returns_no_error():
    dlt_pipeline = MagicMock()
    dlt_pipeline.run.return_value = 0
    _, err = _run_chunks(_specs(5), {}, dlt_pipeline,
                         lambda c, ec: object(), "conn", "p1", "s1", _bytes)
    assert err is None


def test_empty_specs_no_runs():
    dlt_pipeline = MagicMock()
    total, err = _run_chunks([], {}, dlt_pipeline,
                             lambda c, ec: object(), "conn", "p1", "s1", _bytes)
    assert dlt_pipeline.run.call_count == 0
    assert (total, err) == (0, None)


def test_chunk_size_constant():
    assert _CHUNK_SIZE == 10
