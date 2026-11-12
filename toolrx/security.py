"""SecurityPolicy: input sanitization for the tool router.

Defense-in-depth, from the outside in:
  L0  Normalize  : NFKC unicode, lowercase, strip control chars/apostrophes,
                   collapse whitespace, enforce length cap.
  L1  Metachars  : reject any character outside a safe set. This alone
                   destroys shell/injection metacharacters (; | & ` $ ( ) { }
                   < > " etc.) before anything else sees the input.
  L2  Banned cmds: explicit deny of dangerous command/tool names.
  L3  Injection  : explicit prompt-injection patterns (ignore previous
                   instructions, reveal prompt, developer mode, ...).
  L4  Word allowlist: every alphabetic word must be in the whitelist. Words
                   come from the knowledge docs + catalog + a base set. This
                   is a POSITIVE allowlist, so anything off-vocabulary is
                   refused (also naturally shrinks the router's confusion).
  L5  Path sandbox: file/dir args are canonicalized (realpath, symlink-safe)
                   and must remain inside the project root. Extension + name
                   deny patterns applied too.

Everything defaults to DENY. A request is blocked if ANY layer fails.
The policy is operator-authored data (policy.json), independent of the
model output, so it cannot be influenced by a query.
"""

import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(HERE, "policy.json")

# Safe character set for a normalized query. Paths/words/numbers use only
# these characters; everything else (shell & injection metacharacters) is
# rejected outright.
_SAFE_RE = re.compile(r"^[a-z0-9 ._/\-:~\n]*$")

# Path-like token: contains a path-ish separator/char -> handled by sandbox,
# NOT forced through the word allowlist.
_PATHISH = re.compile(r"[./\\:~]")


class SecurityError(Exception):
    pass


