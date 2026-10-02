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

import os

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .commands import Command, CommandSet
from . import osutil
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


class MainWindow(QMainWindow):

    def __init__(self, cmdset: CommandSet, client_exe: str = "", parent=None):
        super().__init__(parent)
        self.cmdset = cmdset
        self.session = None
        self._forms: dict = {}        # command name -> CommandForm (lazy)
        self._settings = QSettings("Proxmark3", "Studio")

        self.setWindowTitle("Proxmark3 Studio — Iceman GUI")
        self.resize(1400, 880)

        self._build_connection_bar(client_exe)
        self._build_body()
        self._build_statusbar()
        self._populate_tree()
        self._restore_settings()
        self._set_connected(False)

    # -- layout -------------------------------------------------------------

    def _build_connection_bar(self, client_exe: str):
        bar = QFrame()
        bar.setObjectName("Panel")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.exe_edit = QLineEdit(client_exe or osutil.find_client())
        self.exe_edit.setMinimumWidth(240)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_exe)

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(220)
        self.port_combo.lineEdit().setPlaceholderText("serial port (blank = offline)")
        self._fill_ports()
        rescan = QPushButton("Rescan")
        rescan.setToolTip("Look for connected serial ports again")
        rescan.clicked.connect(self._fill_ports)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("Primary")
        self.connect_btn.clicked.connect(self._toggle_connection)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.setToolTip(
            "Stop the running command (sends Enter, like the CLI).\n"
            "If it will not stop, use Disconnect to force-kill the client.")
        self.stop_btn.clicked.connect(self._stop_command)
        self.stop_btn.setEnabled(False)

        lay.addWidget(QLabel("Client"))
        lay.addWidget(self.exe_edit, 1)
        lay.addWidget(browse)
        lay.addWidget(QLabel("Port"))
        lay.addWidget(self.port_combo, 1)
        lay.addWidget(rescan)
        lay.addWidget(self.stop_btn)
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
        self.search.setPlaceholderText(
            "Search %d commands by name or description…"
            % len(self.cmdset.commands))
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
            b.setObjectName("Quick")
            group = cmd.split(" ", 1)[0]
            b.setStyleSheet("QPushButton { border-left: 3px solid %s; }"
                            % theme.group_color(group))
            b.clicked.connect(lambda _=False, c=cmd: self._run_command(c))
            qv.addWidget(b)
        qv.addStretch(1)
        left_tabs.addTab(quick_panel, "Quick tasks")

        # Center: lazily populated form stack. Empty state is a compact banner
        # so the console (CLI) owns the space until a command form is opened.
        self.form_stack = QStackedWidget()
        empty = QLabel("No command selected — pick one from Commands for a "
                       "fill-in form, or just type in the console below.")
        empty.setWordWrap(True)
        empty.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        empty.setObjectName("OptHelp")
        self._empty_index = self.form_stack.addWidget(empty)

        form_wrap = QFrame()
        form_wrap.setObjectName("Panel")
        fw = QVBoxLayout(form_wrap)
        fw.setContentsMargins(16, 12, 16, 12)
        fw.addWidget(self.form_stack)

        # Console
        self.console = Console()
        self.console.command.connect(self._run_command)

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(form_wrap)
        right_split.addWidget(self.console)
        right_split.setCollapsible(0, False)
        right_split.setCollapsible(1, False)
        right_split.setStretchFactor(0, 0)
        right_split.setStretchFactor(1, 1)
        # Banner stays small; console gets the room. Opening a form grows the
        # top pane once (see _show_form), then the user's sizing is respected.
        right_split.setSizes([70, 760])
        self._center_split = right_split
        self._center_autosized = False

        main_split = QSplitter(Qt.Horizontal)
        main_split.addWidget(left_tabs)
        main_split.addWidget(right_split)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([480, 900])
        self._main_split = main_split

        central = QWidget()
        cv = QVBoxLayout(central)
        cv.setContentsMargins(12, 12, 12, 12)
        cv.setSpacing(12)
        cv.addWidget(self._conn_bar)
        cv.addWidget(main_split, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        self.dot = QLabel("●")
        self.dot.setObjectName("Dot")
        self.state_label = QLabel("Disconnected")
        self.statusBar().addPermanentWidget(self.dot)
        self.statusBar().addPermanentWidget(self.state_label)
        self._set_dot(theme.MUTED)
        self.statusBar().showMessage("Ready")

    def _set_dot(self, color: str):
        self.dot.setStyleSheet("color: %s;" % color)

    # -- command tree -------------------------------------------------------

    def _populate_tree(self):
        self.tree.clear()
        tree = self.cmdset.tree()

        def add(parent, node, prefix, top_group):
            for key in sorted(node.keys()):
                val = node[key]
                path = (prefix + " " + key).strip()
                group = top_group or key
                desc = self.cmdset.describe(path)
                item = QTreeWidgetItem([key, desc])
                item.setToolTip(0, path)
                item.setToolTip(1, desc)
                item.setForeground(0, QColor(theme.group_color(group)))
                if isinstance(val, Command):
                    item.setData(0, Qt.UserRole, val.name)
                    _attach(parent, item)
                else:
                    item.setData(0, Qt.UserRole, None)
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    _attach(parent, item)
                    add(item, val, path, group)

        def _attach(parent, item):
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        add(None, tree, "", "")

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
        # First form opened: give the top pane real room. After that, leave
        # whatever split the user has chosen alone.
        if not self._center_autosized:
            self._center_autosized = True
            self._center_split.setSizes([480, 360])
        elif self._center_split.sizes()[0] < 160:
            # Pane was dragged (near) shut; reopen enough to see the form.
            self._center_split.setSizes([420, 400])

    def _load_example(self, line: str):
        self.console.entry.setText(line)
        self.console.entry.setFocus()
        self.statusBar().showMessage(
            "Example loaded — edit if needed, then press Enter", 5000)

    # -- settings -----------------------------------------------------------

    def _restore_settings(self):
        exe = osutil.resolve_client(self._settings.value("client", ""))
        if exe and not osutil.resolve_client(self.exe_edit.text()):
            self.exe_edit.setText(exe)
        port = self._settings.value("port", "")
        # A detected Proxmark3 beats the remembered port.
        if port and not self._pm3_detected:
            idx = self.port_combo.findData(port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
            else:
                self.port_combo.setEditText(port)
        geo = self._settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def _save_settings(self):
        self._settings.setValue("client", self.exe_edit.text().strip())
        self._settings.setValue("port", self._current_port())
        self._settings.setValue("geometry", self.saveGeometry())

    # -- connection ---------------------------------------------------------

    def _fill_ports(self):
        typed = self._current_port() if self.port_combo.count() else ""
        self.port_combo.clear()
        self._pm3_detected = False
        for port, label, is_pm3 in osutil.list_ports():
            self.port_combo.addItem(label, port)
            self._pm3_detected |= is_pm3
        if self._pm3_detected:
            self.port_combo.setCurrentIndex(0)
        else:
            self.port_combo.setEditText(typed)

    def _current_port(self) -> str:
        """Port the client expects, even when the combo shows a label."""
        text = self.port_combo.currentText().strip()
        idx = self.port_combo.findText(text)
        if idx >= 0 and self.port_combo.itemData(idx):
            return self.port_combo.itemData(idx)
        return text

    def _browse_exe(self):
        start = os.path.dirname(osutil.resolve_client(self.exe_edit.text())
                                or osutil.resolve_client(osutil.find_client()))
        filt = ("Proxmark3 client (proxmark3.exe);;Programs (*.exe)"
                if osutil.IS_WINDOWS else "")
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate proxmark3 client", start, filt)
        if path:
            self.exe_edit.setText(path)

    def start_connection(self):
        """Public: connect now (used by --port auto-connect and the button)."""
        if self.session and self.session.is_running():
            return
        typed = self.exe_edit.text().strip()
        exe = osutil.resolve_client(typed)
        if not exe:
            # Stale setting or wrong file picked: fall back to auto-detect.
            exe = osutil.resolve_client(osutil.find_client())
            if not exe:
                QMessageBox.warning(
                    self, "Client not found",
                    "Could not find the proxmark3 client%s.\n\nBuild it first, "
                    "then use Browse to select %s."
                    % (" at \"%s\"" % typed if typed else "", osutil.CLIENT_NAME))
                return
            if typed:
                self.console.append_system(
                    "[*] \"%s\" is not a usable client; using %s" % (typed, exe))
        self.exe_edit.setText(exe)
        port = self._current_port()
        self._save_settings()
        self.session = Pm3Session(exe, port)
        self.session.line.connect(self._on_line)
        self.session.state.connect(self._on_state)
        self.session.busy.connect(self._on_busy)
        self.session.started.connect(lambda: self._set_connected(True))
        self.session.stopped.connect(self._on_session_stopped)
        self.session.error.connect(self._on_session_error)
        self.console.append_system(
            "[*] starting %s %s" % (exe, port or "(offline mode)"))
        self.session.start()

    def _toggle_connection(self):
        if self.session and self.session.is_running():
            self.session.stop()
        else:
            self.start_connection()

    def _stop_command(self):
        if self.session and self.session.is_busy():
            self.session.interrupt()
            self.console.append_system("[*] stop requested…")

    def _on_line(self, text: str, kind: str):
        if kind == "echo":
            self.console.append_line(text, "echo")
        else:
            self.console.append_output(text)

    def _on_busy(self, busy: bool):
        self.stop_btn.setEnabled(busy)
        if busy:
            self.statusBar().showMessage("Running…")
        else:
            self.statusBar().showMessage("Ready", 2000)

    def _on_session_stopped(self, code):
        self._set_connected(False)
        self.console.append_system("[*] client exited (code %d)" % code)

    def _on_session_error(self, msg):
        self.statusBar().showMessage("Client error: " + msg, 8000)
        self.console.append_line("[!] " + msg, "error")

    def _on_state(self, state: str):
        online = state.lower() not in ("offline", "")
        if online:
            self.state_label.setText("Device: " + state.upper())
            self._set_dot(theme.GREEN)
        else:
            self.state_label.setText("Offline (no device)")
            self._set_dot(theme.YELLOW)

    def _set_connected(self, connected: bool):
        self.connect_btn.setText("Disconnect" if connected else "Connect")
        self.exe_edit.setEnabled(not connected)
        self.port_combo.setEnabled(not connected)
        if connected:
            self.state_label.setText("Connected")
            self._set_dot(theme.GREEN)
            self.statusBar().showMessage("Client running", 4000)
        else:
            self.state_label.setText("Disconnected")
            self._set_dot(theme.MUTED)
            self.stop_btn.setEnabled(False)

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
        self.session.send(cmd)

    def closeEvent(self, event):
        self._save_settings()
        if self.session and self.session.is_running():
            self.session.stop()
        super().closeEvent(event)
