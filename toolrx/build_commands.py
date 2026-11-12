#!/usr/bin/env python3
"""Generate the deterministic command library used by the in-browser skills.

The library is plain data: each entry is a regex, an op name, and argument
placeholders. `toolrx/web/skills.js` compiles and runs them. Unit conversions
are expanded here because that is where most of the breadth comes from.

    python3 toolrx/build_commands.py
"""
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(os.environ.get("TOOLRX_COMMANDS_OUT")
                   or (ROOT / "web" / "commands.json"))

N = r"(-?(?:\d[\d,]*(?:\.\d+)?|\d*\.\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))"
TXT = r"(.+?)"
REST = r"(.+)"

COMMANDS = []
_SEEN = {}
_DUPLICATES = []


def _pattern_key(pattern):
    """Whitespace-insensitive key for duplicate detection.

    `upper case {text}` and `uppercase {text}` compile to the same regex, so the
    first one wins and the second is dropped instead of shipping a dead entry.
    """
    return re.sub(r"\s+", "", pattern.lower())


def add(cid, op, pattern, args=None, desc="", cat="misc"):
    key = _pattern_key(pattern)
    if key in _SEEN:
        _DUPLICATES.append((cid, _SEEN[key], pattern))
        return False
    _SEEN[key] = cid
    COMMANDS.append({"id": cid, "op": op, "re": pattern,
                     "args": args or {}, "d": desc, "c": cat})
    return True


# ---------------------------------------------------------------- math ----
BINARY = {
    "add": ["add {a} and {b}", "add {a} to {b}", "{a} plus {b}",
            "what is {a} plus {b}", "sum of {a} and {b}", "{a} + {b}"],
    "sub": ["subtract {b} from {a}", "{a} minus {b}", "what is {a} minus {b}",
            "difference between {a} and {b}", "{a} - {b}"],
    "mul": ["multiply {a} and {b}", "multiply {a} by {b}", "{a} times {b}",
            "{a} multiplied by {b}", "what is {a} times {b}",
            "product of {a} and {b}", "{a} * {b}", "{a} x {b}"],
    "div": ["divide {a} by {b}", "{a} divided by {b}",
            "what is {a} divided by {b}", "{a} over {b}", "{a} / {b}"],
    "mod": ["{a} mod {b}", "{a} modulo {b}", "remainder of {a} divided by {b}"],
    "pow": ["{a} to the power of {b}", "{a} raised to the power {b}",
            "{a} raised to {b}", "{a} ^ {b}", "{a} to the {b} power"],
    "gcd": ["gcd of {a} and {b}", "greatest common divisor of {a} and {b}"],
    "lcm": ["lcm of {a} and {b}", "least common multiple of {a} and {b}"],
    "min": ["min of {a} and {b}", "minimum of {a} and {b}", "smaller of {a} and {b}"],
    "max": ["max of {a} and {b}", "maximum of {a} and {b}", "larger of {a} and {b}"],
    "pct_of": ["{a}% of {b}", "{a} percent of {b}", "what is {a} percent of {b}",
               "what is {a}% of {b}"],
    "pct_change": ["percent change from {a} to {b}",
                   "percentage change from {a} to {b}",
                   "percentage increase from {a} to {b}"],
    "log": ["log base {b} of {a}", "logarithm base {b} of {a}"],
    "divisible": ["{a} is divisible by {b}", "is {a} divisible by {b}", "{a} divisible by {b}"],
}
n = 0
for op, patterns in BINARY.items():
    for pat in patterns:
        n += 1
        expr = pat.replace("{a}", N).replace("{b}", N)
        add(f"math.{op}.{n}", "math.binary", "^" + expr + "$",
            {"op": op, "a": "$1", "b": "$2"}, pat, "math")

UNARY = {
    "square": ["square {a}", "{a} squared", "what is {a} squared"],
    "cube": ["cube {a}", "{a} cubed", "what is {a} cubed"],
    "sqrt": ["square root of {a}", "sqrt of {a}", "sqrt {a}",
             "what is the square root of {a}"],
    "cbrt": ["cube root of {a}", "cbrt {a}"],
    "abs": ["absolute value of {a}", "abs {a}", "abs of {a}"],
    "neg": ["negate {a}", "negative of {a}", "opposite of {a}"],
    "round": ["round {a}", "round off {a}", "round {a} to the nearest integer"],
    "floor": ["floor of {a}", "floor {a}"],
    "ceil": ["ceiling of {a}", "ceil of {a}", "ceil {a}"],
    "fact": ["{a} factorial", "factorial of {a}", "{a}!"],
    "recip": ["reciprocal of {a}", "inverse of {a}"],
    "isprime": ["is {a} prime", "is {a} a prime number", "check if {a} is prime"],
    "iseven": ["is {a} even", "is {a} an even number"],
    "isodd": ["is {a} odd", "is {a} an odd number"],
    "sign": ["sign of {a}", "signum of {a}"],
    "double": ["double {a}", "twice {a}", "what is double {a}"],
    "half": ["half of {a}", "{a} halved"],
    "triple": ["triple {a}", "thrice {a}"],
    "factors": ["factors of {a}", "divisors of {a}", "list the factors of {a}"],
    "primefactors": ["prime factors of {a}", "prime factorization of {a}"],
    "divcount": ["number of divisors of {a}", "how many divisors does {a} have"],
    "deg2rad": ["{a} degrees in radians", "degrees to radians {a}"],
    "rad2deg": ["{a} radians in degrees", "radians to degrees {a}"],
}
for op, patterns in UNARY.items():
    for pat in patterns:
        n += 1
        expr = pat.replace("{a}", N)
        add(f"math.{op}.u{n}", "math.unary", "^" + expr + "$",
            {"op": op, "a": "$1"}, pat, "math")

# "square it" / "square the result" — these read the previous step's output
for op, patterns in {
    "square": ["square it", "square that", "square the result", "square the output"],
    "cube": ["cube it", "cube that", "cube the result"],
    "sqrt": ["square root of it", "sqrt it", "sqrt that", "square root of the result"],
    "abs": ["absolute value of it", "abs it"],
    "neg": ["negate it", "negate that"],
    "round": ["round it", "round that", "round the result"],
    "floor": ["floor it", "floor that"],
    "ceil": ["ceil it", "ceiling of it"],
    "recip": ["reciprocal of it", "invert it"],
    "double": ["double it", "double that", "double the result"],
    "half": ["half it", "halve it", "half the result"],
    "triple": ["triple it", "triple that"],
    "fact": ["factorial of it"],
}.items():
    for pat in patterns:
        add(f"math.pronoun.{op}.{len(COMMANDS)}", "math.unary",
            "^" + re.escape(pat) + "$", {"op": op}, pat, "math")

LISTS = {
    "sum": ["sum {list}", "sum of {list}", "total of {list}", "add {list}", "total {list}"],
    "mean": ["mean of {list}", "average of {list}", "avg of {list}"],
    "median": ["median of {list}"],
    "mode": ["mode of {list}"],
    "range": ["range of {list}"],
    "stdev": ["standard deviation of {list}", "std dev of {list}"],
    "minlist": ["smallest of {list}", "minimum of {list}"],
    "maxlist": ["largest of {list}", "maximum of {list}"],
    "product": ["product of {list}", "multiply {list}"],
}
LIST_RE = r"(-?\d[\d,]*(?:\.\d+)?(?:\s*(?:,|and|;|\s)\s*-?\d[\d,]*(?:\.\d+)?)+)"
for op, patterns in LISTS.items():
    for pat in patterns:
        n += 1
        expr = pat.replace("{list}", LIST_RE)
        add(f"math.{op}.l{n}", "math.list", "^" + expr + "$",
            {"op": op, "list": "$1"}, pat, "math")

FORMAT = {
    "words": ["number to words {a}", "{a} in words", "spell out {a}"],
    "roman": ["{a} in roman numerals", "roman numeral for {a}", "to roman {a}"],
    "ordinal": ["ordinal of {a}", "{a} as an ordinal"],
    "base2": ["{a} in binary", "binary of {a}", "convert {a} to binary"],
    "base8": ["{a} in octal", "octal of {a}", "convert {a} to octal"],
    "base16": ["{a} in hex", "{a} in hexadecimal", "hex of {a}", "convert {a} to hex"],
    "sci": ["{a} in scientific notation", "scientific notation of {a}"],
}
for op, patterns in FORMAT.items():
    for pat in patterns:
        n += 1
        expr = pat.replace("{a}", N)
        add(f"math.fmt.{op}.{n}", "math.format", "^" + expr + "$",
            {"op": op, "a": "$1"}, pat, "math")

for expr_pat in (
    r"^(?:calculate|compute|evaluate|work out|solve)\s+(.+)$",
    r"^(?:calc|math)\s+(.+)$",
    r"^what\s+is\s+([-+(]?[\d.][-+*/^%().\d\s]*)$",
    r"^([-+]?[\d.]+(?:\s*[-+*/^%]\s*[-+]?[\d.()]+)+)$",
):
    n += 1
    add(f"math.expr.{n}", "math.expr", expr_pat, {"expr": "$1"},
        "evaluate an arithmetic expression", "math")

