import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from order_booker.add_order_booker import AddOrderBookerDialog


# ---------- small helper so a whole row is clickable ----------

class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------- EDIT ORDER BOOKER DIALOG (reuses AddOrderBookerDialog layout) ----------

class EditOrderBookerDialog(AddOrderBookerDialog):
    """
    Uses the same UI as AddOrderBookerDialog but:
      - Title = "Edit Order Booker"
      - Primary button text = "Save Changes"
      - Fields pre-filled from ob_data
      - Updates existing row instead of inserting a new one
    """

    def __init__(self, db_conn: sqlite3.Connection, ob_data: dict, parent=None):
        self.ob_data = ob_data  # contains: id, name, contact, address, is_active
        super().__init__(db_conn, parent)

        # change heading & primary button text (created in AddOrderBookerDialog)
        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit Order Booker")

        self.primary_btn = self.findChild(QPushButton, "DialogPrimaryButton")
        if self.primary_btn:
            self.primary_btn.setText("Save Changes")

        # pre-fill with existing data
        self._load_ob_data()

    def _load_ob_data(self):
        ob = self.ob_data

        self.edit_name.setText(ob["name"])
        self.edit_contact.setText(ob["contact"])
        self.edit_address.setText(ob["address"])

    # override AddOrderBookerDialog save handler
    def _on_add_clicked(self):
        ob_id = self.ob_data["id"]
        new_name = self.edit_name.text().strip()
        new_contact = self.edit_contact.text().strip()
        new_address = self.edit_address.text().strip()

        if not new_name:
            QMessageBox.warning(
                self,
                "Validation error",
                "Name is required.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE order_bookers
                SET name = ?, contact = ?, address = ?
                WHERE id = ?
                """,
                (new_name, new_contact, new_address, ob_id),
            )
            self.conn.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to update order booker:\n{e}"
            )


# ---------- MANAGE ORDER BOOKERS LIST DIALOG ----------

class ManageOrderBookersDialog(QDialog):
    """
    Shows the list of order bookers with Edit/Delete buttons
    and an Add Order Booker button. Respects parent.dark_mode.
    """

    def __init__(self, db_conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = bool(getattr(parent, "dark_mode", False))

        self.rows = []
        self.page_size = 25


        self.setWindowTitle("Manage Order Bookers")
        self.setModal(True)
        self.resize(700, 600)
        self.setMinimumWidth(650)

        self._build_ui()
        self._apply_styles()
        self.load_order_bookers()


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
        title = QLabel("Manage Order Bookers")
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

        add_btn = QPushButton("+ Add Order Booker")
        add_btn.setObjectName("AddOBBtn")
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self.open_add_order_booker)

        close_footer = QPushButton("Close")
        close_footer.setObjectName("CloseBtn")
        close_footer.setCursor(QCursor(Qt.PointingHandCursor))
        close_footer.clicked.connect(self.reject)

        f_layout.addWidget(add_btn)
        f_layout.addStretch()
        f_layout.addWidget(close_footer)
        layout.addWidget(footer)

    # ----- load + build rows -----------------------------------------

    def load_order_bookers(self):
        """Reload order bookers with lazy loading (keyset pagination)."""
        # Clear existing row widgets
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows.clear()

        # Reset paging
        self._reset_pagination()

        # Load first page
        self._load_next_page(reset_scroll=True)

    def _reset_pagination(self):
        self._cursor_key = None
        self._has_more = True
        self._is_loading = False
        # remove stale empty label
        self._empty_label = None
        # spacer is re-added when needed
        self._spacer = None

    def _fetch_page(self, cursor_key):
        """Fetch one page using (name,id) keyset."""
        query = """
            SELECT id, name, contact, address
            FROM order_bookers
        """
        params = []

        if cursor_key:
            last_name, last_id = cursor_key
            query += """ WHERE (name > ? OR (name = ? AND id > ?)) """
            params.extend([last_name, last_name, last_id])

        query += " ORDER BY name ASC, id ASC LIMIT ?"
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

            # Ensure spacer is last: remove before appending
            if self._spacer is not None:
                self.content_layout.removeWidget(self._spacer)
                self._spacer.deleteLater()
                self._spacer = None

            rows = self._fetch_page(self._cursor_key)

            if not rows and not self.rows:
                lbl = QLabel("No order bookers found.")
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
                    "id": row[0], "name": row[1], "contact": row[2], "address": row[3]
                }
                data["row_number"] = start_idx + off
                self._add_ob_row(data)
                self.rows.append(data) 


            last = rows[-1]
            if isinstance(last, sqlite3.Row):
                self._cursor_key = (last["name"], int(last["id"]))
            else:
                self._cursor_key = (last[1], int(last[0]))

            if len(rows) < int(self.page_size):
                self._has_more = False

        finally:
            # keep a small spacer at bottom
            self._spacer = QWidget()
            self._spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._spacer.setFixedHeight(1)
            self.content_layout.addWidget(self._spacer)
            self._is_loading = False

    def _on_scroll(self, value: int):
        if not hasattr(self, "scroll_area") or not self.scroll_area:
            return
        sb = self.scroll_area.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        if value >= sb.maximum() - 150:
            self._load_next_page()



    def _add_ob_row(self, ob_data: dict):
        row = ClickableFrame()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # ✅ prevents vertical stretch
        row.setObjectName("OBRow")
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(16)

        # Left: name + contact + address
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        name_label = QLabel(ob_data["name"])
        name_label.setObjectName("OBNameLabel")

        contact_label = QLabel(ob_data["contact"])
        contact_label.setObjectName("OBContactLabel")

        address_label = QLabel(ob_data["address"])
        address_label.setObjectName("OBAddressLabel")

        left_layout.addWidget(name_label)
        left_layout.addWidget(contact_label)
        left_layout.addWidget(address_label)

        row_layout.addLayout(left_layout, 1)

        # Right: Edit / Delete
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("EditBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda _, ob=ob_data: self.open_edit_order_booker(ob))

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DeleteBtn")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        delete_btn.clicked.connect(
            lambda _, ob=ob_data: self.confirm_delete(ob["id"], ob["name"])
        )

        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        row_layout.addLayout(btn_layout)

        # clicking row (anywhere) also opens edit
        row.clicked.connect(lambda ob=ob_data: self.open_edit_order_booker(ob))

        self.content_layout.addWidget(row)

    # ----- actions ----------------------------------------------------

    def open_add_order_booker(self):
        dlg = AddOrderBookerDialog(self.conn, self)
        dlg.order_booker_added.connect(lambda _id, _name: self.load_order_bookers())
        dlg.exec()


    def open_edit_order_booker(self, ob_data: dict):
        dlg = EditOrderBookerDialog(self.conn, ob_data, self)
        if dlg.exec():
            self.load_order_bookers()

    def confirm_delete(self, ob_id: int, ob_name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete order booker <b>{ob_name}</b>?<br><br>"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                cur = self.conn.cursor()
                cur.execute("DELETE FROM order_bookers WHERE id = ?", (ob_id,))
                self.conn.commit()
                self.load_order_bookers()
            except sqlite3.IntegrityError as e:
                # Likely there are PJPs referencing this order booker (FK RESTRICT)
                QMessageBox.warning(
                    self,
                    "Cannot Delete",
                    "This order booker has PJPs assigned and cannot be deleted.\n\n"
                    "Remove or reassign those PJPs first, then try deleting this order booker again",
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete order booker:\n{e}")

    # ----- styles (light & dark, matching your dashboard) ------------

    def _apply_styles(self):
        dark = self.dark_mode

        # Define colors
        bg       = "#000000" if dark else "#ffffff"      # Overall dialog background (dark/white)
        header_bg = "#020617" if dark else "#f8fafc"     # Header/Footer background
        card_bg  = "#020617" if dark else "#f8fafc"      # Row background
        border   = "#1f2937" if dark else "#e2e8f0"      # Border color
        text     = "#e5e7eb" if dark else "#0f172a"      # Primary text color
        muted    = "#9ca3af" if dark else "#64748b"      # Secondary text
        primary  = "rgb(37, 79, 167)"                    # Primary action color
        danger   = "#ef4444"                             # Delete button color

        # For the message box text, ensure it’s readable in dark mode
        msg_box_text = "#e0e0e0" if dark else "#333333"

        # Close button colors
        close_bg     = "#020617" if dark else "#f1f5f9"
        close_text   = text
        close_border = border
        close_hover  = "#1f2937" if dark else "#e2e8f0"

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

            #OBRow {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}

            #OBNameLabel {{
                font-weight: 600;
                color: {text};
            }}

            #OBContactLabel, #OBAddressLabel {{
                color: {muted};
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

            #AddOBBtn {{
                background-color: {primary};
                color: white;
            }}
            #AddOBBtn:hover {{
                background-color: rgb(30, 64, 140);
            }}

            #CloseBtn {{
                background-color: {close_bg};
                color: {close_text};
                border: 1px solid {close_border};
            }}
            #CloseBtn:hover {{
                background-color: {close_hover};
            }}

            #EmptyLabel {{
                color: {muted};
            }}

            /* --- QMessageBox Styling --- */
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
