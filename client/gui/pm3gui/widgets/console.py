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
# A colour-coded output console plus a command entry with history, so the full
# client CLI stays available for anything the forms do not cover.
#-----------------------------------------------------------------------------

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from .. import theme

# Maps the client's leading status tag to a console colour kind.
_TAG_RE = re.compile(r"^\s*\[(?P<tag>[-+=!#?@ ]{1,2})\]")
_TAG_KIND = {
    "+": "success",
    "-": "error", "!!": "error",
    "!": "warn",
    "=": "info", "#": "info", "@": "info",
}


def classify(line: str) -> str:
    m = _TAG_RE.match(line)
    if m:
        return _TAG_KIND.get(m.group("tag").strip(), "out")
    return "out"


class Console(QWidget):
    """Terminal-like pane. Emits `command` when the user submits a line."""

    command = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list = []
        self._hist_idx = 0

        self.view = QPlainTextEdit(self)
        self.view.setObjectName("Console")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(8000)

        self.entry = QLineEdit(self)
        self.entry.setPlaceholderText("Type a client command, e.g. hw version")
        self.entry.returnPressed.connect(self._submit)
        self.entry.installEventFilter(self)

        self.send_btn = QPushButton("Send", self)
        self.send_btn.setObjectName("Primary")
        self.send_btn.clicked.connect(self._submit)

        clear = QPushButton("Clear", self)
        clear.clicked.connect(self.view.clear)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("pm3 ›"))
        row.addWidget(self.entry, 1)
        row.addWidget(self.send_btn)
        row.addWidget(clear)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.view, 1)
        lay.addLayout(row)

    def _write(self, text: str, color: str):
        cur = self.view.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cur.insertText(text, fmt)
        self.view.setTextCursor(cur)
        self.view.ensureCursorVisible()

    def append_line(self, text: str, kind: str = "out"):
        color = theme.CONSOLE_COLORS.get(kind, theme.CONSOLE_FG)
        if kind == "echo":
            text = "› " + text
        self._write(text + "\n", color)

    def append_output(self, line: str):
        """A plain output line from the client, auto-classified by its tag."""
        self.append_line(line, classify(line))

    def append_system(self, text: str):
        self._write(text + "\n", theme.CONSOLE_COLORS["sys"])

    def echo_command(self, cmd: str):
        self.append_line(cmd, "echo")

    def _submit(self):
        cmd = self.entry.text().strip()
        if not cmd:
            return
        self._history.append(cmd)
        self._hist_idx = len(self._history)
        self.entry.clear()
        self.command.emit(cmd)

    def eventFilter(self, obj, event):
        if obj is self.entry and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Up:
                self._recall(-1)
                return True
            if event.key() == Qt.Key_Down:
                self._recall(1)
                return True
        return super().eventFilter(obj, event)

    def _recall(self, delta: int):
        if not self._history:
            return
        self._hist_idx = max(0, min(len(self._history), self._hist_idx + delta))
        if self._hist_idx >= len(self._history):
            self.entry.clear()
        else:
            self.entry.setText(self._history[self._hist_idx])
            self.entry.end(False)
