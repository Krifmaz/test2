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
# Entry point: python -m pm3gui [--client PATH] [--port DEV] [--commands FILE]
#-----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pm3gui",
        description="Modern Qt front-end for the Proxmark3 (Iceman) client.")
    parser.add_argument("--client", default="",
                        help="path to the proxmark3 client binary")
    parser.add_argument("--port", default="",
                        help="serial port to connect on launch (optional)")
    parser.add_argument("--commands", default="",
                        help="path to doc/commands.json (auto-detected if omitted)")
    args = parser.parse_args(argv)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "PySide6 is required. Install it with:\n"
            "    pip install -r client/gui/requirements.txt\n")
        return 2

    from .commands import CommandSet
    from .mainwindow import MainWindow
    from . import theme

    try:
        cmdset = CommandSet.load(args.commands or None)
    except FileNotFoundError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Proxmark3 Studio")
    app.setStyleSheet(theme.STYLESHEET)

    win = MainWindow(cmdset, client_exe=args.client)
    if args.port:
        win.port_combo.setEditText(args.port)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
