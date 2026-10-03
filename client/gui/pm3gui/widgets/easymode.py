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
# Easy mode: a guided read -> identify -> clone -> verify flow for LF 125 kHz
# cards. It drives the same client commands as the rest of the GUI; the card
# recognition lives in pm3gui.clone so it can be tested without a device.
#-----------------------------------------------------------------------------

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .. import clone, theme


class EasyMode(QWidget):
    """Guided LF card copying.

    Emits run_requested(command) for the main window to execute; receives each
    finished command through command_finished() to advance the flow.
    """

    run_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._clone_cmd = ""        # command that writes the last-read card
        self._pending_write = ""    # clone command we issued, awaiting result
        self._expected = ""         # clone cmd we wrote, to confirm on verify
        self._mode = "read"         # "read" or "verify": how to treat a search
        self._build()
        self._set_step(1)

    # -- layout -------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        intro = QLabel("Copy a 125 kHz (LF) card onto a blank T5577 in three "
                       "steps. Keep one card on the antenna at a time.")
        intro.setObjectName("OptHelp")
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Step 1 — read the original
        self.read_btn = QPushButton("①  Read the original card")
        self.read_btn.setObjectName("Primary")
        self.read_btn.clicked.connect(self._do_read)
        root.addWidget(self._step_box(
            "Place the card you want to copy on the antenna, then:",
            self.read_btn))

        # Result of the read
        self.result = QLabel("No card read yet.")
        self.result.setObjectName("Subtitle")
        self.result.setWordWrap(True)
        res_box = QFrame()
        res_box.setObjectName("Panel")
        rv = QVBoxLayout(res_box)
        rv.setContentsMargins(14, 12, 14, 12)
        rv.addWidget(self.result)
        root.addWidget(res_box)

        # Step 2 — write the copy
        self.write_btn = QPushButton("②  Write the copy to a blank T5577")
        self.write_btn.setObjectName("Primary")
        self.write_btn.clicked.connect(self._do_write)
        root.addWidget(self._step_box(
            "Take the original off, put a blank T5577 on the antenna, then:",
            self.write_btn))

        # Step 3 — verify
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
        if cmd == self._pending_write:
            self._pending_write = ""
            self._after_write(output)
        elif cmd == clone.READ_COMMAND or cmd.startswith("lf search"):
            if self._mode == "verify":
                self._after_verify(output)
            else:
                self._after_read(output)

    # -- step 1: read -------------------------------------------------------

    def _do_read(self):
        self._mode = "read"
        self.result.setText("Reading…")
        self.status.setText("Scanning for a 125 kHz card…")
        self.run_requested.emit(clone.READ_COMMAND)

    def _after_read(self, output: str):
        matches = clone.detect(output)
        clonable = [m for m in matches if m.command]
        if clonable:
            m = clonable[0]
            self._clone_cmd = m.command
            self._expected = m.command
            extra = ("  Other reads: "
                     + ", ".join(x.label for x in matches if x is not m)
                     if len(matches) > 1 else "")
            self.result.setText(
                "Found: %s\nWill clone with:  %s%s"
                % (m.label, m.command, extra))
            self.status.setText("Step ②: swap in a blank T5577, then write.")
            self._set_step(2)
        elif matches:
            m = matches[0]
            self._clone_cmd = ""
            self.result.setText("Found: %s\n%s" % (m.label, m.note))
            self.status.setText("This card can't be auto-cloned here.")
            self._set_step(1)
        elif clone.is_blank_t55xx(output):
            self._clone_cmd = ""
            self.result.setText(
                "This is a blank T5577 — a good target to write to, but there's "
                "no card data to copy from. Put the card you want to copy on "
                "the antenna and read again.")
            self.status.setText("Blank T5577 detected.")
            self._set_step(1)
        else:
            self._clone_cmd = ""
            self.result.setText(
                "No 125 kHz card found. Reposition the card over the LF coil "
                "and try again. (HF 13.56 MHz cards aren't handled by Easy "
                "mode — use the Commands tab.)")
            self.status.setText("Nothing detected.")
            self._set_step(1)
        self._refresh_buttons()

    # -- step 2: write ------------------------------------------------------

    def _do_write(self):
        if not self._clone_cmd:
            return
        ok = QMessageBox.question(
            self, "Write copy?",
            "Write this card onto the T5577 now on the antenna?\n\n%s\n\n"
            "This overwrites the tag on the antenna. Make sure it's the blank "
            "target, not your original."
            % self._clone_cmd,
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if ok != QMessageBox.Yes:
            return
        self._pending_write = self._clone_cmd
        self.status.setText("Writing…")
        self.run_requested.emit(self._clone_cmd)

    def _after_write(self, output: str):
        if "Done" in output or "done" in output:
            self.status.setText("Write finished. Step ③: verify the copy.")
            self._set_step(3)
        else:
            self.status.setText(
                "Write finished, but the client didn't confirm success — "
                "verify to check, or try again.")
            self._set_step(3)
        self._refresh_buttons()

    # -- step 3: verify -----------------------------------------------------

    def _do_verify(self):
        self._mode = "verify"
        self.result.setText("Verifying…")
        self.status.setText("Reading the copy back…")
        self.run_requested.emit(clone.READ_COMMAND)

    def _after_verify(self, output: str):
        self._mode = "read"
        clonable = [m for m in clone.detect(output) if m.command]
        got = clonable[0].command if clonable else ""
        if got and got == self._expected:
            self.result.setText(
                "✓ Verified — the copy reads the same as the original:\n%s"
                % clonable[0].label)
            self.status.setText("Copy complete. You can read another card to "
                                "start over.")
        elif got:
            self.result.setText(
                "The copy reads as a different card than expected:\n"
                "  wrote:  %s\n  reads:  %s\nTry writing again."
                % (self._expected, got))
            self.status.setText("Verification mismatch.")
        else:
            self.result.setText(
                "Couldn't read the copy back. Make sure the T5577 you wrote is "
                "on the antenna, then verify again.")
            self.status.setText("Nothing read on verify.")
        self._refresh_buttons()

    # -- helpers ------------------------------------------------------------

    def _set_step(self, step: int):
        self._step = step

    def _refresh_buttons(self):
        self.read_btn.setEnabled(self._connected)
        self.verify_btn.setEnabled(self._connected)
        self.write_btn.setEnabled(self._connected and bool(self._clone_cmd))
