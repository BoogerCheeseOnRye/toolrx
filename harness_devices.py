#!/usr/bin/env python3
"""harness_devices.py — shared loader for optional phone-harness device config.

The public toolrx router needs no phones. These helpers are only for the
optional adb/needle/llama cluster scripts in the repo root.

Config path: $TOOLRX_HARNESS_DEVICES or ./harness-devices.json (gitignored).
Ship harness-devices.example.json; never commit real serials.

Format::

    {"devices": [
      {"serial": "EXAMPLE0001", "name": "phone-a",
       "needle_port": 8355, "executor_port": 8086, "training": false,
       "forwards": [[8355, 8355], [8086, 8086]]}
    ]}
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("TOOLRX_HARNESS_DEVICES",
                        os.path.join(HERE, "harness-devices.json"))


def load():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return [d for d in cfg.get("devices", []) if d.get("serial")]
    except Exception:
        return []


def known():
    return [(d["serial"], d.get("name") or d["serial"]) for d in load()]


def forwards():
    out = []
    for d in load():
        for host, guest in d.get("forwards", []):
            out.append((d["serial"], int(host), int(guest)))
        # derive obvious forwards when only ports are configured
        if not d.get("forwards"):
            for key in ("needle_port", "executor_port"):
                port = d.get(key)
                if port:
                    out.append((d["serial"], int(port), int(port)))
    # de-duplicate while preserving order
    seen, uniq = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def needles():
    out = []
    for d in load():
        if d.get("needle_port"):
            out.append((d["serial"], d.get("name") or d["serial"],
                        int(d["needle_port"])))
    return out


def executors():
    out = []
    for d in load():
        if d.get("executor_port"):
            out.append((d["serial"], d.get("name") or d["serial"],
                        int(d["executor_port"])))
    return out


def training_serial():
    explicit = os.environ.get("TRAIN_SERIAL")
    if explicit:
        return explicit
    for d in load():
        if d.get("training"):
            return d["serial"]
    return ""


def device_map():
    """serial -> dict, convenient for hotplug-style scripts."""
    return {d["serial"]: d for d in load()}