# ---------------------------------------------------------------- units ---
UNITS = {
    "length": {
        "mm": ("millimeter", "millimeters", "mm"), "cm": ("centimeter", "centimeters", "cm"),
        "m": ("meter", "meters", "metre", "metres", "m"),
        "km": ("kilometer", "kilometers", "kilometre", "kilometres", "km"),
        "in": ("inch", "inches", "in"), "ft": ("foot", "feet", "ft"),
        "yd": ("yard", "yards", "yd"), "mi": ("mile", "miles", "mi"),
        "nmi": ("nautical mile", "nautical miles", "nmi"),
    },
    "mass": {
        "mg": ("milligram", "milligrams", "mg"), "g": ("gram", "grams", "g"),
        "kg": ("kilogram", "kilograms", "kg", "kilo", "kilos"),
        "t": ("tonne", "tonnes", "metric ton", "metric tons", "t"),
        "oz": ("ounce", "ounces", "oz"), "lb": ("pound", "pounds", "lb", "lbs"),
        "st": ("stone", "stones", "st"),
    },
    "volume": {
        "ml": ("milliliter", "milliliters", "ml"),
        "l": ("liter", "liters", "litre", "litres", "l"),
        "tsp": ("teaspoon", "teaspoons", "tsp"),
        "tbsp": ("tablespoon", "tablespoons", "tbsp"),
        "floz": ("fluid ounce", "fluid ounces", "fl oz", "floz"),
        "cup": ("cup", "cups"), "pt": ("pint", "pints", "pt"),
        "qt": ("quart", "quarts", "qt"), "gal": ("gallon", "gallons", "gal"),
    },
    "data": {
        "kb": ("kilobyte", "kilobytes", "kb"), "mb": ("megabyte", "megabytes", "mb"),
        "gb": ("gigabyte", "gigabytes", "gb"), "tb": ("terabyte", "terabytes", "tb"),
        "kib": ("kibibyte", "kibibytes", "kib"), "mib": ("mebibyte", "mebibytes", "mib"),
        "gib": ("gibibyte", "gibibytes", "gib"),
    },
    "time": {
        "ms": ("millisecond", "milliseconds", "ms"), "s": ("second", "seconds", "s"),
        "min": ("minute", "minutes", "min", "mins"), "h": ("hour", "hours", "h", "hr", "hrs"),
        "day": ("day", "days"), "week": ("week", "weeks"),
    },
    "speed": {
        "mps": ("meter per second", "meters per second", "mps"),
        "kph": ("kilometer per hour", "kilometers per hour", "kph", "kmh"),
        "mph": ("mile per hour", "miles per hour", "mph"),
        "knot": ("knot", "knots", "kt"),
    },
    "area": {
        "mm2": ("square millimeter", "square millimeters", "mm2"),
        "cm2": ("square centimeter", "square centimeters", "cm2"),
        "m2": ("square meter", "square meters", "m2"),
        "km2": ("square kilometer", "square kilometers", "km2"),
        "ha": ("hectare", "hectares", "ha"), "acre": ("acre", "acres"),
        "ft2": ("square foot", "square feet", "ft2"),
        "in2": ("square inch", "square inches", "in2"),
    },
    "energy": {
        "j": ("joule", "joules", "j"), "kj": ("kilojoule", "kilojoules", "kj"),
        "cal": ("calorie", "calories", "cal"), "kcal": ("kilocalorie", "kilocalories", "kcal"),
        "wh": ("watt hour", "watt hours", "wh"), "kwh": ("kilowatt hour", "kilowatt hours", "kwh"),
    },
    "pressure": {
        "pa": ("pascal", "pascals", "pa"), "kpa": ("kilopascal", "kilopascals", "kpa"),
        "bar": ("bar", "bars"), "atm": ("atmosphere", "atmospheres", "atm"),
        "psi": ("psi",), "mmhg": ("mmhg", "millimeter of mercury"),
    },
    "angle": {"deg": ("degree", "degrees", "deg"), "rad": ("radian", "radians", "rad"),
              "grad": ("gradian", "gradians", "grad")},
}

FACTORS = {
    "length": {"mm": .001, "cm": .01, "m": 1, "km": 1000, "in": .0254, "ft": .3048,
               "yd": .9144, "mi": 1609.344, "nmi": 1852},
    "mass": {"mg": .001, "g": 1, "kg": 1000, "t": 1e6, "oz": 28.349523125,
             "lb": 453.59237, "st": 6350.29318},
    "volume": {"ml": .001, "l": 1, "tsp": .00492892159375, "tbsp": .01478676478125,
               "floz": .0295735295625, "cup": .2365882365, "pt": .473176473,
               "qt": .946352946, "gal": 3.785411784},
    "data": {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
             "kib": 1024, "mib": 1048576, "gib": 1073741824},
    "time": {"ms": .001, "s": 1, "min": 60, "h": 3600, "day": 86400, "week": 604800},
    "speed": {"mps": 1, "kph": 1 / 3.6, "mph": 0.44704, "knot": 1852 / 3600},
    "area": {"mm2": 1e-6, "cm2": 1e-4, "m2": 1, "km2": 1e6, "ha": 1e4,
             "acre": 4046.8564224, "ft2": .09290304, "in2": .00064516},
    "energy": {"j": 1, "kj": 1000, "cal": 4.184, "kcal": 4184, "wh": 3600, "kwh": 3.6e6},
    "pressure": {"pa": 1, "kpa": 1000, "bar": 1e5, "atm": 101325, "psi": 6894.757293,
                 "mmhg": 133.322387},
    "angle": {"deg": 1, "rad": 57.29577951308232, "grad": .9},
}

PHRASINGS = [
    r"^convert\s+{n}\s+{from}\s+(?:to|into)\s+{to}$",
    r"^{n}\s+{from}\s+(?:to|into|in)\s+{to}$",
    r"^how many\s+{to}\s+(?:are\s+|is\s+)?in\s+{n}\s+{from}$",
    r"^(?:what is|what's|whats)\s+{n}\s+{from}\s+in\s+{to}$",
    r"^{n}\s+{from}\s+(?:equals|is)\s+(?:how many\s+)?{to}$",
]
for cat, units in UNITS.items():
    names = list(units)
    for src in names:
        for dst in names:
            if src == dst:
                continue
            fa = "(?:" + "|".join(re.escape(x) for x in units[src]) + ")"
            fb = "(?:" + "|".join(re.escape(x) for x in units[dst]) + ")"
            for k, ph in enumerate(PHRASINGS):
                pattern = (ph.replace("{n}", N).replace("{from}", fa)
                             .replace("{to}", fb))
                add(f"unit.{cat}.{src}.{dst}.{k}", "unit.convert", pattern,
                    {"from": src, "to": dst, "n": "$1", "cat": cat},
                    f"{src} -> {dst}", "units")

for src, dst in (("c", "f"), ("c", "k"), ("f", "c"), ("f", "k"), ("k", "c"), ("k", "f")):
    fa = {"c": "(?:celsius|c)", "f": "(?:fahrenheit|f)", "k": "(?:kelvin|k)"}[src]
    fb = {"c": "(?:celsius|c)", "f": "(?:fahrenheit|f)", "k": "(?:kelvin|k)"}[dst]
    for k, ph in enumerate(PHRASINGS):
        pattern = ph.replace("{n}", N).replace("{from}", fa).replace("{to}", fb)
        add(f"unit.temp.{src}.{dst}.{k}", "unit.convert", pattern,
            {"from": src, "to": dst, "n": "$1", "cat": "temperature"},
            f"{src} -> {dst}", "units")

# ---------------------------------------------------------------- text ----
TEXT_OPS = {
    "reverse": ["reverse {text}", "reverse the text {text}", "backwards {text}"],
    "upper": ["uppercase {text}", "upper case {text}", "make {text} uppercase"],
    "lower": ["lowercase {text}", "lower case {text}", "make {text} lowercase"],
    "title": ["title case {text}", "title case of {text}", "make {text} title case"],
    "sentence": ["sentence case {text}", "sentence case of {text}"],
    "capitalize": ["capitalize {text}", "capitalize the first letter of {text}"],
    "trim": ["trim {text}", "strip whitespace from {text}"],
    "collapse": ["remove extra whitespace from {text}", "collapse whitespace in {text}"],
    "slug": ["slugify {text}", "make a slug from {text}"],
    "snake": ["snake case {text}", "snake case of {text}"],
    "kebab": ["kebab case {text}", "kebab case of {text}"],
    "camel": ["camel case {text}", "camel case of {text}"],
    "pascal": ["pascal case {text}", "pascal case of {text}"],
    "sortlines": ["sort the lines in {text}", "sort lines of {text}"],
    "sortwords": ["sort the words in {text}", "sort words of {text}"],
    "uniqlines": ["remove duplicate lines from {text}", "unique lines of {text}"],
    "reverselines": ["reverse the lines in {text}", "reverse lines of {text}"],
    "reversewords": ["reverse the words in {text}", "reverse word order of {text}"],
    "striptags": ["strip html from {text}", "remove html tags from {text}"],
    "leet": ["leet speak {text}", "leetspeak {text}"],
    "initials": ["initials of {text}", "initial letters of {text}"],
    "acronym": ["acronym for {text}", "acronym of {text}"],
    "longest": ["longest word in {text}", "longest word of {text}"],
    "freq": ["word frequency in {text}", "frequency of words in {text}"],
    "charfreq": ["character frequency in {text}", "letter frequency of {text}"],
    "indent": ["indent {text}", "indent the lines of {text}"],
    "dedupe": ["remove duplicate words from {text}", "dedupe words in {text}"],
}
for op, patterns in TEXT_OPS.items():
    for pat in patterns:
        add(f"text.{op}.{len(COMMANDS)}", "text.transform",
            "^" + pat.replace("{text}", TXT) + "$",
            {"op": op, "text": "$1"}, pat, "text")

