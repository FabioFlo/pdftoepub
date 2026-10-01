"""Explicit desktop colours, independent of the native control palette."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

COLOURS = {
    "light": dict(bg="#f2f4f3", panel="#ffffff", text="#203438", muted="#526663",
                  border="#cbd7d2", accent="#216e62", hover="#edf6f1", selection="#dcefe6",
                  alternate="#f5f8f6", disabled="#687a73", inactive="#e8eeea", canvas="#e9eeeb"),
    "dark": dict(bg="#171e1d", panel="#222c29", text="#edf3ef", muted="#b3c4bb",
                 border="#53675d", accent="#83d1b1", hover="#31443b", selection="#365747",
                 alternate="#28332e", disabled="#99aaa0", inactive="#2c3831", canvas="#121916"),
}


def resolve_theme(choice, scheme):
    if choice in ("light", "dark"):
        return choice
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def palette_for(theme):
    c = COLOURS[theme]
    palette = QPalette()
    roles = {"Window": "bg", "WindowText": "text", "Base": "panel", "AlternateBase": "alternate",
             "Text": "text", "Button": "panel", "ButtonText": "text", "ToolTipBase": "panel",
             "ToolTipText": "text", "Highlight": "selection", "HighlightedText": "text",
             "Link": "accent", "PlaceholderText": "muted", "Light": "border", "Mid": "border",
             "Dark": "canvas"}
    for role, key in roles.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(c[key]))
    for role in ("WindowText", "Text", "ButtonText", "PlaceholderText"):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor(c["disabled"]))
    return palette


def stylesheet(theme):
    c = COLOURS[theme]
    return """
QWidget { color: %(text)s; font-size: 13px; }
QMainWindow, QWidget#root { background: %(bg)s; }
QLabel#brand { font-size: 26px; font-weight: 700; }
QLabel#eyebrow { color: %(accent)s; font-size: 12px; font-weight: 600; }
QLabel#muted { color: %(muted)s; }
QFrame#panel { background: %(panel)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#header { background: transparent; }
QWidget#preferences { background: %(panel)s; }
QLineEdit, QComboBox { padding: 8px; border: 1px solid %(border)s; border-radius: 5px; background: %(panel)s; color: %(text)s; selection-background-color: %(selection)s; selection-color: %(text)s; }
QLineEdit:focus, QComboBox:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; selection-background-color: %(selection)s; selection-color: %(text)s; outline: 0; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 4px 8px; }
QPushButton { padding: 9px 14px; border: 1px solid %(border)s; border-radius: 6px; background: %(panel)s; color: %(text)s; font-weight: 600; }
QPushButton:hover, QPushButton:checked { background: %(hover)s; border-color: %(accent)s; }
QPushButton:focus { border-color: %(accent)s; }
QPushButton#primary { background: %(accent)s; color: %(bg)s; border-color: %(accent)s; }
QPushButton#primary:hover { background: %(accent)s; border-color: %(text)s; }
QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled { background: %(inactive)s; color: %(disabled)s; border-color: %(border)s; }
QLabel:disabled, QCheckBox:disabled { color: %(disabled)s; }
QProgressBar { border: 0; border-radius: 4px; background: %(inactive)s; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 4px; }
QTreeWidget { border: 0; background: %(panel)s; alternate-background-color: %(alternate)s; color: %(text)s; }
QTreeWidget::item { padding: 6px; }
QTreeWidget::item:selected { background: %(selection)s; color: %(text)s; }
QHeaderView::section { background: %(alternate)s; padding: 7px; border: 0; color: %(muted)s; }
QTextBrowser#document { border: 0; background: white; color: #223338; font-size: 16px; }
QScrollArea { border: 0; background: %(canvas)s; }
QCheckBox { spacing: 8px; }
QScrollBar:vertical { background: %(inactive)s; width: 12px; margin: 0; }
QScrollBar:horizontal { background: %(inactive)s; height: 12px; margin: 0; }
QScrollBar::handle { background: %(border)s; border-radius: 5px; min-height: 28px; min-width: 28px; }
QScrollBar::handle:hover { background: %(muted)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; padding: 6px; }
QSplitter::handle { background: transparent; width: 10px; }
""" % c
