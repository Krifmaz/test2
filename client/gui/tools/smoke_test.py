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

from pm3gui import clone, osutil, theme  # noqa: E402
from pm3gui.commands import CommandSet  # noqa: E402
from pm3gui.mainwindow import MainWindow  # noqa: E402
from pm3gui.session import Pm3Session  # noqa: E402
from pm3gui.widgets.easymode import EasyMode  # noqa: E402
from pm3gui.widgets.formbuilder import CommandForm  # noqa: E402

# Real/representative `lf search` outputs for the offline clone-parser checks.
HID_SEARCH = """
[+] [H10301  ] HID H10301 26-bit                FC: 34  CN: 31568  parity ( ok )
[=] raw: 00000000000000200644f6a0
[+] Valid HID Prox ID found!
[+] Chipset... T55xx
"""
EM410X_SEARCH = """
[+] EM 410x ID 1234567890
[+] Valid EM410x ID found!
[+] Chipset... T55xx
"""
AWID_SEARCH = """
[+] AWID - len: 26 FC: 12 Card: 3456 - Wiegand: ..., Raw: 011db399300000000000
[+] Valid AWID ID found!
"""
BLANK_SEARCH = """
[-] No known 125/134 kHz tags found!
[+] Chipset... T55xx
[?] Hint: Try `lf t55xx` commands
"""
NOTHING_SEARCH = "[-] No known 125/134 kHz tags found!\n"
BLANK_EM_SEARCH = """
[-] No known 125/134 kHz tags found!
[+] Chipset... EM4x05 / EM4x69
"""
HF_MFC_SEARCH = """
[+] UID: 04 11 22 33
[+] ATQA: 00 04
[+]  SAK: 08 [2]
[+] MIFARE Classic 1K
[+] Valid ISO 14443-A tag found
"""
HF_DESFIRE_SEARCH = """
[+] MIFARE DESFire EV2
[+] Valid ISO 14443-A tag found
"""
HF_ICLASS_SEARCH = "[+] Valid iCLASS tag / PicoPass tag found\n"
HF_NONE_SEARCH = "[-] No known/supported 13.56 MHz tags found!\n"


def check_clone(check):
    m = clone.detect(HID_SEARCH)
    check(len(m) == 1 and m[0].label == "HID Prox", "clone: HID recognised")
    check(m and m[0].command == "lf hid clone -r 200644f6a0",
          "clone: HID command (leading zeros trimmed)")
    m = clone.detect(EM410X_SEARCH)
    check(m and m[0].command == "lf em 410x clone --id 1234567890",
          "clone: EM410x command")
    m = clone.detect(AWID_SEARCH)
    check(m and m[0].command == "lf awid clone --fmt 26 --fc 12 --cn 3456",
          "clone: AWID fields")
    check(clone.detect(NOTHING_SEARCH) == [], "clone: nothing when no tag")
    check(clone.is_blank_t55xx(BLANK_SEARCH) is True, "clone: blank T5577")
    check(not clone.is_blank_t55xx(HID_SEARCH), "clone: HID is not blank")
    # Target chip detection drives the clone flag.
    check(clone.target_chip(BLANK_SEARCH) == "t5577", "target: T5577 chip")
    check(clone.target_chip(BLANK_EM_SEARCH) == "em4x05", "target: EM4x05 chip")
    check(clone.target_chip(NOTHING_SEARCH) == "", "target: none when no chip")
    base = "lf hid clone -r 200644f6a0"
    check(clone.apply_target(base, "t5577") == base, "target: T5577 no --em")
    check(clone.apply_target(base, "em4x05") == base + " --em",
          "target: EM4x05 adds --em")
    check(clone.apply_target(base + " --em", "em4x05") == base + " --em",
          "target: --em not doubled")
    # HF identification (identify-only, never auto-cloned).
    hf = clone.detect_hf(HF_MFC_SEARCH)
    check(hf and hf.label == "MIFARE Classic 1K" and hf.security == "weak",
          "hf: MIFARE Classic 1K, weak")
    hf = clone.detect_hf(HF_DESFIRE_SEARCH)
    check(hf and "DESFire" in hf.label and hf.security == "strong",
          "hf: DESFire strong")
    hf = clone.detect_hf(HF_ICLASS_SEARCH)
    check(hf and hf.security == "varies", "hf: iCLASS varies")
    check(clone.detect_hf(HF_NONE_SEARCH) is None, "hf: none when no tag")
    # HF copy plans: which family is copyable, and the dump/restore commands.
    check(clone.detect_hf(HF_MFC_SEARCH).clone == "mfc", "hf: MFC is copyable")
    check(clone.detect_hf(HF_DESFIRE_SEARCH).clone == "",
          "hf: DESFire not copyable")
    check(clone.hf_dump_cmd("mfc") == "hf mf autopwn", "hf: MFC dump cmd")
    # Magic generation picks cload (gen1a) vs restore (gen2); non-magic -> none.
    gen1a = "[?] Hint: Use `hf mf c*` magic commands\n"
    gen2 = "[?] Hint: Use `hf mf` commands\n"
    plain = "[?] Hint: Try `hf mf info`\n"
    check(clone.magic_gen(gen1a) == "gen1a", "hf: gen1a detected (14a hint)")
    check(clone.magic_gen(gen2) == "gen2", "hf: gen2 detected (14a hint)")
    check(clone.magic_gen(plain) == "", "hf: non-magic detected")
    # `hf mf info`'s explicit capability line (real output from a Fudan gen1a).
    mfinfo = ("[+] Magic capabilities... Gen 1a\n"
              "[+] Magic capabilities... Gen 4 GDM / USCUID\n")
    check(clone.magic_gen(mfinfo) == "gen1a", "hf: gen1a from hf mf info")
    check(clone.magic_gen("[+] Magic capabilities... Gen 2\n") == "gen2",
          "hf: gen2 from hf mf info")
    check(clone.magic_write_cmd("mfc", gen1a, "d.json") == "hf mf cload -f d.json",
          "hf: gen1a uses cload")
    check(clone.magic_write_cmd("mfc", gen2, "d.json") == "hf mf restore -f d.json",
          "hf: gen2 uses restore")
    check(clone.magic_write_cmd("mfc", plain, "d.json") == "",
          "hf: non-magic refuses write")
    check(clone.magic_write_cmd("mfu", "", "a.json") == "hf mfu restore -f a.json",
          "hf: MFU restore cmd")
    check(clone.saved_file("[+] Saved to json file hf-mf-04-dump.json")
          == "hf-mf-04-dump.json", "hf: json dump filename parsed")
    check(clone.saved_file("[+] Saved 320 bytes to binary file `d.bin`")
          == "d.bin", "hf: binary dump filename parsed")