COUNTS = {
    "words": ["count the words in {text}", "word count of {text}", "how many words in {text}"],
    "chars": ["count the characters in {text}", "character count of {text}",
              "how many characters in {text}"],
    "lines": ["count the lines in {text}", "line count of {text}", "how many lines in {text}"],
    "sentences": ["count the sentences in {text}", "sentence count of {text}"],
    "vowels": ["count the vowels in {text}", "vowel count of {text}"],
    "consonants": ["count the consonants in {text}", "consonant count of {text}"],
}
for op, patterns in COUNTS.items():
    for pat in patterns:
        add(f"text.count.{op}.{len(COMMANDS)}", "text.count",
            "^" + pat.replace("{text}", TXT) + "$",
            {"what": op, "text": "$1"}, pat, "text")

# bare counts work on the previous step's output
for op, patterns in {
    "words": ["count the words", "count words", "word count", "how many words"],
    "chars": ["count the characters", "count characters", "character count",
              "how many characters", "count the letters"],
    "lines": ["count the lines", "count lines", "line count", "how many lines"],
    "sentences": ["count the sentences", "sentence count", "how many sentences"],
    "vowels": ["count the vowels", "vowel count", "how many vowels"],
    "consonants": ["count the consonants", "consonant count", "how many consonants"],
}.items():
    for pat in patterns:
        add(f"text.count.bare.{op}.{len(COMMANDS)}", "text.count",
            "^" + re.escape(pat) + "$", {"what": op}, pat, "text")

# "it" / "that" forms so a multi-step chain can feed the previous result
for op, patterns in {
    "reverse": ["reverse it", "reverse that", "flip it", "reverse the result"],
    "upper": ["uppercase it", "upper case it", "make it uppercase", "shout it"],
    "lower": ["lowercase it", "lower case it", "make it lowercase"],
    "title": ["title case it", "title case that"],
    "sentence": ["sentence case it"],
    "capitalize": ["capitalize it"],
    "trim": ["trim it", "strip the whitespace"],
    "collapse": ["collapse the whitespace", "remove extra whitespace"],
    "slug": ["slugify it", "slug it", "make it a slug"],
    "snake": ["snake case it"],
    "kebab": ["kebab case it"],
    "camel": ["camel case it"],
    "pascal": ["pascal case it"],
    "sortlines": ["sort it", "sort the lines", "sort those lines"],
    "reverselines": ["reverse the lines", "reverse the line order"],
    "sortwords": ["sort the words", "sort words"],
    "reversewords": ["reverse the words", "reverse word order"],
    "uniqlines": ["remove duplicate lines", "unique the lines"],
    "striptags": ["strip the html", "remove the html tags"],
    "leet": ["leet speak it", "leetspeak it"],
    "initials": ["get the initials", "initials"],
    "longest": ["longest word", "find the longest word"],
    "dedupe": ["remove duplicate words", "dedupe it", "dedupe the words"],
    "indent": ["indent it", "indent the lines"],
}.items():
    for pat in patterns:
        add(f"text.pronoun.{op}.{len(COMMANDS)}", "text.transform",
            "^" + re.escape(pat) + "$", {"op": op}, pat, "text")

for pat, op in (
    ("is {text} a palindrome", "palindrome"),
    ("check if {text} is a palindrome", "palindrome"),
    ("is {text} an anagram of {text2}", "anagram"),
):
    args = {"op": op, "text": "$1"}
    if "{text2}" in pat:
        args["text2"] = "$2"
    add(f"text.check.{op}.{len(COMMANDS)}", "text.check",
        "^" + pat.replace("{text2}", TXT).replace("{text}", TXT) + "$",
        args, pat, "text")

for pat, what in (
    ("extract emails from {text}", "emails"),
    ("extract email addresses from {text}", "emails"),
    ("extract urls from {text}", "urls"),
    ("extract links from {text}", "urls"),
    ("extract numbers from {text}", "numbers"),
):
    add(f"text.extract.{what}.{len(COMMANDS)}", "text.extract",
        "^" + pat.replace("{text}", TXT) + "$", {"what": what, "text": "$1"}, pat, "text")

for pat in ("replace {find} with {repl} in {text}", "replace {find} by {repl} in {text}"):
    add(f"text.replace.{len(COMMANDS)}", "text.replace",
        "^" + pat.replace("{find}", TXT).replace("{repl}", TXT).replace("{text}", TXT) + "$",
        {"find": "$1", "repl": "$2", "text": "$3"}, pat, "text")

# -------------------------------------------------------------- encoding --
ENCODE = {
    "b64e": ["base64 encode {text}", "encode {text} as base64"],
    "b64d": ["base64 decode {text}", "decode base64 {text}"],
    "urle": ["url encode {text}", "percent encode {text}"],
    "urld": ["url decode {text}", "percent decode {text}"],
    "hexe": ["hex encode {text}", "encode {text} as hex"],
    "hexd": ["hex decode {text}", "decode hex {text}"],
    "bine": ["binary encode {text}", "encode {text} as binary"],
    "bind": ["binary decode {text}", "decode binary {text}"],
    "rot13": ["rot13 {text}", "rot 13 {text}"],
    "morse": ["morse code for {text}", "encode {text} as morse"],
    "unmorse": ["decode morse {text}", "morse decode {text}"],
}
for op, patterns in ENCODE.items():
    for pat in patterns:
        add(f"enc.{op}.{len(COMMANDS)}", "encode",
            "^" + pat.replace("{text}", TXT) + "$", {"op": op, "text": "$1"}, pat, "encoding")

for alg in ("blake2b", "sha256", "md5"):
    for pat in (f"{alg} hash of {{text}}", f"{alg} of {{text}}", f"hash {{text}} with {alg}"):
        add(f"hash.{alg}.{len(COMMANDS)}", "hash",
            "^" + pat.replace("{text}", TXT) + "$", {"algo": alg, "text": "$1"}, pat, "encoding")

# ------------------------------------------------------------ json / csv --
JSON_OPS = {
    "pretty": ["pretty print json {text}", "format json {text}", "pretty json {text}"],
    "minify": ["minify json {text}", "compact json {text}"],
    "validate": ["validate json {text}", "is {text} valid json"],
    "keys": ["json keys of {text}", "list json keys in {text}"],
    "values": ["json values of {text}", "list json values in {text}"],
    "tocsv": ["json to csv {text}", "convert json to csv {text}"],
}
for op, patterns in JSON_OPS.items():
    for pat in patterns:
        add(f"json.{op}.{len(COMMANDS)}", "json.op",
            "^" + pat.replace("{text}", REST) + "$", {"op": op, "text": "$1"}, pat, "data")

for op, pat in (("tocsv", "csv to json {text}"), ("tocsv", "convert csv to json {text}")):
    add(f"csv.{op}.{len(COMMANDS)}", "csv.op", "^" + pat.replace("{text}", REST) + "$",
        {"op": op, "text": "$1"}, pat, "data")

# ---------------------------------------------------------------- dates ---
for pat, op in (
    ("what time is it", "now"), ("current time", "time"), ("what is the time", "time"),
    ("what date is it", "today"), ("today's date", "today"), ("current date", "today"),
    ("current timestamp", "unix"), ("unix timestamp", "unix"),
    ("what is the unix timestamp", "unix"),
):
    add(f"date.{op}.{len(COMMANDS)}", "date.op", "^" + re.escape(pat) + "$",
        {"op": op}, pat, "date")

for pat, op in (
    ("{n} days from now", "add"), ("{n} days ago", "sub"),
    ("add {n} days", "add"), ("subtract {n} days", "sub"),
    ("date in {n} days", "add"), ("date {n} days ago", "sub"),
):
    add(f"date.{op}.{len(COMMANDS)}", "date.op", "^" + pat.replace("{n}", N) + "$",
        {"op": op, "n": "$1"}, pat, "date")

for pat, op in (
    ("days between {a} and {b}", "diff"), ("days from {a} to {b}", "diff"),
    ("how many days between {a} and {b}", "diff"),
):
    add(f"date.diff.{len(COMMANDS)}", "date.op",
        "^" + pat.replace("{a}", TXT).replace("{b}", TXT) + "$",
        {"op": op, "a": "$1", "b": "$2"}, pat, "date")

for pat in ("what weekday is {text}", "day of the week for {text}"):
    add(f"date.weekday.{len(COMMANDS)}", "date.op", "^" + pat.replace("{text}", TXT) + "$",
        {"op": "weekday", "text": "$1"}, pat, "date")
for pat in ("is {n} a leap year", "is leap year {n}"):
    add(f"date.leap.{len(COMMANDS)}", "date.op", "^" + pat.replace("{n}", N) + "$",
        {"op": "leap", "n": "$1"}, pat, "date")
