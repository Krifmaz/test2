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
# Turn `lf search` output into a clone command for the Easy mode tab.
#
# Each recognizer is anchored on the client's authoritative "Valid <X> ID
# found!" line (cmdlf.c), then pulls the fields its `lf <t> clone` needs from
# that type's demod line. Pure text in, command out: no Qt, no device, so it
# is unit-tested offline in tools/smoke_test.py.
#-----------------------------------------------------------------------------

from __future__ import annotations

import re
from collections import namedtuple

# label:   human name of the card type
# command: client command that writes it to a blank T5577, or "" if the type
#          is recognised but we can't safely build a clone for it
# note:    short caveat shown under the command, or ""
Match = namedtuple("Match", "label command note")

READ_COMMAND = "lf search"


def _hexstrip(h: str) -> str:
    """Drop leading zeros the way the client's own clone examples are written."""
    h = h.lstrip("0")
    return h or "0"


# -- per-type field extractors -------------------------------------------------
# Each takes the full search output and returns the clone command, or "" if the
# marker was present but the detail line could not be parsed.

def _em410x(out):
    m = re.search(r"EM 410x ID\s+([0-9A-Fa-f]{10})", out)
    return "lf em 410x clone --id %s" % m.group(1).upper() if m else ""


def _hid(out):
    m = re.search(r"\braw:\s*([0-9A-Fa-f]{6,})", out)
    return "lf hid clone -r %s" % _hexstrip(m.group(1)) if m else ""


def _awid(out):
    m = re.search(r"AWID - len:\s*(\d+)\s+FC:\s*(\d+)\s+Card:\s*(\d+)", out)
    return ("lf awid clone --fmt %s --fc %s --cn %s"
            % (m.group(1), m.group(2), m.group(3))) if m else ""


def _io(out):
    m = re.search(r"XSF\((\d+)\)([0-9A-Fa-f]+):(\d+)", out)
    if not m:
        return ""
    return ("lf io clone --vn %d --fc %d --cn %d"
            % (int(m.group(1)), int(m.group(2), 16), int(m.group(3))))


