#!/usr/bin/env python3
"""Pre-show smoke test. Run while the stack is up (make run).

Checks:
  1. All three color tools return valid HSL for known seeds
  2. peek_attendees is denied by Regorus
  3. SSE broadcast delivers to a subscriber
"""

import json
import os
import queue
import re
import sys
import threading
import urllib.request
import urllib.error

BASE = os.environ.get("BASE", "http://127.0.0.1:8080")
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

failures = 0


def check(label, ok, detail=""):
    global failures
    status = PASS if ok else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures += 1


def post(path, body=None):
    data = json.dumps(body).encode() if body else b""
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


HSL_RE = re.compile(r"^hsl\(\d+,\s*\d+%,\s*\d+%\)$")

# ── 1. Color tools ────────────────────────────────────────────────────────────
print("\nColor tools")
SEEDS = {"alice": "python", "bob": "rust", "charlie": "typescript"}
for seed, expected_lang in SEEDS.items():
    try:
        resp = post("/color", {"seed": seed})
        color = resp.get("hsl", "")
        lang = resp.get("language", "")
        valid_hsl = bool(HSL_RE.match(color))
        right_lang = lang == expected_lang
        check(
            f"seed={seed}",
            valid_hsl and right_lang,
            f"lang={lang} color={color}",
        )
    except Exception as e:
        check(f"seed={seed}", False, str(e))

# ── 2. Regorus denial ────────────────────────────────────────────────────────
print("\nRegorus policy")
try:
    resp = post("/trigger-denial")
    denied = resp.get("denied", False)
    check("peek_attendees denied", denied, resp.get("policy_reason", ""))
except Exception as e:
    check("peek_attendees denied", False, str(e))

# ── 3. SSE broadcast ─────────────────────────────────────────────────────────
print("\nSSE broadcast")
received: queue.Queue = queue.Queue()
ready = threading.Event()


def listen():
    try:
        req = urllib.request.Request(f"{BASE}/events")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ready.set()
            for raw in resp:
                line = raw.decode().strip()
                if line.startswith("data:"):
                    received.put(line[5:].strip())
                    return
    except Exception as e:
        ready.set()
        received.put(f"ERROR: {e}")


t = threading.Thread(target=listen, daemon=True)
t.start()
ready.wait(timeout=5)

try:
    urllib.request.urlopen(
        urllib.request.Request(
            f"{BASE}/broadcast", method="POST",
            data=json.dumps({"event": "flash"}).encode(),
            headers={"Content-Type": "application/json"},
        ),
        timeout=5,
    )
    event = received.get(timeout=5)
    check("flash delivered", "flash" in event, event)
except Exception as e:
    check("flash delivered", False, str(e))

# ── Result ───────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"  {failures} check(s) failed — do not go on stage.")
    sys.exit(1)
else:
    print("  All checks passed. Good to go.")