for pat in ("convert {text} to a date", "parse date {text}", "format date {text}"):
    add(f"date.parse.{len(COMMANDS)}", "date.op", "^" + pat.replace("{text}", TXT) + "$",
        {"op": "parse", "text": "$1"}, pat, "date")

for pat, op in (("what day is it", "dayname"), ("what day is today", "dayname"),
                ("what weekday is it", "dayname"), ("what year is it", "year")):
    add(f"date.{op}.{len(COMMANDS)}", "date.op", "^" + re.escape(pat) + "$",
        {"op": op}, pat, "date")

for pat in ("how many days in {text}", "days in {text}", "how many days are in {text}"):
    add(f"date.daysin.{len(COMMANDS)}", "date.op", "^" + pat.replace("{text}", TXT) + "$",
        {"op": "daysin", "text": "$1"}, pat, "date")

# ------------------------------------------------------------ common facts -
add("fact.capital", "fact.capital",
    r"^(?:what is the |whats the |what's the )?capital(?: city)? of (.+)$",
    {"subject": "$1"}, "capital of a country", "facts")
add("fact.symbol", "fact.symbol",
    r"^(?:what is the |whats the |what's the )?(?:chemical )?symbol (?:for|of) (.+)$",
    {"subject": "$1"}, "chemical symbol of an element", "facts")

# --------------------------------------------------------------- colors ---
for pat, op in (
    ("{text} to rgb", "toRgb"), ("rgb of {text}", "toRgb"),
    ("what is {text} in rgb", "toRgb"),
    ("rgb({a}, {b}, {c}) to hex", "toHex"),
    ("convert rgb {a} {b} {c} to hex", "toHex"),
):
    add(f"color.{op}.{len(COMMANDS)}", "color.op", "^" + pat.replace("{text}", TXT)
        .replace("{a}", N).replace("{b}", N).replace("{c}", N) + "$",
        {"op": op, "text": "$1", "a": "$1", "b": "$2", "c": "$3"}, pat, "color")

for pat, op in (
    ("lighten {text} by {n}%", "lighten"), ("darken {text} by {n}%", "darken"),
    ("mix {a} and {b}", "mix"), ("contrast ratio of {a} and {b}", "contrast"),
    ("luminance of {text}", "luminance"),
):
    add(f"color.{op}.{len(COMMANDS)}", "color.op",
        "^" + pat.replace("{text}", TXT).replace("{n}", N)
        .replace("{a}", TXT).replace("{b}", TXT) + "$",
        {"op": op, "text": "$1", "n": "$1", "a": "$1", "b": "$2"}, pat, "color")

# ------------------------------------------------------------- generators -
for pat, op in (
    ("flip a coin", "coin"), ("toss a coin", "coin"), ("heads or tails", "coin"),
    ("roll a die", "die"), ("roll a dice", "die"),
    ("generate a uuid", "uuid"), ("create a uuid", "uuid"), ("uuid", "uuid"),
    ("generate a password", "pw"), ("create a password", "pw"),
):
    add(f"gen.{op}.{len(COMMANDS)}", "gen.op", "^" + re.escape(pat) + "$",
        {"op": op}, pat, "generate")

for pat, op in (
    ("roll {a} dice", "dice"), ("roll {a}d{b}", "dice2"),
    ("random number between {a} and {b}", "rand"),
    ("pick one of {text}", "pick"), ("pick {text}", "pick"),
    ("shuffle {text}", "shuffle"), ("generate {a} lorem words", "lorem"),
    ("generate a password of length {a}", "pwlen"),
    ("choose between {text}", "pick"),
):
    add(f"gen.{op}.{len(COMMANDS)}", "gen.op",
        "^" + pat.replace("{a}", N).replace("{b}", N).replace("{text}", TXT) + "$",
        {"op": op, "a": "$1", "b": "$2", "text": "$1"}, pat, "generate")

# ---------------------------------------------------------------- regex ---
for pat, op in (
    ("test {text} against {pat}", "test"), ("match {pat} in {text}", "match"),
    ("find {pat} in {text}", "match"),
    ("replace {pat} with {repl} in {text}", "replace"),
):
    add(f"regex.{op}.{len(COMMANDS)}", "regex.op",
        "^" + pat.replace("{pat}", TXT).replace("{repl}", TXT).replace("{text}", TXT) + "$",
        {"op": op, "pat": "$1", "repl": "$2", "text": "$3"}, pat, "regex")

# -------------------------------------------------------------- library ---
# The book archive is metadata-only. Its catalog ships inside commands.json so
# the browser can search it offline without a second fetch or a build step.
LIBRARY_FILE = ROOT.parent / "library" / "catalog.json"
LIBRARY = None
if LIBRARY_FILE.exists():
    try:
        _catalog = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        _records = _catalog.get("records", [])
        _langs, _topics = {}, {}
        for _rec in _records:
            _cls = _rec.get("classification") or {}
            for _lang in _cls.get("programming_languages") or []:
                _langs[_lang] = _langs.get(_lang, 0) + 1
            for _topic in _cls.get("topics") or []:
                _topics[_topic] = _topics.get(_topic, 0) + 1
        LIBRARY = {
            "version": _catalog.get("version"),
            "updated": _catalog.get("updated"),
            "records": _records,
            "stats": {
                "records": len(_records),
                "parts": sum(len(r.get("parts") or []) for r in _records),
                "files": sum(len(r.get("parts") or []) or 1 for r in _records),
                "programming": dict(sorted(_langs.items(), key=lambda kv: (-kv[1], kv[0]))),
                "topics": dict(sorted(_topics.items(), key=lambda kv: (-kv[1], kv[0]))),
            },
        }
    except (OSError, ValueError) as _exc:  # pragma: no cover - build-time warning
        print(f"warning: could not read {LIBRARY_FILE}: {_exc}")

for pat in ("library stats", "library summary", "show my library", "show the library",
            "what books do i have", "what is in my library", "what's in my library",
            "my library", "library"):
    add(f"library.stats.{len(COMMANDS)}", "library.stats", "^" + re.escape(pat) + "$",
        {}, pat, "library")

for pat in ("find a book about {topic}", "find books about {topic}",
            "find a book on {topic}", "find books on {topic}",
            "which book covers {topic}", "which books cover {topic}",
            "what do i have on {topic}", "what books do i have on {topic}",
            "what books cover {topic}", "recommend a book about {topic}",
            "recommend a book for {topic}", "search my library for {topic}",
            "list books about {topic}", "list books on {topic}"):
    add(f"library.find.{len(COMMANDS)}", "library.find",
        "^" + pat.replace("{topic}", REST) + "$", {"topic": "$1"}, pat, "library")

for pat in ("list books by language {lang}", "which books are in {lang}",
            "books for {lang}", "books on {lang}"):
    add(f"library.language.{len(COMMANDS)}", "library.language",
        "^" + pat.replace("{lang}", REST) + "$", {"lang": "$1"}, pat, "library")

for pat in ("what should i read next", "what should i read now",
            "what is next in my library", "recommend my next book"):
    add(f"library.next.{len(COMMANDS)}", "library.next", "^" + re.escape(pat) + "$",
        {}, pat, "library")

for pat in ("what should i read after {id}", "what comes after {id} in my library",
            "what is next after {id}"):
    add(f"library.after.{len(COMMANDS)}", "library.after",
        "^" + pat.replace("{id}", REST) + "$", {"id": "$1"}, pat, "library")

for pat in ("library gaps", "library coverage", "what gaps are in my library",
            "where is my library thin", "what is missing from my library"):
    add(f"library.gaps.{len(COMMANDS)}", "library.gaps", "^" + re.escape(pat) + "$",
        {}, pat, "library")

for pat in ("list {level} books", "show {level} books", "which books are {level}",
            "books at {level} level"):
    add(f"library.level.{len(COMMANDS)}", "library.level",
        "^" + pat.replace("{level}", "(beginner|intermediate|advanced|reference|all)")
        + "$", {"level": "$1"}, pat, "library")

# ------------------------------------------------------- composable edits ---
# Follow-ups patch the active project: a named function or constant in a real
# file, plus the build spec. Unsupported combinations answer honestly instead
# of rebuilding something unrelated.
EDIT_PATTERNS = [
    ("double-jump", ("add double jump", "add a double jump",
                     "give it a double jump", "give it double jump",
                     "double jump")),
    ("enemy-types", ("add three enemy types", "add 3 enemy types",
                     "add enemy types", "add three types of enemy",
                     "add 3 types of enemies", "add different enemy types")),
    ("boss", ("add a boss", "add a boss fight", "add boss", "add a final boss")),
    ("quest", ("add a quest", "add a quest line", "add a questline",
               "add another quest", "add quests")),
    ("day-night", ("add day/night", "add a day night cycle", "add day and night",
                   "add a day/night cycle", "add day night")),
    ("sound", ("add sound", "add sound effects", "add audio",
               "add sound to it")),
    ("harder", ("make it harder", "increase the difficulty", "raise the difficulty",
                "make it more difficult", "hard mode", "make the game harder")),
    ("isometric", ("switch to isometric", "make it isometric",
                   "use an isometric view", "switch to an isometric view",
                   "change the view to isometric")),
    ("three-d", ("make it 3d", "make it 3-d", "make this 3d", "convert it to 3d",
                 "turn it into 3d", "give it 3d graphics", "make the game 3d")),
]
for patch, pats in EDIT_PATTERNS:
    for pat in pats:
        add(f"edit.{patch}.{len(COMMANDS)}", "edit.apply", "^" + re.escape(pat) + "$",
            {"patch": patch}, pat, "edit")