def _indala(out):
    m = re.search(r"Indala \(len \d+\)\s+Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf indala clone -r %s" % m.group(1) if m else ""


def _paradox(out):
    m = re.search(r"Paradox -.*Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf paradox clone -r %s" % m.group(1) if m else ""


def _viking(out):
    m = re.search(r"Viking - Card\s+([0-9A-Fa-f]+)", out)
    return "lf viking clone --cn %s" % m.group(1) if m else ""


def _pyramid(out):
    m = re.search(r"Pyramid - len:\s*\d+,?\s*FC:\s*(\d+)\s+Card:\s*(\d+)", out)
    return ("lf pyramid clone --fc %s --cn %s"
            % (m.group(1), m.group(2))) if m else ""


def _pac(out):
    m = re.search(r"PAC/Stanley -.*Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf pac clone -r %s" % m.group(1) if m else ""


def _visa2000(out):
    m = re.search(r"Visa2000 - Card\s+(\d+)", out)
    return "lf visa2000 clone --cn %s" % m.group(1) if m else ""


def _securakey(out):
    m = re.search(r"Securakey -.*Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf securakey clone -r %s" % m.group(1) if m else ""


def _idteck(out):
    m = re.search(r"IDTECK Tag Found:.*Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf idteck clone -r %s" % m.group(1) if m else ""


def _motorola(out):
    m = re.search(r"Motorola -.*Raw:\s*([0-9A-Fa-f]+)", out)
    return "lf motorola clone -r %s" % m.group(1) if m else ""


def _nexwatch(out):
    m = re.search(r"\bRaw\s*:\s*([0-9A-Fa-f]{24})", out)
    return "lf nexwatch clone -r %s" % m.group(1) if m else ""


def _gallagher(out):
    m = re.search(r"\bRaw:\s*([0-9A-Fa-f]{24})", out)
    return "lf gallagher clone -r %s" % m.group(1) if m else ""


def _noralsy(out):
    m = re.search(r"Noralsy - Card:\s*(\d+),\s*Year:\s*(\d+)", out)
    return ("lf noralsy clone --cn %s -y %s"
            % (m.group(1), m.group(2))) if m else ""


def _jablotron(out):
    m = re.search(r"Jablotron - Card:\s*([0-9A-Fa-f]+)", out)
    return "lf jablotron clone --cn %s" % m.group(1) if m else ""


# marker -> (human label, extractor). The marker is the client's green text in
# "Valid <marker> found!"; order is only for stable output.
_RECOGNIZERS = [
    ("EM410x ID",               "EM410x",              _em410x),
    ("HID Prox ID",             "HID Prox",            _hid),
    ("AWID ID",                 "AWID",                _awid),
    ("IO Prox ID",              "IO Prox",             _io),
    ("Indala ID",               "Indala",              _indala),
    ("Paradox ID",              "Paradox",             _paradox),
    ("Viking ID",               "Viking",              _viking),
    ("Pyramid ID",              "Farpointe/Pyramid",   _pyramid),
    ("PAC/Stanley ID",          "PAC/Stanley",         _pac),
    ("Visa2000 ID",             "Visa2000",            _visa2000),
    ("Securakey ID",            "Securakey",           _securakey),
    ("Idteck ID",               "Idteck",              _idteck),
    ("Motorola FlexPass ID",    "Motorola FlexPass",   _motorola),
    ("NexWatch ID",             "NexWatch",            _nexwatch),
    ("GALLAGHER ID",            "Gallagher",           _gallagher),
    ("Noralsy ID",              "Noralsy",             _noralsy),
    ("Jablotron ID",            "Jablotron",           _jablotron),
]

# Types a search can name that Easy mode identifies but deliberately won't
# auto-clone (scrambled/ambiguous fields, no stable single-card T5577 clone).
_IDENTIFY_ONLY = {
    "KERI ID": "KERI",
    "FDX-B ID": "FDX-B",
    "FDX-A FECAVA Destron ID": "Destron",
    "NEDAP ID": "NEDAP",
    "Guardall G-Prox II ID": "G-Prox II",
    "Presco ID": "Presco",
    "Texas Instrument ID": "Texas Instrument",
    "Trovan ID": "Trovan",
    "COTAG ID": "COTAG",
    "EM4x50 ID": "EM4x50",
    "Fermax ID": "Fermax",
    "Paxton ID": "Paxton",
}


def is_blank_t55xx(out: str) -> bool:
    """True when a search found no credential but the chip is a writable T55xx."""
    return ("No known" in out and "Chipset" in out and "T55" in out)


# How the client names each writable target on its "Chipset..." summary line,
# and the human label / clone flag that goes with it.
_TARGETS = [
    ("em4x05", ("EM4x05", "EM4x69"), "EM4305/4469", "--em"),
    ("t5577",  ("T55",),             "T5577",       ""),
]


def target_chip(out: str) -> str:
    """Writable target on the antenna, from the search "Chipset..." line.

    Returns "t5577", "em4x05", or "" when it isn't a chip Easy mode can write.
    """
    m = re.search(r"Chipset[^\n]*", out or "")
    line = m.group(0) if m else ""
    for key, needles, _label, _flag in _TARGETS:
        if any(n in line for n in needles):
            return key
    return ""


def target_label(chip: str) -> str:
    for key, _needles, label, _flag in _TARGETS:
        if key == chip:
            return label
    return chip


def apply_target(command: str, chip: str) -> str:
    """Point a T5577-default clone command at the detected chip."""
    for key, _needles, _label, flag in _TARGETS:
        if key == chip and flag and flag not in command.split():
            return command + " " + flag
    return command


def detect(out: str) -> list:
    """Clonable/identified card types found in `lf search` output, best first.

    Returns Match(label, command, note). command=="" means identified but not
    auto-clonable here. An empty list means nothing was recognised.
    """
    out = out or ""
    found = []
    for marker, label, extract in _RECOGNIZERS:
        if ("Valid " + marker + " found") in out:
            cmd = extract(out)
            note = "" if cmd else "Detected, but the ID could not be read cleanly — rescan the card."
            found.append(Match(label, cmd, note))
    for marker, label in _IDENTIFY_ONLY.items():
        if ("Valid " + marker + " found") in out:
            found.append(Match(
                label, "",
                "Identified, but Easy mode doesn't auto-clone this type. "
                "Use the `%s` commands." % _group_hint(label)))
    return found


# -- HF (13.56 MHz) identification --------------------------------------------
# Easy mode identifies HF cards and reports their security, but does not
# auto-clone them: HF copying needs key recovery and a "magic" card, is
# card-specific, and a wrong write bricks the tag. Each entry is matched as a
# substring of `hf search` output; specific chips come before their family.
# clone: "" = identify only, "mfc" = MIFARE Classic family (keys + magic card),
# "mfu" = Ultralight/NTAG family (dump + magic card).
HF_INFO = namedtuple("HF_INFO", "label security advice clone")

_HF_CHECKS = [
    ("MIFARE DESFire", "strong",
     "AES/3DES with per-app keys. Not copyable by reading — needs the keys.",
     ""),
    ("MIFARE Plus",    "strong",
     "AES in SL3. Not copyable without the keys.", ""),
    ("MIFARE DUOX",    "strong",
     "AES/ECC. Not copyable without the keys.", ""),
    ("MIFARE Hospitality", "strong",
     "Keyed. Not copyable without the keys.", ""),
    ("NTAG",           "none/password",
     "Usually no crypto (may have a password). Copyable onto a magic NTAG.",
     "mfu"),
    ("MIFARE Ultralight", "none/password",
     "Little or no crypto (UL-C/EV1 may use a password). Copyable onto a "
     "magic Ultralight.", "mfu"),
    ("MIFARE Mini",    "weak",
     "Crypto1 (broken). Keys are recovered, then written to a magic MIFARE "
     "card.", "mfc"),
    ("MIFARE Classic", "weak",
     "Crypto1, broken. Keys are recovered, then written to a magic MIFARE "
     "card.", "mfc"),
    ("iCLASS",         "varies",
     "Legacy iCLASS is weak (keys often recoverable); iCLASS SE/SEOS is "
     "strong. Check with `hf iclass info`.", ""),
    ("PicoPass",       "varies",
     "Check with `hf iclass info`; legacy is weak, SE/SEOS is strong.", ""),
    ("ISO 15693",      "varies",
     "Vicinity card (e.g. ICODE). Many have no crypto and are readable; some "
     "variants add crypto. Try `hf 15 info`.", ""),
    ("FeliCa",         "strong",
     "Used in transit/payment. Not copyable without keys.", ""),
    ("LEGIC Prime",    "weak",
     "Legacy, weak. Potentially copyable — see the `hf legic` commands.", ""),
    ("Topaz",          "none",
     "NFC Type 1, typically open. Read with `hf topaz info`.", ""),
    ("ISO 14443-B",    "varies",
     "14443-B family (often passports/banking). Identify further with "
     "`hf 14b info` before judging.", ""),
    ("ISO 14443-A",    "varies",
     "14443-A, exact chip not pinned down. Try `hf 14a info`.", ""),
]

# Per-family HF copy: read-only dump of the source, then a write from that dump
# to a magic card. restore accepts the dump file the dump step saves.
_HF_PLANS = {
    "mfc": ("hf mf autopwn",  "hf mf restore -f %s"),
    "mfu": ("hf mfu dump",    "hf mfu restore -f %s"),
}


def detect_hf(out: str):
    """Identify an HF card from `hf search` output as an HF_INFO, or None."""
    out = out or ""
    for needle, security, advice, clone_family in _HF_CHECKS:
        if needle in out:
            return HF_INFO(_hf_label(out, needle), security, advice,
                           clone_family)
    return None


def hf_dump_cmd(family: str) -> str:
    return _HF_PLANS.get(family, ("", ""))[0]


def magic_gen(info_out: str) -> str:
    """Magic generation: gen1a, gen2, or '' (not magic).

    Reads `hf mf info`'s explicit "Magic capabilities... Gen 1a/Gen 2" line,
    and also the `hf 14a info` hints (`hf mf c*` = gen1a) as a fallback. gen1a
    wins when a card reports both, since its backdoor writes block 0/UID.
    """
    out = info_out or ""
    if "Gen 1a" in out or "hf mf c*" in out:
        return "gen1a"
    if "Gen 2" in out or "Use `hf mf` commands" in out:
        return "gen2"
    return ""


def magic_write_cmd(family: str, info_out: str, dump_file: str) -> str:
    """Command to write a dump to the magic target, or '' if it isn't magic.

    gen1a MIFARE loads through the backdoor (cload); gen2/CUID writes with keys
    (restore). Magic Ultralight/NTAG uses mfu restore.
    """
    if family == "mfu":
        return "hf mfu restore -f %s" % dump_file
    if family == "mfc":
        gen = magic_gen(info_out)
        if gen == "gen1a":
            return "hf mf cload -f %s" % dump_file
        if gen == "gen2":
            return "hf mf restore -f %s" % dump_file
    return ""


def saved_file(out: str) -> str:
    """Path of a dump the client just saved, preferring the JSON dump."""
    j = re.search(r"Saved to json file\s+(\S+)", out or "")
    if j:
        return j.group(1)
    b = re.search(r"Saved .*? to binary file\s+`([^`]+)`", out or "")
    return b.group(1) if b else ""


def _hf_label(out: str, needle: str) -> str:
    """The client's own type phrase for a match, e.g. 'MIFARE Classic 1K'."""
    m = re.search(r"([A-Za-z0-9/()\- ]*" + re.escape(needle)
                  + r"[A-Za-z0-9/()\- ]*)", out)
    return m.group(1).strip() if m else needle


def _group_hint(label: str) -> str:
    hints = {
        "KERI": "lf keri", "FDX-B": "lf fdxb", "Destron": "lf destron",
        "NEDAP": "lf nedap", "G-Prox II": "lf gproxii", "Presco": "lf presco",
        "Trovan": "lf trovan", "EM4x50": "lf em 4x50",
    }
    return hints.get(label, "lf")
