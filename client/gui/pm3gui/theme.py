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
# OLED-black theme with a pastel ROYGBIV accent set. True black (#000) so the
# window goes dark on OLED panels; panels are barely lifted off black.
#-----------------------------------------------------------------------------

# Pastel ROYGBIV
RED = "#ff9aa2"
ORANGE = "#ffc49b"
YELLOW = "#ffe7a3"
GREEN = "#a7e8a0"
BLUE = "#a6d4ff"
INDIGO = "#b4acf2"
VIOLET = "#e3b0ff"
ROYGBIV = [RED, ORANGE, YELLOW, GREEN, BLUE, INDIGO, VIOLET]

# Surfaces
BG0 = "#000000"      # window — true black
BG1 = "#0b0c0e"      # panels
BG2 = "#15171b"      # inputs / rows
BG3 = "#1d2026"      # hover
BORDER = "#23262d"
FG = "#eef0f4"
MUTED = "#8b93a1"
ACCENT = BLUE        # primary accent
ACCENT_INK = "#06121f"   # text on top of a pastel fill
DANGER = RED
CONSOLE_BG = "#000000"
CONSOLE_FG = "#c9cdd6"


def group_color(name: str) -> str:
    """Stable pastel for a top-level command group (hf, lf, data, ...)."""
    if not name:
        return MUTED
    return ROYGBIV[sum(name.encode("utf-8")) % len(ROYGBIV)]


STYLESHEET = f"""
* {{
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {FG};
}}
QMainWindow, QWidget {{ background: {BG0}; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QLabel#Title {{ font-size: 18px; font-weight: 700; }}
QLabel#Subtitle {{ color: {MUTED}; }}
QLabel#SectionHeader {{ color: {MUTED}; font-weight: 700; font-size: 11px; letter-spacing: 1px; }}
QLabel#OptHelp {{ color: {MUTED}; font-size: 12px; }}
QLabel#Crumb {{ color: {ACCENT}; font-size: 12px; }}

QFrame#Panel {{ background: {BG1}; border: 1px solid {BORDER}; border-radius: 12px; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {BG2}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 6px 9px; selection-background-color: {ACCENT}; selection-color: {ACCENT_INK};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit:read-only {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: 0; width: 20px; }}
QComboBox QAbstractItemView {{ background: {BG2}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; selection-color: {ACCENT_INK}; }}

QPushButton {{
    background: {BG2}; border: 1px solid {BORDER}; border-radius: 7px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ border: 1px solid {ACCENT}; background: {BG3}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {BORDER}; background: {BG1}; }}
QPushButton#Primary {{ background: {ACCENT}; color: {ACCENT_INK}; border: 0; }}
QPushButton#Primary:hover {{ background: {GREEN}; }}
QPushButton#Danger {{ border: 1px solid {DANGER}; color: {DANGER}; background: {BG2}; }}
QPushButton#Danger:hover {{ background: {DANGER}; color: {ACCENT_INK}; }}
QPushButton#Example {{ text-align: left; font-weight: 400; color: {ACCENT};
    font-family: "JetBrains Mono", "Cascadia Code", "DejaVu Sans Mono", "Menlo", monospace;
    font-size: 12px; padding: 5px 10px; }}
QPushButton#Example:hover {{ color: {ACCENT_INK}; background: {ACCENT}; border-color: {ACCENT}; }}
QPushButton#Quick {{ text-align: left; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER};
    border-radius: 4px; background: {BG2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}

QTreeWidget, QListWidget {{ background: {BG1}; border: 1px solid {BORDER};
    border-radius: 12px; outline: 0; }}
QTreeWidget::item, QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {BG3}; color: {FG}; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {BG2}; }}
QHeaderView::section {{ background: {BG1}; color: {MUTED}; border: 0;
    border-bottom: 1px solid {BORDER}; padding: 6px; font-weight: 700; }}

QPlainTextEdit#Console {{
    background: {CONSOLE_BG}; color: {CONSOLE_FG}; border: 1px solid {BORDER};
    border-radius: 12px;
    font-family: "JetBrains Mono", "Cascadia Code", "DejaVu Sans Mono", "Menlo", monospace;
    font-size: 12.5px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}

QStatusBar {{ background: {BG1}; border-top: 1px solid {BORDER}; }}
QStatusBar QLabel {{ color: {MUTED}; }}
QLabel#Dot {{ font-size: 15px; }}

QTabBar::tab {{ background: transparent; padding: 8px 14px; color: {MUTED}; border: 0; }}
QTabBar::tab:selected {{ color: {FG}; border-bottom: 2px solid {ACCENT}; }}
QTabWidget::pane {{ border: 0; }}

QToolTip {{ background: {BG2}; color: {FG}; border: 1px solid {BORDER}; padding: 4px; }}
"""

# Console line colours by semantic kind (matched from the client's [x] tags).
CONSOLE_COLORS = {
    "echo": ACCENT,
    "success": GREEN,     # [+]
    "error": RED,         # [!!] [-]
    "warn": YELLOW,       # [!]
    "info": BLUE,         # [=] [#]
    "sys": MUTED,
    "out": CONSOLE_FG,
}
