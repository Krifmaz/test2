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
# OS-specific bits: locating the client binary, the environment it needs to
# start (DLL search path on Windows), and serial port discovery.
#-----------------------------------------------------------------------------

from __future__ import annotations

import glob
import os
import shutil
import sys

IS_WINDOWS = sys.platform.startswith("win")
CLIENT_NAME = "proxmark3.exe" if IS_WINDOWS else "proxmark3"

# USB IDs, same as the pm3 launcher script: Proxmark3 (Iceman bootrom) and PM5.
PM3_USB_IDS = {(0x9AC4, 0x4B8F), (0x2D2D, 0x504D)}

# Default ProxSpace location used by the Windows install guide.
_PROXSPACE_DEFAULTS = [r"C:\ProxSpace"]


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", ".."))


def find_client() -> str:
    """Best guess at the client binary: this checkout's build, then PATH."""
    root = _repo_root()
    for c in (os.path.join(root, "client", CLIENT_NAME),
              os.path.join(root, "client", "build", CLIENT_NAME),
              os.path.join(root, CLIENT_NAME)):
        if os.path.isfile(c):
            return c
    for name in ("proxmark3", "pm3"):
        found = shutil.which(name)
        if found:
            return found
    return CLIENT_NAME


def resolve_client(path: str) -> str:
    """Absolute path of a usable client binary, or "" if `path` isn't one.

    Accepts a full path or a bare name on PATH. Rejects files that can't be
    the client (on Windows, anything but an .exe), so a stray pick in the
    file dialog or a stale saved setting never reaches QProcess.
    """
    path = (path or "").strip().strip('"')
    if not path:
        return ""
    if os.path.dirname(path):
        found = path if os.path.isfile(path) else ""
    else:
        found = shutil.which(path) or ""
    if not found:
        return ""
    if IS_WINDOWS and not found.lower().endswith(".exe"):
        return ""
    if not IS_WINDOWS and not os.access(found, os.X_OK):
        return ""
    return os.path.abspath(found)


def _proxspace_roots(exe: str) -> list:
    """ProxSpace folders: any parent of the client that holds msys2/, then defaults."""
    roots = []
    d = os.path.dirname(os.path.abspath(exe))
    while True:
        if os.path.isdir(os.path.join(d, "msys2")):
            roots.append(d)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for r in _PROXSPACE_DEFAULTS:
        if os.path.isdir(os.path.join(r, "msys2")) and r not in roots:
            roots.append(r)
    return roots


def dll_dirs(exe: str) -> list:
    """Folders a ProxSpace-built proxmark3.exe needs on PATH to load its DLLs.

    Outside the ProxSpace shell those DLLs (readline, lz4, Qt, ...) are not
    on PATH, so launching the exe directly fails with no output.
    """
    if not IS_WINDOWS:
        return []
    dirs = [os.path.dirname(os.path.abspath(exe))]
    for root in _proxspace_roots(exe):
        # ProxSpace builds the client in MINGW64. Never mix in ucrt64 DLLs
        # (e.g. from an ARM toolchain installed there): libstdc++ / libgcc
        # from the other runtime make the client die with "entry point not
        # found" before printing anything.
        for sub in ("mingw64", "ucrt64"):
            d = os.path.join(root, "msys2", sub, "bin")
            if os.path.isdir(d):
                dirs.append(d)
                break
        dirs.append(os.path.join(root, "msys2", "usr", "bin"))
    return [d for d in dirs if os.path.isdir(d)]


def client_env(exe: str, base: dict = None) -> dict:
    """Environment for the client process, as a plain dict."""
    env = dict(os.environ if base is None else base)
    extra = dll_dirs(exe)
    if extra:
        env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    # The client keeps prefs/logs in $HOME/.proxmark3 and falls back to its
    # working directory without $HOME, which Windows does not set (outside
    # ProxSpace). A GUI launched from a shortcut may sit in System32.
    if not env.get("HOME"):
        env["HOME"] = user_home().replace("\\", "/")
    return env


def user_home() -> str:
    """Folder to run the client in, so its default save paths are sensible."""
    return os.path.expanduser("~")


def list_ports() -> list:
    """[(port, label, is_pm3)], Proxmark3 devices first.

    `port` is what the client expects: "COM5" on Windows, a /dev path elsewhere.
    """
    ports = []
    try:
        from PySide6.QtSerialPort import QSerialPortInfo
        for info in QSerialPortInfo.availablePorts():
            port = info.portName() if IS_WINDOWS else info.systemLocation()
            ids = (info.vendorIdentifier(), info.productIdentifier()) \
                if info.hasVendorIdentifier() and info.hasProductIdentifier() else None
            is_pm3 = ids in PM3_USB_IDS
            desc = info.description() or info.manufacturer() or ""
            label = port + ("  \u2014  Proxmark3" if is_pm3 else
                            ("  \u2014  " + desc if desc else ""))
            ports.append((port, label, is_pm3))
    except ImportError:
        pass
    if not ports and not IS_WINDOWS:
        for pat in ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/tty.usbmodem*",
                    "/dev/cu.usbmodem*"):
            for p in sorted(glob.glob(pat)):
                ports.append((p, p, False))
    # Proxmark3 first, then by name; drop the noise of legacy ttyS* ports.
    ports = [p for p in ports if p[2] or not os.path.basename(p[0]).startswith("ttyS")]
    ports.sort(key=lambda p: (not p[2], p[0]))
    return ports
