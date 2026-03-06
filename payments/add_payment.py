# payments/add_payment.py
import sqlite3
import os
from datetime import datetime

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
    QDateEdit,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer
from PySide6.QtGui import QDoubleValidator

# --------------------------------------------------------------------
#  AddPaymentDialog
# --------------------------------------------------------------------


class AddPaymentDialog(QDialog):
    """
    Dialog for adding a new Payment.

    Behavior:
      - User types an Invoice ID.
      - Real-time lookup fills details.
      - Payment ID is auto-generated based on Invoice ID.
      - On "Add": Saves to DB, shows success banner, clears form, keeps dialog open.
    """

    # Signal emitted when a payment is successfully added
    payment_added = Signal()

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        # state for current invoice lookup
        self._current_invoice_id: int | None = None
        self._current_invoice_amount: float = 0.0

        self.setWindowTitle("Add Payment")

        self._build_ui()
        # Enter in amount -> submit
        self.edit_amount.returnPressed.connect(self._on_add_clicked)

        QTimer.singleShot(0, self.edit_invoice_code.setFocus)
        self._apply_local_styles()

        # connect real-time lookup for invoice code
        self.edit_invoice_code.textChanged.connect(self._on_invoice_code_changed)

        self._preview_next_payment_id()

        # Let Qt pick a natural size first
        self.adjustSize()

        # Make the dialog a bit smaller so it fits nicely
        max_height = 520          # reduce if you still feel it is tall
        min_width  = 780          # wide enough, but not huge

        width  = max(min_width, self.width())
        height = min(self.height(), max_height)
        self.resize(width, height)

        # When opened from Manage Payments, place it next to that window
        self._position_next_to_parent()
        self._invoice_resolved = False

        # Enter in invoice id -> jump to amount if valid
        self.edit_invoice_code.returnPressed.connect(self._jump_to_amount_if_valid)


    def _jump_to_amount_if_valid(self):
        if not self._invoice_resolved or not self._current_invoice_id:
            QMessageBox.warning(self, "Validation error", "Please enter a valid Invoice ID first.")
            self.edit_invoice_code.setFocus()
            self.edit_invoice_code.selectAll()
            return

        self.edit_amount.setFocus()
        self.edit_amount.selectAll()


    def _position_next_to_parent(self):
        """
        Position this dialog side-by-side with its parent dialog (Manage Invoices)
        instead of centered on top of it.
        """
        parent = self.parent()
        if parent is None or not parent.isVisible():
            return

        parent_geom = parent.frameGeometry()

        # Use the same screen as the parent if possible
        screen = parent.screen() or self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
        else:
            avail = parent_geom

        # Try to place to the right of parent
        x_right = parent_geom.x() + parent_geom.width()
        new_x = x_right
        new_y = parent_geom.y()

        # If there is not enough space on the right, place to the left
        if new_x + self.width() > avail.right():
            new_x = max(avail.left(), parent_geom.x() - self.width() - 10)

        # Clamp vertical position within screen
        if new_y + self.height() > avail.bottom():
            new_y = max(avail.top(), avail.bottom() - self.height())

        self.move(new_x, new_y)


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
        y = 20  # a bit from the top of the dialog
        notification.move(x, y)

        notification.raise_()  # ensure it’s above all child widgets
        notification.show()

        QTimer.singleShot(2000, notification.deleteLater)

    # --------------------------- UI ---------------------------


    def _preview_next_payment_id(self):
        
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM payment_meta WHERE key = 'payment_last_number'")
            last_no = cur.fetchone()[0]
            self.edit_payment_code.setText(str(last_no + 1))
        except Exception:
            pass


    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- Header ----
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.addStretch()

        title_label = QLabel("Add Payment")
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

        # =========== ROW 1: Payment ID | Payment Date ===========
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Payment ID
        col_pay_code = QVBoxLayout()
        lbl_pay_code = QLabel("Payment ID")
        lbl_pay_code.setCursor(Qt.PointingHandCursor)
        self.edit_payment_code = QLineEdit()
        self.edit_payment_code.setReadOnly(True)
        self.edit_payment_code.setPlaceholderText("Auto-generated from Invoice ID")
        self.edit_payment_code.setMinimumHeight(36)
        self.edit_payment_code.setCursor(Qt.ArrowCursor)
        col_pay_code.addWidget(lbl_pay_code)
        col_pay_code.addWidget(self.edit_payment_code)

        # Payment Date
        col_pay_date = QVBoxLayout()
        lbl_pay_date = QLabel("Payment Date")
        lbl_pay_date.setCursor(Qt.PointingHandCursor)
        self.date_payment = QDateEdit()
        self.date_payment.setCalendarPopup(True)
        self.date_payment.setDisplayFormat("dd/MM/yyyy")
        self.date_payment.setDate(QDate.currentDate())
        self.date_payment.setMinimumHeight(36)
        self.date_payment.setCursor(Qt.PointingHandCursor)
        col_pay_date.addWidget(lbl_pay_date)
        col_pay_date.addWidget(self.date_payment)

        row1.addLayout(col_pay_code, 1)
        row1.addLayout(col_pay_date, 1)
        body_layout.addLayout(row1)

        # =========== ROW 2: Invoice ID | Invoice Date ===========
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        # Invoice ID (user types)
        col_inv_code = QVBoxLayout()
        lbl_inv_code = QLabel("Invoice ID")
        lbl_inv_code.setCursor(Qt.PointingHandCursor)
        self.edit_invoice_code = QLineEdit()
        self.edit_invoice_code.setPlaceholderText("Enter Invoice ID (e.g. 1,2,3)")
        self.edit_invoice_code.setMinimumHeight(36)
        self.edit_invoice_code.setCursor(Qt.PointingHandCursor)
        col_inv_code.addWidget(lbl_inv_code)
        col_inv_code.addWidget(self.edit_invoice_code)

        # Invoice Date (auto, read-only)
        col_inv_date = QVBoxLayout()
        lbl_inv_date = QLabel("Invoice Date")
        lbl_inv_date.setCursor(Qt.PointingHandCursor)
        self.edit_invoice_date = QLineEdit()
        self.edit_invoice_date.setReadOnly(True)
        self.edit_invoice_date.setMinimumHeight(36)
        self.edit_invoice_date.setCursor(Qt.ArrowCursor)
        col_inv_date.addWidget(lbl_inv_date)
        col_inv_date.addWidget(self.edit_invoice_date)

        row2.addLayout(col_inv_code, 1)
        row2.addLayout(col_inv_date, 1)
        body_layout.addLayout(row2)

        # =========== ROW 3: Customer | Order Booker ===========
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        # Customer
        col_customer = QVBoxLayout()
        lbl_customer = QLabel("Customer")
        lbl_customer.setCursor(Qt.PointingHandCursor)
        self.edit_customer = QLineEdit()
        self.edit_customer.setReadOnly(True)
        self.edit_customer.setMinimumHeight(36)
        self.edit_customer.setCursor(Qt.ArrowCursor)
        col_customer.addWidget(lbl_customer)
        col_customer.addWidget(self.edit_customer)

        # Order Booker
        col_ob = QVBoxLayout()
        lbl_ob = QLabel("Order Booker")
        lbl_ob.setCursor(Qt.PointingHandCursor)
        self.edit_ob = QLineEdit()
        self.edit_ob.setReadOnly(True)
        self.edit_ob.setMinimumHeight(36)
        self.edit_ob.setCursor(Qt.ArrowCursor)
        col_ob.addWidget(lbl_ob)
        col_ob.addWidget(self.edit_ob)

        row3.addLayout(col_customer, 1)
        row3.addLayout(col_ob, 1)
        body_layout.addLayout(row3)

        # =========== ROW 4: PJP | Invoice Amount ===========
        row4 = QHBoxLayout()
        row4.setSpacing(12)

        # PJP
        col_pjp = QVBoxLayout()
        lbl_pjp = QLabel("PJP")
        lbl_pjp.setCursor(Qt.PointingHandCursor)
        self.edit_pjp = QLineEdit()
        self.edit_pjp.setReadOnly(True)
        self.edit_pjp.setMinimumHeight(36)
        self.edit_pjp.setCursor(Qt.ArrowCursor)
        col_pjp.addWidget(lbl_pjp)
        col_pjp.addWidget(self.edit_pjp)

        # Invoice Amount (auto, read-only)
        col_inv_amount = QVBoxLayout()
        lbl_inv_amount = QLabel("Invoice Amount (PKR)")
        lbl_inv_amount.setCursor(Qt.PointingHandCursor)
        self.edit_invoice_amount = QLineEdit()
        self.edit_invoice_amount.setReadOnly(True)
        self.edit_invoice_amount.setMinimumHeight(36)
        self.edit_invoice_amount.setCursor(Qt.ArrowCursor)
        col_inv_amount.addWidget(lbl_inv_amount)
        col_inv_amount.addWidget(self.edit_invoice_amount)

        row4.addLayout(col_pjp, 1)
        row4.addLayout(col_inv_amount, 1)
        body_layout.addLayout(row4)

        # =========== ROW 5: Payment Amount ===========
        row5 = QHBoxLayout()
        row5.setSpacing(12)

        col_pay_amount = QVBoxLayout()
        lbl_pay_amount = QLabel("Payment Amount (PKR)")
        lbl_pay_amount.setCursor(Qt.PointingHandCursor)
        self.edit_amount = QLineEdit()
        self.edit_amount.setPlaceholderText("Enter amount received")
        self.edit_amount.setMinimumHeight(36)
        self.edit_amount.setCursor(Qt.PointingHandCursor)

        validator = QDoubleValidator(0.0, 999999999.99, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.edit_amount.setValidator(validator)

        col_pay_amount.addWidget(lbl_pay_amount)
        col_pay_amount.addWidget(self.edit_amount)

        row5.addLayout(col_pay_amount, 1)
        row5.addStretch()
        body_layout.addLayout(row5)

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

        btn_add.setDefault(False)
        btn_add.setAutoDefault(False)
        btn_cancel.setAutoDefault(False)


        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_add)



        main_layout.addWidget(footer)

    # ------------------------- Styles -------------------------

    def _apply_local_styles(self):
        """Local style for Add Payment dialog."""
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

                QLineEdit, QDateEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus,
                QDateEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
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

                QLineEdit, QDateEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus,
                QDateEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
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

    # ---------------------- Invoice Lookup ----------------------


    def _normalize_numeric_code(self, raw: str) -> str:
        """Return digits-only code. Accepts inputs like '123', 'INV123', 'inv-123'."""
        s = (raw or "").strip().upper()
        if s.startswith("INV"):
            s = s[3:]
        s = s.strip()
        if s.startswith("-"):
            s = s[1:].strip()
        # remove any remaining non-digit characters (safety)
        s = "".join(ch for ch in s if ch.isdigit())
        return s
    def _on_invoice_code_changed(self, text: str):
        """
        Real-time lookup as user types Invoice ID.
        No popups, just auto-fill fields if invoice exists.
        """
        code = self._normalize_numeric_code(text)

        # normalize to digits-only without infinite recursion
        if code != (text or ""):
            self.edit_invoice_code.blockSignals(True)
            self.edit_invoice_code.setText(code)
            self.edit_invoice_code.blockSignals(False)
            return

        if not code:
            self._invoice_resolved = False
            self._clear_invoice_fields()
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    i.id,
                    i.invoice_code,
                    i.invoice_date,
                    i.amount,
                    c.name AS customer_name,
                    ob.name AS ob_name,
                    pj.pjp_name
                FROM invoices i
                LEFT JOIN customers c     ON c.id  = i.customer_id
                LEFT JOIN order_bookers ob ON ob.id = i.order_booker_id
                LEFT JOIN pjps pj         ON pj.id = i.pjp_id
                WHERE i.invoice_code = ?
                """,
                (code,),
            )
            row = cur.fetchone()
        except Exception:
            self._invoice_resolved = False
            self._clear_invoice_fields()
            return

        if not row:
            self._invoice_resolved = False
            self._clear_invoice_fields()
            return
        
        self._invoice_resolved = True

        (
            invoice_id,
            invoice_code,
            invoice_date,
            invoice_amount,
            customer_name,
            ob_name,
            pjp_name,
        ) = row

        self._current_invoice_id = invoice_id
        self._current_invoice_amount = float(invoice_amount or 0)

        # invoice date
        try:
            dti = datetime.strptime(invoice_date, "%Y-%m-%d")
            display_date = QDate(dti.year, dti.month, dti.day).toString("dd/MM/yyyy")
        except Exception:
            display_date = invoice_date or ""

        self.edit_invoice_date.setText(display_date)
        self.edit_customer.setText(customer_name or "-")
        self.edit_ob.setText(ob_name or "-")
        self.edit_pjp.setText(pjp_name or "-")
        self.edit_invoice_amount.setText(f"{self._current_invoice_amount:,.0f}")



    def _clear_invoice_fields(self):
        self._current_invoice_id = None
        self._current_invoice_amount = 0.0
        self.edit_invoice_date.setText("")
        self.edit_customer.setText("")
        self.edit_ob.setText("")
        self.edit_pjp.setText("")
        self.edit_invoice_amount.setText("")

    # --------------------------- Logic ---------------------------

    
    def _invoice_payment_totals(self, invoice_id: int) -> tuple[float, float]:
        """
        Returns (invoice_amount, total_paid_so_far) for a given invoice_id.
        """
        cur = self.conn.cursor()

        cur.execute("SELECT amount FROM invoices WHERE id = ?", (invoice_id,))
        r = cur.fetchone()
        inv_amt = float((r["amount"] if isinstance(r, sqlite3.Row) else r[0]) or 0.0) if r else 0.0

        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?", (invoice_id,))
        r2 = cur.fetchone()
        paid_amt = float((r2[0] if r2 else 0.0) or 0.0)

        return inv_amt, paid_amt

    
    def _on_add_clicked(self):
        """
        Insert payment row into DB.
        Requires a valid invoice (resolved) and positive amount.
        """
        if not self._current_invoice_id:
            QMessageBox.warning(
                self,
                "Validation error",
                "Please enter a valid Invoice ID that exists in the system.",
            )
            return

        payment_date_iso = self.date_payment.date().toString("yyyy-MM-dd")

        amount_text = self.edit_amount.text().strip()
        amount = float(amount_text) if amount_text else 0.0

        if amount <= 0:
            QMessageBox.warning(
                self,
                "Validation error",
                "Payment amount must be greater than zero.",
            )
            return
        

        # ---- NEW: prevent extra payment if invoice already fully paid / overpayment ----
        inv_amt, paid_amt = self._invoice_payment_totals(self._current_invoice_id)


        if inv_amt > 0 and paid_amt >= inv_amt:
            QMessageBox.warning(
                self,
                "Not allowed",
                f"This invoice is already fully paid.\n\n"
                f"Invoice Amount: {inv_amt:,.0f} PKR\n"
                f"Paid: {paid_amt:,.0f} PKR",
            )
            return

        if inv_amt > 0 and (paid_amt + amount) > inv_amt:
            remaining = inv_amt - paid_amt
            QMessageBox.warning(
                self,
                "Not allowed",
                f"This payment would exceed the invoice total.\n\n"
                f"Remaining: {remaining:,.0f} PKR",
            )
            return


        # ✅ Generate independent numeric Payment ID here (NOT inside the if block)
        cur = self.conn.cursor()

        cur.execute("SELECT value FROM payment_meta WHERE key = 'payment_last_number'")
        last_no = cur.fetchone()[0]

        new_no = last_no + 1
        payment_code = new_no  # keep as INTEGER

        cur.execute(
            "UPDATE payment_meta SET value = ? WHERE key = 'payment_last_number'",
            (new_no,),
        )

        # Optional: show it in the UI
        self.edit_payment_code.setText(str(payment_code))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO payments (
                    payment_code,
                    payment_date,
                    invoice_id,
                    amount,
                    in_ledger,
                    created_at
                )
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (payment_code, payment_date_iso, self._current_invoice_id, amount, now_str),
            )
            self.conn.commit()

        except sqlite3.IntegrityError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not add payment. It may already exist for this Invoice ID "
                f"or the Payment ID is not unique.\n\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving payment:\n\n{e}",
            )
            return

        # --- SUCCESS ---

        # 1) Show green banner
        self._show_success_banner("Payment added successfully")

        # 2) Emit signal to refresh Manage view
        self.payment_added.emit()

        # 3) Clear form for next entry
        self.edit_invoice_code.clear()  # This triggers _on_invoice_code_changed which clears fields
        self.edit_amount.clear()
        self.date_payment.setDate(QDate.currentDate())
        self.edit_invoice_code.setFocus()
        self._preview_next_payment_id()
