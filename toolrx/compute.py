#!/usr/bin/env python3
"""One bounded pure-compute program (step 63).

This is the Python twin of the compute block in `toolrx/web/skills.js`. Both
run the same grammar over the same caps and print the same bytes:

  * statements separated by `|`, `;`, or a newline (`|` is the chat-safe form)
  * `let name = value` and `name = value` local assignments
  * numbers, quoted strings, booleans, null, arrays
  * `+ - * / % ^`, comparisons, `and` / `or` / `not`, indexing, slicing
  * a fixed table of pure builtins (no host object is reachable)

Nothing here can read a file, open a socket, start a timer, use storage, or
reach the DOM. Names resolve only against the builtin table and the locals
declared earlier in the same script, so an unknown name refuses before
anything is evaluated. Every cap comes from `toolrx/limits.json` and a refusal
names the cap it hit.

    python3 toolrx/compute.py --write   # refresh tests/fixtures/compute.json
    python3 toolrx/compute.py --check   # fail if the fixture drifted
"""

import argparse
import json
import math
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
FIXTURE = ROOT.parent / "tests" / "fixtures" / "compute.json"

CAP_NAMES = {
    "chars": "computeChars",
    "statements": "computeStatements",
    "ops": "computeOps",
    "vars": "computeVars",
    "ms": "computeMs",
    "resultChars": "computeResultChars",
}

DENY = frozenset("""
eval function new import require process globalthis window document
localstorage sessionstorage indexeddb fetch xmlhttprequest websocket worker
sharedworker importscripts sendbeacon navigator location history alert confirm
prompt settimeout setinterval cleartimeout clearinterval requestanimationframe
queuemicrotask fs os sys subprocess child_process open exec execfile spawn
compile __proto__ prototype constructor reflect proxy symbol math date regexp
object array string boolean json atom deno bun postmessage crypto this self
parent top frames opener
""".split())

BUILTINS = {
    "abs": (1, 1), "round": (1, 1), "floor": (1, 1), "ceil": (1, 1),
    "sqrt": (1, 1), "cbrt": (1, 1), "sign": (1, 1),
    "sin": (1, 1), "cos": (1, 1), "tan": (1, 1), "log": (1, 1),
    "ln": (1, 1), "exp": (1, 1), "min": (1, 8), "max": (1, 8),
    "pow": (2, 2), "upper": (1, 1), "lower": (1, 1), "trim": (1, 1),
    "title": (1, 1), "reverse": (1, 1), "replace": (3, 3), "split": (2, 2),
    "join": (2, 2), "slice": (2, 3), "repeat": (2, 2), "contains": (2, 2),
    "starts": (2, 2), "ends": (2, 2), "length": (1, 1), "count": (1, 1),
    "sum": (1, 1), "sort": (1, 1), "unique": (1, 1), "first": (1, 1),
    "last": (1, 1), "str": (1, 1), "number": (1, 1), "type": (1, 1),
}

CONST = {"pi": math.pi, "e": math.e}

