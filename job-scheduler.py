#!/usr/bin/env python3
"""job-scheduler.py — detached background jobs for the swarm router.

Rewritten 2026-08-22 from AGENTS.md specs after the /tmp wipe lost the original.
Run:   nohup python3 job-scheduler.py [WORKDIR] [INTERVAL] > logs/job-scheduler.log &

Watches <WORKDIR>/.jobs/ (default ./swarm-work/.jobs) for *.json files:
    {"query": "build a tetris game", "status": "pending"}
Picks up pending files, POSTs the query to the swarm router (:8900), then writes
the result back into the same file atomically:
    {"query": ..., "status": "done",  "result": {...}}
or  {"query": ..., "status": "error", "result": "..."}   (retryable by hand-editing
the status back to "pending").

Long executor builds are normal -> HTTP timeout is 1800s, matching the router's own
per-turn ceiling. Files are claimed via a .claim marker so two schedulers can't
double-run a job.
"""

import json
import os
import sys
import time
import urllib.request

ROUTER = os.environ.get("SWARM_ROUTER", "http://127.0.0.1:8900/")
HTTP_TIMEOUT = int(os.environ.get("SWARM_JOB_TIMEOUT", "1800"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def run_job(path):
    try:
        with open(path) as fh:
            job = json.load(fh)
    except Exception as e:
        log(f"unreadable job {os.path.basename(path)}: {e}")
        return
    if job.get("status") != "pending" or not job.get("query"):
        return

    claim = path + ".claim"
    if os.path.exists(claim):
        return
    open(claim, "w").close()

    q = job["query"]
    jid = job.get("id") or os.path.basename(path)
    log(f"running {jid}: {q[:70]}")
    started = time.time()
    try:
        req = urllib.request.Request(
            ROUTER, data=json.dumps({"query": q}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            result = json.loads(resp.read().decode())
        job["result"] = result
        job["status"] = "done"
        log(f"done   {jid} in {time.time()-started:.0f}s")
    except Exception as e:
        job["result"] = str(e)
        job["status"] = "error"
        log(f"error  {jid}: {str(e)[:120]}")
    job.setdefault("id", jid)
    job["seconds"] = round(time.time() - started, 1)
    atomic_json(path, job)
    try:
        os.remove(claim)
    except OSError:
        pass


def main():
    workdir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "TOOLRX_WORKDIR", os.path.join(os.getcwd(), "swarm-work"))
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 10
    jobs_dir = os.path.join(workdir, ".jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    log(f"job-scheduler watching {jobs_dir} (interval={interval}s)")
    while True:
        try:
            if os.path.isdir(jobs_dir):
                for fn in sorted(os.listdir(jobs_dir)):
                    if fn.endswith(".json"):
                        run_job(os.path.join(jobs_dir, fn))
        except Exception as e:
            log(f"cycle error (suppressed): {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