class SecurityPolicy:
    def __init__(self, policy):
        self.vocab = set(policy.get("vocab", []))
        self.denied_words = set(policy.get("denied_words", []))
        self.banned_commands = policy.get("banned_commands", [])
        self.injection_patterns = [re.compile(p, re.IGNORECASE) for p in policy.get("injection_patterns", [])]
        self.allowed_extensions = set(policy.get("allowed_extensions", []))
        self.allowed_hosts = set(policy.get("allowed_hosts", []))
        self.denied_path_substrings = policy.get("denied_path_substrings", [])
        self.max_len = int(policy.get("max_len", 2000))
        self.max_plan_len = max(self.max_len, int(policy.get("max_plan_len", 8000)))
        self.max_plan_steps = int(policy.get("max_plan_steps", 40))
        # Sandbox root: env override wins; otherwise a relative/empty config
        # value means "the directory this package lives in". This keeps the
        # shipped policy.json free of machine-specific absolute paths.
        env_root = os.environ.get("TOOLRX_SANDBOX_ROOT")
        root = env_root or policy.get("sandbox_root") or HERE
        if not env_root and not os.path.isdir(root):
            root = HERE
        self.sandbox_root = os.path.realpath(root)

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path=POLICY_PATH):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    # -- L0 normalize -----------------------------------------------------
    @staticmethod
    def normalize(text, keep_lines=False):
        t = unicodedata.normalize("NFKC", text or "")
        t = t.lower()
        # Control characters become spaces instead of being deleted, so two
        # words cannot fuse into one allowed token (e.g. "files\nshow").
        t = "".join(ch if ch == "\n" and keep_lines else
                    (" " if unicodedata.category(ch) == "Cc" else ch) for ch in t)
        t = t.replace("'", "").replace('"', "")
        if keep_lines:
            t = re.sub(r"[^\S\n]+", " ", t)
            t = re.sub(r" *\n *", "\n", t)
            return re.sub(r"\n{2,}", "\n", t).strip()
        return re.sub(r"\s+", " ", t).strip()

    # -- main check --------------------------------------------------------
    def sanitize(self, raw, limit=None, keep_lines=False):
        """Return (ok, clean_text, reason). Raises nothing; ok=False on deny.

        `limit` overrides the single-route cap for a plan-sized request. The
        plan path passes `max_plan_len`; every split step is then checked again
        against the ordinary single-route cap. `keep_lines` preserves newlines
        so the splitter can see numbered and multi-line plans.
        """
        text = self.normalize(raw, keep_lines=keep_lines)
        if not text:
            return False, text, "empty query"

        cap = self.max_len if limit is None else int(limit)
        if len(text) > cap:
            extra = " (split it into steps)" if cap == self.max_len else ""
            return False, text, f"query too long ({len(text)} > {cap}){extra}"

        if not _SAFE_RE.match(text):
            bad = sorted({c for c in text if not _SAFE_RE.match(c)})
            return False, text, f"disallowed character(s): {bad}"

        # path-traversal sequences (.., ../, ....) rejected at input layer
        if re.search(r"(^|[/\s])\.{2,}([/\s]|$)", text.replace("\\", "/")):
            return False, text, "path traversal (..) rejected"

        # L2 banned commands
        for cmd in self.banned_commands:
            # match as a standalone word or within a dotted token
            if re.search(r"(^|[\s._/:])" + re.escape(cmd) + r"(?=$|[\s._/:])", text):
                return False, text, f"banned command: {cmd}"

        # L3 prompt-injection patterns
        for pat in self.injection_patterns:
            m = pat.search(text)
            if m:
                return False, text, f"injection pattern: {m.group(0)!r}"

        # L4 word allowlist
        unknown = self._unknown_words(text)
        if unknown:
            return False, text, f"word not allowed: {sorted(unknown)[:5]}"

        return True, text, "ok"

    def sanitize_plan(self, raw):
        """Sanitize a prompt that may be longer than one route but not a plan."""
        return self.sanitize(raw, limit=self.max_plan_len, keep_lines=True)

    def _unknown_words(self, text):
        unknown = []
        for tok in re.findall(r"[a-z0-9._~/:-]+", text):
            if _PATHISH.search(tok):  # path-like run -> handled by sandbox
                continue
            if tok.isdigit():
                continue
            if tok in self.denied_words or tok not in self.vocab:
                unknown.append(tok)
        return set(unknown)

    # -- L5 path sandbox ----------------------------------------------------
    def safe_path(self, path):
        """Canonicalize a user-supplied path and enforce it stays in the root."""
        if path is None:
            raise SecurityError("no path")
        if "\x00" in path:
            raise SecurityError("null byte in path")
        p = os.path.normpath(path)
        # deny explicit traversal segments and absolute escapes early
        if re.search(r"(^|/)\s*\.\.\s*(/|$)", p.replace("\\", "/")):
            raise SecurityError("path traversal (..) rejected")
        if p.startswith("/"):
            raise SecurityError("absolute path rejected")

        low = p.lower()
        for sub in self.denied_path_substrings:
            if sub in low:
                raise SecurityError(f"denied path component: {sub}")
        ext = os.path.splitext(p)[1].lower()
        if ext and ext not in self.allowed_extensions:
            raise SecurityError(f"extension not allowed: {ext}")

        root = self.sandbox_root
        target = os.path.realpath(os.path.join(root, p))  # symlink-safe
        if target != root and not target.startswith(root + os.sep):
            raise SecurityError("path escapes sandbox root")
        return target


# ---------------------------------------------------------------------------
# Vocabulary construction + policy generation (operator-authored file)
# ---------------------------------------------------------------------------

