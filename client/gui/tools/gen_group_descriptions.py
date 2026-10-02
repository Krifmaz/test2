#!/usr/bin/env python3
#-----------------------------------------------------------------------------
# Copyright (C) Proxmark3 contributors. See AUTHORS.md for details.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# See LICENSE.txt for the text of the license.
#-----------------------------------------------------------------------------
# Regenerates pm3gui/group_descriptions.json from the client's command_t
# tables, so command groups ("hf 14a", "lf em") get the same one-line help
# the client's own "help" listing shows.
# Usage: python3 tools/gen_group_descriptions.py
#-----------------------------------------------------------------------------

import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "src"))
OUT = os.path.normpath(os.path.join(HERE, "..", "pm3gui", "group_descriptions.json"))

TABLE_RE = re.compile(r"static\s+command_t\s+(\w+)\s*\[\]\s*=\s*\{(.*?)\n\};", re.S)
ENTRY_RE = re.compile(r'\{\s*"([^"]+)"\s*,\s*(\w+)\s*,\s*[^,]+,\s*"((?:[^"\\]|\\.)*)"\s*\}')
FUNC_RE = re.compile(r"^(?:static\s+)?int\s+(\w+)\s*\(\s*const\s+char\s*\*\s*\w+\s*\)\s*\{", re.M)
PARSE_RE = re.compile(r"CmdsParse\(\s*(\w+)\s*,")
CALL_RE = re.compile(r"\b(Cmd\w+)\(\s*Cmd\s*\)")


def clean(desc):
    # "{ ISO14443A RFIDs...   }" -> "ISO14443A RFIDs"
    d = desc.strip().strip("{}").strip()
    return re.sub(r"\s*\.\.\.\s*$", "", d).strip()


def main():
    tables = {}      # (file, table) -> [(name, handler, desc)]
    handlers = {}    # handler fn -> (file, table) it dispatches to
    delegates = {}   # wrapper fn -> handler it forwards to, e.g. CmdPref
    for path in glob.glob(os.path.join(SRC, "**", "*.c"), recursive=True):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        f = os.path.relpath(path, SRC)
        for m in TABLE_RE.finditer(text):
            tables[(f, m.group(1))] = ENTRY_RE.findall(m.group(2))
        funcs = list(FUNC_RE.finditer(text))
        for i, m in enumerate(funcs):
            end = funcs[i + 1].start() if i + 1 < len(funcs) else len(text)
            p = PARSE_RE.search(text, m.end(), end)
            if p:
                handlers.setdefault(m.group(1), (f, p.group(1)))
            else:
                c = CALL_RE.search(text, m.end(), end)
                if c:
                    delegates.setdefault(m.group(1), c.group(1))

    for fn, target in delegates.items():
        if fn not in handlers and target in handlers:
            handlers[fn] = handlers[target]

    out = {}

    def walk(key, prefix, seen):
        if key in seen or key not in tables:
            return
        seen = seen | {key}
        for name, handler, desc in tables[key]:
            if name in ("help", "-------------") or not desc.lstrip().startswith("{"):
                continue
            path = (prefix + " " + name).strip()
            out[path] = clean(desc)
            if handler in handlers:
                walk(handlers[handler], path, seen)

    walk(("cmdmain.c", "CommandTable"), "", frozenset())
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(out.items())), fh, indent=1)
        fh.write("\n")
    print("wrote %d group descriptions to %s" % (len(out), OUT))


if __name__ == "__main__":
    main()