# A single request may bundle two to five known edits. The bundle is applied to
# one working copy and written only if every patch fits, so it is all-or-none.
MANY_PATCH_ALIASES = [
    ("double-jump", ("double jump", "a double jump", "double-jump")),
    ("enemy-types", ("three enemy types", "3 enemy types", "enemy types")),
    ("boss", ("a boss", "a boss fight", "boss", "boss fight")),
    ("quest", ("a quest", "a quest line", "another quest", "quests")),
    ("day-night", ("day/night", "day night", "day and night", "day night cycle")),
    ("sound", ("sound", "sound effects", "audio")),
    ("harder", ("harder", "hard mode")),
    ("isometric", ("isometric", "isometric view")),
    ("three-d", ("3d", "3-d", "three-d")),
]


def _phrase(text):
    return r"\s+".join(re.escape(word) for word in text.split())


def _alternation(groups):
    words = sorted({word for _, aliases in groups for word in aliases},
                   key=lambda w: (-len(w), w))
    return "(?:" + "|".join(_phrase(w) for w in words) + ")"


_MANY_ONE = _alternation(MANY_PATCH_ALIASES)
_MANY_SEP = r"(?:\s*,\s*(?:and\s+)?|\s+and\s+)"
_MANY_LIST = ("((?:" + _MANY_ONE + ")(?:" + _MANY_SEP + "(?:" + _MANY_ONE
              + ")){1,4})")
add(f"edit.many.{len(COMMANDS)}", "edit.apply.many", "^add " + _MANY_LIST + "$",
    {"list": "$1"}, "add <edit> and <edit>", "edit")

# Multi-file growth: additive module and system files, never a rebuild.
GROWTH_MODULES = ["core", "ui", "data", "content"]
GROWTH_SYSTEMS = ["inventory", "crafting", "quests", "weather", "audio",
                  "save", "particles", "ai", "combat", "dialogue"]
for pat in ("grow project", "grow the project", "split into modules",
            "split the project into modules", "add modules",
            "grow the codebase"):
    add(f"grow.project.{len(COMMANDS)}", "project.grow", "^" + re.escape(pat) + "$",
        {}, pat, "edit")
for module in GROWTH_MODULES:
    for pat in (f"expand module {module}", f"expand the {module} module",
                f"add the {module} module", f"grow the {module} module"):
        add(f"grow.module.{module}.{len(COMMANDS)}", "module.expand",
            "^" + re.escape(pat) + "$", {"module": module}, pat, "edit")
for system in GROWTH_SYSTEMS:
    for pat in (f"add {system} system", f"add a {system} system",
                f"add the {system} system", f"add {system} mechanics"):
        add(f"grow.system.{system}.{len(COMMANDS)}", "system.add",
            "^" + re.escape(pat) + "$", {"system": system}, pat, "edit")

for pat in ("make the world {n}x{n}", "make the world {n} by {n}",
            "resize the world to {n}x{n}", "grow the world to {n}x{n}",
            "set the world size to {n}x{n}"):
    rx = re.escape(pat).replace(r"\{n\}", r"(\d{2,3})", 1).replace(r"\{n\}", r"\1")
    add(f"edit.world.{len(COMMANDS)}", "edit.apply", "^" + rx + "$",
        {"patch": "world", "arg": "$1"}, pat, "edit")

for pat in ("undo", "undo that", "undo the last edit", "undo last edit",
            "revert", "revert that", "revert the last change",
            "undo the last change"):
    add(f"edit.undo.{len(COMMANDS)}", "edit.undo", "^" + re.escape(pat) + "$",
        {}, pat, "edit")

# -------------------------------------------------------------- context ---
# Step 31: inspect, clear, continue, expand, and replay the small per-project
# working memory. These routes are exact so they never fall into a build.
for pat in ("what is in context", "what's in context", "whats in context",
            "show context", "show the context", "show my context",
            "what is the context", "what is in my context", "context"):
    add(f"context.show.{len(COMMANDS)}", "context.show", "^" + re.escape(pat) + "$",
        {}, pat, "context")

for pat in ("clear context", "clear the context", "clear my context",
            "forget context", "reset context", "wipe the context"):
    add(f"context.clear.{len(COMMANDS)}", "context.clear", "^" + re.escape(pat) + "$",
        {}, pat, "context")

for pat in ("clear all context", "clear context for all projects",
            "forget all context", "reset all context", "clear every context"):
    add(f"context.clear.all.{len(COMMANDS)}", "context.clear.all",
        "^" + re.escape(pat) + "$", {}, pat, "context")

for pat in ("continue from previous", "continue from the previous",
            "continue from where you left off", "continue where you left off",
            "continue the last plan", "continue the previous plan",
            "resume the last plan", "continue previous"):
    add(f"context.continue.{len(COMMANDS)}", "context.continue",
        "^" + re.escape(pat) + "$", {}, pat, "context")

for pat in ("apply the same changes to the other files",
            "apply the same changes to other files",
            "apply the same changes to the other projects",
            "apply the same changes to other projects",
            "apply the last changes to the other files",
            "apply the last changes to other projects"):
    add(f"context.apply_others.{len(COMMANDS)}", "context.apply_others",
        "^" + re.escape(pat) + "$", {}, pat, "context")

add(f"context.expand.{len(COMMANDS)}", "context.expand",
    r"^(?:expand|extend|add to) (?:the )?(?:last|previous) plan with (.+)$",
    {"more": "$1"}, "expand the last plan with <steps>", "context")