# A conservative base set of common English/query words that are safe to route
# on, independent of the knowledge docs. Add here (then regenerate) to widen.
BASE_WORDS = """
the a an and or but not is are was were be been being to of in on at for
from with about into by what which who whom whose when where why how does do
did can could would should will shall may might must has have had this that
these those it its my your our their his her we they he she i you me us them
all some any no yes more most less much many each every other another same
up down off on out over under again further then once here there
please tell know show see use read list open view display print get find
give make take set check total add sum count number numbers value values
file files folder folders directory dir path home memory ram storage usage
used free available total status info information system machine device
config configuration settings note notes text doc document log file
contents items entries data my project
cat changelog config cfg ini html whats usage check
then print text inspect within inside folder browse open view
ping host hosts ip local localhost alive reachable latency packet packets route routing
network net interface interfaces nic port ports traffic link gateway
ifconfig netstat ss process processes procs running cpu load disk disks
storage space uptime time monitor open listening connection diff compare
difference proposed current between
zero one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty
".format"."txt"."md".log".json" json yaml toml csv
linux unix shell command exec
"""

_DEFAULT_POLICY = {
    "max_len": 2000,
    "max_plan_len": 8000,
    "max_plan_steps": 40,
    "sandbox_root": "",
    "allowed_extensions": [".txt", ".md", ".json", ".yaml", ".yml", ".log", ".csv", ".toml", ".ini", ".cfg", ".html", ".htm", ".py", ".pyc", ".c", ".h", ".sh", ".bash", ".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".java", ".go", ".rs", ".rb", ".php", ".env", ".sql", ".conf", ".example", ".bak", ".orig", ".out"],
    "denied_path_substrings": [
        "/etc/", "/root/", "/proc/", "/sys/", "/dev/", "/boot/",
        "/usr/", "/bin/", "/sbin/", "/lib", "/var/", "/home/",
        ".ssh", "shadow", "passwd", ".bash_history", ".gnupg",
        "id_rsa", "id_ed25519", "credentials", "secret",
    ],
    "denied_words": ["ignore", "bypass", "override", "reveal", "injection", "prompt"],
    "banned_commands": [
        "rm", "mv", "cp", "chmod", "chown", "dd", "mkfs", "passwd",
        "reboot", "shutdown", "sudo", "su", "exec", "curl", "wget",
        "nc", "netcat", "bash", "sh", "zsh", "python", "perl", "ruby",
        "php", "node", "ssh", "scp", "kill", "pkill", "fdisk",
    ],
    "injection_patterns": [
        r"ignore\s+(all\s+)?(previous|prior|above)?\s*(instructions|prompts?|rules)",
        r"you\s+are\s+now\s+(in\s+)?(developer|root|jailbreak|god)\s*mode",
        r"reveal\s+(the\s+|your\s+)?(system\s+)?(prompt|instructions|rules)",
        r"system\s+override",
        r"forget\s+(all\s+)?(your\s+)?(rules|instructions)",
        r"disregard\s+(all\s+)?(previous|prior)?\s*(instructions|rules)",
    ],
    "allowed_hosts": ["127.0.0.1", "localhost", "::1", "0.0.0.0"],
}


def build_vocab(catalog_path, policy_out=POLICY_PATH, base=BASE_WORDS):
    """Derive the word whitelist from knowledge docs + catalog + base words."""
    base_dir = os.path.dirname(os.path.abspath(catalog_path))
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)

    words = set()
    for w in base.split():
        words.add(w.strip('".'))

    def add_text(t):
        for tok in re.findall(r"[a-z0-9]+", t.lower()):
            if not tok.isdigit():
                words.add(tok)

    for tool in catalog["tools"]:
        add_text(tool["name"])
        for p in tool["params"]:
            add_text(p["name"])
        for rel in tool.get("knowledge", []):
            path = os.path.join(base_dir, rel)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    add_text(f.read())

    policy = dict(_DEFAULT_POLICY)
    policy["vocab"] = sorted(words)
    with open(policy_out, "w", encoding="utf-8") as f:
        json.dump(policy, f, indent=2)
    print(f"wrote {policy_out} with {len(policy['vocab'])} whitelisted words")
    return policy


if __name__ == "__main__":
    import sys
    build_vocab(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "catalog.json"))