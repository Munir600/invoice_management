import os

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QFileDialog,
    QLineEdit
)
from PySide6.QtCore import Qt, QSize, QByteArray
from PySide6.QtGui import QCursor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def _create_toggle_button(dark_mode: bool):
    """
    Create a small toggle button with SVG icons.
    Returns (btn, set_checked) where:

      set_checked(checked: bool, quiet: bool = False)

    If quiet=True, the state+icon are updated WITHOUT emitting toggled().
    """
    from PySide6.QtWidgets import QToolButton

    btn = QToolButton()
    btn.setObjectName("SettingsToggle")
    btn.setCheckable(True)
    btn.setCursor(QCursor(Qt.PointingHandCursor))

    # Off icons differ slightly between light/dark to match your style
    if dark_mode:
        toggle_off_base64 = (
            "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAw"
            "L3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjIwIiByeD0iMTAiIGZpbGw9IiM0YjU1"
            "NjMiLz48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSI5IiBmaWxsPSJ3aGl0ZSIvPjwvc3Zn"
            "Pg=="
        )
    else:
        toggle_off_base64 = (
            "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAw"
            "L3N2ZyI+CjxyZWN0IHdpZHRoPSI0MCIgaGVpZ2h0PSIyMCIgcng9IjEwIiBmaWxsPSIjNkI3"
            "MjgwIi8+CjxjaXJjbGUgY3g9IjEwIiBjeT0iMTAiIHI9IjkiIGZpbGw9IndoaXRlIi8+Cjwv"
            "c3ZnPg=="
        )

    toggle_on_base64 = (
        "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAw"
        "L3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjIwIiByeD0iMTAiIGZpbGw9IiMyNTRG"
        "QTciLz48Y2lyY2xlIGN4PSIzMCIgY3k9IjEwIiByPSI5IiBmaWxsPSJ3aGl0ZSIvPjwvc3Zn"
        "Pg=="
    )

    def create_icon(base64_str: str) -> QIcon:
        svg_bytes = QByteArray.fromBase64(base64_str.encode("utf-8"))
        renderer = QSvgRenderer(svg_bytes)
        pix = QPixmap(40, 20)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        return QIcon(pix)

    off_icon = create_icon(toggle_off_base64)
    on_icon = create_icon(toggle_on_base64)

    btn.setIcon(off_icon)
    btn.setIconSize(QSize(40, 20))

    def set_checked(checked: bool, quiet: bool = False):
        """Set toggle state; quiet=True does not emit toggled."""
        if quiet:
            btn.blockSignals(True)
        btn.setChecked(checked)
        btn.setIcon(on_icon if checked else off_icon)
        if quiet:
            btn.blockSignals(False)

    # When user toggles, just update icon (and let external handler react)
    def on_toggled(checked: bool):
        btn.setIcon(on_icon if checked else off_icon)

    btn.toggled.connect(on_toggled)

    # Initial visual state (OFF, but quiet so no signals)
    set_checked(False, quiet=True)

    return btn, set_checked


