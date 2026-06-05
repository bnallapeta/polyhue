#!/usr/bin/env python3
"""Simulate N concurrent SSE subscribers, trigger a denial, report delivery."""

import argparse
import queue
import threading
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8080"


def subscribe(idx, results: queue.Queue, ready: threading.Event):
    try:
        req = urllib.request.Request(f"{BASE}/events")
        with urllib.request.urlopen(req, timeout=30) as resp:
            ready.set()
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if line.startswith("data:"):
                    results.put((idx, line[5:].strip()))
                    return
    except Exception as e:
        ready.set()
        results.put((idx, f"ERROR: {e}"))


def trigger():
    body = b""
    req = urllib.request.Request(
        f"{BASE}/trigger-denial", data=body, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode()
    except Exception as e:
        return f"trigger error: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=50, help="number of simulated clients")
    args = parser.parse_args()
    n = args.n

    print(f"Opening {n} SSE connections...")
    results: queue.Queue = queue.Queue()
    ready_events = [threading.Event() for _ in range(n)]
    threads = []
    for i in range(n):
        t = threading.Thread(target=subscribe, args=(i, results, ready_events[i]), daemon=True)
        t.start()
        threads.append(t)

    # Wait for all subscribers to connect
    for ev in ready_events:
        ev.wait(timeout=10)

    print(f"All {n} clients connected. Triggering denial...")
    t0 = time.time()
    trigger_resp = trigger()
    elapsed = time.time() - t0

    # Collect results with a timeout
    received = []
    deadline = time.time() + 5
    while time.time() < deadline and len(received) < n:
        try:
            received.append(results.get(timeout=0.2))
        except queue.Empty:
            pass

    errors = [r for r in received if "ERROR" in r[1]]
    flashes = [r for r in received if "flash" in r[1]]

    print(f"\nTrigger response: {trigger_resp}")
    print(f"Trigger RTT:      {elapsed*1000:.0f}ms")
    print(f"Clients:          {n}")
    print(f"Received flash:   {len(flashes)}")
    print(f"Errors:           {len(errors)}")
    print(f"Silent (no event):{n - len(received)}")
    if errors:
        for _, msg in errors[:5]:
            print(f"  {msg}")


if __name__ == "__main__":
    main()
