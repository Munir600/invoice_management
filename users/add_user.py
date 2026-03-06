import sqlite3
import hashlib
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QSizePolicy,
    QMessageBox,
    QWidget,
    QToolButton,
    QScrollArea,
)

from PySide6.QtSvg import QSvgRenderer

from PySide6.QtGui import QIcon, QPainter, QPixmap, QCursor, QGuiApplication
from PySide6.QtCore import Qt, Signal, QByteArray, QSize, QTimer, QPoint, Signal

def ensure_permissions_columns(conn: sqlite3.Connection) -> None:
    """Ensure users table has all granular permission columns (adds any missing)."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = {r[1] for r in cur.fetchall()}

        new_cols = [
            "can_add_invoices", "can_edit_invoices", "can_manage_invoices",
            "can_add_payments", "can_edit_payments", "can_manage_payments",
            "can_add_order_booker", "can_edit_order_booker",
            "can_add_pjp", "can_edit_pjp",
            "can_add_customer", "can_edit_customer",
            "can_ledger",
            "can_settings",
        ]

        for c in new_cols:
            if c not in cols:
                cur.execute(f"ALTER TABLE users ADD COLUMN {c} INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass


def hash_password(password: str) -> str:
    """
    Very simple SHA-256 hash for now.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""
    clicked = Signal()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class AddUserDialog(QDialog):
    """
    Dialog for adding a new user.
    """

    user_added = Signal()

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = parent.dark_mode if parent and hasattr(parent, 'dark_mode') else False
        self.setWindowTitle("Add New User")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(620)
        self.setSizeGripEnabled(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        ensure_permissions_columns(self.conn)
        self._build_ui()
        self._apply_local_styles()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # behave as if the primary button was clicked
            self._on_add_clicked()
        else:
            super().keyPressEvent(event)

    def _show_success_banner(self, message: str):
        notification = QLabel(message, self)
        notification.setStyleSheet(
            "background-color: #22c55e; color: white; padding: 10px;"
            "border-radius: 5px; font-weight: bold;"
        )
        notification.setAlignment(Qt.AlignCenter)

        # Size and position: top-center of this dialog window
        width = notification.sizeHint().width() + 20
        height = notification.sizeHint().height()
        notification.setFixedSize(width, height)

        x = (self.width() - width) // 2
        y = 20   # a bit from the top of the dialog
        notification.move(x, y)

        notification.raise_()   # ensure it’s above all child widgets
        notification.show()

        QTimer.singleShot(2000, notification.deleteLater)

    # def showEvent(self, event):
    #     super().showEvent(event)
    #     # Ensure the dialog is fully visible on-screen (prevents cropped footer/buttons).
    #     QTimer.singleShot(0, self._ensure_on_screen)


    def _ensure_fully_visible(self):
        # Choose the screen where the dialog currently is
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()      # excludes taskbar
        geo = self.frameGeometry()

        # If bottom is going out of screen, move up
        overflow_bottom = geo.bottom() - avail.bottom()
        if overflow_bottom > 0:
            new_y = self.y() - overflow_bottom - 10  # 10px padding
            if new_y < avail.top():
                new_y = avail.top() + 10
            self.move(self.x(), new_y)

        # Also keep top inside screen (optional safety)
        if geo.top() < avail.top():
            self.move(self.x(), avail.top() + 10)


    def _ensure_on_screen(self):
        # Prefer the screen where the parent lives; fallback to primary screen.
        screen = None
        if self.parent():
            screen = QGuiApplication.screenAt(self.parent().mapToGlobal(QPoint(0, 0)))
        if screen is None:
            screen = QGuiApplication.screenAt(self.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        geo = screen.availableGeometry()

        # Clamp height to screen while keeping a usable minimum.
        min_h = 620
        h = max(self.height(), min_h)
        h = min(h, max(min_h, geo.height() - 80))
        self.resize(self.width(), h)

        # Center on parent if possible; otherwise center on screen.
        if self.parent():
            target = self.parent().frameGeometry().center()
        else:
            target = geo.center()
        self.move(target - self.rect().center())

        # Final clamp inside available geometry.
        x = max(geo.left(), min(self.x(), geo.right() - self.width()))
        y = max(geo.top(), min(self.y(), geo.bottom() - self.height()))
        self.move(x, y)


    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- Header (centered title) ----
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.addStretch()
        title_label = QLabel("Add New User")
        title_label.setObjectName("DialogTitle")
        header_layout.addWidget(title_label, alignment=Qt.AlignCenter)
        header_layout.addStretch()
        main_layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(sep)

        # ---- Body ----
        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(8)

        # Username
        lbl_username = QLabel("Username")
        lbl_username.setCursor(Qt.PointingHandCursor)
        self.edit_username = QLineEdit()
        self.edit_username.setPlaceholderText("Enter username")
        self.edit_username.setMinimumHeight(36)
        self.edit_username.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_username)
        body_layout.addWidget(self.edit_username)

        # Password and Confirm Password
        self.edit_password = self._create_password_input("Password", body_layout)
        self.edit_confirm = self._create_password_input("Confirm Password", body_layout)

        # Small separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        body_layout.addWidget(sep2)

        # Permissions section
        lbl_permissions = QLabel("User Permissions")
        lbl_permissions.setObjectName("SectionLabel")
        body_layout.addWidget(lbl_permissions)


        # --- Permissions (granular) ---
       
        self.chk_add_invoices    = self._permission_row("Add Invoices", body_layout)
        self.chk_edit_invoices   = self._permission_row("Edit Invoices", body_layout)
        self.chk_manage_invoices = self._permission_row("Manage Invoices", body_layout)

        self.chk_add_payments    = self._permission_row("Add Payments", body_layout)
        self.chk_edit_payments   = self._permission_row("Edit Payments", body_layout)
        self.chk_manage_payments = self._permission_row("Manage Payments", body_layout)

        self.chk_add_order_booker  = self._permission_row("Add Order Booker", body_layout)
        self.chk_edit_order_booker = self._permission_row("Edit Order Booker", body_layout)

        self.chk_add_pjp  = self._permission_row("Add PJP", body_layout)
        self.chk_edit_pjp = self._permission_row("Edit PJP", body_layout)

        self.chk_add_customer  = self._permission_row("Add Customer", body_layout)
        self.chk_edit_customer = self._permission_row("Edit Customer", body_layout)

        self.chk_ledger = self._permission_row("Ledger", body_layout)


        self.chk_settings = self._permission_row("Settings", body_layout)
        # Body should scroll so footer buttons never go off-screen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        main_layout.addWidget(scroll)

        # ---- Footer Buttons ----
        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 20)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("DialogCancelButton")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setCursor(Qt.PointingHandCursor)

        btn_add = QPushButton("Add User")
        btn_add.setObjectName("DialogPrimaryButton")
        btn_add.clicked.connect(self._on_add_clicked)
        btn_add.setCursor(Qt.PointingHandCursor)

        btn_cancel.setMinimumWidth(140)
        btn_add.setMinimumWidth(160)

        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_add)

        main_layout.addWidget(footer)

    def _create_password_input(self, label_text: str, parent_layout: QVBoxLayout) -> QLineEdit:
        """
        Helper to create a QLineEdit with an embedded eye toggle action inside the input box.
        """
        lbl = QLabel(label_text)
        lbl.setCursor(Qt.PointingHandCursor)

        edit_field = QLineEdit()
        edit_field.setObjectName("PasswordEdit")
        edit_field.setEchoMode(QLineEdit.Password)
        edit_field.setPlaceholderText(f"Enter {label_text.lower()}")
        edit_field.setMinimumHeight(36)
        edit_field.setCursor(Qt.PointingHandCursor)

        # Base64 for eye icons depending on mode
        if self.dark_mode:
            open_eye_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzljYTNhZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xIDEyczQtOCAxMS04czExIDggMTEgOC00IDgtMTEgOC0xMS04LTExLTh6Ij48L3BhdGg+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyI+PC9jaXJjbGU+PC9zdmc+"
            slashed_eye_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzljYTNhZiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNy45NCAxNy45NEE5LjYxIDkuNjEgMCAwMSAxMiAyMGMtNi44OSAwLTEwLjgzLTgtMTAuODMtOGExNi41MiAxNi41MiAwIDAxNS4zNy01LjY2Ii8+PHBhdGggZD0iTTkuOSAxNC4xQTkgOSAwIDAxMTIgMTJjNi44OSAwIDExIDggMTEgOGExNi41MiAxNi41MiAwIDAxLTQuNi00LjR6Ii8+PHBhdGggZD0iTTkgOSBhMyAzIDAgMTEgNiAweiIvPjxsaW5lIHgxPSIxIiB5MT0iMjMiIHgyPSIyMyIgeTI9IjEiLz48L3N2Zz4="
        else:
            open_eye_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzZiNzI4MCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xIDEyczQtOCAxMS04czExIDggMTEgOC00IDgtMTEgOC0xMS04LTExLTh6Ij48L3BhdGg+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMyI+PC9jaXJjbGU+PC9zdmc+"
            slashed_eye_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgMjQgMjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzZiNzI4MCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNy45NCAxNy45NGE5LjYxIDkuNjEgMCAwMSAxMiAyMGMtNi44OSAwLTEwLjgzLTgtMTAuODMtOGExNi41MiAxNi41MiAwIDAxNS4zNy01LjY2Ii8+PHBhdGggZD0iTTkuOSAxNC4xQTkgOSAwIDAxMTIgMTJjNi44OSAwIDExIDggMTEgOGExNi41MiAxNi41MiAwIDAxLTQuNi00LjR6Ii8+PHBhdGggZD0iTTkgOSBhMyAzIDAgMTEgNiAweiIvPjxsaW5lIHgxPSIxIiB5MT0iMjMiIHgyPSIyMyIgeTI9IjEiLz48L3N2Zz4="

        def create_icon(base64_str):
            svg_bytes = QByteArray.fromBase64(base64_str.encode('utf-8'))
            renderer = QSvgRenderer(svg_bytes)
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)

        open_eye_icon = create_icon(open_eye_base64)
        slashed_eye_icon = create_icon(slashed_eye_base64)

        # Add toggle action to the trailing position (inside the input on the right)
        toggle_action = edit_field.addAction(open_eye_icon, QLineEdit.TrailingPosition)
        toggle_action.setToolTip("Toggle password visibility")

        def toggle_visibility():
            if edit_field.echoMode() == QLineEdit.Password:
                edit_field.setEchoMode(QLineEdit.Normal)
                toggle_action.setIcon(slashed_eye_icon)
            else:
                edit_field.setEchoMode(QLineEdit.Password)
                toggle_action.setIcon(open_eye_icon)

        toggle_action.triggered.connect(toggle_visibility)

        parent_layout.addWidget(lbl)
        parent_layout.addWidget(edit_field)
        return edit_field
    
    def _permission_row(self, label_text: str, parent_layout: QVBoxLayout) -> QToolButton:
        """
        Helper to add a single permission row using a toggle switch with SVG icons.
        """
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 3, 0, 3)

        lbl = ClickableLabel(label_text)
        lbl.setCursor(QCursor(Qt.PointingHandCursor))

        btn = QToolButton()
        btn.setObjectName("PermissionToggle")
        btn.setCheckable(True)
        btn.setCursor(QCursor(Qt.PointingHandCursor))

        # Base64 for toggle icons depending on mode
        if self.dark_mode:
            toggle_off_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjIwIiByeD0iMTAiIGZpbGw9IiM0YjU1NjMiLz48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSI5IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg=="
        else:
            toggle_off_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSI0MCIgaGVpZ2h0PSIyMCIgcng9IjEwIiBmaWxsPSIjNkI3MjgwIi8+CjxjaXJjbGUgY3g9IjEwIiBjeT0iMTAiIHI9IjkiIGZpbGw9IndoaXRlIi8+Cjwvc3ZnPg=="

        toggle_on_base64 = "PHN2ZyB2aWV3Qm94PSIwIDAgNDAgMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjIwIiByeD0iMTAiIGZpbGw9IiMyNTRGQTciLz48Y2lyY2xlIGN4PSIzMCIgY3k9IjEwIiByPSI5IiBmaWxsPSJ3aGl0ZSIvPjwvc3ZnPg=="

        def create_icon(base64_str: str) -> QIcon:
            svg_bytes = QByteArray.fromBase64(base64_str.encode("utf-8"))
            renderer = QSvgRenderer(svg_bytes)
            pixmap = QPixmap(40, 20)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)

        off_icon = create_icon(toggle_off_base64)
        on_icon = create_icon(toggle_on_base64)

        btn.setIcon(off_icon)
        btn.setIconSize(QSize(40, 20))

        def on_toggled(checked: bool):
            btn.setIcon(on_icon if checked else off_icon)

        btn.toggled.connect(on_toggled)

        # clicking on label toggles button
        lbl.clicked.connect(btn.toggle)

        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(btn)

        parent_layout.addWidget(row)
        return btn



    def _apply_local_styles(self):
        """
        Local QSS for the dialog – input styling, tick checkboxes, buttons.
        Updated to remove separate toggle button styles and add padding for embedded icon.
        """
        if self.dark_mode:
            self.setStyleSheet(
                """
                QDialog {
                    background-color: #000000;
                }
                QLabel {
                    color: #e5e7eb;
                }
                QLabel#DialogTitle {
                    font-size: 18px;
                    font-weight: 600;
                    color: #f9fafb;
                }
                QLabel#SectionLabel {
                    font-weight: 600;
                    margin-top: 4px;
                    color: #e5e7eb;
                }
                /* Text fields */
                QLineEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                
                QLineEdit#PasswordEdit {
                    padding-right: 40px;

                }
                /* Primary / Cancel buttons */
                QPushButton#DialogPrimaryButton {
                    background-color: rgb(37, 79, 167);
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogPrimaryButton:hover {
                    background-color: rgb(30, 64, 140);
                }
                QPushButton#DialogCancelButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogCancelButton:hover {
                    background-color: #b91c1c;
                }
                /* Permission Toggle Button */
                QToolButton#PermissionToggle {
                    background: transparent;
                    border: none;
                    padding: 0px;
                }
                QToolButton#PermissionToggle:hover {
                    background: transparent;
                }
                QFrame[frameShape="4"] {
                    background-color: #1a1a1a;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog {
                    background-color: #ffffff;
                }
                QLabel#DialogTitle {
                    font-size: 18px;
                    font-weight: 600;
                }
                QLabel#SectionLabel {
                    font-weight: 600;
                    margin-top: 4px;
                }
                /* Text fields */
                QLineEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                /* Add right padding for password fields to accommodate the embedded icon */
                QLineEdit#PasswordEdit {
                    padding-right: 40px;
                }
                /* Primary / Cancel buttons */
                QPushButton#DialogPrimaryButton {
                    background-color: rgb(37, 79, 167);
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogPrimaryButton:hover {
                    background-color: rgb(30, 64, 140);
                }
                QPushButton#DialogCancelButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogCancelButton:hover {
                    background-color: #b91c1c;
                }
                /* Permission Toggle Button */
                QToolButton#PermissionToggle {
                    background: transparent;
                    border: none;
                    padding: 0px;
                }
                QToolButton#PermissionToggle:hover {
                    background: transparent;
                }
                """
            )

    # ------------------------------------------------------------------ Logic
    def _on_add_clicked(
        self):
        username = self.edit_username.text().strip()
        password = self.edit_password.text()
        confirm = self.edit_confirm.text()

        if not username:
            QMessageBox.warning(self, "Validation error", "Username is required.")
            return
        if not password:
            QMessageBox.warning(self, "Validation error", "Password is required.")
            return
        if password != confirm:
            QMessageBox.warning(self, "Validation error", "Passwords do not match.")
            return

        # -------------------------
        # NEW: granular permissions
        # -------------------------
        can_add_invoices    = 1 if self.chk_add_invoices.isChecked() else 0
        can_edit_invoices   = 1 if self.chk_edit_invoices.isChecked() else 0
        can_manage_invoices = 1 if self.chk_manage_invoices.isChecked() else 0

        can_add_payments    = 1 if self.chk_add_payments.isChecked() else 0
        can_edit_payments   = 1 if self.chk_edit_payments.isChecked() else 0
        can_manage_payments = 1 if self.chk_manage_payments.isChecked() else 0

        can_add_order_booker  = 1 if self.chk_add_order_booker.isChecked() else 0
        can_edit_order_booker = 1 if self.chk_edit_order_booker.isChecked() else 0

        can_add_pjp  = 1 if self.chk_add_pjp.isChecked() else 0
        can_edit_pjp = 1 if self.chk_edit_pjp.isChecked() else 0

        can_add_customer  = 1 if self.chk_add_customer.isChecked() else 0
        can_edit_customer = 1 if self.chk_edit_customer.isChecked() else 0

        can_ledger = 1 if self.chk_ledger.isChecked() else 0

        can_settings = 1 if self.chk_settings.isChecked() else 0
        # ----------------------------------------
        # Backward-compatible coarse permissions
        # ----------------------------------------
        can_invoices     = 1 if (can_add_invoices or can_edit_invoices or can_manage_invoices) else 0
        can_payments     = 1 if (can_add_payments or can_edit_payments or can_manage_payments) else 0
        can_order_booker = 1 if (can_add_order_booker or can_edit_order_booker) else 0
        can_pjps         = 1 if (can_add_pjp or can_edit_pjp) else 0
        can_customers    = 1 if (can_add_customer or can_edit_customer) else 0

        # ✅ enforce at least one permission
        if not (can_invoices or can_payments or can_order_booker or can_pjps or can_customers or can_ledger):
            QMessageBox.warning(self, "Validation error", "At least one permission is required.")
            return

        is_superuser = 0  # only the seeded admin user is superuser

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    is_superuser,

                    -- coarse
                    can_invoices,
                    can_payments,
                    can_order_booker,
                    can_pjps,
                    can_customers,

                    -- granular
                    can_add_invoices,
                    can_edit_invoices,
                    can_manage_invoices,

                    can_add_payments,
                    can_edit_payments,
                    can_manage_payments,

                    can_add_order_booker,
                    can_edit_order_booker,

                    can_add_pjp,
                    can_edit_pjp,

                    can_add_customer,
                    can_edit_customer,

                    can_ledger,
                    can_settings
                )
                VALUES (?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?)
                """,
                (
                    username,
                    hash_password(password),
                    is_superuser,

                    # coarse
                    can_invoices,
                    can_payments,
                    can_order_booker,
                    can_pjps,
                    can_customers,

                    # granular
                    can_add_invoices,
                    can_edit_invoices,
                    can_manage_invoices,

                    can_add_payments,
                    can_edit_payments,
                    can_manage_payments,

                    can_add_order_booker,
                    can_edit_order_booker,

                    can_add_pjp,
                    can_edit_pjp,

                    can_add_customer,
                    can_edit_customer,

                    can_ledger,
                    can_settings,
                ),
            )



            self.conn.commit()
        except sqlite3.IntegrityError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not add user. This username may already exist.\n\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving user:\n\n{e}",
            )
            return
        
        self._show_success_banner("User added successfully")
        self.user_added.emit()

 
        # Clear fields for next entry
        self.edit_username.clear()
        self.edit_password.clear()
        self.edit_confirm.clear()

        # Uncheck all permissions (if you want a fresh start each time)
        
        for cb in [
            self.chk_add_invoices, self.chk_edit_invoices, self.chk_manage_invoices,
            self.chk_add_payments, self.chk_edit_payments, self.chk_manage_payments,
            self.chk_add_order_booker, self.chk_edit_order_booker,
            self.chk_add_pjp, self.chk_edit_pjp,
            self.chk_add_customer, self.chk_edit_customer,
            self.chk_ledger,
            self.chk_settings,
        ]:
            cb.setChecked(False)


        # Focus back to first field
        self.edit_username.setFocus()
        # Note: do NOT call self.accept()

