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
# The application window: connection bar, searchable command tree for the full
# command set, lazily-built per-command forms, quick-task shortcuts, and a
# shared console. All command execution funnels through one Pm3Session.
#-----------------------------------------------------------------------------

from __future__ import annotations

import glob
import os
import shutil
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .commands import Command, CommandSet
from .session import Pm3Session
from . import theme
from .widgets.console import Console
from .widgets.formbuilder import CommandForm

# Curated one-click tasks: (button label, client command). These are just
# shortcuts into the same command set; nothing here is exclusive to them.
QUICK_TASKS = [
    ("Device version", "hw version"),
    ("Device status", "hw status"),
    ("Tune antennas", "hw tune"),
    ("Auto-detect card (LF)", "lf search"),
    ("Auto-detect card (HF)", "hf search"),
    ("Identify any tag", "auto"),
    ("MIFARE Classic autopwn", "hf mf autopwn"),
    ("Read HID Prox (LF)", "lf hid reader"),
    ("Read EM410x (LF)", "lf em 410x reader"),
    ("Read ISO14443-A (HF)", "hf 14a reader"),
    ("Read iCLASS (HF)", "hf iclass reader"),
    ("List known LF tags", "lf search -1"),
]


def guess_ports() -> list:
    pats = ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/tty.usbmodem*",
            "/dev/cu.usbmodem*", "/dev/tty.usbserial*"]
    found = []
    for p in pats:
        found += sorted(glob.glob(p))
    if sys.platform.startswith("win"):
        found += ["COM%d" % i for i in range(3, 12)]
    return found


def guess_client() -> str:
    # Prefer a sibling build of this very checkout, then PATH.
    here = os.path.dirname(os.path.abspath(__file__))
    local = [
        os.path.join(here, "..", "..", "proxmark3"),           # client/proxmark3
        os.path.join(here, "..", "..", "..", "client", "proxmark3"),
        os.path.join(here, "..", "..", "..", "pm3"),
    ]
    for c in local:
        c = os.path.normpath(c)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    for name in ("proxmark3", "pm3"):
        found = shutil.which(name)
        if found:
            return found
    return "proxmark3"


