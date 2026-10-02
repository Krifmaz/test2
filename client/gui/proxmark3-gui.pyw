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
# Double-click launcher for Windows: .pyw runs under pythonw, so no console
# window opens alongside the GUI.
#-----------------------------------------------------------------------------

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pm3gui.__main__ import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
