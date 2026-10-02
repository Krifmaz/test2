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
# A single flat dark stylesheet. Colours live here so the look is consistent.
#-----------------------------------------------------------------------------

# Palette
BG0 = "#15171c"      # window
BG1 = "#1c1f27"      # panels
BG2 = "#242834"      # inputs / rows
BORDER = "#2f3440"
FG = "#e6e8ee"
MUTED = "#9aa3b2"
ACCENT = "#36c2a6"   # teal
ACCENT_DIM = "#2a8c79"
DANGER = "#e5534b"
CONSOLE_BG = "#101216"
CONSOLE_FG = "#d7dbe3"

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

QLabel#Title {{ font-size: 18px; font-weight: 600; }}
QLabel#Subtitle {{ color: {MUTED}; }}
QLabel#SectionHeader {{ color: {MUTED}; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }}
QLabel#OptHelp {{ color: {MUTED}; font-size: 12px; }}

QFrame#Panel {{ background: {BG1}; border: 1px solid {BORDER}; border-radius: 10px; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 6px 8px; selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: 0; width: 20px; }}
QComboBox QAbstractItemView {{ background: {BG2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_DIM}; }}

QPushButton {{
    background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ border: 1px solid {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#Primary {{ background: {ACCENT}; color: #06201b; border: 0; }}
QPushButton#Primary:hover {{ background: {ACCENT_DIM}; }}
QPushButton#Danger {{ border: 1px solid {DANGER}; color: {DANGER}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {BORDER};
    border-radius: 4px; background: {BG2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}

QTreeWidget, QListWidget {{ background: {BG1}; border: 1px solid {BORDER};
    border-radius: 10px; outline: 0; }}
QTreeWidget::item, QListWidget::item {{ padding: 4px 6px; border-radius: 5px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {ACCENT_DIM}; color: #06201b; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {BG2}; }}

QPlainTextEdit#Console {{
    background: {CONSOLE_BG}; color: {CONSOLE_FG}; border: 1px solid {BORDER};
    border-radius: 10px;
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

QTabBar::tab {{ background: transparent; padding: 8px 14px; color: {MUTED}; border: 0; }}
QTabBar::tab:selected {{ color: {FG}; border-bottom: 2px solid {ACCENT}; }}
QTabWidget::pane {{ border: 0; }}
"""