class MainWindow(QMainWindow):

    def __init__(self, cmdset: CommandSet, client_exe: str = "", parent=None):
        super().__init__(parent)
        self.cmdset = cmdset
        self.session = None
        self._forms: dict = {}        # command name -> CommandForm (lazy)

        self.setWindowTitle("Proxmark3 Studio — Iceman GUI")
        self.resize(1400, 880)

        self._build_connection_bar(client_exe)
        self._build_body()
        self._build_statusbar()
        self._populate_tree()
        self._set_connected(False)

    # -- layout -------------------------------------------------------------

    def _build_connection_bar(self, client_exe: str):
        bar = QFrame()
        bar.setObjectName("Panel")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.exe_edit = QLineEdit(client_exe or guess_client())
        self.exe_edit.setMinimumWidth(240)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_exe)

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(200)
        for p in guess_ports():
            self.port_combo.addItem(p)
        self.port_combo.lineEdit().setPlaceholderText("serial port (blank = offline)")

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("Primary")
        self.connect_btn.clicked.connect(self._toggle_connection)

        lay.addWidget(QLabel("Client"))
        lay.addWidget(self.exe_edit, 1)
        lay.addWidget(browse)
        lay.addWidget(QLabel("Port"))
        lay.addWidget(self.port_combo, 1)
        lay.addWidget(self.connect_btn)
        self._conn_bar = bar

    def _build_body(self):
        # Left: tabs (Commands tree / Quick tasks)
        left_tabs = QTabWidget()

        tree_panel = QWidget()
        tv = QVBoxLayout(tree_panel)
        tv.setContentsMargins(8, 8, 8, 8)
        tv.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all 935 commands…")
        self.search.textChanged.connect(self._filter_tree)
        tv.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Command", "What it does"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setWordWrap(False)
        self.tree.currentItemChanged.connect(self._on_tree_select)
        tv.addWidget(self.tree, 1)
        left_tabs.addTab(tree_panel, "Commands")

        quick_panel = QWidget()
        qv = QVBoxLayout(quick_panel)
        qv.setContentsMargins(10, 10, 10, 10)
        qv.setSpacing(8)
        hint = QLabel("One-click shortcuts. Connect a device first for "
                      "anything that reads hardware.")
        hint.setObjectName("OptHelp")
        hint.setWordWrap(True)
        qv.addWidget(hint)
        for label, cmd in QUICK_TASKS:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, c=cmd: self._run_command(c))
            qv.addWidget(b)
        qv.addStretch(1)
        left_tabs.addTab(quick_panel, "Quick tasks")

        # Center: lazily populated form stack + empty-state hint
        self.form_stack = QStackedWidget()
        empty = QLabel("Select a command on the left, or use the console "
                       "below.\n\nEvery client command has a form here.")
        empty.setAlignment(Qt.AlignCenter)
        empty.setObjectName("Subtitle")
        self._empty_index = self.form_stack.addWidget(empty)

        form_wrap = QFrame()
        form_wrap.setObjectName("Panel")
        fw = QVBoxLayout(form_wrap)
        fw.setContentsMargins(16, 16, 16, 16)
        fw.addWidget(self.form_stack)

        # Console
        self.console = Console()
        self.console.command.connect(self._run_command)

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(form_wrap)
        right_split.addWidget(self.console)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)
        right_split.setSizes([520, 280])

        main_split = QSplitter(Qt.Horizontal)
        main_split.addWidget(left_tabs)
        main_split.addWidget(right_split)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([480, 900])

        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(12, 12, 12, 12)
        cv.setSpacing(12)
        cv.addWidget(self._conn_bar)
        cv.addWidget(main_split, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        self.state_label = QLabel("Disconnected")
        self.statusBar().addPermanentWidget(self.state_label)
        self.statusBar().showMessage("Ready")

    # -- command tree -------------------------------------------------------

    def _populate_tree(self):
        self.tree.clear()
        tree = self.cmdset.tree()

        def add(parent, node, prefix):
            for key in sorted(node.keys()):
                val = node[key]
                path = (prefix + " " + key).strip()
                desc = self.cmdset.describe(path)
                item = QTreeWidgetItem([key, desc])
                item.setToolTip(0, path)
                item.setToolTip(1, desc)
                if isinstance(val, Command):
                    item.setData(0, Qt.UserRole, val.name)
                    _attach(parent, item)
                else:
                    item.setData(0, Qt.UserRole, None)
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    _attach(parent, item)
                    add(item, val, path)

        def _attach(parent, item):
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        add(None, tree, "")

    def _filter_tree(self, text: str):
        text = text.strip().lower()

        def visit(item) -> bool:
            name = item.data(0, Qt.UserRole)
            match = (text in item.text(0).lower()
                     or text in item.text(1).lower()
                     or text in item.toolTip(0).lower())
            if name and text in name.lower():
                match = True
            child_match = False
            for i in range(item.childCount()):
                child_match = visit(item.child(i)) or child_match
            visible = (not text) or match or child_match
            item.setHidden(not visible)
            if text and child_match:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    def _on_tree_select(self, cur, _prev):
        if cur is None:
            return
        name = cur.data(0, Qt.UserRole)
        if not name:
            return
        self._show_form(name)

    def _show_form(self, name: str):
        form = self._forms.get(name)
        if form is None:
            cmd = self.cmdset.by_name.get(name)
            if cmd is None:
                return
            form = CommandForm(cmd, self.cmdset)
            form.run_requested.connect(self._run_command)
            form.example_chosen.connect(self._load_example)
            self._forms[name] = form
            self.form_stack.addWidget(form)
        self.form_stack.setCurrentWidget(form)

    def _load_example(self, line: str):
        self.console.entry.setText(line)
        self.console.entry.setFocus()
        self.statusBar().showMessage("Example loaded \u2014 edit if needed, then press Enter", 5000)

    # -- connection ---------------------------------------------------------

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Locate proxmark3 client")
        if path:
            self.exe_edit.setText(path)

    def _toggle_connection(self):
        if self.session and self.session.is_running():
            self.session.stop()
            return
        exe = self.exe_edit.text().strip()
        if not exe:
            QMessageBox.warning(self, "No client", "Set the proxmark3 client path.")
            return
        port = self.port_combo.currentText().strip()
        self.session = Pm3Session(exe, port)
        self.session.output.connect(self.console.append)
        self.session.started.connect(lambda: self._set_connected(True))
        self.session.stopped.connect(self._on_session_stopped)
        self.session.prompt.connect(self._on_prompt)
        self.session.error.connect(self._on_session_error)
        self.console.append_line(
            "\n[*] starting %s %s\n" % (exe, port or "(offline)"))
        self.session.start()

    def _on_session_stopped(self, code):
        self._set_connected(False)
        self.console.append_line("\n[*] client exited (code %d)\n" % code)

    def _on_session_error(self, msg):
        self.statusBar().showMessage("Client error: " + msg, 8000)
        self.console.append_line("[!] " + msg)

    def _on_prompt(self, state: str):
        online = state.lower() not in ("offline", "")
        pretty = state.upper() if state else "OFFLINE"
        self.state_label.setText(("Device: " + pretty) if online
                                 else "Offline (no device)")

    def _set_connected(self, connected: bool):
        self.connect_btn.setText("Disconnect" if connected else "Connect")
        self.exe_edit.setEnabled(not connected)
        self.port_combo.setEnabled(not connected)
        if connected:
            self.state_label.setText("Connected")
            self.statusBar().showMessage("Client running", 4000)
        else:
            self.state_label.setText("Disconnected")

    # -- running ------------------------------------------------------------

    def _run_command(self, cmd: str):
        cmd = cmd.strip()
        if not cmd:
            return
        if not (self.session and self.session.is_running()):
            QMessageBox.information(
                self, "Not connected",
                "Connect to the client first (a blank port starts it offline).")
            return
        self.console.echo_command(cmd)
        self.session.send(cmd)

    def closeEvent(self, event):
        if self.session and self.session.is_running():
            self.session.stop()
        super().closeEvent(event)
