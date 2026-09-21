#!/usr/bin/env python3
"""Bounded opt-in baseline for durable append and outer transport queue costs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import queue
import resource
import statistics
import sys
import tempfile
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[2]
TRANSPORT = ROOT / "skills/agent/runtime/process_transport.py"
MAX_CHUNKS = 2_000


def load_transport():
    runtime = str(TRANSPORT.parent)
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    spec = importlib.util.spec_from_file_location("resource_baseline_process_transport", TRANSPORT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rss_bytes() -> int:
    # Linux reports KiB; macOS reports bytes. This fixture records the platform.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def measure(action):
    before_cpu = time.process_time_ns()
    before_wall = time.perf_counter_ns()
    before_rss = rss_bytes()
    tracemalloc.start()
    try:
        value = action()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {
        "wallMs": (time.perf_counter_ns() - before_wall) / 1_000_000,
        "cpuMs": (time.process_time_ns() - before_cpu) / 1_000_000,
        "rssGrowthBytes": max(0, rss_bytes() - before_rss),
        "tracemallocPeakBytes": peak,
        **value,
    }


def append_scenario(transport, directory: Path, chunks: int, chunk_bytes: int):
    path = directory / f"append-{chunks}-{chunk_bytes}.jsonl"
    path.unlink(missing_ok=True)
    payload = (b"x" * (chunk_bytes - 1)) + b"\n"

    def action():
        for _ in range(chunks):
            if not transport.append_bounded(path, payload, chunks * chunk_bytes):
                raise RuntimeError("bounded append unexpectedly rejected fixture content")
        return {
            "chunks": chunks,
            "chunkBytes": chunk_bytes,
            "writtenBytes": path.stat().st_size,
            "openCallsByContract": chunks,
            "fsyncCallsByContract": chunks,
            "closeCallsByContract": chunks,
        }

    return measure(action)


def queue_scenario(items: int, payload_bytes: int):
    output: queue.Queue[tuple[str, str | None]] = queue.Queue()
    payload = "x" * payload_bytes

    def action():
        for _ in range(items):
            output.put(("line", payload))
        high_water = output.qsize()
        for _ in range(items):
            output.get_nowait()
        return {"items": items, "payloadBytes": payload_bytes, "highWaterItems": high_water,
                "queueMaxsize": output.maxsize, "remainingItems": output.qsize()}

    return measure(action)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=3, choices=range(3, 6))
    args = parser.parse_args()
    output = args.output.absolute()
    # Reserve the destination before doing work; never overwrite or follow a final symlink.
    with output.open("x", encoding="utf-8") as stream:
        stream.write("{}\n")

    transport = load_transport()
    evidence = {
        "schemaVersion": 1,
        "label": "Agent Factory plugin bounded resource baseline",
        "source": {"path": "skills/agent/runtime/process_transport.py",
                   "sha256": hashlib.sha256(TRANSPORT.read_bytes()).hexdigest()},
        "environment": {"python": sys.version, "platform": platform.platform()},
        "isolation": {"disposableFixture": True, "realRuntimeHistoryUsed": False,
                      "networkUsed": False, "maxChunks": MAX_CHUNKS},
        "durableAppend": [],
        "outerQueueBurst": [],
        "limitations": [
            "The append fixture measures the existing durability contract, including one open/fsync/close cycle per chunk; it does not change batching or recovery semantics.",
            "The queue burst is a bounded producer-only stress proxy for the outer queue.Queue used by exec.py; native RPC queue behavior is outside this measurement.",
            "No live Codex process, cancellation, runtime history, or GPU is exercised.",
        ],
    }
    with tempfile.TemporaryDirectory(prefix="af-plugin-resource-baseline-") as temporary:
        directory = Path(temporary)
        for chunks, chunk_bytes in ((200, 256), (1_000, 256), (2_000, 1_024)):
            rows = [append_scenario(transport, directory, chunks, chunk_bytes)
                    for _ in range(args.iterations)]
            evidence["durableAppend"].append({
                "chunks": chunks,
                "chunkBytes": chunk_bytes,
                "iterations": rows,
                "medianWallMs": statistics.median(row["wallMs"] for row in rows),
                "medianCpuMs": statistics.median(row["cpuMs"] for row in rows),
                "openCallsByContract": chunks,
                "fsyncCallsByContract": chunks,
                "closeCallsByContract": chunks,
                "writtenBytes": chunks * chunk_bytes,
            })
        for items in (1_000, 5_000, 20_000):
            rows = [queue_scenario(items, 256) for _ in range(args.iterations)]
            evidence["outerQueueBurst"].append({
                "items": items,
                "payloadBytes": 256,
                "iterations": rows,
                "medianWallMs": statistics.median(row["wallMs"] for row in rows),
                "medianCpuMs": statistics.median(row["cpuMs"] for row in rows),
                "highWaterItems": items,
                "queueMaxsize": 0,
            })

    evidence["comparisonMethod"] = {
        "command": "python3 tests/benchmarks/benchmark_resource_baseline.py --output <new-json-path>",
        "compare": "Use the same filesystem and Python build; compare exact call/byte counts and medians from at least three iterations.",
        "thresholds": {
            "durability": "written bytes must equal chunks x chunkBytes; any batching optimization must separately prove equivalent crash recovery before changing fsync frequency",
            "resourceRegression": "call counts and bytes must not increase; median CPU/wall may not exceed max(1.25x baseline, baseline + 5ms)",
            "backpressure": "a bounded replacement must cap high-water items without losing shutdown, cancellation, EOF, overflow, or error signals",
            "scaling": "the largest/smallest workload wall-time ratio must not worsen by more than 25% versus this recorded curve; investigate super-linear growth",
        },
    }
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output),
                      "appendScenarios": len(evidence["durableAppend"]),
                      "queueScenarios": len(evidence["outerQueueBurst"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
