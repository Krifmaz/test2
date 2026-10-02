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
# Owns a long-lived `proxmark3` client subprocess. Commands are written to
# the client's stdin one at a time; its merged stdout/stderr is streamed back
# and split into per-command blocks using the "[...] pm3 -->" prompt as the
# completion marker (see client/src/proxmark3.h PROXPROMPT_COMPOSE).
#-----------------------------------------------------------------------------

from __future__ import annotations

import re

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


# Strips ANSI SGR / cursor sequences so the console and prompt matcher see
# plain text regardless of whether the client emitted colour.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][AB012]|[\r\x07]")

# The interactive prompt the client prints when it is ready for input, e.g.
#   "[usb] pm3 --> "  "[offline] pm3 --> "  "[usb|tcp] pm5 --> "
_PROMPT_RE = re.compile(r"\[(?P<state>[^\]]*)\]\s*pm[35]\s*-->\s*$")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class Pm3Session(QObject):
    """A single interactive client session.

    Signals:
        output(str)          raw (ansi-stripped) text as it streams in
        prompt(str)          device state token at each prompt ("usb"/"offline"/...)
        command_finished(str, str)   (command, full captured output block)
        started()            client process is up
        stopped(int)         client exited, with exit code
        error(str)           spawn / pipe failure
    """

    output = Signal(str)
    prompt = Signal(str)
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
        self._proc.started.connect(self.started)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)

        self._buf = ""          # text seen since the last prompt
        self._pending = None     # command we are currently waiting on
        self._queue: list = []   # commands waiting for their turn
        self._ready = False      # at a prompt, free to send the next command
        self._last_state = "offline"

    # -- lifecycle ----------------------------------------------------------

    def start(self):
        args = []
        if self._port:
            args += [self._port]
        else:
            # No device: still useful for offline commands (demod, file ops).
            args += ["--offline"]
        # -f flushes output after every print so the GUI stays responsive.
        args += ["-f"] + self._extra
        env = QProcessEnvironment.systemEnvironment()
        # Ask the client not to use the pager; we scroll in the GUI.
        env.insert("PAGER", "cat")
        self._proc.setProcessEnvironment(env)
        self._proc.start(self._exe, args)

    def stop(self):
        if self._proc.state() != QProcess.NotRunning:
            # "quit" lets the client flush and close the device cleanly.
            self._write_line("quit")
            if not self._proc.waitForFinished(3000):
                self._proc.kill()

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.NotRunning

    def device_state(self) -> str:
        return self._last_state

    # -- sending commands ---------------------------------------------------

    def send(self, command: str):
        """Queue a command. It runs once the client is back at a prompt."""
        command = command.strip()
        if not command:
            return
        self._queue.append(command)
        self._pump()

    def interrupt(self):
        """Best-effort cancel of a long-running command (Ctrl-C to client)."""
        # QProcess has no portable SIGINT; closing the write channel and
        # sending an empty line nudges most blocking reader loops. Callers
        # that need a hard stop should stop()/start() the session.
        self._proc.write(b"\n")

    def _pump(self):
        if not self._ready or self._pending is not None:
            return
        if not self._queue:
            return
        self._pending = self._queue.pop(0)
        self._buf = ""
        self._ready = False
        self._write_line(self._pending)

    def _write_line(self, line: str):
        if self._proc.state() == QProcess.NotRunning:
            self.error.emit("Client is not running.")
            return
        self._proc.write((line + "\n").encode("utf-8", "replace"))

    # -- process plumbing ---------------------------------------------------

    def _on_ready_read(self):
        chunk = bytes(self._proc.readAll()).decode("utf-8", "replace")
        text = strip_ansi(chunk)
        if text:
            self.output.emit(text)
        self._buf += text
        self._drain_prompts()

    def _drain_prompts(self):
        # A prompt can arrive mid-buffer; process every complete line that
        # ends in the prompt marker.
        while True:
            m = None
            for cand in _PROMPT_RE.finditer(self._buf):
                m = cand
            if not m:
                # No prompt yet; keep buffering until more output arrives.
                return
            state = m.group("state").split("|", 1)[0].strip() or "offline"
            self._last_state = state
            self.prompt.emit(state)

            if self._pending is not None:
                block = self._buf[:m.start()]
                self.command_finished.emit(self._pending, block.strip("\n"))
                self._pending = None
            self._buf = self._buf[m.end():]
            self._ready = True
            self._pump()
            # Loop again in case the trailing buffer already holds another
            # prompt (queued commands echoed back-to-back).
            if self._pending is not None or not self._queue:
                return

    def _on_finished(self, code, _status):
        self._ready = False
        self.stopped.emit(int(code))

    def _on_error(self, _err):
        self.error.emit(self._proc.errorString())
