#!/usr/bin/env python3
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
# Headless end-to-end check of pm3gui against a real built client, offline.
# Usage: python3 tools/smoke_test.py --client ../proxmark3[.exe] [--shot out.png]
#-----------------------------------------------------------------------------

import argparse
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from pm3gui import osutil, theme  # noqa: E402
from pm3gui.commands import CommandSet  # noqa: E402
from pm3gui.mainwindow import MainWindow  # noqa: E402
from pm3gui.session import Pm3Session  # noqa: E402
from pm3gui.widgets.formbuilder import CommandForm  # noqa: E402

# Waits for Enter (what the GUI's Stop sends), with a timeout so it can't hang.
WAIT_ENTER_LUA = """
print("waiting for enter")
local t0 = os.clock()
while not core.kbd_enter_pressed() do
    if os.clock() - t0 > 20 then
        print("timed out")
        return
    end
end
print("stopped by enter")
"""

failures = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what, flush=True)
    if not cond:
        failures.append(what)


def wait_until(app, pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default=osutil.find_client())
    ap.add_argument("--shot", default="")
    ap.add_argument("--strip-path", action="store_true",
                    help="drop ProxSpace/msys2 dirs from PATH first, to prove "
                         "the GUI finds the client's DLLs on its own")
    args = ap.parse_args()

    if args.strip_path:
        keep = [p for p in os.environ.get("PATH", "").split(os.pathsep)
                if "msys2" not in p.lower() and "proxspace" not in p.lower()]
        os.environ["PATH"] = os.pathsep.join(keep)
        print("PATH stripped; DLL dirs the GUI will add:", osutil.dll_dirs(args.client))

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(theme.STYLESHEET)

    cs = CommandSet.load()
    check(len(cs.commands) > 500, "loaded %d commands" % len(cs.commands))
    bad = 0
    for c in cs.commands:
        try:
            CommandForm(c, cs)
        except Exception as exc:  # report every broken form, keep going
            bad += 1
            print("  form error:", c.name, exc)
    check(bad == 0, "all command forms build")

    ports = osutil.list_ports()
    check(isinstance(ports, list), "port scan ok (%d found)" % len(ports))

    s = Pm3Session(args.client, "")
    lines, done, errors = [], [], []
    s.line.connect(lambda t, k: lines.append(t))
    s.command_finished.connect(lambda c, o: done.append(c))
    s.error.connect(errors.append)
    s.start()
    check(wait_until(app, s.is_running, 15), "client started: " + args.client)
    if errors:
        print("  errors:", errors)

    s.send("prefs show")
    s.send("rem hello from smoke test")
    check(wait_until(app, lambda: len(done) >= 2, 30), "commands complete in order")
    check(done[:2] == ["prefs show", "rem hello from smoke test"], "completion order")
    check(s.device_state() == "offline", "device state offline (%s)" % s.device_state())
    check(not any("__pm3gui" in ln for ln in lines), "no internal markers in output")
    check(any("hello from smoke test" in ln for ln in lines), "command output captured")

    check(s.send("rem " + "x" * 400) is False, "over-long command rejected")

    tmp = os.path.join(tempfile.mkdtemp(), "pm3gui_waitenter.lua")
    with open(tmp, "w") as fh:
        fh.write(WAIT_ENTER_LUA)
    n = len(done)
    s.send("script run " + tmp)
    check(wait_until(app, lambda: any("waiting for enter" in ln for ln in lines), 20),
          "wait-for-enter script running")
    s.interrupt()
    t0 = time.time()
    stopped = wait_until(app, lambda: len(done) > n, 10)
    check(stopped and any("stopped by enter" in ln for ln in lines),
          "Stop interrupts a running command (%.2fs)" % (time.time() - t0))

    s.stop()
    check(wait_until(app, lambda: not s.is_running(), 10), "client quits cleanly")

    win = MainWindow(cs, client_exe=args.client)
    win.resize(1400, 880)
    win.show()
    app.processEvents()
    if args.shot:
        win.grab().save(args.shot)
        print("screenshot:", args.shot)
    win.close()

    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
