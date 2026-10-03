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
# Easy mode: a guided read -> identify -> copy -> verify flow.
#
# LF 125 kHz access cards clone onto a blank T5577/EM4305. HF 13.56 MHz cards
# that can be copied (MIFARE Classic, Ultralight/NTAG) are dumped and then
# written to a magic card. The card recognition lives in pm3gui.clone so it
# can be tested without a device.
#-----------------------------------------------------------------------------

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .. import clone

_FAMILY_NAME = {"mfc": "MIFARE", "mfu": "NTAG / Ultralight"}


class EasyMode(QWidget):
    """Guided card copying.

    Emits run_requested(command) for the main window to execute; receives each
    finished command through command_finished() to advance the flow.
    """

    run_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._mode = "read"          # read | target | verify
        self._copy_kind = ""         # "lf" or "hf": which verify to run
        # LF
        self._clone_cmd = ""         # LF command that writes the last-read card
        self._expected = ""          # LF clone cmd, to confirm on verify
        # HF
        self._hf_family = ""         # "mfc"/"mfu" when an HF card can be copied
        self._hf_restore_file = ""   # dump file to write to the magic card
        self._hf_label = ""          # type label, to confirm on verify
        # in flight
        self._pending_write = ""
        self._pending_dump = ""
        self._build()

    # -- layout -------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        intro = QLabel("Read any card to identify it (LF 125 kHz and HF 13.56 "
                       "MHz). Copyable cards clone in three steps — LF onto a "
                       "blank T5577/EM4305, HF onto a magic card. Keep one card "
                       "on the antenna at a time.")
        intro.setObjectName("OptHelp")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.read_btn = QPushButton("①  Read / identify the card")
        self.read_btn.setObjectName("Primary")
        self.read_btn.clicked.connect(self._do_read)
        root.addWidget(self._step_box(
            "Place the card on the antenna, then read it (LF, then HF):",
            self.read_btn))

        self.result = QLabel("No card read yet.")
        self.result.setObjectName("Subtitle")
        self.result.setWordWrap(True)
        res_box = QFrame()
        res_box.setObjectName("Panel")
        rv = QVBoxLayout(res_box)
        rv.setContentsMargins(14, 12, 14, 12)
        rv.addWidget(self.result)
        root.addWidget(res_box)

        self.write_btn = QPushButton("②  Write the copy")
        self.write_btn.setObjectName("Primary")
        self.write_btn.clicked.connect(self._do_write)
        root.addWidget(self._step_box(
            "Take the original off, put the target on the antenna, then click. "
            "Easy mode writes to whatever it detects (T5577/EM4305 for LF, a "
            "magic card for HF):",
            self.write_btn))

        self.verify_btn = QPushButton("③  Verify the copy")
        self.verify_btn.clicked.connect(self._do_verify)
        root.addWidget(self._step_box(
            "Leave the new copy on the antenna and read it back:",
            self.verify_btn))

        self.status = QLabel("")
        self.status.setObjectName("OptHelp")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)

    def _step_box(self, text: str, button: QPushButton) -> QFrame:
        box = QFrame()
        box.setObjectName("Panel")
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        v.addWidget(lbl)
        row = QHBoxLayout()
        row.addWidget(button)
        row.addStretch(1)
        v.addLayout(row)
        return box

    # -- external hooks -----------------------------------------------------

    def set_connected(self, connected: bool):
        self._connected = connected
        self._refresh_buttons()
        if not connected:
            self.status.setText("Connect to the Proxmark3 to use Easy mode.")
        elif not self.status.text():
            self.status.setText("Ready.")

    def command_finished(self, cmd: str, output: str):
        """Called by the main window for every completed command."""
        cmd = cmd.strip()
        if cmd == self._pending_dump:
            self._pending_dump = ""
            self._after_dump(output)
        elif cmd == self._pending_write:
            self._pending_write = ""
            self._after_write(output)
        elif cmd.startswith("hf 14a info") and self._mode == "magic":
            self._after_magic(output)
        elif cmd.startswith("hf search"):
            if self._mode == "verify":
                self._after_verify_hf(output)
            else:
                self._after_hf(output)
        elif cmd == clone.READ_COMMAND or cmd.startswith("lf search"):
            if self._mode == "target":
                self._after_target(output)
            elif self._mode == "verify":
                self._after_verify(output)
            else:
                self._after_read(output)

    # -- step 1: read -------------------------------------------------------

    def _do_read(self):
        self._mode = "read"
        self._reset_copy()
        self.result.setText("Reading…")
        self.status.setText("Scanning for a 125 kHz (LF) card…")
        self.run_requested.emit(clone.READ_COMMAND)

    def _after_read(self, output: str):
        matches = clone.detect(output)
        clonable = [m for m in matches if m.command]
        if clonable:
            m = clonable[0]
            self._clone_cmd = m.command
            self._expected = m.command
            self._copy_kind = "lf"
            extra = ("  Other reads: "
                     + ", ".join(x.label for x in matches if x is not m)
                     if len(matches) > 1 else "")
            self.result.setText(
                "Found: %s\nWill clone with:  %s%s" % (m.label, m.command, extra))
            self.status.setText("Step ②: put a blank (T5577/EM4305) on, write.")
        elif matches:
            m = matches[0]
            self.result.setText("Found: %s\n%s" % (m.label, m.note))
            self.status.setText("This card can't be auto-cloned here.")
        elif clone.is_blank_t55xx(output):
            self.result.setText(
                "This is a blank T5577 — a good target to write to, but there's "
                "no card data to copy from. Put the card you want to copy on "
                "the antenna and read again.")
            self.status.setText("Blank T5577 detected.")
        else:
            # Nothing on LF — the card may be HF. Check 13.56 MHz too.
            self.status.setText("No LF card — checking 13.56 MHz (HF)…")
            self.run_requested.emit("hf search")
            return
        self._refresh_buttons()

    def _after_hf(self, output: str):
        info = clone.detect_hf(output)
        if info and info.clone:
            self._hf_family = info.clone
            self._hf_label = info.label
            self._copy_kind = "hf"
            self.result.setText(
                "Found (HF 13.56 MHz): %s\nSecurity: %s\n%s\n\nCopyable — needs "
                "a magic %s card. Click ② to dump this card, then write it."
                % (info.label, info.security, info.advice,
                   _FAMILY_NAME[info.clone]))
            self.status.setText("Step ②: copy to a magic card.")
        elif info:
            self.result.setText(
                "Found (HF 13.56 MHz): %s\nSecurity: %s\n%s"
                % (info.label, info.security, info.advice))
            self.status.setText("Identified — this type isn't copyable here.")
        else:
            self.result.setText(
                "No card found on LF (125 kHz) or HF (13.56 MHz). Reposition "
                "the card on the antenna and read again.")
            self.status.setText("Nothing detected.")
        self._refresh_buttons()

    # -- step 2: write ------------------------------------------------------

    def _do_write(self):
        if self._clone_cmd:
            self._write_lf()
        elif self._hf_family:
            self._write_hf()

    # LF: detect the blank on the antenna, then clone to it.
    def _write_lf(self):
        self._mode = "target"
        self.status.setText("Checking the target chip…")
        self.run_requested.emit(clone.READ_COMMAND)

    def _after_target(self, output: str):
        self._mode = "read"
        chip = clone.target_chip(output)
        if not chip:
            QMessageBox.warning(
                self, "No writable tag",
                "The tag on the antenna isn't a T5577 or EM4305/4469, so Easy "
                "mode can't write to it. Put a blank writable tag on the "
                "antenna and try again.")
            self.status.setText("Target isn't writable.")
            return
        final = clone.apply_target(self._clone_cmd, chip)
        ok = QMessageBox.question(
            self, "Write copy?",
            "Target detected: %s\n\nWrite the copy now?\n\n%s\n\n"
            "This overwrites the tag on the antenna. Make sure it's the blank "
            "target, not your original."
            % (clone.target_label(chip), final),
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if ok != QMessageBox.Yes:
            self.status.setText("Write cancelled.")
            return
        self._pending_write = final
        self.status.setText("Writing to %s…" % clone.target_label(chip))
        self.run_requested.emit(final)

    # HF: dump the original (read-only), then write the dump to a magic card.
    def _write_hf(self):
        fam = _FAMILY_NAME[self._hf_family]
        dump = clone.hf_dump_cmd(self._hf_family)
        slow = " — this can take a minute" if self._hf_family == "mfc" else ""
        ok = QMessageBox.question(
            self, "Copy HF card?",
            "Copy this card in two stages:\n\n"
            "1) Dump the ORIGINAL now on the antenna (%s)%s.\n"
            "2) Then put a MAGIC %s card on to write the copy.\n\n"
            "A normal blank will NOT work for HF — you need a magic card.\n"
            "(HF copy is new and not yet tested on real hardware here.)"
            % (dump, slow, fam),
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if ok != QMessageBox.Yes:
            self.status.setText("Copy cancelled.")
            return
        self._pending_dump = dump
        self.status.setText("Dumping the original (%s)…" % dump)
        self.run_requested.emit(dump)

    def _after_dump(self, output: str):
        dump_file = clone.saved_file(output)
        if not dump_file:
            self.result.setText(
                "Couldn't dump the card. For MIFARE Classic the keys may not "
                "have been recovered (a hardened card), or the read failed. "
                "Reposition the original and try ② again.")
            self.status.setText("Dump failed — nothing saved.")
            self._refresh_buttons()
            return
        self._hf_restore_file = dump_file
        fam = _FAMILY_NAME[self._hf_family]
        QMessageBox.information(
            self, "Put the magic card on",
            "Original dumped to:\n%s\n\nNow take the original OFF, put a MAGIC "
            "%s card on the antenna, and click OK to check it."
            % (dump_file, fam))
        # Probe the magic card so we write it the right way (gen1a vs gen2).
        self._mode = "magic"
        self.status.setText("Checking the magic card…")
        self.run_requested.emit("hf 14a info")

    def _after_magic(self, output: str):
        self._mode = "read"
        write = clone.magic_write_cmd(self._hf_family, output,
                                      self._hf_restore_file)
        if not write:
            QMessageBox.warning(
                self, "Not a magic card",
                "The card on the antenna doesn't look like a magic MIFARE "
                "(gen1a/UID or gen2/CUID). A copy can only be written to a "
                "magic card. Put one on and press ② again.")
            self.status.setText("Target isn't a magic card.")
            self._refresh_buttons()
            return
        gen = clone.magic_gen(output)
        ok = QMessageBox.question(
            self, "Write copy?",
            "Magic card detected (%s). Write the copy now?\n\n%s\n\n"
            "This overwrites the card on the antenna."
            % (gen or "magic", write),
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if ok != QMessageBox.Yes:
            self.status.setText("Write cancelled.")
            self._refresh_buttons()
            return
        self._pending_write = write
        self.status.setText("Writing the copy to the magic card…")
        self.run_requested.emit(write)

    def _after_write(self, output: str):
        low = output.lower()
        if any(w in low for w in ("done", "success", "wrote", "written")):
            self.status.setText("Write finished. Step ③: verify the copy.")
        else:
            self.status.setText(
                "Write finished, but the client didn't confirm success — "
                "verify to check, or try again.")
        self._refresh_buttons()

    # -- step 3: verify -----------------------------------------------------

    def _do_verify(self):
        self._mode = "verify"
        self.result.setText("Verifying…")
        self.status.setText("Reading the copy back…")
        if self._copy_kind == "hf":
            self.run_requested.emit("hf search")
        else:
            self.run_requested.emit(clone.READ_COMMAND)

    def _after_verify(self, output: str):
        self._mode = "read"
        clonable = [m for m in clone.detect(output) if m.command]
        got = clonable[0].command if clonable else ""
        if got and got == self._expected:
            self.result.setText(
                "✓ Verified — the copy reads the same as the original:\n%s"
                % clonable[0].label)
            self.status.setText("Copy complete. Read another card to start over.")
        elif got:
            self.result.setText(
                "The copy reads as a different card than expected:\n"
                "  wrote:  %s\n  reads:  %s\nTry writing again."
                % (self._expected, got))
            self.status.setText("Verification mismatch.")
        else:
            self.result.setText(
                "Couldn't read the copy back. Make sure the tag you wrote is on "
                "the antenna, then verify again.")
            self.status.setText("Nothing read on verify.")
        self._refresh_buttons()

    def _after_verify_hf(self, output: str):
        self._mode = "read"
        info = clone.detect_hf(output)
        if info and info.label == self._hf_label:
            self.result.setText(
                "✓ Verified — the copy reads as the same type:\n%s" % info.label)
            self.status.setText("Copy complete. Read another card to start over.")
        elif info:
            self.result.setText(
                "The copy reads as a different card than expected:\n"
                "  original:  %s\n  copy:      %s"
                % (self._hf_label, info.label))
            self.status.setText("Verification mismatch.")
        else:
            self.result.setText(
                "Couldn't read the copy back. Make sure the magic card is on "
                "the antenna, then verify again.")
            self.status.setText("Nothing read on verify.")
        self._refresh_buttons()

    # -- helpers ------------------------------------------------------------

    def _reset_copy(self):
        self._clone_cmd = ""
        self._expected = ""
        self._hf_family = ""
        self._hf_restore_file = ""
        self._hf_label = ""
        self._copy_kind = ""

    def _refresh_buttons(self):
        self.read_btn.setEnabled(self._connected)
        self.verify_btn.setEnabled(self._connected)
        can_write = bool(self._clone_cmd) or bool(self._hf_family)
        self.write_btn.setEnabled(self._connected and can_write)
        if self._hf_family:
            self.write_btn.setText(
                "②  Copy to a magic %s card" % _FAMILY_NAME[self._hf_family])
        elif self._clone_cmd:
            self.write_btn.setText("②  Write the copy to a blank (T5577/EM4305)")
        else:
            self.write_btn.setText("②  Write the copy")
