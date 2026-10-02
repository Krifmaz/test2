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
# Owns a long-lived `proxmark3` client fed through a stdin pipe.
# On a pipe the client echoes "[dev|script] pm3 --> <cmd>" before each
# command and never prints an idle prompt, so each command line gets a
# trailing "rem" marker and its remark line signals completion.
#-----------------------------------------------------------------------------

from __future__ import annotations

import re

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from . import osutil


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][AB012]|[\x01\x02\x07]")

# Echo of a command about to run: "[usb|script] pm3 --> hw version"
_ECHO_RE = re.compile(r"^\[(?P<state>[^\]]*)\]\s*pm[35]\s*-->\s?(?P<cmd>.*)$")

_MARK = "__pm3gui_done_"
_MARK_RE = re.compile(r"remark:\s*" + _MARK + r"(?P<seq>\d+)__")

# Client reads stdin with fgets into a 256-byte buffer (proxmark3.c).
MAX_LINE = 255


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class Pm3Session(QObject):
    """A single client session.

    Signals:
        line(str, str)        one output line and its kind:
                              "echo" (command echo) or "out"
        state(str)            device token from each echo: "usb", "offline", ...
        busy(bool)            a command is running / the queue drained
        command_finished(str, str)  (command, captured output)
        started() / stopped(int) / error(str)
    """

    line = Signal(str, str)
    state = Signal(str)
    busy = Signal(bool)
    command_finished = Signal(str, str)
    started = Signal()
    stopped = Signal(int)
    error = Signal(str)

    def __init__(self, exe: str, port: str = "", extra_args=None, parent=None):
        super().__init__(parent)
        self._exe = exe
        self._port = port
        self._extra = list(extra_args or [])
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyRead.connect(self._on_ready_read)
        self._proc.started.connect(self._on_started)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        self._partial = ""       # trailing text without a newline yet
        self._pending = None     # (seq, command) currently running
        self._captured: list = []
        self._queue: list = []
        self._seq = 0
        self._last_state = "offline"
        self._no_comms = False   # client reported it can't talk to the device

    # -- lifecycle ----------------------------------------------------------

    def start(self):
        # No port: the client starts in offline mode on its own.
        args = [self._port] if self._port else []
        # -f flushes after every print so output streams live.
        args += ["-f"] + self._extra
        env = QProcessEnvironment()
        for k, v in osutil.client_env(self._exe).items():
            env.insert(k, v)
        self._proc.setProcessEnvironment(env)
        self._proc.setWorkingDirectory(osutil.user_home())
        self._no_comms = False
        self._proc.start(self._exe, args)

    def stop(self):
        if self._proc.state() == QProcess.NotRunning:
            return
        self._queue.clear()
        self._proc.write(b"quit\n")
        if not self._proc.waitForFinished(3000):
            self._proc.kill()
            self._proc.waitForFinished(1000)

    def kill(self):
        """Hard stop for a command that ignores Stop."""
        self._queue.clear()
        if self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.NotRunning

    def is_busy(self) -> bool:
        return self._pending is not None

    def device_state(self) -> str:
        return self._last_state

    # -- commands -----------------------------------------------------------

    def send(self, command: str) -> bool:
        """Queue a command; returns False if it is too long for the client."""
        command = command.strip()
        if not command:
            return True
        if len(self._wire(command, 999999)) > MAX_LINE:
            self.error.emit("Command is too long for the client (max %d "
                            "characters). Split it up or use a script file."
                            % (MAX_LINE - len(self._wire("", 999999))))
            return False
        self._queue.append(command)
        self._pump()
        return True

    def interrupt(self):
        """Ask the running command to stop, same as pressing Enter."""
        if self._pending is not None:
            self._proc.write(b"\n")

    def _wire(self, command: str, seq: int) -> str:
        return "%s;rem %s%d__" % (command, _MARK, seq)

    def _pump(self):
        if self._pending is not None or not self._queue:
            return
        if self._proc.state() != QProcess.Running:
            return
        self._seq += 1
        cmd = self._queue.pop(0)
        self._pending = (self._seq, cmd)
        self._captured = []
        self.busy.emit(True)
        self._proc.write((self._wire(cmd, self._seq) + "\n").encode("utf-8", "replace"))

    # -- process plumbing ---------------------------------------------------

    def _on_started(self):
        self.started.emit()
        self._pump()

    def _on_ready_read(self):
        text = strip_ansi(bytes(self._proc.readAll()).decode("utf-8", "replace"))
        # Progress lines redraw with a bare CR; show each redraw as a line.
        text = self._partial + text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        self._partial = lines.pop()
        for ln in lines:
            self._handle_line(ln)

    def _handle_line(self, ln: str):
        mark = _MARK_RE.search(ln)
        if mark:
            if self._pending and int(mark.group("seq")) == self._pending[0]:
                _, cmd = self._pending
                self._pending = None
                self.command_finished.emit(cmd, "\n".join(self._captured))
                self._captured = []
                if self._queue:
                    self._pump()
                else:
                    self.busy.emit(False)
            return

        echo = _ECHO_RE.match(ln)
        if echo:
            state = echo.group("state").split("|", 1)[0].strip() or "offline"
            if state != self._last_state:
                self._last_state = state
            self.state.emit(state)
            if echo.group("cmd").startswith("rem " + _MARK):
                return
            self.line.emit(echo.group("cmd"), "echo")
            return

        if "cannot communicate with the Proxmark3" in ln:
            self._no_comms = True
        if self._pending is not None:
            self._captured.append(ln)
        self.line.emit(ln, "out")

    def _on_finished(self, code, _status):
        if self._partial:
            self.line.emit(self._partial, "out")
            self._partial = ""
        was_busy = self._pending is not None
        self._pending = None
        self._queue.clear()
        if was_busy:
            self.busy.emit(False)
        if self._no_comms:
            self._no_comms = False
            self.error.emit("The client opened the port but the device did not "
                            "answer. Usually the firmware on the Proxmark3 does "
                            "not match this client: flash it from this checkout "
                            "(pm3-flash-all), then reconnect.")
        self.stopped.emit(int(code))

    def _on_error(self, err):
        msg = self._proc.errorString()
        if err == QProcess.FailedToStart:
            msg = "Could not start %s: %s" % (self._exe, msg)
            if osutil.IS_WINDOWS:
                msg += (". On Windows, check the path points at proxmark3.exe "
                        "and that ProxSpace's msys2 folder is next to it or at "
                        "C:\\ProxSpace (its DLLs are needed).")
        self.error.emit(msg)
