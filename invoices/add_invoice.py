# invoices/add_invoice.py
import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QWidget,
    QComboBox,
    QDateEdit,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer
from PySide6.QtGui import QDoubleValidator, QGuiApplication
from datetime import datetime

class AddInvoiceDialog(QDialog):

    invoice_created = Signal()

    """
    Dialog for adding a new Invoice.

    Fields:
      - Auto-generated Invoice ID (INVddMMyyXXXXXXXX, read-only)
      - Invoice Date (QDateEdit with calendar popup)
      - Order Booker (combo)
      - PJP (combo, filtered by OB)
      - Customer (combo, filtered by PJP)
      - Amount (numeric, PKR)
    """

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        self.setWindowTitle("Add Invoice")    
        # self.setModal(True)

        self._build_ui()
        self._customer_popup_after_add = False
        self.combo_customer.activated.connect(self._on_customer_selected)
        self._apply_local_styles()

        self._load_order_bookers()
        self._load_initial_pjps_and_customers()

        # Wider dialog, let Qt decide the height
        self.resize(800, self.sizeHint().height())

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


    # --------------------------- UI ---------------------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- Header (centered title) ----
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.addStretch()

        title_label = QLabel("Add Invoice")
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
        body_layout.setSpacing(16)

        # =========== ROW 1: Invoice ID | Invoice Date ===========
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # left: Invoice ID
        col_code = QVBoxLayout()
        lbl_code = QLabel("Invoice ID")
        lbl_code.setCursor(Qt.PointingHandCursor)
        self.edit_code = QLineEdit()
        self.edit_code.setReadOnly(True)
        self.edit_code.setMinimumHeight(36)
        self.edit_code.setCursor(Qt.ArrowCursor)
        self.edit_code.setText(self._generate_invoice_code())
        col_code.addWidget(lbl_code)
        col_code.addWidget(self.edit_code)

        # right: Invoice Date
        col_date = QVBoxLayout()
        lbl_date = QLabel("Invoice Date")
        lbl_date.setCursor(Qt.PointingHandCursor)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)  # calendar popup
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMinimumHeight(36)
        self.date_edit.setCursor(Qt.PointingHandCursor)
        col_date.addWidget(lbl_date)
        col_date.addWidget(self.date_edit)

        row1.addLayout(col_code, 1)
        row1.addLayout(col_date, 1)
        body_layout.addLayout(row1)

        # =========== ROW 2: Order Booker | PJP ===========
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # left: Order Booker
        col_ob = QVBoxLayout()
        lbl_ob = QLabel("Order Booker")
        lbl_ob.setCursor(Qt.PointingHandCursor)
        self.combo_ob = QComboBox()
        self.combo_ob.setMinimumHeight(36)
        self.combo_ob.setCursor(Qt.PointingHandCursor)
        self.combo_ob.currentIndexChanged.connect(self._on_ob_changed)
        col_ob.addWidget(lbl_ob)
        col_ob.addWidget(self.combo_ob)

        # right: PJP
        col_pjp = QVBoxLayout()
        lbl_pjp = QLabel("PJP")
        lbl_pjp.setCursor(Qt.PointingHandCursor)
        self.combo_pjp = QComboBox()
        self.combo_pjp.setMinimumHeight(36)
        self.combo_pjp.setCursor(Qt.PointingHandCursor)
        self.combo_pjp.currentIndexChanged.connect(self._on_pjp_changed)
        col_pjp.addWidget(lbl_pjp)
        col_pjp.addWidget(self.combo_pjp)

        row2.addLayout(col_ob, 1)
        row2.addLayout(col_pjp, 1)
        body_layout.addLayout(row2)

        # =========== ROW 3: Customer | Amount (PKR) ===========
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        # left: Customer
        col_customer = QVBoxLayout()
        lbl_customer = QLabel("Customer")
        lbl_customer.setCursor(Qt.PointingHandCursor)
        self.combo_customer = QComboBox()
        self.combo_customer.setMinimumHeight(36)
        self.combo_customer.setCursor(Qt.PointingHandCursor)
        col_customer.addWidget(lbl_customer)
        col_customer.addWidget(self.combo_customer)

        # right: Amount
        col_amount = QVBoxLayout()
        lbl_amount = QLabel("Amount (PKR)")
        lbl_amount.setCursor(Qt.PointingHandCursor)
        self.edit_amount = QLineEdit()
        self.edit_amount.setPlaceholderText("Enter invoice amount in PKR")
        self.edit_amount.setMinimumHeight(36)
        self.edit_amount.setCursor(Qt.PointingHandCursor)

        validator = QDoubleValidator(0.0, 999999999.99, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.edit_amount.setValidator(validator)

        col_amount.addWidget(lbl_amount)
        col_amount.addWidget(self.edit_amount)

        row3.addLayout(col_customer, 1)
        row3.addLayout(col_amount, 1)
        body_layout.addLayout(row3)

        main_layout.addWidget(body)

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

        btn_add = QPushButton("Add")
        btn_add.setObjectName("DialogPrimaryButton")
        btn_add.clicked.connect(self._on_add_clicked)
        btn_add.setCursor(Qt.PointingHandCursor)

        btn_cancel.setMinimumWidth(140)
        btn_add.setMinimumWidth(140)

        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_add)

        main_layout.addWidget(footer)

    # ------------------ Invoice Code Generation ------------------

    def _generate_invoice_code(self) -> str:
            """
            Generates the next numeric Invoice ID (integer sequence starting at 1).
            """
            try:
                cur = self.conn.cursor()
                # Fetch the last used number from meta
                cur.execute("SELECT value FROM invoice_meta WHERE key = 'invoice_last_number'")
                row = cur.fetchone()
                
                if row:
                    # Handle both row factory and tuple results
                    last_num = int(row[0]) if isinstance(row, (list, tuple)) else int(row['value'])
                    next_num = last_num + 1
                else:
                    next_num = 1
                    
                return str(next_num)
            except Exception:
                return "1"


    # ------------------ Data loading ------------------

    def _load_order_bookers(self):
        self.combo_ob.clear()

        # Placeholder (not a real OB)
        self.combo_ob.addItem("Select Order Booker", None)

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, name
                FROM order_bookers
                WHERE is_active = 1
                ORDER BY name ASC
                """
            )
            rows = cur.fetchall()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load Order Bookers:\n{e}",
            )
            return

        for row in rows:
            ob_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
            ob_name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
            self.combo_ob.addItem(ob_name, ob_id)

        # Start at the placeholder
        self.combo_ob.setCurrentIndex(0)


    def _load_pjps_for_ob(self, order_booker_id: int | None):
        self.combo_pjp.clear()
        self.combo_customer.clear()

        # Placeholders
        self.combo_pjp.addItem("Select PJP", None)
        self.combo_customer.addItem("Select Customer", None)

        if not order_booker_id:
            # No OB selected -> just placeholders
            self.combo_pjp.setCurrentIndex(0)
            self.combo_customer.setCurrentIndex(0)
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, pjp_name
                FROM pjps
                WHERE order_booker_id = ?
                  AND is_active = 1
                ORDER BY pjp_name ASC
                """,
                (order_booker_id,),
            )
            rows = cur.fetchall()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load PJPs:\n{e}",
            )
            return

        for row in rows:
            p_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
            p_name = row["pjp_name"] if isinstance(row, sqlite3.Row) else row[1]
            self.combo_pjp.addItem(p_name, p_id)

        self.combo_pjp.setCurrentIndex(0)
        self.combo_customer.setCurrentIndex(0)


    def _load_customers_for_pjp(self, pjp_id: int | None):
        self.combo_customer.clear()

        # Placeholder
        self.combo_customer.addItem("Select Customer", None)

        if not pjp_id:
            self.combo_customer.setCurrentIndex(0)
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, name
                FROM customers
                WHERE pjp_id = ?
                  AND is_active = 1
                ORDER BY name ASC
                """,
                (pjp_id,),
            )
            rows = cur.fetchall()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load customers:\n{e}",
            )
            return

        for row in rows:
            c_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
            c_name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
            self.combo_customer.addItem(c_name, c_id)

        self.combo_customer.setCurrentIndex(0)


    def _load_initial_pjps_and_customers(self):
        # After loading OBs, we just want placeholders initially
        self._load_pjps_for_ob(None)
        self._load_customers_for_pjp(None)


    def _on_ob_changed(self, index: int):
        ob_id = self.combo_ob.itemData(index) if index >= 0 else None
        self._load_pjps_for_ob(ob_id)

    def _on_pjp_changed(self, index: int):
        pjp_id = self.combo_pjp.itemData(index) if index >= 0 else None
        self._load_customers_for_pjp(pjp_id)

    # ------------------------- Styles -------------------------

    def _apply_local_styles(self):
        """Local style for Add Invoice dialog – NO arrow overrides."""
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

                /* Base fields */
                QLineEdit, QComboBox, QDateEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus,
                QComboBox:focus,
                QDateEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }

                /* Dropdown list */
                QComboBox QAbstractItemView {
                    background-color: #020617;
                    color: #e5e7eb;
                    selection-background-color: rgb(37, 79, 167);
                }

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

                /* Base fields */
                QLineEdit, QComboBox, QDateEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus,
                QComboBox:focus,
                QDateEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }

                /* Dropdown list */
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #0f172a;
                    selection-background-color: rgb(37, 79, 167);
                    selection-color: white;
                }

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
                """
            )




    # --------------------------- Logic ---------------------------

    def _on_add_clicked(self):
        code_raw = self.edit_code.text().strip()
        # Enforce pure numeric invoice ID (no prefixes like 'INV')
        code_clean = code_raw.upper().strip()
        if code_clean.startswith('INV'):
            code_clean = code_clean[3:]
        code_clean = code_clean.strip().lstrip('-')
        if not code_clean.isdigit():
            QMessageBox.warning(self, 'Validation error', 'Invoice ID must be numeric (e.g., 1, 2, 3...).')
            return
        code = int(code_clean)
        invoice_date_iso = self.date_edit.date().toString("yyyy-MM-dd")

        ob_index = self.combo_ob.currentIndex()
        pjp_index = self.combo_pjp.currentIndex()
        cust_index = self.combo_customer.currentIndex()

        order_booker_id = self.combo_ob.itemData(ob_index) if ob_index >= 0 else None
        pjp_id = self.combo_pjp.itemData(pjp_index) if pjp_index >= 0 else None
        customer_id = (
            self.combo_customer.itemData(cust_index) if cust_index >= 0 else None
        )

        amount_text = self.edit_amount.text().strip()
        amount = float(amount_text) if amount_text else 0.0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        if (
            not code
            or not invoice_date_iso
            or not order_booker_id
            or not pjp_id
            or not customer_id
            or amount <= 0
        ):
            QMessageBox.warning(
                self,
                "Validation error",
                "All fields are required and amount must be greater than zero.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO invoices (
                    invoice_code,
                    invoice_date,
                    order_booker_id,
                    pjp_id,
                    customer_id,
                    amount,
                    in_ledger,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (code, invoice_date_iso, order_booker_id, pjp_id, customer_id, amount, now_str),
            )

            self.conn.commit()
        except sqlite3.IntegrityError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not add invoice. It may already exist.\n\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving invoice:\n\n{e}",
            )
            return

        # Update the numeric counter used for invoice codes
        try:
            numeric_val = int(code)
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE invoice_meta SET value = ? WHERE key = 'invoice_last_number'",
                (numeric_val,),
            )
            self.conn.commit()
        except Exception:
            # Non-critical; ignore errors updating meta
            pass

        # Show success just once
        self._show_success_banner("Invoice added successfully")

        # Prepare form for next invoice:
        # - generate next invoice code
        # - reset date and amount
        # - KEEP OB / PJP / Customer selections as they are
        self.edit_code.setText(self._generate_invoice_code())
        self.date_edit.setDate(QDate.currentDate())
        self.edit_amount.clear()
        self.invoice_created.emit()
        QTimer.singleShot(0, self._prompt_next_customer)




    def _prompt_next_customer(self):
        """After saving, open Customer dropdown for quick next invoice entry."""
        # If there are no customers loaded, just focus Amount.
        if self.combo_customer.count() <= 1:
            self.edit_amount.setFocus()
            return

        self._customer_popup_after_add = True
        self.combo_customer.setFocus()
        # showPopup works best when scheduled for the next event loop.
        QTimer.singleShot(0, self.combo_customer.showPopup)


    def _on_customer_selected(self, *_):
        """When the user picks a customer after saving, move focus to Amount."""
        if not getattr(self, "_customer_popup_after_add", False):
            return
        self._customer_popup_after_add = False
        self.edit_amount.setFocus()


    