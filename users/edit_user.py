# users/edit_user.py
import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QMessageBox,
    QLayout, 
    QLayoutItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint
from PySide6.QtGui import QCursor

from users.add_user import AddUserDialog, hash_password, ensure_permissions_columns


# ---------- small helper so a whole row is clickable ----------

class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------- EDIT USER DIALOG (reuses AddUserDialog layout) ----------

class EditUserDialog(AddUserDialog):
    """
    Uses the same UI as AddUserDialog but:
      - Title = "Edit User"
      - Primary button text = "Edit User"
      - Fields pre-filled from user_data
      - Updates existing row instead of inserting a new one
    """

    def __init__(self, db_conn: sqlite3.Connection, user_data: dict, parent=None):
        self.user_data = user_data  # must contain at least: id, username, permission flags
        super().__init__(db_conn, parent)

        # change heading & primary button text (they were created in AddUserDialog)
        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit User")

        self.primary_btn = self.findChild(QPushButton, "DialogPrimaryButton")
        if self.primary_btn:
            self.primary_btn.setText("Edit User")

        # pre-fill with existing data
        self._load_user_data()

    def _load_user_data(self):
        u = self.user_data

        # username editable (can be changed)
        self.edit_username.setText(u.get("username", ""))

        # cannot recover password hash -> keep empty, optional update
        self.edit_password.clear()
        self.edit_confirm.clear()
        self.edit_password.setPlaceholderText("Leave blank to keep current password")
        self.edit_confirm.setPlaceholderText("Leave blank to keep current password")

        # permissions (granular)
        self.chk_add_invoices.setChecked(bool(u.get("can_add_invoices", 0)))
        self.chk_edit_invoices.setChecked(bool(u.get("can_edit_invoices", 0)))
        self.chk_manage_invoices.setChecked(bool(u.get("can_manage_invoices", 0)))

        self.chk_add_payments.setChecked(bool(u.get("can_add_payments", 0)))
        self.chk_edit_payments.setChecked(bool(u.get("can_edit_payments", 0)))
        self.chk_manage_payments.setChecked(bool(u.get("can_manage_payments", 0)))

        self.chk_add_order_booker.setChecked(bool(u.get("can_add_order_booker", 0)))
        self.chk_edit_order_booker.setChecked(bool(u.get("can_edit_order_booker", 0)))

        self.chk_add_pjp.setChecked(bool(u.get("can_add_pjp", 0)))
        self.chk_edit_pjp.setChecked(bool(u.get("can_edit_pjp", 0)))

        self.chk_add_customer.setChecked(bool(u.get("can_add_customer", 0)))
        self.chk_edit_customer.setChecked(bool(u.get("can_edit_customer", 0)))

        self.chk_ledger.setChecked(bool(u.get("can_ledger", 0)))

        if hasattr(self, "chk_settings") and self.chk_settings:
            self.chk_settings.setChecked(bool(u.get("can_settings", 0)))

    # override AddUserDialog save handler
    def _on_add_clicked(self):
        user_id = self.user_data["id"]
        new_username = self.edit_username.text().strip()
        password = self.edit_password.text()
        confirm = self.edit_confirm.text()

        if not new_username:
            QMessageBox.warning(self, "Validation error", "Username is required.")
            return

        if password or confirm:
            if password != confirm:
                QMessageBox.warning(self, "Validation error", "Passwords do not match.")
                return
            new_hash = hash_password(password)
        else:
            new_hash = None

        # read granular widgets
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
        can_settings = 1 if (
            hasattr(self, "chk_settings")
            and self.chk_settings
            and self.chk_settings.isChecked()
        ) else 0

        # backward-compatible coarse permissions
        can_invoices     = 1 if (can_add_invoices or can_edit_invoices or can_manage_invoices) else 0
        can_payments     = 1 if (can_add_payments or can_edit_payments or can_manage_payments) else 0
        can_order_booker = 1 if (can_add_order_booker or can_edit_order_booker) else 0
        can_pjps         = 1 if (can_add_pjp or can_edit_pjp) else 0
        can_customers    = 1 if (can_add_customer or can_edit_customer) else 0

        # enforce at least one permission
        if not (can_invoices or can_payments or can_order_booker or can_pjps or can_customers or can_ledger or can_settings):
            QMessageBox.warning(self, "Validation error", "At least one permission is required.")
            return

        try:
            cur = self.conn.cursor()

            if new_hash is not None:
                cur.execute(
                    """
                    UPDATE users SET
                        username = ?,
                        password_hash = ?,

                        can_invoices = ?,
                        can_payments = ?,
                        can_order_booker = ?,
                        can_pjps = ?,
                        can_customers = ?,

                        can_add_invoices = ?,
                        can_edit_invoices = ?,
                        can_manage_invoices = ?,

                        can_add_payments = ?,
                        can_edit_payments = ?,
                        can_manage_payments = ?,

                        can_add_order_booker = ?,
                        can_edit_order_booker = ?,

                        can_add_pjp = ?,
                        can_edit_pjp = ?,

                        can_add_customer = ?,
                        can_edit_customer = ?,

                        can_ledger = ?,
                        can_settings = ?
                    WHERE id = ?
                    """,
                    (
                        new_username,
                        new_hash,

                        can_invoices, can_payments, can_order_booker, can_pjps, can_customers,

                        can_add_invoices, can_edit_invoices, can_manage_invoices,
                        can_add_payments, can_edit_payments, can_manage_payments,
                        can_add_order_booker, can_edit_order_booker,
                        can_add_pjp, can_edit_pjp,
                        can_add_customer, can_edit_customer,
                        can_ledger,
                        can_settings,

                        user_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE users SET
                        username = ?,

                        can_invoices = ?,
                        can_payments = ?,
                        can_order_booker = ?,
                        can_pjps = ?,
                        can_customers = ?,

                        can_add_invoices = ?,
                        can_edit_invoices = ?,
                        can_manage_invoices = ?,

                        can_add_payments = ?,
                        can_edit_payments = ?,
                        can_manage_payments = ?,

                        can_add_order_booker = ?,
                        can_edit_order_booker = ?,

                        can_add_pjp = ?,
                        can_edit_pjp = ?,

                        can_add_customer = ?,
                        can_edit_customer = ?,

                        can_ledger = ?,
                        can_settings = ?
                    WHERE id = ?
                    """,
                    (
                        new_username,

                        can_invoices, can_payments, can_order_booker, can_pjps, can_customers,

                        can_add_invoices, can_edit_invoices, can_manage_invoices,
                        can_add_payments, can_edit_payments, can_manage_payments,
                        can_add_order_booker, can_edit_order_booker,
                        can_add_pjp, can_edit_pjp,
                        can_add_customer, can_edit_customer,
                        can_ledger,
                        can_settings,

                        user_id,
                    ),
                )

            self.conn.commit()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update user:\n\n{e}")
            return

        self.accept()

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, hspacing=8, vspacing=8):
        super().__init__(parent)
        self._items = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        l, t, r, b = self.getContentsMargins()
        size += QSize(l + r, t + b)
        return size

    def _do_layout(self, rect: QRect, test_only: bool):
        x = rect.x()
        y = rect.y()
        line_h = 0

        for item in self._items:
            w = item.widget()
            if w is None or not w.isVisible():
                continue

            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspace

            if next_x - self._hspace > rect.right() and line_h > 0:
                x = rect.x()
                y += line_h + self._vspace
                next_x = x + hint.width() + self._hspace
                line_h = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x = next_x
            line_h = max(line_h, hint.height())

        return (y - rect.y()) + line_h



# ---------- MANAGE USERS LIST DIALOG ----------

class ManageUsersDialog(QDialog):
    """
    Shows the list of users with their permissions, Edit/Delete buttons,
    and an Add User button. Respects parent.dark_mode.
    """

    def __init__(self, db_conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = db_conn
        self.conn.row_factory = sqlite3.Row
        ensure_permissions_columns(self.conn)
        self.dark_mode = bool(getattr(parent, "dark_mode", False))

        self.setWindowTitle("Manage Users")
        self.setModal(True)
        self.resize(860, 640)
        self.setMinimumWidth(820)

        self._build_ui()
        self._apply_styles()

        # IMPORTANT: define before load_users()
        self.rows = []
        self.page_size = 50  # avoid "refresh but not visible" due to pagination

        self.load_users()

    # ----- UI ---------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("ManageHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        title = QLabel("Manage Users")
        title.setObjectName("ManageTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)

        # Scroll area with rows
        scroll = QScrollArea()
        scroll.setObjectName("ManageScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("ManageContent")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # lazy loading trigger
        self.scroll_area = scroll
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(80)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(24, 16, 24, 16)

        add_btn = QPushButton("+ Add User")
        add_btn.setObjectName("AddUserBtn")
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self.open_add_user)

        close_footer = QPushButton("Close")
        close_footer.setObjectName("CloseBtn")
        close_footer.setCursor(QCursor(Qt.PointingHandCursor))
        close_footer.clicked.connect(self.reject)

        f_layout.addWidget(add_btn)
        f_layout.addStretch()
        f_layout.addWidget(close_footer)
        layout.addWidget(footer)

    # ----- load + build rows -----------------------------------------

    def load_users(self):
        """Reload users with lazy loading (keyset pagination)."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.rows.clear()
        self._reset_pagination()
        self._load_next_page(reset_scroll=True)

    def _reset_pagination(self):
        self._cursor_key = None
        self._has_more = True
        self._is_loading = False
        self._spacer = None
        self._empty_label = None

    def _fetch_page(self, cursor_key):
        query = """
            SELECT
                id,
                username,
                is_superuser,
                can_add_invoices, can_edit_invoices, can_manage_invoices,
                can_add_payments, can_edit_payments, can_manage_payments,
                can_add_order_booker, can_edit_order_booker,
                can_add_pjp, can_edit_pjp,
                can_add_customer, can_edit_customer,
                can_ledger,
                can_settings
            FROM users
        """

        params = []
        if cursor_key:
            last_is_super, last_username, last_id = cursor_key
            query += """
                WHERE (
                    is_superuser < ?
                    OR (is_superuser = ? AND username COLLATE NOCASE > ?)
                    OR (is_superuser = ? AND username COLLATE NOCASE = ? AND id > ?)
                )
            """
            params.extend([last_is_super, last_is_super, last_username, last_is_super, last_username, last_id])

        query += """
            ORDER BY
                is_superuser DESC,
                username COLLATE NOCASE ASC,
                id ASC
            LIMIT ?
        """
        params.append(int(self.page_size))

        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur.fetchall() or []


    def _load_next_page(self, *, reset_scroll: bool = False):
        if self._is_loading or not self._has_more:
            return
        self._is_loading = True
        try:
            if reset_scroll and hasattr(self, "scroll_area") and self.scroll_area:
                self.scroll_area.verticalScrollBar().setValue(0)

            if self._spacer is not None:
                self.content_layout.removeWidget(self._spacer)
                self._spacer.deleteLater()
                self._spacer = None

            rows = self._fetch_page(self._cursor_key)

            if not rows and not self.rows:
                lbl = QLabel("No users found.")
                lbl.setObjectName("EmptyLabel")
                lbl.setAlignment(Qt.AlignCenter)
                self.content_layout.addWidget(lbl)
                self._empty_label = lbl
                self._has_more = False
                return

            if not rows:
                self._has_more = False
                return

            start_idx = len(self.rows) + 1
            for off, row in enumerate(rows):
                data = dict(row) if isinstance(row, sqlite3.Row) else {
                    "id": row[0],
                    "username": row[1],
                    "is_superuser": row[2],

                    "can_add_invoices": row[3],
                    "can_edit_invoices": row[4],
                    "can_manage_invoices": row[5],

                    "can_add_payments": row[6],
                    "can_edit_payments": row[7],
                    "can_manage_payments": row[8],

                    "can_add_order_booker": row[9],
                    "can_edit_order_booker": row[10],

                    "can_add_pjp": row[11],
                    "can_edit_pjp": row[12],

                    "can_add_customer": row[13],
                    "can_edit_customer": row[14],

                    "can_ledger": row[15],
                    "can_settings": row[16],
                }

                data["row_number"] = start_idx + off
                self._add_user_row(data)
                self.rows.append(data)  # store data (not widgets)

            last = rows[-1]
            if isinstance(last, sqlite3.Row):
                self._cursor_key = (int(last["is_superuser"] or 0), (last["username"] or ""), int(last["id"]))

            else:
                self._cursor_key = (int(last[2] or 0), (last[1] or ""), int(last[0]))

            if len(rows) < int(self.page_size):
                self._has_more = False

        finally:
            # spacer should eat extra vertical space so rows don't stretch
            self._spacer = QWidget()
            self._spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._spacer.setMinimumHeight(1)
            self.content_layout.addWidget(self._spacer)

            # CRITICAL: allow future loads
            self._is_loading = False

    def _on_scroll(self, value: int):
        if not hasattr(self, "scroll_area") or not self.scroll_area:
            return
        sb = self.scroll_area.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        if value >= sb.maximum() - 150:
            self._load_next_page()

    def _add_user_row(self, user_data: dict):
        is_super = bool(user_data.get("is_superuser", 0))

        row = ClickableFrame()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # ✅ row won’t stretch vertically
        row.setObjectName("UserRowSuper" if is_super else "UserRow")
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(16)

        # Left: username + "Super User" badge + permission badges
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        # top line: username + super badge
        name_layout = QHBoxLayout()
        name_label = QLabel(user_data.get("username", ""))
        name_label.setObjectName("UsernameLabel")
        name_layout.addWidget(name_label)

        if is_super:
            super_badge = QLabel("Super User")
            super_badge.setObjectName("SuperBadge")
            name_layout.addWidget(super_badge)

        name_layout.addStretch()
        left_layout.addLayout(name_layout)

        # permission pills (category-level)
        perms = []

        if user_data.get("can_add_invoices") or user_data.get("can_edit_invoices") or user_data.get("can_manage_invoices"):
            perms.append("Invoices")
        if user_data.get("can_add_payments") or user_data.get("can_edit_payments") or user_data.get("can_manage_payments"):
            perms.append("Payments")
        if user_data.get("can_add_order_booker") or user_data.get("can_edit_order_booker"):
            perms.append("Order Booker")
        if user_data.get("can_add_pjp") or user_data.get("can_edit_pjp"):
            perms.append("PJPs")
        if user_data.get("can_add_customer") or user_data.get("can_edit_customer"):
            perms.append("Customers")
        if user_data.get("can_ledger"):
            perms.append("Ledger")
        if user_data.get("can_settings"):
            perms.append("Settings")

# permission pills (packed + wrap)
        perm_wrap = QWidget()
        perm_layout = FlowLayout(perm_wrap, margin=0, hspacing=8, vspacing=8)

        for p in perms:
            badge = QLabel(p)
            badge.setObjectName("PermBadge")
            badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            badge.adjustSize()
            perm_layout.addWidget(badge)

        left_layout.addWidget(perm_wrap)

        # Row layout: left content + right buttons
        row_layout.addLayout(left_layout, 1)

        # Right: Edit / Delete
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("EditBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda _, u=user_data: self.open_edit_user(u))

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DeleteBtn")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))

        if is_super:
            delete_btn.setEnabled(False)
            delete_btn.setToolTip("Cannot delete Super User")
        else:
            delete_btn.clicked.connect(lambda _, u=user_data.get("username", ""): self.confirm_delete(u))

        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        row_layout.addLayout(btn_layout)

        # clicking row (anywhere) also opens edit
        row.clicked.connect(lambda u=user_data: self.open_edit_user(u))

        self.content_layout.addWidget(row)

    # ----- actions ----------------------------------------------------

    def open_add_user(self):
        dlg = AddUserDialog(self.conn, self)
        dlg.user_added.connect(self.load_users)
        dlg.exec()

    def open_edit_user(self, user_data: dict):
        dlg = EditUserDialog(self.conn, user_data, self)
        if dlg.exec():
            self.load_users()

    def confirm_delete(self, username: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete user <b>{username}</b>?<br><br>"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                cur = self.conn.cursor()
                cur.execute("DELETE FROM users WHERE username = ?", (username,))
                self.conn.commit()
                self.load_users()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete user:\n{e}")

    # ----- styles (light & dark, matching your dashboard) ------------

    def _apply_styles(self):
        dark = self.dark_mode

        bg = "#000000" if dark else "#ffffff"
        header_bg = "#020617" if dark else "#f8fafc"
        card_bg = "#020617" if dark else "#f8fafc"
        border = "#1f2937" if dark else "#e2e8f0"
        text = "#e5e7eb" if dark else "#0f172a"
        msg_box_text = "#e0e0e0" if dark else "#333333"
        muted = "#9ca3af" if dark else "#64748b"
        primary = "rgb(37, 79, 167)"
        danger = "#ef4444"

        close_bg = "#020617" if dark else "#f1f5f9"
        close_text = text
        close_border = border
        close_hover = "#1f2937" if dark else "#e2e8f0"

        title_color = "#f9fafb" if dark else "#111827"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}

            #ManageScroll, #ManageContent {{
                background-color: {bg};
            }}

            #ManageHeader {{
                background-color: {header_bg};
            }}

            #ManageTitle {{
                font-size: 20px;
                font-weight: 600;
                color: {title_color};
            }}

            QPushButton {{
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
                border: none;
            }}

            #UserRow, #UserRowSuper {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}

            #UsernameLabel {{
                font-weight: 600;
                color: {text};
            }}

            #SuperBadge {{
                background-color: {primary};
                color: white;
                padding: 2px 10px;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 500;
            }}

            #PermBadge {{
                background-color: {'#000000' if dark else '#e5e7eb'};
                color: {muted};
                padding: 4px 10px;
                border-radius: 999px;
                font-size: 12px;
            }}

            #EditBtn {{
                background-color: {'#020617' if dark else '#f1f5f9'};
                color: {text};
                border: 1px solid {border};
            }}
            #EditBtn:hover {{
                background-color: {primary};
                color: white;
            }}

            #DeleteBtn {{
                background-color: {danger};
                color: white;
            }}
            #DeleteBtn:hover {{
                background-color: #dc2626;
            }}
            #DeleteBtn:disabled {{
                background-color: #4b5563;
            }}

            #AddUserBtn {{
                background-color: {primary};
                color: white;
                padding: 10px 22px;
            }}
            #AddUserBtn:hover {{
                background-color: rgb(30, 64, 140);
            }}

            #CloseBtn {{
                background-color: {close_bg};
                color: {close_text};
                border: 1px solid {close_border};
                padding: 8px 20px;
            }}
            #CloseBtn:hover {{
                background-color: {close_hover};
            }}

            QFrame {{
                background-color: {header_bg};
            }}

            QMessageBox {{
                background-color: {bg};
                color: {msg_box_text};
            }}

            QMessageBox QLabel {{
                color: {msg_box_text};
            }}

            QMessageBox QPushButton {{
                background-color: {primary};
                color: white;
                border: 1px solid {primary};
                padding: 5px 15px;
                border-radius: 5px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: rgb(30, 64, 140);
            }}
            QMessageBox QPushButton#qt_msgbox_buttonbox_No {{
                background-color: {close_bg};
                color: {close_text};
                border: 1px solid {close_border};
            }}
            QMessageBox QPushButton#qt_msgbox_buttonbox_No:hover {{
                background-color: {close_hover};
            }}
        """)