class SettingsDialog(QDialog):
    """
    Settings dialog:
      - Shows username (read-only)
      - Shows permissions as tags
      - Dark mode toggle (syncs with main.dark_mode)
      - Backup toggle with folder selection (syncs with main.backup_enabled)
      - Logout button
    """

    def __init__(self, main_window, parent: QWidget | None = None):
        super().__init__(parent or main_window)
        self.main = main_window
        self.dark_mode = bool(getattr(main_window, "dark_mode", False))

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(700, 520)

        # Will hold references to toggle buttons
        self.theme_toggle_btn = None
        self.theme_toggle_set_checked = None
        self.backup_toggle_btn = None
        self.backup_toggle_set_checked = None
        self.backup_path_label: QLabel | None = None

        self._build_ui()
        self._apply_styles()
        self._populate()

    # ---------- UI ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("SettingsTitle")
        layout.addWidget(title)

        # Scroll area
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_widget = QWidget()
        scroll_widget.setObjectName("SettingsContent")

        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # ---- Profile section ----
        profile_frame = QFrame()
        profile_frame.setObjectName("SettingsSection")
        pf_layout = QVBoxLayout(profile_frame)
        pf_layout.setContentsMargins(16, 12, 16, 12)
        pf_layout.setSpacing(8)

        profile_title = QLabel("Profile")
        profile_title.setObjectName("SettingsSectionTitle")
        pf_layout.addWidget(profile_title)

        # username row
        user_row = QHBoxLayout()
        lbl_username = QLabel("Username:")
        lbl_username.setObjectName("SettingsLabel")
        val_username = QLabel(self.main.current_user)
        val_username.setObjectName("SettingsValue")
        user_row.addWidget(lbl_username)
        user_row.addWidget(val_username)
        user_row.addStretch()
        pf_layout.addLayout(user_row)

        # permissions row
        perms_label = QLabel("Permissions")
        perms_label.setObjectName("SettingsLabel")
        pf_layout.addWidget(perms_label)

        perms_row = QHBoxLayout()
        perms_row.setSpacing(6)
        for name, allowed in self.main.user_perms.items():
            tag = QLabel(name)
            tag.setObjectName("PermTagEnabled" if allowed else "PermTagDisabled")
            perms_row.addWidget(tag)
        perms_row.addStretch()
        pf_layout.addLayout(perms_row)

        scroll_layout.addWidget(profile_frame)

        # ---- Appearance section ----
        theme_frame = QFrame()
        theme_frame.setObjectName("SettingsSection")
        th_layout = QVBoxLayout(theme_frame)
        th_layout.setContentsMargins(16, 12, 16, 12)
        th_layout.setSpacing(8)

        theme_title = QLabel("Appearance")
        theme_title.setObjectName("SettingsSectionTitle")
        th_layout.addWidget(theme_title)

        theme_row = QFrame()
        theme_row.setObjectName("SettingsRow")
        tr_layout = QHBoxLayout(theme_row)
        tr_layout.setContentsMargins(0, 0, 0, 0)
        tr_layout.setSpacing(8)

        theme_label = QLabel("Dark Mode")
        theme_label.setObjectName("SettingsLabel")
        tr_layout.addWidget(theme_label)
        tr_layout.addStretch()

        self.theme_toggle_btn, self.theme_toggle_set_checked = _create_toggle_button(
            self.dark_mode
        )
        tr_layout.addWidget(self.theme_toggle_btn)

        # Clicking label toggles as well
        def theme_label_press(event):
            if event.button() == Qt.LeftButton and self.theme_toggle_btn is not None:
                self.theme_toggle_btn.toggle()
            super(QLabel, theme_label).mousePressEvent(event)

        theme_label.mousePressEvent = theme_label_press

        self.theme_toggle_btn.toggled.connect(self._on_theme_toggled)

        th_layout.addWidget(theme_row)
        scroll_layout.addWidget(theme_frame)

        # ---- Backup section ----
        backup_frame = QFrame()
        backup_frame.setObjectName("SettingsSection")
        b_layout = QVBoxLayout(backup_frame)
        b_layout.setContentsMargins(16, 12, 16, 12)
        b_layout.setSpacing(8)

        backup_title = QLabel("Database Backup")
        backup_title.setObjectName("SettingsSectionTitle")
        b_layout.addWidget(backup_title)

        backup_row = QFrame()
        backup_row.setObjectName("SettingsRow")
        br_layout = QHBoxLayout(backup_row)
        br_layout.setContentsMargins(0, 0, 0, 0)
        br_layout.setSpacing(8)

        backup_label = QLabel("Enable daily backup")
        backup_label.setObjectName("SettingsLabel")
        br_layout.addWidget(backup_label)
        br_layout.addStretch()

        self.backup_toggle_btn, self.backup_toggle_set_checked = _create_toggle_button(
            self.dark_mode
        )
        br_layout.addWidget(self.backup_toggle_btn)

        def backup_label_press(event):
            if event.button() == Qt.LeftButton and self.backup_toggle_btn is not None:
                self.backup_toggle_btn.toggle()
            super(QLabel, backup_label).mousePressEvent(event)

        backup_label.mousePressEvent = backup_label_press

        self.backup_toggle_btn.toggled.connect(self._on_backup_toggled)

        b_layout.addWidget(backup_row)

        self.backup_path_label = QLabel()
        self.backup_path_label.setObjectName("SettingsHint")
        b_layout.addWidget(self.backup_path_label)

        scroll_layout.addWidget(backup_frame)


        # ---- Reports section ----
        reports_frame = QFrame()
        reports_frame.setObjectName("SettingsSection")
        r_layout = QVBoxLayout(reports_frame)
        r_layout.setContentsMargins(16, 12, 16, 12)
        r_layout.setSpacing(8)

        reports_title = QLabel("Reports")
        reports_title.setObjectName("SettingsSectionTitle")
        r_layout.addWidget(reports_title)

        row = QHBoxLayout()
        row.setSpacing(10)

        lbl = QLabel("Report name")
        lbl.setObjectName("SettingsLabel")

        self.edit_report_name = QLineEdit()
        self.edit_report_name.setPlaceholderText("e.g., AK ENTERPRISES")

        self.edit_report_name.setReadOnly(True)
        self.edit_report_name.setEnabled(False)


        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self.edit_report_name)
        self.btn_edit_report = QPushButton("Edit")
        self.btn_edit_report.setObjectName("SecondaryButton")
        self.btn_edit_report.setCursor(QCursor(Qt.PointingHandCursor))

        self.btn_save_report = QPushButton("Save")
        self.btn_save_report.setObjectName("SecondaryButton")
        self.btn_save_report.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_save_report.setEnabled(False)

        row.addWidget(self.btn_edit_report)
        row.addWidget(self.btn_save_report)

        self.btn_edit_report.clicked.connect(self._on_edit_report_title)
        self.btn_save_report.clicked.connect(self._on_save_report_title)


        r_layout.addLayout(row)
        scroll_layout.addWidget(reports_frame)
        scroll_layout.addStretch()


        scroll.setWidget(scroll_widget)
        self.scroll = scroll
        layout.addWidget(scroll)

        

        # ---- Footer buttons ----
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 8, 0, 0)
        footer.addStretch()

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("LogoutButton")
        logout_btn.setCursor(QCursor(Qt.PointingHandCursor))
        logout_btn.clicked.connect(self._on_logout_clicked)
        footer.addWidget(logout_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("SecondaryButton")
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)

        layout.addLayout(footer)

    def _populate(self):
        """Sync toggle states with main window WITHOUT side-effects."""
        # Theme toggle: reflect main.dark_mode, but quiet so we don't flip it.
        if self.theme_toggle_set_checked:
            self.theme_toggle_set_checked(bool(self.main.dark_mode), quiet=True)

        # Backup toggle: reflect main.backup_enabled
        if self.backup_toggle_set_checked:
            self.backup_toggle_set_checked(bool(self.main.backup_enabled), quiet=True)

        if self.main.backup_enabled and self.main.backup_dir:
            self.backup_path_label.setText(
                f"Backups folder: {self.main.backup_dir}"
            )
        else:
            self.backup_path_label.setText("Backups are currently disabled.")

        current = getattr(self.main, "report_title", getattr(self.main, "report_name", "AK ENTERPRISES"))
        self.edit_report_name.setText(current)
        

    # ---------- Handlers ----------

    def _on_theme_toggled(self, checked: bool):
        """
        Called ONLY when user clicks the toggle.
        We delegate theme switching to main and then re-style this dialog.
        """
        self.main.toggle_theme()
        self.dark_mode = self.main.dark_mode
        self._apply_styles()

    def _on_backup_toggled(self, checked: bool):
        enabled = checked

        if enabled:
            # Ask for folder if we don't have one yet
            if not self.main.backup_dir:
                folder = QFileDialog.getExistingDirectory(
                    self,
                    "Select backup folder",
                    "",
                )
                if not folder:
                    # user cancelled -> revert toggle quietly
                    if self.backup_toggle_set_checked:
                        self.backup_toggle_set_checked(False, quiet=True)
                    return
                self.main.backup_dir = folder

            self.main.backup_enabled = True
            # FIRST: make today's backup immediately
            self.main._perform_backup()
            # THEN: start the timer (no initial check needed now)
            self.main._setup_backup_schedule(initial_check=False)

        else:
            self.main.backup_enabled = False
            self.main._save_app_settings()
            self.main._setup_backup_schedule(initial_check=False)

        # update label
        if self.main.backup_enabled and self.main.backup_dir:
            self.backup_path_label.setText(
                f"Backups folder: {self.main.backup_dir}"
            )
        else:
            self.backup_path_label.setText("Backups are currently disabled.")

            
    def _on_logout_clicked(self):
        self.main.logout()
        self.accept()


    def _on_report_name_changed(self):
        title = (self.edit_report_name.text() or "").strip() or "AK ENTERPRISES"
        self.main.report_title = title
        self.main.report_name = title  # optional compatibility
        if hasattr(self.main, "_save_app_settings"):
            self.main._save_app_settings()
    def _on_edit_report_title(self):
        self.edit_report_name.setEnabled(True)
        self.edit_report_name.setReadOnly(False)
        self.edit_report_name.setFocus()
        self.btn_save_report.setEnabled(True)

    def _on_save_report_title(self):
        title = (self.edit_report_name.text() or "").strip() or "AK ENTERPRISES"

        self.main.report_title = title
        self.main.report_name = title  # optional compatibility

        if hasattr(self.main, "_save_app_settings"):
            self.main._save_app_settings()

        # lock again
        self.edit_report_name.setReadOnly(True)
        self.edit_report_name.setEnabled(False)
        self.btn_save_report.setEnabled(False)


    # ---------- styles ----------

    def _apply_styles(self):
        dark = self.dark_mode

        bg = "#000000" if dark else "#ffffff"          # full dialog background
        section_bg = "#020617" if dark else "#f9fafb"  # cards
        border = "#1f2937" if dark else "#e2e8f0"
        text = "#e5e7eb" if dark else "#0f172a"
        muted = "#9ca3af" if dark else "#64748b"
        danger_bg = "#fee2e2"
        danger_fg = "#b91c1c"

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg};
            }}

            #SettingsScroll {{
                background-color: {bg};
                border: none;
            }}

            #SettingsContent {{
                background-color: {bg};
            }}

            #SettingsTitle {{
                font-size: 20px;
                font-weight: 600;
                color: {text};
            }}

            #SettingsSection {{
                background-color: {section_bg};
                border-radius: 16px;
                border: 1px solid {border};
            }}

            #SettingsSectionTitle {{
                font-size: 14px;
                font-weight: 600;
                color: {text};
            }}

            #SettingsLabel {{
                font-size: 12px;
                color: {muted};
            }}

            #SettingsValue {{
                font-size: 13px;
                font-weight: 500;
                color: {text};
            }}

            #SettingsHint {{
                font-size: 11px;
                color: {muted};
            }}

            #PermTagEnabled, #PermTagDisabled {{
                border-radius: 999px;
                padding: 4px 12px;
                font-size: 11px;
            }}

            #PermTagEnabled {{
                background-color: rgba(22, 163, 74, 0.12);
                color: #16a34a;
                border: 1px solid rgba(22, 163, 74, 0.35);
            }}

            #PermTagDisabled {{
                background-color: rgba(148, 163, 184, 0.18);
                color: {muted};
                border: 1px dashed rgba(148, 163, 184, 0.7);
            }}

            QLabel {{
                color: {text};
            }}

            QPushButton#LogoutButton {{
                background-color: {danger_bg};
                color: {danger_fg};
                border-radius: 8px;
                padding: 6px 20px;
                border: 1px solid {danger_fg};
                font-weight: 500;
            }}
            QPushButton#LogoutButton:hover {{
                background-color: #fecaca;
            }}

            QPushButton#SecondaryButton {{
                background-color: transparent;
                color: {text};
                border-radius: 8px;
                padding: 6px 20px;
                border: 1px solid {border};
                font-weight: 500;
            }}
            QPushButton#SecondaryButton:hover {{
                background-color: rgba(148, 163, 184, 0.18);
            }}

            QToolButton#SettingsToggle {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            QToolButton#SettingsToggle:hover {{
                background: transparent;
            }}
            """
        )
