from __future__ import annotations

APP_STYLESHEET = """
QMainWindow, QWidget#AppRoot {
    background-color: #02080d;
    color: #d9fbff;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QPushButton {
    background-color: rgba(7, 37, 48, 235);
    color: #b9f6ff;
    border: 1px solid #17677a;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 650;
}
QPushButton:hover {
    background-color: rgba(10, 68, 83, 245);
    border-color: #32d9f5;
}
QPushButton:pressed, QPushButton:checked {
    background-color: rgba(0, 163, 195, 85);
    border-color: #5cecff;
    color: white;
}
QLineEdit {
    background-color: #06141c;
    border: 1px solid #155064;
    border-radius: 9px;
    color: #e7fdff;
    padding: 10px 12px;
    selection-background-color: #087d92;
}
QLineEdit:focus {
    border-color: #34ddf8;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #031016;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #17677a;
    min-height: 32px;
    border-radius: 4px;
}
QLabel#TransientStatus {
    color: rgba(139, 238, 255, 205);
    font-size: 12px;
    font-weight: 650;
    letter-spacing: 2px;
    padding: 9px 18px;
}
QLineEdit#DebugCommand {
    background-color: rgba(3, 17, 28, 235);
    border: 1px solid #1ccde9;
    border-radius: 18px;
    color: #ddfbff;
    padding: 11px 18px;
}
QFrame#FloatingHologram {
    background-color: transparent;
    border: none;
}
QFrame#FloatingHologram[selected="true"] {
    background-color: transparent;
    border: none;
}
QFrame#ResearchPanel {
    background-color: transparent;
    border: none;
}
QLabel#ResearchSystem {
    color: #6cecff;
    font-size: 10px;
    font-weight: 750;
    letter-spacing: 2px;
}
QLabel#ResearchState {
    color: #8d72ff;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#ResearchQuery {
    color: #e5fdff;
    font-size: 18px;
    font-weight: 720;
    letter-spacing: 1px;
}
QFrame#ResearchDivider {
    background-color: rgba(46, 218, 255, 95);
    border: none;
}
QScrollArea#ResearchScroll, QScrollArea#ResearchScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QLabel#ResearchAnswer {
    color: rgba(196, 246, 255, 225);
    font-size: 12px;
    line-height: 1.4;
}
QLabel#ResearchSourcesTitle {
    color: rgba(110, 225, 246, 180);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    padding-top: 6px;
}
QPushButton#ResearchSource {
    background-color: rgba(12, 58, 78, 130);
    color: #b9f7ff;
    border: 1px solid rgba(40, 204, 237, 105);
    border-radius: 8px;
    padding: 9px 11px;
    text-align: left;
    font-size: 11px;
}
QPushButton#ResearchSource:hover {
    background-color: rgba(24, 102, 132, 165);
    border-color: #59e8ff;
}
QPushButton#ResearchClose {
    background-color: rgba(48, 20, 85, 120);
    color: #bdaeff;
    border: 1px solid rgba(131, 95, 255, 140);
    border-radius: 15px;
    padding: 0;
    font-size: 19px;
}
QPushButton#ResearchClose:hover {
    background-color: rgba(117, 51, 173, 150);
    border-color: #d2c7ff;
}
QLabel#ResearchMeta {
    color: rgba(88, 178, 196, 180);
    font-size: 9px;
    letter-spacing: 1px;
}
"""
