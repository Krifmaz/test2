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
# Loads and models the full command set from doc/commands.json so every
# client command gets a GUI form. Nothing is hand-maintained here: the list
# tracks whatever the client shipped alongside this checkout.
#-----------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional


# A single parsed option/flag of a command, e.g. "-f, --file <fn> filename".
@dataclass
class Option:
    short: Optional[str]          # "-f"  (or None)
    long: Optional[str]           # "--file" (or None)
    takes_value: bool             # True when the flag expects an argument
    placeholder: str              # "<fn>" / "<hex>" / "" for switches
    help: str
    optional: bool                # help text advertised it as optional

    @property
    def flag(self) -> str:
        # Prefer the long form on the command line; it is the stable spelling.
        return self.long or self.short or ""

    @property
    def label(self) -> str:
        parts = [p for p in (self.short, self.long) if p]
        return ", ".join(parts) if parts else self.placeholder


# One client command, e.g. "hf 14a reader", with its parsed metadata.
@dataclass
class Command:
    name: str                     # "hf 14a reader"
    description: str
    usage: str
    offline: bool
    notes: list = field(default_factory=list)
    options: list = field(default_factory=list)

    @property
    def group(self) -> str:
        return self.name.split(" ", 1)[0] if self.name else ""

    @property
    def leaf(self) -> str:
        return self.name.rsplit(" ", 1)[-1] if self.name else ""


# Matches the leading flags of an option line: "-f, --file", "--ns", "-@".
# The short form is a single dash + one non-dash char, so it never swallows
# the "--" of a long-only flag.
_FLAGS_RE = re.compile(
    r"^\s*(?:(-[^-\s])\s*,?\s*)?(?:(--[A-Za-z0-9][\w-]*))?"
)
_PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def parse_option(line: str) -> Optional[Option]:
    """Turn a raw option help line into an Option, or None if unparsable."""
    raw = line.strip()
    if not raw:
        return None

    m = _FLAGS_RE.match(raw)
    short = m.group(1) if m else None
    long = m.group(2) if m else None

    # A bare short switch like "-@" has no long form; grab it explicitly.
    if short is None and long is None:
        m2 = re.match(r"^(-\S)", raw)
        if not m2:
            return None
        short = m2.group(1)

    rest = raw[m.end():].strip() if m else raw
    ph = _PLACEHOLDER_RE.search(rest)
    placeholder = ph.group(0) if ph else ""
    takes_value = bool(placeholder)
    if placeholder:
        rest = rest.replace(placeholder, "", 1).strip()

    optional = "optional" in rest.lower() or "(optional)" in line.lower()
    return Option(
        short=short,
        long=long,
        takes_value=takes_value,
        placeholder=placeholder,
        help=rest,
        optional=optional,
    )


def _parse_command(name: str, blob: dict) -> Command:
    opts = []
    for raw in blob.get("options", []) or []:
        o = parse_option(raw)
        # Skip the ubiquitous -h/--help switch; the GUI has its own help pane.
        if o and o.long == "--help":
            continue
        if o:
            opts.append(o)
    return Command(
        name=name,
        description=(blob.get("description") or "").strip(),
        usage=(blob.get("usage") or "").strip(),
        offline=bool(blob.get("offline", False)),
        notes=list(blob.get("notes", []) or []),
        options=opts,
    )


def default_commands_json() -> Optional[str]:
    """Best-effort locate doc/commands.json relative to this checkout."""
    here = os.path.dirname(os.path.abspath(__file__))
    # client/gui/pm3gui/ -> repo root is three levels up.
    candidates = [
        os.path.join(here, "..", "..", "..", "doc", "commands.json"),
        os.path.join(here, "..", "..", "doc", "commands.json"),
    ]
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.isfile(c):
            return c
    return None


class CommandSet:
    """The full parsed command catalogue, plus a group/sub-group tree."""

    def __init__(self, commands: list):
        self.commands = commands
        self.by_name = {c.name: c for c in commands}

    @classmethod
    def load(cls, path: Optional[str] = None) -> "CommandSet":
        path = path or default_commands_json()
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(
                "commands.json not found. Pass --commands /path/to/commands.json"
            )
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        cmds = [_parse_command(name, blob)
                for name, blob in sorted(data.get("commands", {}).items())]
        return cls(cmds)

    @property
    def metadata(self) -> dict:
        return {}

    def tree(self) -> dict:
        """Nested dict keyed by command word, leaves hold a Command.

        {"hf": {"14a": {"reader": Command(...), ...}, ...}, ...}
        """
        root: dict = {}
        for c in self.commands:
            parts = c.name.split(" ")
            node = root
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = c
        return root

    def search(self, needle: str) -> list:
        needle = needle.strip().lower()
        if not needle:
            return list(self.commands)
        out = []
        for c in self.commands:
            if needle in c.name.lower() or needle in c.description.lower():
                out.append(c)
        return out
