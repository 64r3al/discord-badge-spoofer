#!/usr/bin/env python3
"""IVX Discord Lab — modern desktop UI for local profile inventory and safe exports.

This UI intentionally does not read credential stores or submit activity telemetry.
The existing spoofer.py is kept separate and is not invoked by this application.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from game_catalog import FALLBACK_GAMES, fetch_detectable_games
from session_inventory import build_inventory, write_csv_report


APP_NAME = "IVX Discord Lab"
APP_VERSION = "1.3.1"

STYLESHEET = """
QMainWindow, QWidget#appRoot { background: #0a0c11; color: #e7eaf2; }
QWidget { color: #e7eaf2; font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; }
QWidget#sidebar { background: #0d1017; border-right: 1px solid #202532; }
QLabel#brandMark {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #8b5cf6,stop:1 #4f46e5);
    color: white; border-radius: 12px; font-size: 18px; font-weight: 800;
}
QLabel#brandName { font-size: 16px; font-weight: 800; letter-spacing: 1px; color: #f9fafb; }
QLabel#brandSub { color: #858da2; font-size: 10px; letter-spacing: 1.4px; }
QLabel#pageTitle { font-size: 25px; font-weight: 750; color: #f6f7fb; }
QLabel#pageSubtitle { color: #8e97aa; font-size: 12px; }
QLabel#muted { color: #9199ad; }
QLabel#tinyLabel { color: #858da2; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }
QLabel#metricValue { font-size: 29px; font-weight: 800; color: #f9fafb; }
QLabel#metricLabel { color: #929bb0; font-size: 12px; }
QFrame#card {
    background: #11151e; border: 1px solid #242a38; border-radius: 16px;
}
QFrame#hero {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #17182b,stop:0.58 #151a2b,stop:1 #10202c);
    border: 1px solid #34314f; border-radius: 18px;
}
QLabel#heroTitle { font-size: 23px; font-weight: 750; color: #ffffff; }
QLabel#heroCopy { font-size: 13px; color: #aab3c8; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #f0f2f8; }
QLabel#sectionHint { font-size: 11px; color: #8791a7; }
QPushButton {
    background: #191f2c; color: #dce1ec; border: 1px solid #2b3446;
    border-radius: 9px; padding: 10px 14px; font-weight: 650;
}
QPushButton:hover { background: #222a3b; border-color: #4b5872; }
QPushButton:pressed { background: #151a25; }
QPushButton:disabled { color: #646d80; background: #141820; border-color: #222633; }
QPushButton#primaryButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8b5cf6,stop:1 #6366f1);
    color: white; border: 1px solid #9877fa; padding: 11px 16px;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #9a70ff,stop:1 #7375ff);
    border-color: #b09aff;
}
QPushButton#navButton {
    background: transparent; color: #8f98ad; border: 1px solid transparent;
    text-align: left; padding: 12px 13px; font-weight: 600;
}
QPushButton#navButton:hover { background: #151b27; color: #e8ebf4; }
QPushButton#navButton[selected="true"] {
    background: #1a1b30; color: #cfc4ff; border: 1px solid #37315b;
}
QPushButton#quietButton {
    background: transparent; border: 1px solid #2b3446; color: #bac3d4;
}
QLineEdit {
    background: #0d1119; color: #e8ebf4; border: 1px solid #2a3242;
    border-radius: 10px; padding: 11px 13px; selection-background-color: #6850bb;
}
QLineEdit:focus { border-color: #8b5cf6; }
QTableWidget {
    background: #10141c; alternate-background-color: #121823;
    border: 1px solid #252c3a; border-radius: 12px; gridline-color: #252c3a;
    selection-background-color: #282443; selection-color: #f4f1ff;
}
QTableWidget::item { padding: 8px; border-bottom: 1px solid #202633; }
QHeaderView::section {
    background: #151a24; color: #919bb0; font-weight: 700; font-size: 10px;
    letter-spacing: 0.8px; text-transform: uppercase; border: none;
    border-bottom: 1px solid #2a3140; padding: 11px 8px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0d1118; width: 9px; margin: 4px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #31394a; min-height: 25px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #515c75; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def make_label(text: str, object_name: str = "") -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def make_card(parent: QWidget | None = None) -> QFrame:
    card = QFrame(parent)
    card.setObjectName("card")
    shadow = QGraphicsDropShadowEffect(card)
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 5)
    shadow.setColor(QColor(0, 0, 0, 36))
    card.setGraphicsEffect(shadow)
    return card


def clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def discord_process_status() -> tuple[bool | None, str]:
    """Check for a running Discord desktop process on Windows without reading account data."""
    if sys.platform != "win32":
        return None, "Automatic process detection is available on Windows only."

    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "Windows could not provide a process list."

    if result.returncode != 0:
        return None, "Windows process detection did not complete."

    try:
        process_names = {
            row[0].strip().casefold()
            for row in csv.reader(result.stdout.splitlines())
            if row
        }
    except csv.Error:
        return None, "Windows returned an unreadable process list."

    known_names = {"discord.exe", "discordptb.exe", "discordcanary.exe"}
    running = sorted(process_names.intersection(known_names))
    return (True, ", ".join(running)) if running else (False, "")


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", accent: str = "#8b5cf6") -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 17)
        layout.setSpacing(8)
        accent_bar = QFrame()
        accent_bar.setFixedSize(32, 3)
        accent_bar.setStyleSheet(f"background:{accent}; border-radius:1px; border:none;")
        layout.addWidget(accent_bar)
        self.value_label = make_label(value, "metricValue")
        self.title_label = make_label(label, "metricLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)

    def set_value(self, value: str | int) -> None:
        self.value_label.setText(str(value))


class GameCatalogWorker(QThread):
    """Fetch public game names/executable metadata without blocking the UI."""

    catalog_ready = Signal(object, str, str)

    def run(self) -> None:
        games, source, message = fetch_detectable_games()
        self.catalog_ready.emit(games, source, message)


_ACTIVE_CATALOG_WORKERS: set[GameCatalogWorker] = set()


def _release_game_catalog_worker(worker: GameCatalogWorker) -> None:
    _ACTIVE_CATALOG_WORKERS.discard(worker)
    worker.deleteLater()


class MainWindow(QMainWindow):
    def __init__(self, auto_fetch_catalog: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} · {APP_VERSION}")
        self.resize(1260, 840)
        self.setMinimumSize(1020, 700)
        self.setStyleSheet(STYLESHEET)
        self.scan_completed = False
        self.report: dict[str, Any] = {
            "report_type": "local-session-inventory",
            "discord_clients": [],
            "browser_profiles": [],
            "limitations": [],
        }
        self.profile_rows: list[dict[str, str]] = []
        self.nav_buttons: list[QPushButton] = []
        self.activity_catalog: list[dict[str, str]] = [dict(game) for game in FALLBACK_GAMES]
        self.activity_catalog_by_id: dict[str, dict[str, str]] = {
            game["id"]: game for game in self.activity_catalog
        }
        self.activity_selected_game_ids: set[str] = set()
        self.activity_catalog_source = "Built-in fallback"
        self.activity_catalog_worker: GameCatalogWorker | None = None
        self.auto_fetch_catalog = auto_fetch_catalog
        self.activity_schedule: list[tuple[str, int]] = []
        self.activity_tick = 0
        self.activity_total_ticks = 0
        self.activity_current_game = -1
        self.activity_paused = False
        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(300)
        self.activity_timer.timeout.connect(self._activity_simulation_tick)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 23, 28, 22)
        content_layout.setSpacing(20)
        content_layout.addWidget(self._build_topbar())

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        self.pages.setStyleSheet("QStackedWidget#pageStack { background: #0a0c11; border: none; }")
        self.pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pages.addWidget(self._scroll_page(self._build_overview_page()))
        self.pages.addWidget(self._scroll_page(self._build_profiles_page()))
        self.pages.addWidget(self._scroll_page(self._build_badges_page()))
        self.pages.addWidget(self._scroll_page(self._build_activity_lab_page()))
        self.pages.addWidget(self._scroll_page(self._build_exports_page()))
        self.pages.addWidget(self._scroll_page(self._build_about_page()))
        content_layout.addWidget(self.pages, 1)
        content_layout.addWidget(self._build_footer())
        root_layout.addWidget(content, 1)

        self._animate_count = 0
        QTimer.singleShot(120, self.refresh_inventory)
        if self.auto_fetch_catalog:
            QTimer.singleShot(450, self.fetch_activity_catalog)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(226)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(17, 22, 17, 18)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_icon = make_label("IV", "brandMark")
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setFixedSize(43, 43)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        brand_text.addWidget(make_label("IVX DISCORD LAB", "brandName"))
        brand_text.addWidget(make_label("PROFILE INTELLIGENCE", "brandSub"))
        brand_row.addWidget(brand_icon)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(31)
        layout.addWidget(make_label("WORKSPACE", "tinyLabel"))
        layout.addSpacing(4)

        nav_items = [
            ("◫", "Overview"),
            ("▤", "Local profiles"),
            ("✦", "Game badges"),
            ("◉", "Activity Lab"),
            ("⇩", "Export reports"),
            ("ⓘ", "About & safety"),
        ]
        for index, (glyph, label) in enumerate(nav_items):
            button = QPushButton(f"  {glyph}     {label}")
            button.setObjectName("navButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(44)
            button.setProperty("selected", index == 0)
            button.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        local_card = QFrame()
        local_card.setStyleSheet("background:#121923;border:1px solid #263143;border-radius:12px;")
        local_layout = QVBoxLayout(local_card)
        local_layout.setContentsMargins(12, 12, 12, 12)
        local_layout.setSpacing(7)
        local_layout.addWidget(make_label("●  LOCAL-ONLY MODE", "tinyLabel"))
        local_layout.addWidget(make_label("No credential collection. No webhook uploads. Reports stay on your PC.", "sectionHint"))
        layout.addWidget(local_card)
        layout.addSpacing(8)
        layout.addWidget(make_label("IVX  /  COMMUNITY BUILD", "brandSub"))
        return sidebar

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QVBoxLayout()
        heading.setSpacing(5)
        self.page_title = make_label("Overview", "pageTitle")
        self.page_subtitle = make_label("A clear view of detected local profiles.", "pageSubtitle")
        heading.addWidget(self.page_title)
        heading.addWidget(self.page_subtitle)
        layout.addLayout(heading, 1)
        self.scan_button = QPushButton("↻   Scan profiles")
        self.scan_button.setObjectName("primaryButton")
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self.refresh_inventory)
        layout.addWidget(self.scan_button)
        return bar

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = make_label("●  Ready", "sectionHint")
        self.status_label.setStyleSheet("color:#8f98ac;")
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(make_label(f"IVX DISCORD LAB  ·  v{APP_VERSION}", "brandSub"))
        return footer

    @staticmethod
    def _scroll_page(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(22)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(9)
        hero_copy.addWidget(make_label("Your local profile overview.", "heroTitle"))
        hero_copy.addWidget(make_label(
            "Discover installed Discord clients and supported browser profiles, then export a clean inventory report.",
            "heroCopy"
        ))
        hero_copy.addSpacing(4)
        hero_copy.addWidget(make_label("PRIVATE BY DESIGN  ·  NO TOKENS OR COOKIES READ", "tinyLabel"))
        hero_layout.addLayout(hero_copy, 1)
        hero_glyph = make_label("◈", "")
        hero_glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_glyph.setFixedSize(82, 82)
        hero_glyph.setStyleSheet(
            "font-size:42px;font-weight:800;color:#c4b5fd;"
            "background:rgba(139,92,246,0.12);border:1px solid #514277;border-radius:24px;"
        )
        hero_layout.addWidget(hero_glyph)
        layout.addWidget(hero)

        metric_row = QHBoxLayout()
        metric_row.setSpacing(13)
        self.metric_discord = MetricCard("DISCORD CLIENTS FOUND", accent="#8b5cf6")
        self.metric_browsers = MetricCard("BROWSER PROFILES", accent="#22d3ee")
        self.metric_storage = MetricCard("STORAGE FOLDERS DETECTED", accent="#34d399")
        for card in (self.metric_discord, self.metric_browsers, self.metric_storage):
            metric_row.addWidget(card, 1)
        layout.addLayout(metric_row)

        lower = QHBoxLayout()
        lower.setSpacing(15)
        discord_card = make_card()
        discord_layout = QVBoxLayout(discord_card)
        discord_layout.setContentsMargins(18, 17, 18, 18)
        discord_layout.setSpacing(11)
        discord_head = QHBoxLayout()
        discord_head.addWidget(make_label("Discord installations", "sectionTitle"), 1)
        self.discord_count = make_label("0 found", "sectionHint")
        discord_head.addWidget(self.discord_count)
        discord_layout.addLayout(discord_head)
        discord_layout.addWidget(make_label("Standard Stable, PTB and Canary user-data paths.", "sectionHint"))
        self.discord_list_layout = QVBoxLayout()
        self.discord_list_layout.setSpacing(8)
        discord_layout.addLayout(self.discord_list_layout)
        discord_layout.addStretch(1)

        browser_card = make_card()
        browser_layout = QVBoxLayout(browser_card)
        browser_layout.setContentsMargins(18, 17, 18, 18)
        browser_layout.setSpacing(11)
        browser_head = QHBoxLayout()
        browser_head.addWidget(make_label("Browser profiles", "sectionTitle"), 1)
        self.browser_count = make_label("0 detected", "sectionHint")
        browser_head.addWidget(self.browser_count)
        browser_layout.addLayout(browser_head)
        browser_layout.addWidget(make_label("Supported browser profile directories found on this device.", "sectionHint"))
        self.browser_list_layout = QVBoxLayout()
        self.browser_list_layout.setSpacing(8)
        browser_layout.addLayout(self.browser_list_layout)
        browser_layout.addStretch(1)

        lower.addWidget(discord_card, 1)
        lower.addWidget(browser_card, 1)
        layout.addLayout(lower)
        layout.addStretch(1)
        return page

    def _build_profiles_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(15)

        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 17, 18, 18)
        card_layout.setSpacing(13)
        head = QHBoxLayout()
        head.addWidget(make_label("Detected profiles", "sectionTitle"), 1)
        self.table_count = make_label("Waiting for scan…", "sectionHint")
        head.addWidget(self.table_count)
        card_layout.addLayout(head)
        tools = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("⌕   Search client, browser, profile or path…")
        self.search_input.textChanged.connect(self.filter_profiles)
        tools.addWidget(self.search_input, 1)
        clear_button = QPushButton("Clear search")
        clear_button.setObjectName("quietButton")
        clear_button.clicked.connect(self.search_input.clear)
        tools.addWidget(clear_button)
        card_layout.addLayout(tools)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["TYPE", "APPLICATION", "PROFILE", "STORAGE", "LOCATION"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(420)
        card_layout.addWidget(self.table)
        layout.addWidget(card)
        layout.addWidget(make_label(
            "Presence checks only: a folder does not prove that an account is signed in or that a session is valid.",
            "sectionHint"
        ))
        layout.addStretch(1)
        return page

    def _build_badges_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(17)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 21, 22, 21)
        hero_layout.setSpacing(9)
        hero_layout.addWidget(make_label("Game Time & Game Variety", "heroTitle"))
        hero_layout.addWidget(make_label(
            "A practical setup guide for earning activity badges through real, detectable PC gameplay.",
            "heroCopy"
        ))
        hero_layout.addWidget(make_label(
            "NO TOKENS  ·  NO COOKIES  ·  NO FAKE ACTIVITY  ·  NO BADGE GUARANTEES",
            "tinyLabel"
        ))
        layout.addWidget(hero)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(14)
        for title, body, accent in [
            (
                "GAME TIME",
                "Discord counts eligible time spent playing games it detects while the desktop app is running. "
                "Time may take a while to appear in your badge progress.",
                "#8b5cf6",
            ),
            (
                "GAME VARIETY",
                "Discord counts different games it recognizes. Some titles may not be detected, and multiple "
                "experiences within Roblox or Fortnite may count as one game.",
                "#22d3ee",
            ),
        ]:
            card = make_card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 17, 18, 18)
            card_layout.setSpacing(10)
            accent_bar = QFrame()
            accent_bar.setFixedSize(34, 3)
            accent_bar.setStyleSheet(f"background:{accent};border:none;border-radius:1px;")
            card_layout.addWidget(accent_bar)
            card_layout.addWidget(make_label(title, "sectionTitle"))
            card_layout.addWidget(make_label(body, "sectionHint"))
            card_layout.addStretch(1)
            badge_row.addWidget(card, 1)
        layout.addLayout(badge_row)

        setup_card = make_card()
        setup_layout = QVBoxLayout(setup_card)
        setup_layout.setContentsMargins(18, 17, 18, 18)
        setup_layout.setSpacing(12)
        setup_layout.addWidget(make_label("Before you test", "sectionTitle"))
        steps = [
            ("01", "Use Discord desktop",
             "Keep the official Discord desktop app open while you actually play a supported PC game. "
             "Console play and mobile play do not count toward these desktop activity badges."),
            ("02", "Enable the required privacy setting",
             "In Discord, open User Settings → Data & Privacy and enable “Use data to personalize my Discord experience.”"),
            ("03", "Play games Discord recognizes",
             "Use real gameplay rather than synthetic activity. Some smaller or unusual games may not be detected by Discord."),
            ("04", "Check the Badge Directory later",
             "Badge processing can be delayed. Review your profile’s Badge Directory; this app cannot read or confirm "
             "Discord's server-side badge progress."),
        ]
        for number, heading, body in steps:
            row = QHBoxLayout()
            row.setSpacing(12)
            marker = make_label(number)
            marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marker.setFixedSize(38, 38)
            marker.setStyleSheet(
                "background:#211c37;color:#c4b5fd;border:1px solid #423762;"
                "border-radius:11px;font-size:12px;font-weight:800;"
            )
            copy = QVBoxLayout()
            copy.setSpacing(4)
            copy.addWidget(make_label(heading, "sectionTitle"))
            copy.addWidget(make_label(body, "sectionHint"))
            row.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(copy, 1)
            setup_layout.addLayout(row)
        layout.addWidget(setup_card)

        diagnostic_card = make_card()
        diagnostic_layout = QVBoxLayout(diagnostic_card)
        diagnostic_layout.setContentsMargins(18, 17, 18, 18)
        diagnostic_layout.setSpacing(10)
        diagnostic_layout.addWidget(make_label("Local readiness check", "sectionTitle"))
        diagnostic_layout.addWidget(make_label(
            "Checks whether a standard Discord profile folder was found and, on Windows, whether a Discord desktop "
            "process is running. It cannot inspect your privacy setting or confirm badge credit.",
            "sectionHint"
        ))
        actions = QHBoxLayout()
        self.badge_check_button = QPushButton("Run readiness check")
        self.badge_check_button.setObjectName("primaryButton")
        self.badge_check_button.setProperty("test_id", "badgeCheckButton")
        self.badge_check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge_check_button.clicked.connect(self.run_badge_readiness_check)
        self.badge_guide_button = QPushButton("Open Discord’s official badge guide  ↗")
        self.badge_guide_button.setObjectName("badgeGuideButton")
        self.badge_guide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.badge_guide_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(
                "https://support.discord.com/hc/en-us/articles/44369363856663-Discord-Profile-Badges-What-Each-Badge-Means"
            ))
        )
        actions.addWidget(self.badge_check_button)
        actions.addWidget(self.badge_guide_button)
        actions.addStretch(1)
        diagnostic_layout.addLayout(actions)
        layout.addWidget(diagnostic_card)

        note = QFrame()
        note.setStyleSheet("background:#211a12;border:1px solid #4b3520;border-radius:12px;")
        note_layout = QVBoxLayout(note)
        note_layout.setContentsMargins(15, 13, 15, 13)
        note_layout.setSpacing(5)
        note_layout.addWidget(make_label("Important limitation", "tinyLabel"))
        note_layout.addWidget(make_label(
            "No third-party tool can guarantee that Discord will grant or update a badge. This app does not generate "
            "fake activity, reuse account tokens or cookies, or make account changes. Only Discord can confirm credited progress.",
            "sectionHint"
        ))
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def run_badge_readiness_check(self) -> None:
        if not self.scan_completed:
            QMessageBox.information(
                self,
                "Readiness check unavailable",
                "The initial profile scan has not completed successfully. Wait for it to finish or click Scan profiles, then try again.",
            )
            return

        clients = [
            item for item in self.report.get("discord_clients", [])
            if item.get("user_data_found")
        ]
        lines = [
            "LOCAL READINESS CHECK",
            "",
            f"Discord profile folders: {len(clients)} found out of {len(self.report.get('discord_clients', []))}.",
        ]
        if clients:
            lines.append("Detected: " + ", ".join(str(item.get("client", "Discord")) for item in clients))
        else:
            lines.append("No standard Discord user-data folder was found. Run Scan profiles or install Discord desktop.")
        running, details = discord_process_status()
        if running is True:
            lines.append(f"Discord desktop process: RUNNING ({details}).")
        elif running is False:
            lines.append("Discord desktop process: NOT DETECTED. Open the official Discord desktop app before playing.")
        else:
            lines.append(f"Discord desktop process: NOT VERIFIED ({details})")
        lines.extend([
            "",
            "Manual check required: in Discord User Settings → Data & Privacy, enable "
            "“Use data to personalize my Discord experience.”",
            "",
            "Play actual PC games that Discord recognizes. Then check your profile’s Badge Directory later; "
            "progress may be delayed. This diagnostic cannot confirm badge credit.",
        ])
        QMessageBox.information(self, "Game badge readiness", "\n".join(lines))
        self.status_label.setText("●  Local badge-readiness check complete")
        self.status_label.setStyleSheet("color:#8f98ac;")

    def _build_activity_lab_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(8)
        hero_layout.addWidget(make_label("Activity Lab", "heroTitle"))
        hero_layout.addWidget(make_label(
            "Test game selection, planned hours, run controls, progress updates and logs in a safe offline simulation.",
            "heroCopy"
        ))
        hero_layout.addWidget(make_label(
            "SIMULATION ONLY  ·  NO TOKENS OR COOKIES  ·  NO DISCORD REQUESTS",
            "tinyLabel"
        ))
        layout.addWidget(hero)

        context_card = make_card()
        context_layout = QVBoxLayout(context_card)
        context_layout.setContentsMargins(18, 16, 18, 16)
        context_layout.setSpacing(8)
        context_layout.addWidget(make_label("Profile context", "sectionTitle"))
        context_layout.addWidget(make_label(
            "Choose a detected installation label for the demo report. This is display-only: the simulator does not log in, "
            "read credentials, or send activity to Discord.",
            "sectionHint"
        ))
        self.activity_profile_combo = QComboBox()
        self.activity_profile_combo.setObjectName("activityProfileCombo")
        self.activity_profile_combo.addItem("Scanning for local Discord profiles…")
        context_layout.addWidget(self.activity_profile_combo)
        layout.addWidget(context_card)

        select_card = make_card()
        select_layout = QVBoxLayout(select_card)
        select_layout.setContentsMargins(18, 16, 18, 16)
        select_layout.setSpacing(11)
        select_head = QHBoxLayout()
        select_head.addWidget(make_label("Detectable game catalog", "sectionTitle"), 1)
        select_actions = QHBoxLayout()
        self.activity_select_all_button = QPushButton("Select visible")
        self.activity_select_all_button.setObjectName("quietButton")
        self.activity_refresh_catalog_button = QPushButton("↻  Refresh catalog")
        self.activity_refresh_catalog_button.setObjectName("quietButton")
        self.activity_clear_button = QPushButton("Clear selection")
        self.activity_clear_button.setObjectName("quietButton")
        select_actions.addWidget(self.activity_select_all_button)
        select_actions.addWidget(self.activity_refresh_catalog_button)
        select_actions.addWidget(self.activity_clear_button)
        select_head.addLayout(select_actions)
        select_layout.addLayout(select_head)

        self.activity_catalog_status = make_label(
            "Built-in fallback · 8 examples. Fetching Discord's public catalog on startup…",
            "sectionHint",
        )
        select_layout.addWidget(self.activity_catalog_status)
        self.activity_game_search = QLineEdit()
        self.activity_game_search.setObjectName("activityGameSearch")
        self.activity_game_search.setPlaceholderText("Search game name or executable…")
        self.activity_game_search.textChanged.connect(self._render_activity_game_list)
        select_layout.addWidget(self.activity_game_search)

        self.activity_game_list = QListWidget()
        self.activity_game_list.setObjectName("activityGameList")
        self.activity_game_list.setMinimumHeight(210)
        self.activity_game_list.setMaximumHeight(250)
        self.activity_game_list.setSpacing(3)
        self.activity_game_list.setUniformItemSizes(True)
        self.activity_game_list.itemChanged.connect(self._activity_game_item_changed)
        self._render_activity_game_list()
        select_layout.addWidget(self.activity_game_list)

        config_row = QHBoxLayout()
        config_row.setSpacing(14)
        hours_col = QVBoxLayout()
        hours_col.setSpacing(6)
        hours_col.addWidget(make_label("Simulated hours per selected game", "sectionTitle"))
        self.activity_hours_spin = QSpinBox()
        self.activity_hours_spin.setObjectName("activityHoursSpin")
        self.activity_hours_spin.setRange(1, 24)
        self.activity_hours_spin.setValue(2)
        self.activity_hours_spin.setSuffix(" hours")
        self.activity_hours_spin.setToolTip("These are simulated values only; real time is not sent to Discord.")
        self.activity_hours_spin.valueChanged.connect(self._update_activity_total)
        hours_col.addWidget(self.activity_hours_spin)
        config_row.addLayout(hours_col, 1)

        self.activity_total_label = make_label("0 games selected · 0 simulated hours", "sectionHint")
        self.activity_total_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        config_row.addWidget(self.activity_total_label, 1)
        select_layout.addLayout(config_row)
        layout.addWidget(select_card)

        run_card = make_card()
        run_layout = QVBoxLayout(run_card)
        run_layout.setContentsMargins(18, 16, 18, 16)
        run_layout.setSpacing(11)
        run_layout.addWidget(make_label("Simulation run", "sectionTitle"))
        self.activity_progress = QProgressBar()
        self.activity_progress.setObjectName("activityProgress")
        self.activity_progress.setRange(0, 100)
        self.activity_progress.setValue(0)
        self.activity_progress.setTextVisible(True)
        self.activity_progress.setFormat("%p%  ·  demo progress")
        self.activity_progress.setStyleSheet(
            "QProgressBar { background:#202536; color:#e9e7ff; border:1px solid #34394e;"
            "border-radius:7px; text-align:center; min-height:19px; font-size:10px; }"
            "QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7657ec,stop:1 #a78bfa); border-radius:6px; }"
        )
        run_layout.addWidget(self.activity_progress)
        self.activity_status_label = make_label("Ready · select one or more games to begin.", "sectionHint")
        run_layout.addWidget(self.activity_status_label)

        buttons = QHBoxLayout()
        self.activity_start_button = QPushButton("▶   Start simulation")
        self.activity_start_button.setObjectName("primaryButton")
        self.activity_start_button.setProperty("test_id", "activityStartButton")
        self.activity_pause_button = QPushButton("Ⅱ   Pause")
        self.activity_pause_button.setObjectName("quietButton")
        self.activity_stop_button = QPushButton("■   Stop")
        self.activity_stop_button.setObjectName("quietButton")
        self.activity_pause_button.setEnabled(False)
        self.activity_stop_button.setEnabled(False)
        buttons.addWidget(self.activity_start_button)
        buttons.addWidget(self.activity_pause_button)
        buttons.addWidget(self.activity_stop_button)
        buttons.addStretch(1)
        run_layout.addLayout(buttons)
        layout.addWidget(run_card)

        log_card = make_card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_head = QHBoxLayout()
        log_head.addWidget(make_label("Local activity log", "sectionTitle"), 1)
        self.activity_clear_log_button = QPushButton("Clear log")
        self.activity_clear_log_button.setObjectName("quietButton")
        log_head.addWidget(self.activity_clear_log_button)
        log_layout.addLayout(log_head)
        self.activity_log = QTextEdit()
        self.activity_log.setObjectName("activityLog")
        self.activity_log.setReadOnly(True)
        self.activity_log.setMinimumHeight(140)
        self.activity_log.setMaximumHeight(190)
        self.activity_log.setPlaceholderText("Simulation messages will appear here…")
        self.activity_log.setStyleSheet(
            "QTextEdit { background:#0b0e15; color:#aeb8ce; border:1px solid #252c3a;"
            "border-radius:9px; padding:9px; font-family:Consolas,monospace; font-size:11px; }"
        )
        log_layout.addWidget(self.activity_log)
        layout.addWidget(log_card)

        self.activity_select_all_button.clicked.connect(self._select_all_activity_games)
        self.activity_refresh_catalog_button.clicked.connect(self.fetch_activity_catalog)
        self.activity_clear_button.clicked.connect(self._clear_activity_games)
        self.activity_start_button.clicked.connect(self.start_activity_simulation)
        self.activity_pause_button.clicked.connect(self.toggle_activity_simulation_pause)
        self.activity_stop_button.clicked.connect(self.stop_activity_simulation)
        self.activity_clear_log_button.clicked.connect(self.activity_log.clear)
        self._update_activity_total()
        self._append_activity_log("Ready. This local simulator never contacts Discord.")
        layout.addStretch(1)
        return page

    def _populate_activity_profiles(self) -> None:
        if not hasattr(self, "activity_profile_combo"):
            return
        self.activity_profile_combo.clear()
        found = [
            str(item.get("client", "Discord"))
            for item in self.report.get("discord_clients", [])
            if item.get("user_data_found")
        ]
        if found:
            for client in found:
                self.activity_profile_combo.addItem(client)
        else:
            self.activity_profile_combo.addItem("No detected Discord profile · demo mode")

    def fetch_activity_catalog(self) -> None:
        """Fetch public detectable-game metadata in a worker so the UI stays responsive."""
        if self.activity_catalog_worker is not None and self.activity_catalog_worker.isRunning():
            self._append_activity_log("Catalog refresh is already running.")
            return
        self.activity_refresh_catalog_button.setEnabled(False)
        self.activity_catalog_status.setText("Fetching public game catalog… the UI remains responsive.")
        self._append_activity_log("Fetching public detectable-game metadata. No credentials are sent.")
        worker = GameCatalogWorker()
        self.activity_catalog_worker = worker
        _ACTIVE_CATALOG_WORKERS.add(worker)
        worker.catalog_ready.connect(self._apply_activity_catalog)
        worker.finished.connect(lambda w=worker: _release_game_catalog_worker(w))
        worker.start()

    def _apply_activity_catalog(self, games: object, source: str, message: str) -> None:
        if not isinstance(games, list):
            games = []
        valid_games = [
            item for item in games
            if isinstance(item, dict) and item.get("id") and item.get("name")
        ]
        if valid_games:
            previously_selected_names = {
                self.activity_catalog_by_id[game_id]["name"].casefold()
                for game_id in self.activity_selected_game_ids
                if game_id in self.activity_catalog_by_id
            }
            self.activity_catalog = [
                {
                    "id": str(item["id"]),
                    "name": str(item["name"]),
                    "executable": str(item.get("executable") or "Executable not listed"),
                }
                for item in valid_games
            ]
            self.activity_catalog_by_id = {
                game["id"]: game for game in self.activity_catalog
            }
            self.activity_selected_game_ids = {
                game["id"] for game in self.activity_catalog
                if game["name"].casefold() in previously_selected_names
                or game["id"] in self.activity_selected_game_ids
            }
            self.activity_catalog_source = source
            self.activity_catalog_status.setText(f"{source} · {len(self.activity_catalog):,} games available")
            self._append_activity_log(message)
        else:
            self.activity_catalog_status.setText("Catalog unavailable · built-in fallback remains available")
            self._append_activity_log("Catalog fetch returned no usable game list; kept the current catalog.")
            if message:
                self._append_activity_log(message[:600])
        self.activity_refresh_catalog_button.setEnabled(True)
        self._render_activity_game_list()
        self._update_activity_total()

    def _render_activity_game_list(self, *_args: object) -> None:
        if not hasattr(self, "activity_game_list"):
            return
        query = self.activity_game_search.text().strip().casefold()
        matches = [
            game for game in self.activity_catalog
            if not query
            or query in game["name"].casefold()
            or query in game["executable"].casefold()
        ]
        visible_limit = 250
        visible = matches[:visible_limit]
        self.activity_game_list.blockSignals(True)
        self.activity_game_list.clear()
        for game in visible:
            label = game["name"]
            if game["executable"] != "Executable not listed":
                label = f'{game["name"]}  ·  {game["executable"]}'
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, game["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, game["name"])
            item.setToolTip(f'Game: {game["name"]}\nExecutable hint: {game["executable"]}')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(
                Qt.CheckState.Checked
                if game["id"] in self.activity_selected_game_ids
                else Qt.CheckState.Unchecked
            )
            self.activity_game_list.addItem(item)
        self.activity_game_list.blockSignals(False)
        if query:
            self.activity_catalog_status.setText(
                f"{self.activity_catalog_source} · {len(matches):,} matches"
                + (f" · showing first {visible_limit}" if len(matches) > visible_limit else "")
            )
        elif len(matches) > visible_limit:
            self.activity_catalog_status.setText(
                f"{self.activity_catalog_source} · {len(matches):,} games · showing first {visible_limit}; search to narrow"
            )
        else:
            self.activity_catalog_status.setText(f"{self.activity_catalog_source} · {len(matches):,} games")
        self._update_activity_total()

    def _activity_game_item_changed(self, item: QListWidgetItem) -> None:
        game_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not game_id:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self.activity_selected_game_ids.add(game_id)
        else:
            self.activity_selected_game_ids.discard(game_id)
        self._update_activity_total()

    def _select_all_activity_games(self) -> None:
        self.activity_game_list.blockSignals(True)
        for index in range(self.activity_game_list.count()):
            item = self.activity_game_list.item(index)
            game_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if game_id:
                self.activity_selected_game_ids.add(game_id)
            item.setCheckState(Qt.CheckState.Checked)
        self.activity_game_list.blockSignals(False)
        self._update_activity_total()

    def _clear_activity_games(self) -> None:
        self.activity_selected_game_ids.clear()
        self._render_activity_game_list()
        self._update_activity_total()

    def _selected_activity_games(self) -> list[str]:
        return [
            self.activity_catalog_by_id[game_id]["name"]
            for game_id in self.activity_selected_game_ids
            if game_id in self.activity_catalog_by_id
        ]

    def _select_all_activity_games(self) -> None:
        self.activity_game_list.blockSignals(True)
        for index in range(self.activity_game_list.count()):
            self.activity_game_list.item(index).setCheckState(Qt.CheckState.Checked)
        self.activity_game_list.blockSignals(False)
        self._update_activity_total()

    def _clear_activity_games(self) -> None:
        self.activity_game_list.blockSignals(True)
        for index in range(self.activity_game_list.count()):
            self.activity_game_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        self.activity_game_list.blockSignals(False)
        self._update_activity_total()

    def _selected_activity_games(self) -> list[str]:
        return [
            self.activity_game_list.item(index).text()
            for index in range(self.activity_game_list.count())
            if self.activity_game_list.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _update_activity_total(self, *_args: object) -> None:
        if not hasattr(self, "activity_game_list"):
            return
        count = len(self._selected_activity_games())
        hours = count * self.activity_hours_spin.value()
        self.activity_total_label.setText(
            f"{count} game{'s' if count != 1 else ''} selected · {hours} simulated hour{'s' if hours != 1 else ''}"
        )
        if hasattr(self, "activity_start_button") and not self.activity_timer.isActive():
            self.activity_start_button.setEnabled(count > 0)

    def _append_activity_log(self, message: str) -> None:
        if hasattr(self, "activity_log"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.activity_log.append(f"[{timestamp}] {message}")

    def start_activity_simulation(self) -> None:
        if self.activity_timer.isActive():
            return
        games = self._selected_activity_games()
        if not games:
            QMessageBox.information(self, "Choose demo games", "Select at least one game before starting the simulation.")
            return
        hours = self.activity_hours_spin.value()
        self.activity_schedule = [(game, hours) for game in games]
        self.activity_tick = 0
        self.activity_total_ticks = len(self.activity_schedule) * 8
        self.activity_current_game = -1
        self.activity_paused = False
        self.activity_progress.setValue(0)
        self.activity_status_label.setText("Simulation running · accelerated demo timeline.")
        self.activity_start_button.setEnabled(False)
        self.activity_pause_button.setEnabled(True)
        self.activity_pause_button.setText("Ⅱ   Pause")
        self.activity_stop_button.setEnabled(True)
        self._append_activity_log(
            f"Simulation started for {len(games)} demo game(s), {len(games) * hours} simulated hour(s)."
        )
        self._append_activity_log(f"Profile context: {self.activity_profile_combo.currentText()} (label only).")
        self._append_activity_log("No credentials loaded. No Discord request will be made.")
        self.activity_timer.start()

    def toggle_activity_simulation_pause(self) -> None:
        if not self.activity_timer.isActive() and not self.activity_paused:
            return
        if self.activity_paused:
            self.activity_paused = False
            self.activity_timer.start()
            self.activity_pause_button.setText("Ⅱ   Pause")
            self.activity_status_label.setText("Simulation resumed.")
            self._append_activity_log("Simulation resumed.")
        else:
            self.activity_timer.stop()
            self.activity_paused = True
            self.activity_pause_button.setText("▶   Resume")
            self.activity_status_label.setText("Simulation paused.")
            self._append_activity_log("Simulation paused.")

    def stop_activity_simulation(self) -> None:
        was_running = self.activity_timer.isActive() or self.activity_paused
        self.activity_timer.stop()
        self.activity_paused = False
        self.activity_start_button.setEnabled(bool(self._selected_activity_games()))
        self.activity_pause_button.setEnabled(False)
        self.activity_pause_button.setText("Ⅱ   Pause")
        self.activity_stop_button.setEnabled(False)
        if was_running:
            self.activity_status_label.setText("Simulation stopped · no Discord activity was sent.")
            self._append_activity_log("Simulation stopped by user. No activity or credentials sent to Discord.")
        else:
            self.activity_status_label.setText("Ready · select games and start a simulation.")

    def _activity_simulation_tick(self) -> None:
        if not self.activity_schedule or self.activity_total_ticks <= 0:
            self.stop_activity_simulation()
            return
        self.activity_tick += 1
        game_index = min((self.activity_tick - 1) // 8, len(self.activity_schedule) - 1)
        if game_index != self.activity_current_game:
            self.activity_current_game = game_index
            game, hours = self.activity_schedule[game_index]
            self.activity_status_label.setText(
                f"Simulating {game} · {hours} planned hour(s) · offline demo"
            )
            self._append_activity_log(
                f"Demo event: {game} · {hours} simulated hour(s). This is not Discord activity."
            )
        percent = min(100, round(self.activity_tick / self.activity_total_ticks * 100))
        self.activity_progress.setValue(percent)
        if self.activity_tick >= self.activity_total_ticks:
            self.activity_timer.stop()
            self.activity_paused = False
            self.activity_start_button.setEnabled(bool(self._selected_activity_games()))
            self.activity_pause_button.setEnabled(False)
            self.activity_pause_button.setText("Ⅱ   Pause")
            self.activity_stop_button.setEnabled(False)
            self.activity_status_label.setText("Simulation complete · no Discord badge progress was requested.")
            self._append_activity_log("Simulation completed successfully.")
            self._append_activity_log("No activity, token, cookie, or badge request was sent to Discord.")

    def _build_exports_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(18)
        layout.addWidget(make_label("Export your inventory", "sectionTitle"))
        layout.addWidget(make_label(
            "Create a portable report of detected client and browser profile metadata. Export is manual and stays on your computer.",
            "pageSubtitle"
        ))
        row = QHBoxLayout()
        row.setSpacing(15)
        for title, ext, glyph, copy, button_text in [
            ("CSV spreadsheet", "csv", "▦", "Open in Excel or a spreadsheet app. Includes type, app, profile, storage-folder presence and a home-relative path.", "Export CSV"),
            ("JSON report", "json", "{ }", "A structured report for audits, scripts or later local analysis. Includes the scan's limitations.", "Export JSON"),
        ]:
            card = make_card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 20, 20, 20)
            card_layout.setSpacing(13)
            icon_label = make_label(glyph)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(53, 53)
            icon_label.setStyleSheet(
                "background:#211c37;color:#c4b5fd;border:1px solid #423762;"
                "border-radius:15px;font-size:23px;font-weight:800;"
            )
            card_layout.addWidget(icon_label)
            card_layout.addWidget(make_label(title, "sectionTitle"))
            card_layout.addWidget(make_label(copy, "sectionHint"))
            card_layout.addStretch(1)
            action = QPushButton(button_text + "   ↗")
            action.setObjectName("primaryButton")
            action.clicked.connect(lambda checked=False, fmt=ext: self.export_report(fmt))
            card_layout.addWidget(action)
            row.addWidget(card, 1)
        layout.addLayout(row)

        privacy = QFrame()
        privacy.setStyleSheet("background:#111b1a;border:1px solid #23423c;border-radius:14px;")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(17, 16, 17, 16)
        privacy_layout.setSpacing(7)
        privacy_layout.addWidget(make_label("●  EXPORT SAFETY", "tinyLabel"))
        privacy_layout.addWidget(make_label(
            "Reports never include Discord tokens, browser cookies, saved passwords, account usernames, or database contents. "
            "No webhook or remote upload is configured.",
            "sectionHint"
        ))
        layout.addWidget(privacy)
        layout.addStretch(1)
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 10, 15)
        layout.setSpacing(15)
        layout.addWidget(make_label("About & safety", "sectionTitle"))

        cards = [
            ("WHAT THIS APP DOES",
             "Detects standard user-data directories for Discord Stable, PTB and Canary, and lists supported browser profile folders. "
             "It can export that metadata as a local CSV or JSON report."),
            ("WHAT THIS APP DOES NOT DO",
             "It does not extract, decrypt, display, or export account tokens, cookies, saved passwords, browser login databases, "
             "or storage contents. It does not send reports to a webhook or run the separate spoofer.py file."),
            ("SEPARATE LEGACY SCRIPT",
             "The repository retains a separate legacy script that constructs synthetic Discord game-activity telemetry. "
             "It is not integrated into this UI, relies on undocumented service behavior, and may violate Discord's Terms of Service. "
             "This app does not run it, reuse account credentials, or guarantee badge progress."),
            ("DATA & PRIVACY",
             "Scanning is local. The only files created by an export are the file you explicitly choose in the Save dialog. "
             "Paths are made relative to your home folder when possible."),
        ]
        for heading, body in cards:
            card = make_card()
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(18, 17, 18, 17)
            c_layout.setSpacing(8)
            c_layout.addWidget(make_label(heading, "tinyLabel"))
            c_layout.addWidget(make_label(body, "sectionHint"))
            layout.addWidget(card)
        layout.addStretch(1)
        return page

    def navigate(self, index: int) -> None:
        if index < 0 or index >= self.pages.count() or index == self.pages.currentIndex():
            return
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setProperty("selected", i == index)
            button.style().unpolish(button)
            button.style().polish(button)
        titles = [
            ("Overview", "A clear view of detected local profiles."),
            ("Local profiles", "Search and inspect profile-folder metadata."),
            ("Game badges", "Check local Discord readiness and follow official badge requirements."),
            ("Activity Lab", "Simulate game selection, durations, progress and logs offline."),
            ("Export reports", "Save a local inventory in CSV or JSON format."),
            ("About & safety", "Understand the tool's scope and privacy boundaries."),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])

        # Keep the stacked pages fully opaque. Applying a persistent graphics-opacity
        # effect to each scroll page can leave stale backing-store images on some Qt builds,
        # which makes old pages appear layered behind the selected page.
        self.pages.currentWidget().update()
        self.pages.update()

    def refresh_inventory(self) -> None:
        if not hasattr(self, "scan_button"):
            return
        self.scan_button.setEnabled(False)
        self.scan_button.setText("Scanning…")
        self.status_label.setText("●  Scanning standard profile folders…")
        QTimer.singleShot(70, self._perform_scan)

    def _perform_scan(self) -> None:
        try:
            self.report = build_inventory()
            self.profile_rows = self._flatten_report(self.report)
            self._render_overview()
            self._populate_table()
            self._populate_activity_profiles()
            self.scan_completed = True
            self.status_label.setText("●  Scan complete · local-only")
            self.status_label.setStyleSheet("color:#6ee7b7;")
        except Exception as exc:
            self.status_label.setText("●  Scan failed")
            self.status_label.setStyleSheet("color:#fca5a5;")
            QMessageBox.warning(self, "Scan failed", f"Could not inspect profile folders.\n\n{exc}")
        finally:
            self.scan_button.setEnabled(True)
            self.scan_button.setText("↻   Scan profiles")

    @staticmethod
    def _flatten_report(report: dict[str, Any]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for item in report.get("discord_clients", []):
            rows.append({
                "type": "Discord client",
                "application": str(item.get("client", "")),
                "profile": "—",
                "storage": "Detected" if item.get("local_storage_folder_found") else "Not detected",
                "path": str(item.get("path", "")),
            })
        for item in report.get("browser_profiles", []):
            rows.append({
                "type": "Browser",
                "application": str(item.get("browser", "")),
                "profile": str(item.get("profile", "")),
                "storage": "Detected" if item.get("local_storage_folder_found") else "Not detected",
                "path": str(item.get("path", "")),
            })
        return rows

    def _render_overview(self) -> None:
        discord = self.report.get("discord_clients", [])
        browsers = self.report.get("browser_profiles", [])
        discord_found = sum(1 for item in discord if item.get("user_data_found"))
        storage_found = sum(
            1 for item in [*discord, *browsers] if item.get("local_storage_folder_found")
        )
        self.metric_discord.set_value(f"{discord_found} / 3")
        self.metric_browsers.set_value(len(browsers))
        self.metric_storage.set_value(storage_found)
        self.discord_count.setText(f"{discord_found} found")
        self.browser_count.setText(f"{len(browsers)} detected")

        clear_layout(self.discord_list_layout)
        for item in discord:
            present = bool(item.get("user_data_found"))
            row = self._summary_row(
                str(item.get("client", "Discord")),
                str(item.get("path", "")),
                "Found" if present else "Not found",
                present,
            )
            self.discord_list_layout.addWidget(row)

        clear_layout(self.browser_list_layout)
        if browsers:
            for item in browsers[:6]:
                row = self._summary_row(
                    f"{item.get('browser', 'Browser')}  /  {item.get('profile', 'Profile')}",
                    str(item.get("path", "")),
                    "Found",
                    True,
                )
                self.browser_list_layout.addWidget(row)
            if len(browsers) > 6:
                self.browser_list_layout.addWidget(make_label(f"+ {len(browsers) - 6} more profiles — see Local profiles", "sectionHint"))
        else:
            self.browser_list_layout.addWidget(make_label("No supported browser profiles found in standard locations.", "sectionHint"))

    @staticmethod
    def _summary_row(title: str, path: str, status: str, found: bool) -> QWidget:
        row = QFrame()
        row.setStyleSheet("background:#0e121a;border:1px solid #222938;border-radius:10px;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(9)
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        name = make_label(title)
        name.setStyleSheet("font-weight:650;color:#e6eaf3;")
        path_label = make_label(path, "sectionHint")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_col.addWidget(name)
        text_col.addWidget(path_label)
        layout.addLayout(text_col, 1)
        badge = QLabel(status)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:#123027;color:#6ee7b7;border:1px solid #235844;border-radius:8px;padding:5px 7px;"
            if found else
            "background:#20232b;color:#8f98ac;border:1px solid #333947;border-radius:8px;padding:5px 7px;"
        )
        layout.addWidget(badge)
        return row

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for record in self.profile_rows:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)
            values = [
                record["type"],
                record["application"],
                record["profile"],
                record["storage"],
                record["path"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setForeground(QColor("#b6a6ff" if value == "Discord client" else "#75d9e8"))
                self.table.setItem(row_index, column, item)
        self.filter_profiles(self.search_input.text() if hasattr(self, "search_input") else "")
        if hasattr(self, "table_count"):
            self.table_count.setText(f"{len(self.profile_rows)} entries")

    def filter_profiles(self, text: str) -> None:
        needle = text.strip().casefold()
        visible = 0
        for row in range(self.table.rowCount()):
            match = not needle or any(
                needle in (self.table.item(row, col).text().casefold() if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not match)
            visible += int(match)
        if hasattr(self, "table_count"):
            self.table_count.setText(f"{visible} shown · {len(self.profile_rows)} total")

    def export_report(self, fmt: str) -> None:
        if not self.report.get("discord_clients") and not self.report.get("browser_profiles"):
            QMessageBox.information(self, "Nothing to export", "Scan the profile folders first, then export the report.")
            return
        if fmt == "csv":
            default = str(Path.home() / "ivx_profile_inventory.csv")
            path, _ = QFileDialog.getSaveFileName(self, "Export inventory as CSV", default, "CSV files (*.csv)")
        else:
            default = str(Path.home() / "ivx_profile_inventory.json")
            path, _ = QFileDialog.getSaveFileName(self, "Export inventory as JSON", default, "JSON files (*.json)")
        if not path:
            return
        target = Path(path).expanduser()
        try:
            if fmt == "csv":
                write_csv_report(self.report, target)
            else:
                target.write_text(json.dumps(self.report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write the report.\n\n{exc}")
            return
        QMessageBox.information(
            self,
            "Export complete",
            f"Your metadata-only report was saved to:\n{target}\n\nNo tokens or cookies were collected.",
        )
        self.status_label.setText(f"●  Exported {target.name}")
        self.status_label.setStyleSheet("color:#6ee7b7;")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