# ----------------------------------------------------------- optional llm --
# Off by default. These commands only reach the network when the user has saved
# an OpenAI-compatible endpoint and enabled the adapter in Command Center.
# Deterministic build/edit commands always win; `llm plan` is the explicit
# request for a speculative choice when no known genre matches.
for pat in ("llm status", "llm settings", "is the llm on", "is the llm enabled",
            "llm info"):
    add(f"llm.status.{len(COMMANDS)}", "llm.status", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

for pat in ("llm on", "turn on the llm", "enable the llm", "switch the llm on"):
    add(f"llm.on.{len(COMMANDS)}", "llm.on", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

for pat in ("llm off", "turn off the llm", "disable the llm", "switch the llm off"):
    add(f"llm.off.{len(COMMANDS)}", "llm.off", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

for pat in ("llm cache clear", "clear the llm cache", "clear llm cache",
            "llm cache reset"):
    add(f"llm.cache.{len(COMMANDS)}", "llm.cache", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

for pat in ("llm plan {prompt}", "ask the llm to plan {prompt}",
            "have the llm plan {prompt}", "let the llm plan {prompt}"):
    add(f"llm.plan.{len(COMMANDS)}", "llm.plan",
        "^" + pat.replace("{prompt}", REST), {"prompt": "$1"}, pat, "llm")

for pat in ("llm patch {file} with {instruction}", "llm patch {file} to {instruction}",
            "let the llm patch {file} with {instruction}",
            "have the llm patch {file} with {instruction}"):
    rx = (re.escape(pat).replace(r"\{file\}",
                                 r"([A-Za-z0-9][A-Za-z0-9._-]*)", 1)
          .replace(r"\{instruction\}", REST))
    add(f"llm.patch.{len(COMMANDS)}", "llm.patch", "^" + rx + "$",
        {"file": "$1", "instruction": "$2"}, pat, "llm")

for pat in ("apply the llm patch", "apply llm patch", "install the llm patch",
            "use the llm patch"):
    add(f"llm.apply.{len(COMMANDS)}", "llm.apply", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

for pat in ("discard the llm patch", "discard llm patch", "reject the llm patch",
            "drop the llm patch"):
    add(f"llm.discard.{len(COMMANDS)}", "llm.discard", "^" + re.escape(pat) + "$",
        {}, pat, "llm")

# ------------------------------------------------------------- language ---
# Exact forms first: a bare "what language is this" inspects the previous step.
for pat in ("what language is this", "what language is that",
            "what language is this code", "what language is that code",
            "what language is in this code", "what is this language"):
    add(f"lang.auto.{len(COMMANDS)}", "lang.detect", "^" + re.escape(pat) + "$",
        {"mode": "auto"}, pat, "lang")

for pat in ("what programming language is this", "what programming language is that",
            "what programming language is this code"):
    add(f"lang.programming.{len(COMMANDS)}", "lang.detect", "^" + re.escape(pat) + "$",
        {"mode": "programming"}, pat, "lang")

for pat in ("what natural language is this", "what natural language is that",
            "what human language is this"):
    add(f"lang.natural.{len(COMMANDS)}", "lang.detect", "^" + re.escape(pat) + "$",
        {"mode": "natural"}, pat, "lang")

for pat in ("what language is this: {text}", "what language is this {text}",
            "what is the language of {text}", "detect the language of {text}",
            "detect language of {text}", "identify the language of {text}",
            "what language is {text}"):
    add(f"lang.auto.text.{len(COMMANDS)}", "lang.detect",
        "^" + pat.replace("{text}", REST) + "$", {"mode": "auto", "text": "$1"},
        pat, "lang")

for pat in ("what programming language is this: {text}",
            "what programming language is {text}",
            "detect the programming language of {text}"):
    add(f"lang.programming.text.{len(COMMANDS)}", "lang.detect",
        "^" + pat.replace("{text}", REST) + "$",
        {"mode": "programming", "text": "$1"}, pat, "lang")

for pat in ("what natural language is this: {text}",
            "what natural language is {text}",
            "detect the natural language of {text}"):
    add(f"lang.natural.text.{len(COMMANDS)}", "lang.detect",
        "^" + pat.replace("{text}", REST) + "$",
        {"mode": "natural", "text": "$1"}, pat, "lang")

# Reply-language preference. The shell localizes only its own short messages;
# the preference is stored in the browser and survives a reload.
for pat in ("reply in english", "respond in english", "answer in english",
            "stop replying in spanish", "stop replying", "back to english",
            "reply normally", "reply in en"):
    add(f"lang.reply.off.{len(COMMANDS)}", "lang.reply",
        "^" + re.escape(pat) + "$", {"lang": "en"}, pat, "lang")

for pat in ("what language are you replying in", "which language are you replying in",
            "reply language", "what is your reply language"):
    add(f"lang.reply.show.{len(COMMANDS)}", "lang.reply",
        "^" + re.escape(pat) + "$", {"show": "1"}, pat, "lang")

REPLY_LANG = r"([A-Za-z\u00c0-\u024f\u0400-\u04ff\u0900-\u097f\u3040-\u30ff\u4e00-\u9fff]+)"
for pat in ("reply in {lang}", "respond in {lang}", "answer in {lang}",
            "speak {lang}", "talk to me in {lang}", "switch to {lang}",
            "use {lang} for replies", "reply language: {lang}"):
    add(f"lang.reply.set.{len(COMMANDS)}", "lang.reply",
        "^" + pat.replace("{lang}", REPLY_LANG) + "$",
        {"lang": "$1"}, pat, "lang")

# ---------------------------------------------------------------- build ---
BUILD_KINDS = ["calculator", "todo list", "todo", "task list", "timer", "countdown",
               "pomodoro", "stopwatch", "notes", "note pad", "notepad", "tic tac toe",
               "memory game", "unit converter", "converter", "chart", "graph",
               "dashboard", "landing page", "landing", "website", "web page", "page",
               "markdown editor", "markdown", "expense tracker", "expenses", "budget",
               "clock", "game", "app", "program", "tool",
               "rpg", "rpg game", "role playing game", "platformer", "snake",
               "snake game", "breakout", "pong", "2048", "minesweeper", "tetris",
               "maze", "maze game", "adventure game", "text adventure",
               "shooter", "top-down shooter", "twin-stick shooter", "wave shooter",
               "shmup", "bullet hell", "racer", "racing game", "racing",
               "kart racer", "kart game", "roguelike", "roguelike game",
               "dungeon crawler", "tower defense", "tower defense game",
               "farming sim", "farming game", "exploration game",
               "twin-stick", "merge puzzle", "merge game", "match-3 puzzle",
               "match 3 puzzle", "card battler", "deck builder", "rhythm game",
               "rhythm", "low-poly exploration", "low poly exploration",
               "block builder", "voxel builder",
               "3d platformer", "3d rpg", "3d maze", "3d snake", "3d breakout",
               "isometric rpg", "isometric platformer", "top-down rpg",
               "first-person maze", "third-person platformer",
               "2d platformer", "2d rpg", "2d shooter",
               "typing test", "typing game", "social media website", "social network",
               "social feed", "blog", "blog website", "forum", "forum website",
               "chat app", "chat website", "chat page"]
for kind in BUILD_KINDS:
    for pat in ("build a {k} app", "build {k} app", "make a {k} app", "create a {k} app",
                "build me a {k}", "build a {k}", "make a {k}", "create a {k}",
                "build an {k}", "make an {k}", "create an {k}", "build me an {k}",
                "build a {k} website", "make a {k} website", "build a {k} page",
                "build a {k} game", "create a {k} game", "build me a {k} game",
                "make a {k} game", "build an {k} game"):
        add(f"build.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}", "build",
            "^" + pat.replace("{k}", re.escape(kind)) + "$",
            {"kind": kind}, pat, "build")

# A request can carry a modifier ("with 3d elements", "based on king arthur").
# Keep the kind explicit and pass the modifier as the description so the
# template picks a deterministic variant instead of falling back to chat.
for kind in BUILD_KINDS:
    for pat in ("build a {k} with {d}", "build an {k} with {d}",
                "make a {k} with {d}", "create a {k} with {d}",
                "build a {k} that has {d}", "build an {k} that has {d}",
                "build a {k} based on {d}", "build an {k} based on {d}",
                "build a {k} set in {d}", "build an {k} set in {d}",
                "build a {k} game with {d}", "build an {k} game with {d}",
                "build a {k} game based on {d}", "build an {k} game based on {d}"):
        add(f"build.variant.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}", "build",
            "^" + pat.replace("{k}", re.escape(kind)).replace("{d}", REST) + "$",
            {"kind": kind, "desc": "$1"}, pat, "build")

# Explicit seed: `build a platformer seed 42` replays an exact world.
SEED = r"(\d{1,10})"
for kind in BUILD_KINDS:
    for pat in ("build a {k} seed {n}", "build an {k} seed {n}",
                "build a {k} game seed {n}", "build an {k} game seed {n}",
                "make a {k} seed {n}", "make a {k} game seed {n}"):
        add(f"build.seed.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}", "build",
            "^" + pat.replace("{k}", re.escape(kind)).replace("{n}", SEED) + "$",
            {"kind": kind, "desc": "seed $1"}, pat, "build")

# Dimension prefixes: `build a 3d platformer`, `build an isometric rpg`.
for dim in ("2d", "3d", "isometric", "top-down", "first-person", "third-person"):
    for kind in ("rpg", "platformer", "shooter", "maze", "racer", "snake",
                 "breakout", "pong", "tetris", "roguelike", "tower defense",
                 "wave shooter", "merge puzzle", "farming sim", "card battler",
                 "rhythm", "low-poly exploration", "block builder"):
        for pat in ("build a {dim} {k} game", "build an {dim} {k} game",
                    "make a {dim} {k} game", "build a {dim} {k}"):
            add(f"build.dim.{dim}.{kind}.{len(COMMANDS)}", "build",
                "^" + pat.replace("{dim}", re.escape(dim)).replace("{k}", re.escape(kind)) + "$",
                {"kind": kind, "desc": dim}, pat, "build")

# --------------------------------------- compositional build phrasing ---
# Step 28: keep kind, sub-genre, scale, theme, and feature separate so a long
# request lands on a specific build instead of the free-form fallback. These
# patterns are literal (not `(.+)`) because the vocabulary is finite; that is
# what makes the expansion predictable and cheap to match.
BUILD_GENRES = [
    "rpg", "platformer", "shooter", "maze", "racer", "snake", "breakout",
    "pong", "tetris", "roguelike", "tower defense", "wave shooter",
    "merge puzzle", "farming sim", "card battler", "rhythm", "block builder",
    "adventure", "dungeon crawler", "kart racer", "typing", "exploration",
    "match-3 puzzle", "2048",
]
BUILD_THEMES = [
    "space", "pirate", "cyberpunk", "medieval", "noir", "underwater", "desert",
    "arctic", "jungle", "haunted", "steampunk", "solarpunk", "post-apocalyptic",
    "cozy", "dark fantasy", "neon", "pixel art", "ancient egypt", "greek myth",
    "wild west", "feudal japan", "ocean", "volcanic", "fungal", "sky islands",
    "clockwork", "dream", "plague", "archipelago", "verdant", "astral",
]
BUILD_FEATURES = [
    "crafting", "survival", "stealth", "puzzles", "boss fights", "quests",
    "inventory", "day night cycle", "weather", "leaderboard", "save slots",
    "achievements", "procedural maps", "dialogue trees", "shops", "companions",
    "base building", "skill trees", "permadeath", "physics", "particles",
    "sound", "mobile controls", "difficulty levels",
]
BUILD_SCALES = [
    "small", "tiny", "big", "large", "huge", "epic", "minimal", "full",
    "compact", "sprawling", "multi-level", "three-level", "five-level", "endless",
]

# Most specific first: scale + theme + kind + feature.
for scale in ("small", "epic"):
    for theme in ("space", "cyberpunk", "medieval"):
        for feature in ("crafting", "survival", "quests", "boss fights",
                        "day night cycle"):
            for kind in BUILD_GENRES:
                pat = ("build a {s} {t} {k} game with {f}"
                       .replace("{s}", scale).replace("{t}", theme)
                       .replace("{k}", kind).replace("{f}", feature))
                add(f"build.compose.full.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}",
                    "build", "^" + re.escape(pat) + "$",
                    {"kind": kind, "desc": f"{scale} {theme} with {feature}"},
                    pat, "build")

# Theme + kind.
for theme in BUILD_THEMES:
    for kind in BUILD_GENRES:
        for pat in ("build a {t} {k} game", "make a {t} {k} game",
                    "build a {t} {k}"):
            text = (pat.replace("{t}", theme).replace("{k}", kind))
            add(f"build.compose.theme.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}",
                "build", "^" + re.escape(text) + "$",
                {"kind": kind, "desc": theme}, text, "build")

# Kind + feature.
for feature in BUILD_FEATURES:
    for kind in BUILD_GENRES:
        for pat in ("build a {k} game with {f}", "build a {k} with {f}"):
            text = pat.replace("{k}", kind).replace("{f}", feature)
            add(f"build.compose.feature.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}",
                "build", "^" + re.escape(text) + "$",
                {"kind": kind, "desc": feature}, text, "build")

# Scale + kind.
for scale in BUILD_SCALES:
    for kind in BUILD_GENRES:
        for pat in ("build a {s} {k} game", "build a {s} {k}"):
            text = pat.replace("{s}", scale).replace("{k}", kind)
            add(f"build.compose.scale.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}",
                "build", "^" + re.escape(text) + "$",
                {"kind": kind, "desc": scale}, text, "build")

# Long modifier tails: any number of scale/theme words before the genre plus a
# feature after it. This is one pattern per genre instead of the full cross
# product, so the tail can grow without multiplying the library.
_MODS = "|".join(re.escape(x) for x in
                 sorted(set(BUILD_SCALES + BUILD_THEMES),
                        key=lambda word: (-len(word), word)))
_CONNECTORS = r"(?:with|that has|based on|set in|featuring)"
for kind in BUILD_GENRES:
    rx = (r"^build an? ((?:(?:" + _MODS + r") )*)" + re.escape(kind)
          + r"(?= game\b| " + _CONNECTORS + r"\b|$)(?: game)?"
          + r"(?: " + _CONNECTORS + r" (.+))?$")
    add(f"build.compose.tail.{re.sub(r'[^a-z0-9]+', '-', kind)}.{len(COMMANDS)}",
        "build", rx, {"kind": kind, "desc": "$1$2"},
        "build a <modifiers> " + kind + " game with <feature>", "build")

# --------------------------------------------------------- web → build ---
# A web lookup feeds `prev`; these patterns turn that text into a real
# research page project. Pronoun forms must come before the {topic} forms.
for pat in ("build a page about it", "build a page about that", "build a page about this",
            "build a webpage about it", "build a web page about it",
            "make a page about it", "make a page about that",
            "make a webpage about it", "make a web page about it",
            "build an article about it", "build an article about that",
            "make an article about it", "make an article about that",
            "build a website about it", "make a website about it",
            "turn it into a page", "turn that into a page",
            "turn it into an article", "turn that into an article",
            "build a page from it", "build a page from that",
            "make a page from it", "make a page from that"):
    add(f"build.web.prev.{len(COMMANDS)}", "build.web",
        "^" + re.escape(pat) + "$", {}, pat, "build")

for pat in ("build a page about {topic}", "build a webpage about {topic}",
            "build a web page about {topic}", "make a page about {topic}",
            "make a webpage about {topic}", "make a web page about {topic}",
            "build an article about {topic}", "make an article about {topic}",
            "build a website about {topic}", "make a website about {topic}",
            "turn {topic} into a page", "turn {topic} into an article"):
    add(f"build.web.topic.{len(COMMANDS)}", "build.web",
        "^" + pat.replace("{topic}", REST) + "$", {"topic": "$1"}, pat, "build")

for pat in ("build a program that {desc}", "build a site that {desc}",
            "make an app that {desc}", "build me a program that {desc}",
            "make a program that {desc}", "build {desc}"):
    add(f"build.free.{len(COMMANDS)}", "build",
        "^" + pat.replace("{desc}", REST) + "$", {"desc": "$1"}, pat, "build")

# ------------------------------------------------------------- projects ---
for pat in ("new project {name}", "new project called {name}", "create a project called {name}",
            "create a new project {name}", "create a project named {name}",
            "start a project called {name}", "start a new project {name}"):
    add(f"project.new.{len(COMMANDS)}", "project.new",
        "^" + pat.replace("{name}", REST) + "$", {"name": "$1"}, pat, "project")

for pat in ("list projects", "show projects", "show my projects", "projects",
            "list my projects", "what projects do i have"):
    add(f"project.list.{len(COMMANDS)}", "project.list", "^" + re.escape(pat) + "$",
        {}, pat, "project")

for pat in ("open project {slug}", "open the project {slug}", "switch to project {slug}",
            "switch to the project {slug}", "load project {slug}"):
    add(f"project.open.{len(COMMANDS)}", "project.open",
        "^" + pat.replace("{slug}", REST) + "$", {"slug": "$1"}, pat, "project")

for pat in ("delete project {slug}", "delete the project {slug}", "remove project {slug}",
            "erase project {slug}", "remove the project {slug}"):
    add(f"project.delete.{len(COMMANDS)}", "project.delete",
        "^" + pat.replace("{slug}", REST) + "$", {"slug": "$1"}, pat, "project")
for pat in ("delete this project", "delete the active project", "erase this project",
            "remove this project"):
    add(f"project.delete.active.{len(COMMANDS)}", "project.delete",
        "^" + re.escape(pat) + "$", {}, pat, "project")

for pat in ("rename project {slug} to {name}", "rename the project {slug} to {name}",
            "change the name from {slug} to {name}",
            "change the name of {slug} to {name}",
            "change the name of the project {slug} to {name}",
            "rename {slug} to {name}"):
    add(f"project.rename.{len(COMMANDS)}", "project.rename",
        "^" + pat.replace("{slug}", REST).replace("{name}", REST) + "$",
        {"slug": "$1", "name": "$2"}, pat, "project")

for pat in ("change the project name to {name}", "change the name to {name}",
            "rename this project to {name}", "rename the project to {name}",
            "rename it to {name}", "call this project {name}",
            "call the project {name}", "call it {name}", "name it {name}",
            "name this project {name}", "set the project name to {name}",
            "set this project name to {name}"):
    add(f"project.rename.active.{len(COMMANDS)}", "project.rename",
        "^" + pat.replace("{name}", REST) + "$",
        {"name": "$1"}, pat, "project")

for pat in ("show project files", "list project files", "project files",
            "show the files in this project", "show the files in the project",
            "what files are in this project"):
    add(f"project.files.{len(COMMANDS)}", "project.files", "^" + re.escape(pat) + "$",
        {}, pat, "project")
add("project.files.slug", "project.files", r"^(?:show|list)\s+(?:the\s+)?files\s+in\s+project\s+(.+)$",
    {"slug": "$1"}, "files in a project", "project")

# Project-aware edits: change the page itself, not the template source. These
# must stay ahead of broad build/chat patterns so "make this project light"
# edits the open page instead of starting a new build.
for pat in ("change the page title to {name}", "change the page title to say {name}",
            "set the page title to {name}", "set the page title to say {name}",
            "retitle the page to {name}", "retitle the page {name}",
            "make the page title {name}", "title the page {name}",
            "change this page title to {name}"):
    add(f"project.title.{len(COMMANDS)}", "project.title",
        "^" + pat.replace("{name}", REST) + "$", {"name": "$1"}, pat, "project")

for pat in ("add a theme toggle", "add a dark mode toggle", "add a light mode toggle",
            "add a theme switch", "add a light/dark toggle", "add a light dark toggle",
            "put a theme toggle on the page", "add theme switching",
            "add a toggle for the theme", "add a toggle to switch themes"):
    add(f"project.themeToggle.{len(COMMANDS)}", "project.themeToggle",
        "^" + re.escape(pat) + "$", {}, pat, "project")

for pat in ("make this project {t}", "make the project {t}",
            "switch this project to {t}", "switch the project to {t}",
            "set this project theme to {t}", "set the project theme to {t}",
            "use a {t} theme for this project", "use a {t} theme for the project",
            "make this page {t}", "switch this page to {t}"):
    add(f"project.theme.{len(COMMANDS)}", "project.theme",
        "^" + pat.replace("{t}", "(light|dark)") + "$", {"theme": "$1"}, pat, "project")

for pat in ("add a footer note saying {text}", "add a footer note that says {text}",
            "add a note in the footer saying {text}",
            "put a note in the footer saying {text}",
            "put a footer note saying {text}", "set the footer note to {text}",
            "set the footer note to say {text}", "add a footer that says {text}",
            "add a footer note {text}"):
    add(f"project.note.{len(COMMANDS)}", "project.note",
        "^" + pat.replace("{text}", REST) + "$", {"text": "$1"}, pat, "project")

# ------------------------------------------------------------- memory ----
# Conversation memory is explicit and inspectable: facts, notes, and the last
# build live in localStorage; nothing is inferred or sent anywhere.
for pat in ("remember that {key} is {value}", "remember {key} is {value}",
            "remember that my {key} is {value}", "remember my {key} is {value}",
            "remember {key} = {value}", "note that {key} is {value}",
            "keep in mind that {key} is {value}"):
    add(f"memory.remember.{len(COMMANDS)}", "memory.remember",
        "^" + pat.replace("{key}", r"(.+?)").replace("{value}", REST) + "$",
        {"key": "$1", "value": "$2"}, pat, "memory")

for pat in ("remember that {text}", "remember this: {text}", "make a note that {text}",
            "make a note: {text}", "note down that {text}", "note this: {text}"):
    add(f"memory.note.{len(COMMANDS)}", "memory.note",
        "^" + pat.replace("{text}", REST) + "$", {"text": "$1"}, pat, "memory")

add("memory.recall.what", "memory.recall",
    r"^(?:what(?:'s| is)|whats) my (?!name\b)(.+)$",
    {"key": "$1"}, "what is my {key}", "memory")
for pat in ("what do you remember about my {key}", "what do you remember about {key}",
            "what did i tell you about my {key}", "what did i tell you about {key}",
            "do you remember my {key}", "do you remember {key}"):
    add(f"memory.recall.{len(COMMANDS)}", "memory.recall",
        "^" + pat.replace("{key}", r"(.+?)") + "$", {"key": "$1"}, pat, "memory")

for pat in ("what do you remember", "what do you know about me", "show your memory",
            "list memory", "show memory", "what have you saved", "what have you remembered"):
    add(f"memory.list.{len(COMMANDS)}", "memory.list", "^" + re.escape(pat) + "$",
        {}, pat, "memory")

for pat in ("forget everything", "forget it all", "forget all of that",
            "clear your memory", "clear memory", "wipe your memory"):
    add(f"memory.forget.all.{len(COMMANDS)}", "memory.forget", "^" + re.escape(pat) + "$",
        {}, pat, "memory")
for pat in ("forget my {key}", "forget about my {key}", "forget about {key}",
            "forget {key}", "remove my {key} from memory"):
    add(f"memory.forget.{len(COMMANDS)}", "memory.forget",
        "^" + pat.replace("{key}", r"(.+?)") + "$", {"key": "$1"}, pat, "memory")

for pat in ("what was i working on", "what did i build last", "what is the active project",
            "what is my current project", "what am i building", "where was i",
            "show my current project", "what have i built"):
    add(f"memory.context.{len(COMMANDS)}", "memory.context",
        "^" + re.escape(pat) + "$", {}, pat, "memory")

# --------------------------------------------------------- architecture ---
for pat in ("plan a {kind}", "plan an {kind}", "plan {kind} app", "plan out a {kind}",
            "architect a {kind}", "architecture of a {kind}", "architecture for a {kind}",
            "show the architecture of a {kind}", "show the architecture of {kind}",
            "how do i build a {kind}", "how would you build a {kind}",
            "how do i build {kind}", "what is the architecture of a {kind}"):
    add(f"plan.{len(COMMANDS)}", "plan",
        "^" + pat.replace("{kind}", REST) + "$", {"kind": "$1"}, pat, "plan")

for pat in ("blueprint a {kind}", "blueprint for a {kind}", "blueprint for {kind}",
            "give me a blueprint for a {kind}", "blueprint of a {kind}"):
    add(f"blueprint.{len(COMMANDS)}", "blueprint",
        "^" + pat.replace("{kind}", REST) + "$", {"kind": "$1"}, pat, "plan")

# ------------------------------------------------------------- web data ---
for pat in ("wikipedia {q}", "search wikipedia for {q}", "look up {q} on wikipedia",
            "what does wikipedia say about {q}", "wiki {q}"):
    add(f"web.search.{len(COMMANDS)}", "web.search",
        "^" + pat.replace("{q}", REST) + "$", {"q": "$1"}, pat, "web")
for pat in ("search the web for {q}", "search for {q}", "search the internet for {q}",
            "look up {q}", "look {q} up", "google {q}"):
    add(f"web.search.free.{len(COMMANDS)}", "web.search",
        "^" + pat.replace("{q}", REST) + "$", {"q": "$1"}, pat, "web")
for pat in ("duckduckgo {q}", "instant answer for {q}", "quick answer for {q}"):
    add(f"web.answer.{len(COMMANDS)}", "web.answer",
        "^" + pat.replace("{q}", REST) + "$", {"q": "$1"}, pat, "web")
for pat in ("define {word}", "definition of {word}", "what does {word} mean",
            "what is the definition of {word}", "meaning of {word}"):
    add(f"web.define.{len(COMMANDS)}", "web.define",
        "^" + pat.replace("{word}", r"([a-zA-Z][a-zA-Z' -]{0,40})") + "$",
        {"word": "$1"}, pat, "web")
for pat in ("weather in {place}", "what's the weather in {place}", "what is the weather in {place}",
            "weather for {place}", "forecast for {place}"):
    add(f"web.weather.{len(COMMANDS)}", "web.weather",
        "^" + pat.replace("{place}", REST) + "$", {"place": "$1"}, pat, "web")
for pat in ("summarize it", "summarize that", "summarize this", "summarize the result",
            "summarize the text", "summary of it", "summary of that"):
    add(f"web.summary.prev.{len(COMMANDS)}", "text.summarize",
        "^" + re.escape(pat) + "$", {}, pat, "web")
add("web.summary.text", "text.summarize", r"^summarize\s+(?!it$|that$|this$)(.+)$",
    {"text": "$1"}, "summarize text", "web")

# ---------------------------------------------------------------- chat ----
CHAT_PATTERNS = {
    "g.reply": ["hi", "hello", "hey", "yo", "hiya", "hello there", "hey there",
                "good morning", "good afternoon", "good evening"],
    "thanks": ["thanks", "thank you", "thx", "i appreciate it", "appreciate it"],
    "how": ["how are you", "how's it going", "how are things"],
    "joke": ["tell me a joke", "make me laugh", "something funny", "say something funny"],
    "motivate": ["motivate me", "i need motivation", "pep talk", "encourage me"],
    "identity": ["who are you", "what are you", "tell me about yourself",
                 "are you real", "are you alive", "do you have feelings",
                 "are you sentient", "are you conscious"],
    "idea": ["what should i build", "what should i make", "give me an idea",
             "give me a project idea", "project idea"],
    "name": ["what is my name", "what's my name", "who am i", "do you remember my name"],
    "listen": ["i need help", "help me", "can you listen", "listen to me",
               "i need to talk", "can we talk"],
    "bye": ["bye", "goodbye", "see you", "later", "good night", "goodnight"],
}
for intent, pats in CHAT_PATTERNS.items():
    for pat in pats:
        add(f"chat.{intent}.{len(COMMANDS)}", "chat",
            "^" + re.escape(pat) + r"[.!?]?$", {}, pat, "chat")

for pat in (r"^i feel .+$", r"^i (?:am|'m) feeling .+$",
            r"^i (?:am|'m) (?:so |really |very |kind of |kinda )?(?:sad|anxious|angry|mad|stressed|tired|exhausted|lonely|scared|afraid|confused|lost|stuck|overwhelmed|burnt out|burned out|down|empty)$",
            r"^i (?:can'?t|cannot) focus$", r"^i can'?t cope$",
            r"^i (?:can'?t|cannot) sleep$", r"^i (?:can'?t|cannot) do this(?: anymore)?$",
            r"^i'?m stuck$", r"^i don'?t know (?:what to do|how to start)$"):
    add(f"chat.feel.{len(COMMANDS)}", "chat", pat, {}, "talk about a feeling", "chat")

for pat in ("remember my name is {name}", "my name is {name}", "call me {name}"):
    add(f"chat.name.{len(COMMANDS)}", "chat",
        "^" + pat.replace("{name}", REST) + "$", {}, pat, "chat")

add("chat.more", "chat", r"^(?:why|really|and|so)[.!?]?$", {}, "continue the conversation", "chat")

# ----------------------------------------------------------------- misc ---
for pat, op in (("who are you", "who"), ("what are you", "who"),
                ("what is your name", "who"), ("help", "help"),
                ("what can you do", "help"), ("commands", "help"),
                ("list commands", "help"), ("show commands", "help"),
                ("command library", "help")):
    add(f"misc.{op}.{len(COMMANDS)}", "system", "^" + re.escape(pat) + "$",
        {"op": op}, pat, "misc")

add("misc.help.topic", "system", r"^help\s+(.+)$", {"op": "help", "topic": "$1"},
    "help on a topic", "misc")
add("misc.preview", "preview", r"^(?:show|open|display)\s+(?:the\s+)?preview$", {},
    "show the preview pane", "misc")
add("misc.theme.dark", "preview.theme", r"^(?:make it dark|use a dark theme|dark mode)$",
    {"theme": "dark"}, "dark theme", "misc")
add("misc.theme.light", "preview.theme", r"^(?:make it light|use a light theme|light mode)$",
    {"theme": "light"}, "light theme", "misc")
for pat in ("echo {text}", "say {text}"):
    add(f"misc.echo.{len(COMMANDS)}", "echo", "^" + pat.replace("{text}", REST) + "$",
        {"text": "$1"}, pat, "misc")


def main():
    cats = {}
    for c in COMMANDS:
        cats[c["c"]] = cats.get(c["c"], 0) + 1
    payload = {
        "version": 1,
        "count": len(COMMANDS),
        "categories": cats,
        "library": LIBRARY,
        "commands": COMMANDS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    print(f"{len(COMMANDS)} commands, {len(_DUPLICATES)} duplicate pattern(s) skipped")
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"  {k:10} {v}")


if __name__ == "__main__":
    main()
