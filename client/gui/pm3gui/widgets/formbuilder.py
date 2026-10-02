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
# Builds an input form for one Command from its parsed options, assembles the
# resulting CLI string, and runs it. One widget per command, created lazily.
#-----------------------------------------------------------------------------

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..commands import Command, Option


class _OptionRow:
    """Binds one Option to its input widget and reports its CLI fragment."""

    def __init__(self, opt: Option):
        self.opt = opt
        if opt.takes_value:
            self.widget = QLineEdit()
            ph = opt.placeholder.strip("<>") if opt.placeholder else "value"
            self.widget.setPlaceholderText(ph)
            self.check = None
        else:
            self.check = QCheckBox()
            self.widget = self.check

    def fragment(self) -> list:
        """Return CLI tokens for this option, or [] when unset."""
        flag = self.opt.flag
        if self.opt.takes_value:
            val = self.widget.text().strip()
            if not val:
                return []
            return [flag, val] if flag else [val]
        return [flag] if self.check.isChecked() and flag else []


class CommandForm(QWidget):
    """A scrollable form for a single command, with Run + copy actions."""

    run_requested = Signal(str)       # the assembled command line
    preview_changed = Signal(str)

    def __init__(self, command: Command, parent=None):
        super().__init__(parent)
        self.command = command
        self._rows: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Header -----------------------------------------------------------
        title = QLabel(command.name)
        title.setObjectName("Title")
        root.addWidget(title)

        if command.description:
            desc = QLabel(command.description)
            desc.setObjectName("Subtitle")
            desc.setWordWrap(True)
            root.addWidget(desc)

        badge = QLabel("offline capable" if command.offline
                       else "needs connected device")
        badge.setObjectName("Subtitle")
        root.addWidget(badge)

        # Options ----------------------------------------------------------
        body = QWidget()
        form = QVBoxLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        if command.options:
            hdr = QLabel("Options")
            hdr.setObjectName("SectionHeader")
            form.addWidget(hdr)
            for opt in command.options:
                form.addWidget(self._build_row(opt))
        else:
            none = QLabel("This command takes no options. Just run it.")
            none.setObjectName("OptHelp")
            form.addWidget(none)

        # Free-form extra args, for anything the parser could not model
        # (positional args, odd value syntaxes). Always available.
        xhdr = QLabel("Extra arguments (appended verbatim)")
        xhdr.setObjectName("SectionHeader")
        form.addWidget(xhdr)
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("rarely needed — e.g. positional values")
        self.extra.textChanged.connect(self._update_preview)
        form.addWidget(self.extra)
        form.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Preview + actions ------------------------------------------------
        self.preview = QLineEdit()
        self.preview.setReadOnly(True)
        root.addWidget(self.preview)

        actions = QHBoxLayout()
        actions.addStretch(1)
        copy = QPushButton("Copy")
        copy.clicked.connect(self._copy)
        run = QPushButton("Run")
        run.setObjectName("Primary")
        run.clicked.connect(self._run)
        actions.addWidget(copy)
        actions.addWidget(run)
        root.addLayout(actions)

        self._update_preview()

    def _build_row(self, opt: Option) -> QWidget:
        row = _OptionRow(opt)
        self._rows.append(row)
        if isinstance(row.widget, QLineEdit):
            row.widget.textChanged.connect(self._update_preview)
        else:
            row.widget.stateChanged.connect(self._update_preview)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(8)
        label = QLabel(row.opt.label or row.opt.help[:24])
        label.setMinimumWidth(130)
        if opt.takes_value:
            top.addWidget(label)
            top.addWidget(row.widget, 1)
        else:
            top.addWidget(row.widget)
            top.addWidget(label, 1)
        lay.addLayout(top)

        if opt.help:
            h = QLabel(opt.help)
            h.setObjectName("OptHelp")
            h.setWordWrap(True)
            lay.addWidget(h)
        return w

    def build_command(self) -> str:
        tokens = [self.command.name]
        for row in self._rows:
            tokens += row.fragment()
        extra = self.extra.text().strip()
        if extra:
            tokens.append(extra)
        return " ".join(tokens)

    def _update_preview(self, *args):
        cmd = self.build_command()
        self.preview.setText(cmd)
        self.preview_changed.emit(cmd)

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.build_command())

    def _run(self):
        self.run_requested.emit(self.build_command())
