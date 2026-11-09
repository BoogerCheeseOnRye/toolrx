"""Edits: confirm-gated file mutation layer.

Writing a file is a state change, so it goes through a three-step, explicit
flow (default-deny until the operator confirms):

  1. prepare(path, content) -> dry-run: computes a unified diff and registers
     a pending edit. It NEVER writes anything.
  2. apply(id) -> the actual write, only called when the operator confirms in
     the UI. Backs up any existing file to <path>.bak and records undo info.
  3. undo(id) -> restores the previous content (or removes a newly created
     file), then forgets the edit.

No LLM and no prompt is ever involved in generating the content; the operator
types it. The router only picks the tool + target path.
"""

import difflib
import os
import threading
import time

import security

_MAX_PENDING = 16
_MAX_CONTENT = 1_000_000
_LOCK = threading.Lock()
_PENDING = {}
_seq = [0]


class EditError(Exception):
    pass


def _next_id():
    _seq[0] += 1
    return f"e{int(time.time() * 1000)}{_seq[0]}"


def prepare(pol, path, content, mode="replace"):
    """Dry-run only. Returns a pending-edit record (or None if no change)."""
    target = pol.safe_path(path)  # raises SecurityError if outside sandbox
    exists = os.path.isfile(target)
    if exists and mode == "create":
        raise EditError(f"already exists: {path}")
    if not exists and mode == "replace":
        mode = "create"  # naturally create if missing
    old = ""
    if exists:
        with open(target, encoding="utf-8", errors="replace") as f:
            old = f.read()
    if len(content) > _MAX_CONTENT:
        raise EditError(f"content too large ({len(content)})")
    new = content
    if new == old:
        return None  # no-op
    diff = "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=path, tofile=path))
    with _LOCK:
        _purge_locked()
        eid = _next_id()
        rec = {"id": eid, "path": path, "target": target, "old": old, "new": new,
               "mode": mode, "exists": exists, "diff": diff,
               "applied": False, "backup": None, "created": time.time()}
        _PENDING[eid] = rec
    return {"id": eid, "path": path, "exists": exists, "mode": mode,
            "diff": diff, "old_len": len(old), "new_len": len(new)}


def get(eid):
    with _LOCK:
        rec = _PENDING.get(eid)
        return {k: rec[k] for k in ("id", "path", "mode", "exists", "applied")} if rec else None


def apply(eid):
    """Write the pending edit. Only reached after operator confirmation."""
    with _LOCK:
        rec = _PENDING.get(eid)
        if not rec:
            raise EditError("no such pending edit")
        if rec["applied"]:
            raise EditError("edit already applied")
        rec["applied"] = True
        target, old, new = rec["target"], rec["old"], rec["new"]
        exists = rec["exists"]
    backup = None
    if exists:
        backup = target + ".bak"
        with open(backup, "w", encoding="utf-8") as f:
            f.write(old)
    d = os.path.dirname(target)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(new)
    with _LOCK:
        rec["backup"] = backup
        rec["applied_at"] = time.time()
    return {"applied": eid, "path": rec["path"], "backup": backup, "created": not exists}


def undo(eid):
    """Restore the previous content (or remove a created file)."""
    with _LOCK:
        rec = _PENDING.pop(eid, None)
        if not rec:
            raise EditError("no such edit to undo")
        target, old, backup = rec["target"], rec["old"], rec["backup"]
        was_applied = rec["applied"]
        created = rec["mode"] == "create" and not rec["exists"]
    if was_applied:
        if created:
            if os.path.exists(target):
                os.remove(target)
            note = "removed newly created file"
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(old)
            note = "restored previous content"
        if backup and os.path.exists(backup):
            try:
                os.remove(backup)
            except OSError:
                pass
    else:
        note = "edit was not applied; nothing to undo"
    return {"undone": eid, "path": rec["path"], "note": note}


def _purge_locked():
    now = time.time()
    stale = [i for i, r in _PENDING.items()
             if (not r["applied"] and now - r["created"] > 3600)
             or (r["applied"] and now - r.get("applied_at", r["created"]) > 3600)]
    for i in stale:
        _PENDING.pop(i, None)
    if len(_PENDING) > _MAX_PENDING:
        for i in list(_PENDING)[: len(_PENDING) - _MAX_PENDING]:
            _PENDING.pop(i, None)
