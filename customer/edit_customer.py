# customer/edit_customer.py
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
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor

from customer.add_customer import AddCustomerDialog


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------- EDIT CUSTOMER DIALOG (reuses AddCustomerDialog layout) ----------

class EditCustomerDialog(AddCustomerDialog):
    """
    Uses the same UI as AddCustomerDialog but:
      - Title = "Edit Customer"
      - Primary button text = "Save Changes"
      - Fields pre-filled from customer_data
      - Updates existing row instead of inserting a new one
    """

    def __init__(self, db_conn: sqlite3.Connection, customer_data: dict, parent=None):
        self.customer_data = customer_data  # id, pjp_id, name, contact, address
        super().__init__(db_conn, parent)

        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit Customer")

        self.primary_btn = self.findChild(QPushButton, "DialogPrimaryButton")
        if self.primary_btn:
            self.primary_btn.setText("Save Changes")

        self._load_customer_data()

    def _set_combo_by_data(self, combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def _load_customer_data(self):
        c = self.customer_data
        pjp_id = c["pjp_id"]

        # Find order_booker_id for this pjp
        cur = self.conn.cursor()
        cur.execute(
            "SELECT order_booker_id FROM pjps WHERE id = ?",
            (pjp_id,),
        )
        row = cur.fetchone()
        ob_id = row["order_booker_id"] if row else None

        if ob_id:
            # Set OB combo, this will also reload PJPs
            self._set_combo_by_data(self.combo_ob, ob_id)
            # Now set PJP combo
            self._set_combo_by_data(self.combo_pjp, pjp_id)

        self.edit_name.setText(c["name"])
        self.edit_contact.setText(c["contact"])
        self.edit_address.setText(c["address"])

    def _on_add_clicked(self):
        """Override to update instead of insert."""
        c_id = self.customer_data["id"]

        ob_index = self.combo_ob.currentIndex()
        order_booker_id = self.combo_ob.itemData(ob_index) if ob_index >= 0 else None

        pjp_index = self.combo_pjp.currentIndex()
        pjp_id = self.combo_pjp.itemData(pjp_index) if pjp_index >= 0 else None

        name = self.edit_name.text().strip()
        contact = self.edit_contact.text().strip()
        address = self.edit_address.text().strip()

        if not order_booker_id or not pjp_id or not name or not contact or not address:
            QMessageBox.warning(
                self,
                "Validation error",
                "Order Booker, PJP, Name, Contact, and Address are all required.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE customers
                SET pjp_id = ?, name = ?, contact = ?, address = ?
                WHERE id = ?
                """,
                (pjp_id, name, contact, address, c_id),
            )
            self.conn.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to update customer:\n{e}"
            )


# ---------- MANAGE CUSTOMERS LIST DIALOG ----------

class ManageCustomersDialog(QDialog):
    """
    Shows the list of customers with Edit/Delete buttons,
    and an Add Customer button. Respects parent.dark_mode.
    """

    def __init__(self, db_conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = db_conn
        self.conn.row_factory = sqlite3.Row
        self.dark_mode = bool(getattr(parent, "dark_mode", False))

        self.setWindowTitle("Manage Customers")
        self.setModal(True)
        self.resize(700, 600)
        self.setMinimumWidth(650)

        self._build_ui()
        self._apply_styles()
        self.rows = []
        self.page_size = 10

        # Load customers after the dialog is shown, so UI feels instant
        QTimer.singleShot(0, self.load_customers)
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
        title = QLabel("Manage Customers")
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
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)

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

        add_btn = QPushButton("+ Add Customer")
        add_btn.setObjectName("AddCustomerBtn")
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self.open_add_customer)

        close_footer = QPushButton("Close")
        close_footer.setObjectName("CloseBtn")
        close_footer.setCursor(QCursor(Qt.PointingHandCursor))
        close_footer.clicked.connect(self.reject)

        f_layout.addWidget(add_btn)
        f_layout.addStretch()
        f_layout.addWidget(close_footer)
        layout.addWidget(footer)

    # ----- load + build rows -----------------------------------------

    def load_customers(self):
        """Reload customers with lazy loading (keyset pagination)."""
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
                c.id,
                c.name AS customer_name,
                c.contact,
                c.address,
                c.pjp_id,
                COALESCE(pj.pjp_name, '') AS pjp_name,
                COALESCE(ob.name, '')     AS ob_name
            FROM customers c
            LEFT JOIN pjps pj ON pj.id = c.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
        """
        params = []
        if cursor_key:
            last_ob, last_pjp, last_cust, last_id = cursor_key
            query += """
                WHERE (
                    COALESCE(ob.name,'') > ?
                    OR (COALESCE(ob.name,'') = ? AND COALESCE(pj.pjp_name,'') > ?)
                    OR (COALESCE(ob.name,'') = ? AND COALESCE(pj.pjp_name,'') = ? AND c.name > ?)
                    OR (COALESCE(ob.name,'') = ? AND COALESCE(pj.pjp_name,'') = ? AND c.name = ? AND c.id > ?)
                )
            """
            params.extend([
                last_ob,
                last_ob, last_pjp,
                last_ob, last_pjp, last_cust,
                last_ob, last_pjp, last_cust, last_id
            ])

        query += """
            ORDER BY
                COALESCE(ob.name,'') ASC,
                COALESCE(pj.pjp_name,'') ASC,
                c.name ASC,
                c.id ASC
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
                lbl = QLabel("No customers found.")
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
                    "id": row[0], "customer_name": row[1], "contact": row[2], "address": row[3],
                    "pjp_id": row[4], "pjp_name": row[5], "ob_name": row[6]
                }
                data["row_number"] = start_idx + off
# map to the keys your row builder + edit dialog expect
                cust_data = {
                    "id": data["id"],
                    "pjp_id": data["pjp_id"],
                    "name": data.get("customer_name", data.get("name", "")),
                    "contact": data.get("contact", data.get("phone", "")),  # will change in step 3
                    "address": data["address"],
                    "pjp_name": data["pjp_name"],
                    "ob_name": data["ob_name"],
                    "row_number": data.get("row_number"),
                }
                self._add_customer_row(cust_data)
                self.rows.append(cust_data)  # store data, not widgets

            last = rows[-1]
            if isinstance(last, sqlite3.Row):
                self._cursor_key = (
                    last["ob_name"] or "", last["pjp_name"] or "",
                    last["customer_name"] or "", int(last["id"])
                )
            else:
                self._cursor_key = (last[6] or "", last[5] or "", last[1] or "", int(last[0]))

            if len(rows) < int(self.page_size):
                self._has_more = False
        finally:
            # remove old spacer if present
            if self._spacer is not None:
                self.content_layout.removeWidget(self._spacer)
                self._spacer.deleteLater()
                self._spacer = None

            # spacer must EXPAND to eat extra space, so rows don't stretch
            self._spacer = QWidget()
            self._spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._spacer.setMinimumHeight(1)
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


    def _add_customer_row(self, cust_data: dict):
        row = ClickableFrame()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.setObjectName("CustRow")
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(16)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        name_label = QLabel(cust_data["name"])
        name_label.setObjectName("CustNameLabel")

        contact_label = QLabel(cust_data["contact"])
        contact_label.setObjectName("CustContactLabel")

        address_label = QLabel(cust_data["address"])
        address_label.setObjectName("CustAddressLabel")

        meta_label = QLabel(f'{cust_data["ob_name"]} • {cust_data["pjp_name"]}')
        meta_label.setObjectName("CustMetaLabel")

        left_layout.addWidget(name_label)
        left_layout.addWidget(contact_label)
        left_layout.addWidget(address_label)
        left_layout.addWidget(meta_label)

        row_layout.addLayout(left_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("EditBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda _, c=cust_data: self.open_edit_customer(c))

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DeleteBtn")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        delete_btn.clicked.connect(
            lambda _, c=cust_data: self.confirm_delete(c["id"], c["name"])
        )

        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        row_layout.addLayout(btn_layout)

        row.clicked.connect(lambda c=cust_data: self.open_edit_customer(c))
        self.content_layout.addWidget(row)

    # ----- actions ----------------------------------------------------

    def open_add_customer(self):
        from customer.add_customer import AddCustomerDialog

        dlg = AddCustomerDialog(self.conn, self)
        dlg.customer_added.connect(self.load_customers)
        dlg.exec()


    def open_edit_customer(self, cust_data: dict):
        dlg = EditCustomerDialog(self.conn, cust_data, self)
        if dlg.exec():
            self.load_customers()

    def confirm_delete(self, cust_id: int, cust_name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete customer <b>{cust_name}</b>?<br><br>"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                cur = self.conn.cursor()
                cur.execute("DELETE FROM customers WHERE id = ?", (cust_id,))
                self.conn.commit()
                self.load_customers()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete customer:\n{e}")

    # ----- styles (light & dark, with QMessageBox) ------------

    def _apply_styles(self):
        dark = self.dark_mode

        bg       = "#000000" if dark else "#ffffff"
        header_bg = "#020617" if dark else "#f8fafc"
        card_bg  = "#020617" if dark else "#f8fafc"
        border   = "#1f2937" if dark else "#e2e8f0"
        text     = "#e5e7eb" if dark else "#0f172a"
        muted    = "#9ca3af" if dark else "#64748b"
        primary  = "rgb(37, 79, 167)"
        danger   = "#ef4444"
        msg_box_text = "#e0e0e0" if dark else "#333333"
        close_bg     = "#020617" if dark else "#f1f5f9"
        close_text   = text
        close_border = border
        close_hover  = "#1f2937" if dark else "#e2e8f0"
        title_color  = "#f9fafb" if dark else "#111827"

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

            #CustRow {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}

            #CustNameLabel {{
                font-weight: 600;
                color: {text};
            }}

            #CustContactLabel, #CustAddressLabel, #CustMetaLabel {{
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

            #AddCustomerBtn {{
                background-color: {primary};
                color: white;
            }}
            #AddCustomerBtn:hover {{
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