def check_easymode(check):
    easy = EasyMode()
    sent = []
    easy.run_requested.connect(sent.append)
    easy.set_connected(True)
    easy._do_read()
    check(sent == ["lf search"], "easy: read issues lf search")
    easy.command_finished("lf search", HID_SEARCH)
    check(easy._clone_cmd == "lf hid clone -r 200644f6a0",
          "easy: read builds clone command")
    check(easy.write_btn.isEnabled(), "easy: write enabled after clonable read")
    # A blank read leaves nothing to write.
    easy._do_read()
    easy.command_finished("lf search", BLANK_SEARCH)
    check(not easy.write_btn.isEnabled(), "easy: write disabled on blank read")
    # No LF card -> Easy mode falls through to an HF search.
    sent.clear()
    easy._do_read()
    easy.command_finished("lf search", NOTHING_SEARCH)
    check(sent[-1] == "hf search", "easy: no LF card triggers hf search")
    easy.command_finished("hf search", HF_MFC_SEARCH)
    check("MIFARE Classic 1K" in easy.result.text(),
          "easy: HF card identified in result")
    check(easy.write_btn.isEnabled() and easy._hf_family == "mfc",
          "easy: HF MIFARE Classic is copyable")
    check(not easy._clone_cmd, "easy: HF copy sets no LF clone command")
    # A strong HF card is identified but not copyable.
    easy._do_read()
    easy.command_finished("lf search", NOTHING_SEARCH)
    easy.command_finished("hf search", HF_DESFIRE_SEARCH)
    check(not easy.write_btn.isEnabled(), "easy: DESFire not copyable")
    # Disconnected: every action is disabled.
    easy.set_connected(False)
    check(not easy.read_btn.isEnabled(), "easy: read disabled when offline")

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

    check_clone(check)
    check_easymode(check)

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
    check(not any("Could not create user directory" in ln for ln in lines),
          "client has a writable user directory")

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

    check(osutil.resolve_client(args.client) != "", "client path resolves")
    junk = os.path.join(tempfile.mkdtemp(), "preferences.json")
    with open(junk, "w") as fh:
        fh.write("{}")
    check(osutil.resolve_client(junk) == "" if osutil.IS_WINDOWS else True,
          "non-program rejected as client")
    check(osutil.resolve_client("no_such_dir/proxmark3.exe") == "",
          "missing client rejected")

    win = MainWindow(cs, client_exe=args.client)
    win.resize(1400, 880)
    win.show()
    app.processEvents()

    # A stale/wrong client path must fall back to the real client.
    win.exe_edit.setText(junk if osutil.IS_WINDOWS else "proxmark3_missing")
    win.port_combo.setEditText("")
    win.start_connection()
    ok = win.session is not None and wait_until(app, win.session.is_running, 15)
    check(ok and os.path.samefile(win.exe_edit.text(), args.client),
          "bad client path falls back to the built client")
    if win.session:
        win.session.stop()
    if args.shot:
        win.grab().save(args.shot)
        print("screenshot:", args.shot)
    win.close()

    print("\n%d failure(s)" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