_NUM = re.compile(r"\d*\.?\d+(?:[eE][+-]?\d+)?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WORD = re.compile(r"[A-Za-z]+")
_NUMERIC_TEXT = re.compile(r"^-?\d+(?:\.\d+)?$")


class ComputeError(Exception):
    def __init__(self, message, cap=""):
        super().__init__(message)
        self.message = message
        self.cap = cap


def _fail(message, cap=""):
    raise ComputeError(message, cap)


def _type(value):
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object"


def _is_num(value):
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _number(value):
    """Render a number exactly as the JavaScript twin does."""
    if not _is_num(value):
        _fail("compute error: result is not a finite number")
    x = float(value)
    if not math.isfinite(x):
        _fail("compute error: result is not a finite number")
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 1e21:
        return str(int(x))
    if 1e-6 <= abs(x) < 1e21:
        text = ("%.10f" % x).rstrip("0").rstrip(".")
        return text
    mantissa, exponent = ("%.10e" % x).split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exp = int(exponent)
    return mantissa + "e" + ("+" if exp >= 0 else "-") + str(abs(exp))


def _quote(text):
    out = (text.replace("\\", "\\\\").replace('"', '\\"')
           .replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r"))
    return '"' + out + '"'


def _render(value, top=True):
    if _is_num(value):
        return _number(value)
    if isinstance(value, str):
        return value if top else _quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(_render(item, False) for item in value) + "]"
    _fail("compute error: cannot show a " + _type(value))


def _equal(a, b):
    if isinstance(a, list) or isinstance(b, list):
        if not isinstance(a, list) or not isinstance(b, list):
            return False
        if len(a) != len(b):
            return False
        return all(_equal(x, y) for x, y in zip(a, b))
    if a is None or b is None:
        return a is None and b is None
    if _type(a) != _type(b):
        return False
    return a == b


def _as_number(value, fn):
    if not _is_num(value) or not math.isfinite(float(value)):
        _fail("compute error: " + fn + " needs a number")
    return float(value)


def _as_int(value, fn):
    number = _as_number(value, fn)
    if number != int(number):
        _fail("compute error: " + fn + " needs an integer")
    return int(number)


def _as_string(value, fn):
    if not isinstance(value, str):
        _fail("compute error: " + fn + " needs a string")
    return value


def _as_array(value, fn):
    if not isinstance(value, list):
        _fail("compute error: " + fn + " needs an array")
    return value


def _ascii_upper(text):
    return "".join(chr(ord(c) - 32) if "a" <= c <= "z" else c for c in text)


def _ascii_lower(text):
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def _power(a, b):
    if a == 0 and b < 0:
        _fail("compute error: division by zero")
    if a < 0 and b != int(b):
        _fail("compute error: power of a negative number")
    try:
        value = math.pow(a, b)
    except OverflowError:
        value = math.inf
    if not math.isfinite(value):
        _fail("compute error: result is not a finite number")
    return value


def _index(obj, idx):
    i = _as_int(idx, "index")
    seq = list(obj) if isinstance(obj, str) else _as_array(obj, "index")
    if i < 0 or i >= len(seq):
        _fail("compute error: index " + str(i) + " is out of range")
    return seq[i]


def _slice_value(value, start, end):
    is_text = isinstance(value, str)
    seq = list(value) if is_text else _as_array(value, "slice")
    length = len(seq)

    def norm(n):
        return max(length + n, 0) if n < 0 else min(n, length)

    a = norm(start)
    b = length if end is None else norm(end)
    if b < a:
        b = a
    out = seq[a:b]
    return "".join(out) if is_text else out


def _binary(op, a, b):
    if op == "==":
        return _equal(a, b)
    if op == "!=":
        return not _equal(a, b)
    if op in ("<", "<=", ">", ">="):
        if _is_num(a) and _is_num(b):
            c = 0 if float(a) == float(b) else (-1 if float(a) < float(b) else 1)
        elif isinstance(a, str) and isinstance(b, str):
            c = 0 if a == b else (-1 if a < b else 1)
        else:
            _fail("compute error: cannot compare a " + _type(a)
                  + " and a " + _type(b))
        if op == "<":
            return c < 0
        if op == "<=":
            return c <= 0
        if op == ">":
            return c > 0
        return c >= 0
    if op == "+":
        if isinstance(a, str) or isinstance(b, str):
            left = a if isinstance(a, str) else _render(a, False)
            right = b if isinstance(b, str) else _render(b, False)
            return left + right
        return _as_number(a, "+") + _as_number(b, "+")
    x = _as_number(a, op)
    y = _as_number(b, op)
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if op == "/":
        if y == 0:
            _fail("compute error: division by zero")
        return x / y
    if op == "%":
        if y == 0:
            _fail("compute error: division by zero")
        return math.fmod(x, y)
    if op == "^":
        return _power(x, y)
    _fail("compute error: unknown operator " + op)


def _log10(x):
    if x == 0:
        return -math.inf
    if x < 0:
        return math.nan
    return math.log10(x)


def _ln(x):
    if x == 0:
        return -math.inf
    if x < 0:
        return math.nan
    return math.log(x)


def _exp(x):
    try:
        return math.exp(x)
    except OverflowError:
        return math.inf


def _call(name, args):
    if name == "abs":
        return abs(_as_number(args[0], name))
    if name == "round":
        n = _as_number(args[0], name)
        return (-1 if n < 0 else 1) * math.floor(abs(n) + 0.5)
    if name == "floor":
        return math.floor(_as_number(args[0], name))
    if name == "ceil":
        return math.ceil(_as_number(args[0], name))
    if name == "sqrt":
        n = _as_number(args[0], name)
        if n < 0:
            _fail("compute error: square root of a negative number")
        return math.sqrt(n)
    if name == "cbrt":
        return math.cbrt(_as_number(args[0], name))
    if name == "sign":
        n = _as_number(args[0], name)
        return 0 if n == 0 else (1 if n > 0 else -1)
    if name == "sin":
        return math.sin(_as_number(args[0], name))
    if name == "cos":
        return math.cos(_as_number(args[0], name))
    if name == "tan":
        return math.tan(_as_number(args[0], name))
    if name == "log":
        return _log10(_as_number(args[0], name))
    if name == "ln":
        return _ln(_as_number(args[0], name))
    if name == "exp":
        return _exp(_as_number(args[0], name))
    if name in ("min", "max"):
        xs = [_as_number(v, name) for v in args]
        return min(xs) if name == "min" else max(xs)
    if name == "pow":
        return _power(_as_number(args[0], name), _as_number(args[1], name))
    if name == "upper":
        return _ascii_upper(_as_string(args[0], name))
    if name == "lower":
        return _ascii_lower(_as_string(args[0], name))
    if name == "title":
        text = _as_string(args[0], name)
        return _WORD.sub(lambda m: _ascii_upper(m.group(0)[0])
                         + _ascii_lower(m.group(0)[1:]), text)
    if name == "trim":
        return _as_string(args[0], name).strip(" \t\r\n\f\v")
    if name == "reverse":
        value = args[0]
        if isinstance(value, str):
            return value[::-1]
        return list(reversed(_as_array(value, name)))
    if name == "replace":
        text = _as_string(args[0], name)
        old = _as_string(args[1], name)
        new = _as_string(args[2], name)
        if not old:
            _fail("compute error: replace needs a non-empty search string")
        return text.replace(old, new)
    if name == "split":
        text = _as_string(args[0], name)
        sep = _as_string(args[1], name)
        if not sep:
            _fail("compute error: split needs a non-empty separator")
        return text.split(sep)
    if name == "join":
        xs = _as_array(args[0], name)
        sep = _as_string(args[1], name)
        return sep.join(v if isinstance(v, str) else _render(v, False)
                        for v in xs)
    if name == "slice":
        start = _as_int(args[1], name)
        end = _as_int(args[2], name) if len(args) > 2 else None
        return _slice_value(args[0], start, end)
    if name == "repeat":
        text = _as_string(args[0], name)
        count = _as_int(args[1], name)
        if count < 0 or count > 1000:
            _fail("compute error: repeat needs 0-1000")
        return text * count
    if name == "contains":
        if isinstance(args[0], str):
            return _as_string(args[1], name) in args[0]
        xs = _as_array(args[0], name)
        return any(_equal(v, args[1]) for v in xs)
    if name == "starts":
        return _as_string(args[0], name).startswith(_as_string(args[1], name))
    if name == "ends":
        text = _as_string(args[0], name)
        tail = _as_string(args[1], name)
        return len(text) >= len(tail) and text[len(text) - len(tail):] == tail
    if name in ("length", "count"):
        value = args[0]
        if isinstance(value, str) or isinstance(value, list):
            return len(value)
        _fail("compute error: " + name + " needs a string or an array")
    if name == "sum":
        xs = _as_array(args[0], name)
        total = 0.0
        for value in xs:
            total += _as_number(value, name)
        return total
    if name == "sort":
        xs = _as_array(args[0], name)
        all_num = all(_type(v) == "number" for v in xs)
        all_str = all(isinstance(v, str) for v in xs)
        if not all_num and not all_str:
            _fail("compute error: sort needs all numbers or all strings")
        return sorted(xs, key=float) if all_num else sorted(xs)
    if name == "unique":
        xs = _as_array(args[0], name)
        out = []
        for value in xs:
            if not any(_equal(value, seen) for seen in out):
                out.append(value)
        return out
    if name in ("first", "last"):
        value = args[0]
        seq = list(value) if isinstance(value, str) else _as_array(value, name)
        if not seq:
            _fail("compute error: " + name + " needs a non-empty value")
        return seq[0] if name == "first" else seq[-1]
    if name == "str":
        return _render(args[0], True)
    if name == "number":
        value = args[0]
        if _is_num(value):
            return float(value)
        if isinstance(value, str) and _NUMERIC_TEXT.match(value):
            return float(value)
        _fail("compute error: number needs a numeric string")
    if name == "type":
        return _type(args[0])
    _fail("compute error: unknown name " + name)


def _tokens(src):
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if ("0" <= c <= "9") or (c == "." and i + 1 < n
                                 and "0" <= src[i + 1] <= "9"):
            m = _NUM.match(src, i)
            out.append(("num", float(m.group(0))))
            i = m.end()
            continue
        if c in "\"'":
            quote = c
            i += 1
            value = []
            closed = False
            while i < n:
                d = src[i]
                i += 1
                if d == quote:
                    closed = True
                    break
                if d == "\\":
                    e = src[i] if i < n else ""
                    i += 1
                    if e == "n":
                        value.append("\n")
                    elif e == "t":
                        value.append("\t")
                    elif e == "r":
                        value.append("\r")
                    elif e in ("\\", '"', "'"):
                        value.append(e)
                    else:
                        _fail("compute error: unknown escape \\" + e)
                else:
                    value.append(d)
            if not closed:
                _fail("compute error: unterminated string")
            out.append(("str", "".join(value)))
            continue
        if ("A" <= c <= "Z") or ("a" <= c <= "z") or c == "_":
            m = _IDENT.match(src, i)
            out.append(("id", m.group(0)))
            i = m.end()
            continue
        two = src[i:i + 2]
        if two in ("==", "!=", "<=", ">="):
            out.append(("op", two))
            i += 2
            continue
        if c in "+-*/%^=<>(),[]":
            out.append(("op", c))
            i += 1
            continue
        _fail('compute error: unexpected "' + c + '"')
    out.append(("end", ""))
    return out


def _split(src):
    cleaned = []
    quote = ""
    depth = 0
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if quote:
            cleaned.append(c)
            if c == "\\":
                if i + 1 < n:
                    cleaned.append(src[i + 1])
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "\"'":
            quote = c
            cleaned.append(c)
            i += 1
            continue
        if c in "([":
            depth += 1
            cleaned.append(c)
            i += 1
            continue
        if c in ")]":
            depth = max(0, depth - 1)
            cleaned.append(c)
            i += 1
            continue
        if c == "#" and depth == 0:
            while i < n and src[i] != "\n":
                i += 1
            cleaned.append("\n")
            i += 1
            continue
        cleaned.append(c)
        i += 1
    text = "".join(cleaned)
    out = []
    start = 0
    quote = ""
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "\"'":
            quote = c
            i += 1
            continue
        if c in "([":
            depth += 1
            i += 1
            continue
        if c in ")]":
            depth = max(0, depth - 1)
            i += 1
            continue
        if c in ";|\n" and depth == 0:
            part = text[start:i].strip()
            if part:
                out.append(part)
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


class _Run:
    def __init__(self, caps, clock):
        self.caps = caps
        self.now = clock or time.monotonic
        self.started = self.now()
        self.ops = 0
        self.declared = {}
        self.toks = []
        self.pos = 0

    def bump(self, n):
        self.ops += n
        cap = self.caps.get("ops")
        if cap and self.ops > cap:
            _fail("compute refused: " + str(self.ops) + " operations, over "
                  "computeOps (" + str(cap) + ")", "computeOps")

    def syntax(self, what):
        token = self.toks[self.pos]
        near = "end" if token[0] == "end" else str(token[1])
        return ComputeError('compute error: expected ' + what + ' near "'
                            + near + '"')

    def is_op(self, value):
        token = self.toks[self.pos]
        return token[0] == "op" and token[1] == value

    def eat(self, value):
        if self.is_op(value):
            self.pos += 1
            return True
        return False

    def expect(self, value, what):
        if not self.eat(value):
            raise self.syntax(what)

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while (self.toks[self.pos][0] == "id"
               and self.toks[self.pos][1] == "or"):
            self.pos += 1
            self.bump(1)
            node = ("bin", "or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while (self.toks[self.pos][0] == "id"
               and self.toks[self.pos][1] == "and"):
            self.pos += 1
            self.bump(1)
            node = ("bin", "and", node, self.parse_not())
        return node

    def parse_not(self):
        if self.toks[self.pos][0] == "id" and self.toks[self.pos][1] == "not":
            self.pos += 1
            self.bump(1)
            return ("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        node = self.parse_add()
        token = self.toks[self.pos]
        if token[0] == "op" and token[1] in ("==", "!=", "<", "<=", ">", ">="):
            self.pos += 1
            self.bump(1)
            return ("bin", token[1], node, self.parse_add())
        return node

    def parse_add(self):
        node = self.parse_mul()
        while True:
            token = self.toks[self.pos]
            if token[0] == "op" and token[1] in ("+", "-"):
                self.pos += 1
                self.bump(1)
                node = ("bin", token[1], node, self.parse_mul())
            else:
                break
        return node

    def parse_mul(self):
        node = self.parse_unary()
        while True:
            token = self.toks[self.pos]
            if token[0] == "op" and token[1] in ("*", "/", "%"):
                self.pos += 1
                self.bump(1)
                node = ("bin", token[1], node, self.parse_unary())
            else:
                break
        return node

    def parse_unary(self):
        if self.eat("-"):
            self.bump(1)
            return ("neg", self.parse_unary())
        if self.eat("+"):
            self.bump(1)
            return self.parse_unary()
        return self.parse_power()

    def parse_power(self):
        base = self.parse_postfix()
        if self.eat("^"):
            self.bump(1)
            return ("bin", "^", base, self.parse_unary())
        return base

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.is_op("["):
                self.pos += 1
                idx = self.parse_expr()
                self.expect("]", "]")
                self.bump(1)
                node = ("index", node, idx)
            else:
                break
        return node

    def parse_primary(self):
        token = self.toks[self.pos]
        kind = token[0]
        if kind == "end":
            raise self.syntax("a value")
        if kind == "num":
            self.pos += 1
            self.bump(1)
            return ("num", token[1])
        if kind == "str":
            self.pos += 1
            self.bump(1)
            return ("str", token[1])
        if kind == "op" and token[1] == "(":
            self.pos += 1
            node = self.parse_expr()
            self.expect(")", ")")
            return node
        if kind == "op" and token[1] == "[":
            self.pos += 1
            items = []
            if not self.is_op("]"):
                while True:
                    items.append(self.parse_expr())
                    if not self.eat(","):
                        break
            self.expect("]", "]")
            self.bump(1)
            return ("arr", items)
        if kind == "id":
            name = token[1]
            if name.lower() in DENY:
                _fail("compute refused: " + name
                      + " is not available in compute", "name")
            if name in ("true", "false"):
                self.pos += 1
                self.bump(1)
                return ("bool", name == "true")
            if name == "null":
                self.pos += 1
                self.bump(1)
                return ("null",)
            if name in CONST and not self.declared.get(name):
                self.pos += 1
                self.bump(1)
                return ("num", CONST[name])
            if name in BUILTINS:
                self.pos += 1
                self.expect("(", "(")
                args = []
                if not self.is_op(")"):
                    while True:
                        args.append(self.parse_expr())
                        if not self.eat(","):
                            break
                self.expect(")", ")")
                low, high = BUILTINS[name]
                if len(args) < low or len(args) > high:
                    want = str(low) if low == high else str(low) + "-" + str(high)
                    _fail("compute error: " + name + " expects " + want
                          + " argument(s)")
                self.bump(1)
                return ("call", name, args)
            if self.declared.get(name):
                self.pos += 1
                self.bump(1)
                return ("var", name)
            _fail("compute error: unknown name " + name)
        raise self.syntax("a value")

    def parse_assign(self, explicit):
        name = self.toks[self.pos][1]
        self.pos += 1
        self.expect("=", "=")
        if name.lower() in DENY:
            _fail("compute refused: " + name
                  + " is not available in compute", "name")
        if name in BUILTINS or name in CONST:
            _fail("compute error: " + name + " is a builtin")
        if explicit and self.declared.get(name):
            _fail("compute error: " + name + " is already declared")
        if not self.declared.get(name):
            count = len(self.declared)
            cap = self.caps.get("vars")
            if cap and count >= cap:
                _fail("compute refused: " + str(count + 1)
                      + " variables, over computeVars (" + str(cap) + ")",
                      "computeVars")
            self.declared[name] = True
        self.bump(1)
        return ("assign", name, self.parse_expr())

    def parse_statement(self):
        token = self.toks[self.pos]
        nxt = self.toks[self.pos + 1] if self.pos + 1 < len(self.toks) else ("end", "")
        after = self.toks[self.pos + 2] if self.pos + 2 < len(self.toks) else ("end", "")
        if (token[0] == "id" and token[1] == "let" and nxt[0] == "id"
                and after[0] == "op" and after[1] == "="):
            self.pos += 1
            return self.parse_assign(True)
        if (token[0] == "id" and nxt[0] == "op" and nxt[1] == "="):
            return self.parse_assign(False)
        return self.parse_expr()

    def eval_node(self, node, env):
        cap = self.caps.get("ms")
        if cap and self.now() - self.started > cap:
            _fail("compute refused: took longer than computeMs ("
                  + str(cap) + " ms)", "computeMs")
        kind = node[0]
        if kind == "num" or kind == "str" or kind == "bool":
            return node[1]
        if kind == "null":
            return None
        if kind == "arr":
            return [self.eval_node(x, env) for x in node[1]]
        if kind == "var":
            return env[node[1]]
        if kind == "assign":
            value = self.eval_node(node[2], env)
            env[node[1]] = value
            return value
        if kind == "neg":
            return -_as_number(self.eval_node(node[1], env), "-")
        if kind == "not":
            value = self.eval_node(node[1], env)
            if not isinstance(value, bool):
                _fail("compute error: not needs a boolean")
            return not value
        if kind == "index":
            return _index(self.eval_node(node[1], env),
                          self.eval_node(node[2], env))
        if kind == "call":
            args = [self.eval_node(x, env) for x in node[2]]
            return _call(node[1], args)
        if kind == "bin":
            op = node[1]
            if op in ("and", "or"):
                a = self.eval_node(node[2], env)
                if not isinstance(a, bool):
                    _fail("compute error: " + op + " needs a boolean")
                if op == "and" and not a:
                    return False
                if op == "or" and a:
                    return True
                b = self.eval_node(node[3], env)
                if not isinstance(b, bool):
                    _fail("compute error: " + op + " needs a boolean")
                return b
            return _binary(op, self.eval_node(node[2], env),
                           self.eval_node(node[3], env))
        _fail("compute error: unknown node")

    def run(self, parts):
        nodes = []
        for part in parts:
            self.toks = _tokens(part)
            self.pos = 0
            nodes.append(self.parse_statement())
            if self.toks[self.pos][0] != "end":
                _fail('compute error: unexpected "'
                      + str(self.toks[self.pos][1]) + '"')
        env = {}
        value = None
        for node in nodes:
            value = self.eval_node(node, env)
        return value


def caps():
    """The six compute caps, read from the one envelope."""
    try:
        import envelope
    except ImportError:  # pragma: no cover - direct script execution
        sys.path.insert(0, str(ROOT))
        import envelope
    doc = envelope.load()
    return {
        "chars": doc["computeChars"],
        "statements": doc["computeStatements"],
        "ops": doc["computeOps"],
        "vars": doc["computeVars"],
        "ms": doc["computeMs"],
        "resultChars": doc["computeResultChars"],
    }


def run(source, limits=None, clock=None):
    """Evaluate one bounded script. Never raises for user input."""
    caps_ = caps()
    if limits:
        caps_.update(limits)
    text = "" if source is None else str(source)
    total = len(text)

    def fail(message, cap=""):
        return {"ok": False, "error": message, "cap": cap, "ops": 0,
                "vars": 0, "statements": 0}

    if caps_.get("chars") and total > caps_["chars"]:
        return fail("compute refused: source is " + str(total)
                    + " chars, over computeChars (" + str(caps_["chars"]) + ")",
                    "computeChars")
    parts = _split(text)
    if not parts:
        return fail("compute error: nothing to compute")
    if caps_.get("statements") and len(parts) > caps_["statements"]:
        return fail("compute refused: " + str(len(parts))
                    + " statements, over computeStatements ("
                    + str(caps_["statements"]) + ")", "computeStatements")
    runner = _Run(caps_, clock)
    try:
        value = runner.run(parts)
        out = _render(value, True)
        if caps_.get("resultChars") and len(out) > caps_["resultChars"]:
            return fail("compute refused: result is " + str(len(out))
                        + " chars, over computeResultChars ("
                        + str(caps_["resultChars"]) + ")",
                        "computeResultChars")
        return {"ok": True, "text": out, "value": value, "ops": runner.ops,
                "vars": len(runner.declared), "statements": len(parts)}
    except ComputeError as exc:
        return {"ok": False, "error": exc.message, "cap": exc.cap,
                "ops": runner.ops, "vars": len(runner.declared),
                "statements": len(parts)}


CASES = [
    # arithmetic
    {"src": "16/100*4"},
    {"src": "2 + 3 * 4"},
    {"src": "(2 + 3) * 4"},
    {"src": "2 ^ 3 ^ 2"},
    {"src": "-2 ^ 2"},
    {"src": "7 % -3"},
    {"src": "-7 % 3"},
    {"src": "1/3"},
    {"src": "2/3"},
    {"src": "0.1 + 0.2"},
    {"src": "10 / 4"},
    {"src": "2 ^ 0.5"},
    {"src": "1e-7"},
    {"src": "1.5e3"},
    # builtins
    {"src": "abs(-3)"},
    {"src": "round(2.5)"},
    {"src": "round(-2.5)"},
    {"src": "floor(-2.5)"},
    {"src": "ceil(2.1)"},
    {"src": "sqrt(16)"},
    {"src": "cbrt(27)"},
    {"src": "sign(-9)"},
    {"src": "min(3, 1, 2)"},
    {"src": "max(3, 1, 2)"},
    {"src": "pow(2, 10)"},
    {"src": "log(1000)"},
    {"src": "ln(1)"},
    {"src": "exp(0)"},
    # strings
    {"src": 'upper("ada")'},
    {"src": 'lower("ADA")'},
    {"src": 'title("hello world")'},
    {"src": 'trim("  hi  ")'},
    {"src": 'reverse("abc")'},
    {"src": 'replace("a-b-a", "a", "x")'},
    {"src": 'split("a,b", ",")'},
    {"src": 'join(["a","b"], "-")'},
    {"src": 'slice("hello", 1, 3)'},
    {"src": 'slice("hello", -3)'},
    {"src": 'repeat("ab", 3)'},
    {"src": 'contains("hello", "ell")'},
    {"src": 'starts("hello", "he")'},
    {"src": 'ends("hello", "lo")'},
    {"src": 'length("héllo")'},
    {"src": 'first("abc")'},
    {"src": "last([1,2,3])"},
    {"src": "str(12)"},
    {"src": 'number("12.5")'},
    {"src": "type([1])"},
    # booleans, arrays, assignments
    {"src": "true and false"},
    {"src": "not true"},
    {"src": "1 < 2"},
    {"src": '"a" < "b"'},
    {"src": "[1,2] == [1,2]"},
    {"src": "sum([1,2,3])"},
    {"src": "sort([3,1,2])"},
    {"src": 'sort(["b","a"])'},
    {"src": "unique([1,1,2])"},
    {"src": "count([1,2,3])"},
    {"src": '"a" + 1'},
    {"src": "let x = 2 | x * 3"},
    {"src": "let a = 1 | let b = 2 | a + b"},
    {"src": "x = 5 | x + 1"},
    {"src": "# comment | 1 + 2"},
    {"src": "null"},
    {"src": "true"},
    # errors and refusals
    {"src": "1/0"},
    {"src": "sqrt(-1)"},
    {"src": 'fetch("x")'},
    {"src": 'eval("1")'},
    {"src": "unknownname"},
    {"src": "a.b"},
    {"src": "1 +"},
    {"src": "let pi = 1"},
    {"src": "let x = 1 | let x = 2"},
    {"src": "not 1"},
    {"src": "1|2|3", "limits": {"statements": 2}},
    {"src": "1+2+3", "limits": {"ops": 2}},
    {"src": "let a=1 | let b=2", "limits": {"vars": 1}},
    {"src": "1+2", "limits": {"chars": 2}},
    {"src": 'repeat("ab", 3)', "limits": {"resultChars": 4}},
]


def fixture():
    cases = []
    for case in CASES:
        out = run(case["src"], case.get("limits"))
        entry = {"src": case["src"]}
        if case.get("limits"):
            entry["limits"] = case["limits"]
        entry["ok"] = out["ok"]
        if out["ok"]:
            entry["text"] = out["text"]
        else:
            entry["error"] = out["error"]
            entry["cap"] = out["cap"]
        entry["ops"] = out["ops"]
        entry["vars"] = out["vars"]
        entry["statements"] = out["statements"]
        cases.append(entry)
    return {
        "version": 1,
        "caps": caps(),
        "count": len(cases),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/compute.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases)" % (FIXTURE.relative_to(ROOT.parent),
                                       doc["count"]))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("compute fixture drifted; run --write", file=sys.stderr)
            return 1
        print("compute fixture is current")
        return 0
    print(json.dumps(doc["caps"], indent=2))
    print("%d cases" % doc["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
