# payments/add_payment.py
import sqlite3
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
    QComboBox,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer, QPoint
from PySide6.QtGui import QDoubleValidator, QIntValidator, QPainter, QPolygon, QColor


class ArrowComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        arrow_color = QColor("#e5e7eb") if self.palette().color(self.foregroundRole()).lightness() < 180 else QColor("#374151")
        painter.setBrush(arrow_color)
        painter.setPen(Qt.NoPen)

        x = self.width() - 18
        y = self.height() // 2 - 1
        triangle = QPolygon([
            QPoint(x - 5, y - 2),
            QPoint(x + 5, y - 2),
            QPoint(x, y + 4),
        ])
        painter.drawPolygon(triangle)

class AddPaymentDialog(QDialog):
    """
    Dialog for adding a new Payment.

    New behavior:
      - Order Booker is the first selectable field and opens automatically.
      - Invoice ID is a dropdown filtered by the selected Order Booker.
      - Selecting a valid invoice auto-fills customer, PJP, invoice amount,
        remaining amount, and invoice date.
      - After a successful add, the full form resets for the next entry.
      - Reopening the dialog also resets any previous typed/selected values.
    """

    payment_added = Signal()

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        self._current_invoice_id: int | None = None
        self._current_invoice_amount: float = 0.0
        self._current_remaining_amount: float = 0.0
        self._invoice_resolved = False
        self._did_first_show_reset = False

        self._sticky_order_booker_id: int | None = None

        self.setWindowTitle("Add Payment")

        self._build_ui()
        self._apply_local_styles()
        self._preview_next_payment_id()

        self.edit_amount.returnPressed.connect(self._on_add_clicked)
        self.combo_order_booker.currentIndexChanged.connect(self._on_order_booker_changed)
        self.edit_invoice_code.textChanged.connect(self._on_invoice_code_changed)
        self.edit_invoice_code.editingFinished.connect(lambda: self._resolve_invoice_from_input(show_error=False))
        self.edit_invoice_code.returnPressed.connect(lambda: self._resolve_invoice_from_input(show_error=True))

        self.adjustSize()
        max_height = 560
        min_width = 820
        width = max(min_width, self.width())
        height = min(self.height(), max_height)
        self.resize(width, height)

        self._position_next_to_parent()

    # --------------------------- lifecycle ---------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if self.__class__ is AddPaymentDialog:
            # Fresh open -> do not preserve previous Order Booker
            self._sticky_order_booker_id = None
            self.reset_form(auto_open_order_booker=True, preserve_order_booker=False)
        else:
            self._position_next_to_parent()

    def reject(self):
        if self.__class__ is AddPaymentDialog:
            # When dialog closes, forget preserved Order Booker
            self._sticky_order_booker_id = None
            self.reset_form(auto_open_order_booker=False, preserve_order_booker=False)
        super().reject()

    # --------------------------- helpers ---------------------------

    def _focus_payment_amount(self):
        self.edit_amount.setFocus()
        self.edit_amount.selectAll()

    def _position_next_to_parent(self):
        parent = self.parent()
        if parent is None or not parent.isVisible():
            return

        parent_geom = parent.frameGeometry()
        screen = parent.screen() or self.screen()
        avail = screen.availableGeometry() if screen is not None else parent_geom

        x_right = parent_geom.x() + parent_geom.width()
        new_x = x_right
        new_y = parent_geom.y()

        if new_x + self.width() > avail.right():
            new_x = max(avail.left(), parent_geom.x() - self.width() - 10)

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

        width = notification.sizeHint().width() + 20
        height = notification.sizeHint().height()
        notification.setFixedSize(width, height)

        x = (self.width() - width) // 2
        y = 20
        notification.move(x, y)
        notification.raise_()
        notification.show()

        QTimer.singleShot(2000, notification.deleteLater)

    def _preview_next_payment_id(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM payment_meta WHERE key = 'payment_last_number'")
            row = cur.fetchone()
            last_no = row[0] if row else 0
            self.edit_payment_code.setText(str(int(last_no) + 1))
        except Exception:
            self.edit_payment_code.clear()

    def _open_order_booker_dropdown(self):
        if self.combo_order_booker.count() > 1:
            self.combo_order_booker.setFocus()
            QTimer.singleShot(0, self.combo_order_booker.showPopup)
        else:
            self.combo_order_booker.setFocus()

    def _focus_invoice_input(self):
        self.edit_invoice_code.setFocus()
        self.edit_invoice_code.selectAll()

    def reset_form(
        self,
        auto_open_order_booker: bool = True,
        preserve_order_booker: bool = False,
    ):
        self._invoice_resolved = False
        self._current_invoice_id = None
        self._current_invoice_amount = 0.0
        self._current_remaining_amount = 0.0

        self._preview_next_payment_id()
        self.date_payment.setDate(QDate.currentDate())
        self.edit_amount.clear()

        selected_order_booker_id = (
            self._sticky_order_booker_id if preserve_order_booker else None
        )

        self._load_order_bookers(selected_order_booker_id=selected_order_booker_id)
        self._clear_invoice_fields()

        if selected_order_booker_id is not None:
            if auto_open_order_booker:
                QTimer.singleShot(0, self._focus_invoice_input)
        else:
            if auto_open_order_booker:
                QTimer.singleShot(0, self._open_order_booker_dropdown)
    # --------------------------- UI ---------------------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.addStretch()

        title_label = QLabel("Add Payment")
        title_label.setObjectName("DialogTitle")
        header_layout.addWidget(title_label, alignment=Qt.AlignCenter)
        header_layout.addStretch()
        main_layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(sep)

        body = QFrame()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(16)

        # Row 1: Payment ID | Payment Date
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        col_pay_code = QVBoxLayout()
        lbl_pay_code = QLabel("Payment ID")
        self.edit_payment_code = QLineEdit()
        self.edit_payment_code.setReadOnly(True)
        self.edit_payment_code.setMinimumHeight(36)
        col_pay_code.addWidget(lbl_pay_code)
        col_pay_code.addWidget(self.edit_payment_code)

        col_pay_date = QVBoxLayout()
        lbl_pay_date = QLabel("Payment Date")
        self.date_payment = QDateEdit()
        self.date_payment.setCalendarPopup(True)
        self.date_payment.setDisplayFormat("dd/MM/yyyy")
        self.date_payment.setDate(QDate.currentDate())
        self.date_payment.setMinimumHeight(36)
        col_pay_date.addWidget(lbl_pay_date)
        col_pay_date.addWidget(self.date_payment)

        row1.addLayout(col_pay_code, 1)
        row1.addLayout(col_pay_date, 1)
        body_layout.addLayout(row1)

        # Row 2: Invoice ID | Order Booker
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        col_inv_code = QVBoxLayout()
        lbl_inv_code = QLabel("Invoice ID")
        self.edit_invoice_code = QLineEdit()
        self.edit_invoice_code.setPlaceholderText("Enter Invoice ID")
        self.edit_invoice_code.setMinimumHeight(36)
        self.edit_invoice_code.setValidator(QIntValidator(1, 999999999, self))
        col_inv_code.addWidget(lbl_inv_code)
        col_inv_code.addWidget(self.edit_invoice_code)

        col_ob = QVBoxLayout()
        lbl_ob = QLabel("Order Booker")
        self.combo_order_booker = ArrowComboBox()
        self.combo_order_booker.setMinimumHeight(36)
        self.combo_order_booker.setInsertPolicy(QComboBox.NoInsert)
        self.combo_order_booker.setFocusPolicy(Qt.StrongFocus)
        self.combo_order_booker.setCursor(Qt.PointingHandCursor)
        col_ob.addWidget(lbl_ob)
        col_ob.addWidget(self.combo_order_booker)

        row2.addLayout(col_inv_code, 1)
        row2.addLayout(col_ob, 1)
        body_layout.addLayout(row2)

        # Row 3: Customer | PJP
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        col_customer = QVBoxLayout()
        lbl_customer = QLabel("Customer")
        self.edit_customer = QLineEdit()
        self.edit_customer.setReadOnly(True)
        self.edit_customer.setMinimumHeight(36)
        col_customer.addWidget(lbl_customer)
        col_customer.addWidget(self.edit_customer)

        col_pjp = QVBoxLayout()
        lbl_pjp = QLabel("PJP")
        self.edit_pjp = QLineEdit()
        self.edit_pjp.setReadOnly(True)
        self.edit_pjp.setMinimumHeight(36)
        col_pjp.addWidget(lbl_pjp)
        col_pjp.addWidget(self.edit_pjp)

        row3.addLayout(col_customer, 1)
        row3.addLayout(col_pjp, 1)
        body_layout.addLayout(row3)

        # Row 4: Invoice Amount | Remaining Invoice Amount
        row4 = QHBoxLayout()
        row4.setSpacing(12)

        col_inv_amount = QVBoxLayout()
        lbl_inv_amount = QLabel("Total Invoice Amount (PKR)")
        self.edit_invoice_amount = QLineEdit()
        self.edit_invoice_amount.setReadOnly(True)
        self.edit_invoice_amount.setMinimumHeight(36)
        col_inv_amount.addWidget(lbl_inv_amount)
        col_inv_amount.addWidget(self.edit_invoice_amount)

        col_remaining = QVBoxLayout()
        lbl_remaining = QLabel("Remaining Invoice Amount (PKR)")
        self.edit_remaining_amount = QLineEdit()
        self.edit_remaining_amount.setReadOnly(True)
        self.edit_remaining_amount.setMinimumHeight(36)
        col_remaining.addWidget(lbl_remaining)
        col_remaining.addWidget(self.edit_remaining_amount)

        row4.addLayout(col_inv_amount, 1)
        row4.addLayout(col_remaining, 1)
        body_layout.addLayout(row4)

        # Row 5: Invoice Date | Payment Amount
        row5 = QHBoxLayout()
        row5.setSpacing(12)

        col_inv_date = QVBoxLayout()
        lbl_inv_date = QLabel("Invoice Date")
        self.edit_invoice_date = QLineEdit()
        self.edit_invoice_date.setReadOnly(True)
        self.edit_invoice_date.setMinimumHeight(36)
        col_inv_date.addWidget(lbl_inv_date)
        col_inv_date.addWidget(self.edit_invoice_date)

        col_pay_amount = QVBoxLayout()
        lbl_pay_amount = QLabel("Payment Amount (PKR)")
        self.edit_amount = QLineEdit()
        self.edit_amount.setPlaceholderText("Enter amount received")
        self.edit_amount.setMinimumHeight(36)
        validator = QDoubleValidator(0.0, 999999999.99, 2, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.edit_amount.setValidator(validator)
        col_pay_amount.addWidget(lbl_pay_amount)
        col_pay_amount.addWidget(self.edit_amount)

        row5.addLayout(col_inv_date, 1)
        row5.addLayout(col_pay_amount, 1)
        body_layout.addLayout(row5)

        main_layout.addWidget(body)

        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 20)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("DialogCancelButton")
        btn_cancel.clicked.connect(self.reject)

        btn_add = QPushButton("Add")
        btn_add.setObjectName("DialogPrimaryButton")
        btn_add.clicked.connect(self._on_add_clicked)

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
        if self.dark_mode:
            self.setStyleSheet(
                """
                QDialog { background-color: #000000; }
                QLabel { color: #e5e7eb; }
                QLabel#DialogTitle { font-size: 18px; font-weight: 600; color: #f9fafb; }
                QLineEdit, QDateEdit, QComboBox {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                QComboBox {
                    padding: 8px;
                    padding-right: 34px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }

                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border-left: 1px solid #2a2a2a;
                    background-color: #252525;
                    border-top-right-radius: 8px;
                    border-bottom-right-radius: 8px;
                }

                QComboBox::down-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QPushButton#DialogPrimaryButton {
                    background-color: rgb(37, 79, 167);
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogPrimaryButton:hover { background-color: rgb(30, 64, 140); }
                QPushButton#DialogCancelButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogCancelButton:hover { background-color: #b91c1c; }
                QFrame[frameShape="4"] { background-color: #1a1a1a; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog { background-color: #ffffff; }
                QLabel#DialogTitle { font-size: 18px; font-weight: 600; }
                QLineEdit, QDateEdit, QComboBox {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                QComboBox {
                    padding: 8px;
                    padding-right: 34px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                    background-color: #ffffff;
                    color: #111827;
                }

                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 30px;
                    border-left: 1px solid #d1d5db;
                    background-color: #f9fafb;
                    border-top-right-radius: 8px;
                    border-bottom-right-radius: 8px;
                }

                QComboBox::down-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
                QPushButton#DialogPrimaryButton {
                    background-color: rgb(37, 79, 167);
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogPrimaryButton:hover { background-color: rgb(30, 64, 140); }
                QPushButton#DialogCancelButton {
                    background-color: #ef4444;
                    color: white;
                    border-radius: 8px;
                    padding: 8px 24px;
                    border: none;
                    font-weight: 500;
                }
                QPushButton#DialogCancelButton:hover { background-color: #b91c1c; }
                """
            )

    # ---------------------- Dropdown / lookup logic ----------------------

    def _load_order_bookers(self, selected_order_booker_id: int | None = None):
        self.combo_order_booker.blockSignals(True)
        self.combo_order_booker.clear()
        self.combo_order_booker.addItem("Select Order Booker", None)

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT ob.id, ob.name
                FROM invoices i
                JOIN order_bookers ob ON ob.id = i.order_booker_id
                ORDER BY ob.name COLLATE NOCASE
                """
            )
            rows = cur.fetchall()
            for row in rows:
                ob_id = row[0] if not isinstance(row, sqlite3.Row) else row["id"]
                ob_name = row[1] if not isinstance(row, sqlite3.Row) else row["name"]
                self.combo_order_booker.addItem(str(ob_name or "-"), ob_id)

            if selected_order_booker_id is not None:
                for i in range(self.combo_order_booker.count()):
                    if self.combo_order_booker.itemData(i) == selected_order_booker_id:
                        self.combo_order_booker.setCurrentIndex(i)
                        break
            else:
                self.combo_order_booker.setCurrentIndex(0)
        finally:
            self.combo_order_booker.blockSignals(False)


    def _resolve_invoice_from_input(self, show_error: bool = False) -> bool:
        selected_ob_id = self.combo_order_booker.currentData()
        invoice_code = self.edit_invoice_code.text().strip()

        self._clear_invoice_fields(clear_invoice_input=False)

        if not selected_ob_id or not invoice_code:
            if show_error:
                if not selected_ob_id:
                    QMessageBox.warning(self, "Validation error", "Please select Order Booker.")
                else:
                    QMessageBox.warning(self, "Validation error", "Please enter Invoice ID.")
            return False

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT i.id
                FROM invoices i
                WHERE CAST(i.invoice_code AS TEXT) = ?
                  AND i.order_booker_id = ?
                LIMIT 1
                """,
                (invoice_code, selected_ob_id),
            )
            row = cur.fetchone()
        except Exception as e:
            if show_error:
                QMessageBox.critical(self, "Error", f"Failed to validate Invoice ID:\n{e}")
            return False

        if not row:
            if show_error:
                QMessageBox.warning(
                    self,
                    "Invalid Invoice ID",
                    "This Invoice ID does not belong to the selected Order Booker.",
                )
            return False

        invoice_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        self._populate_invoice_fields(invoice_id)
        QTimer.singleShot(0, self._focus_payment_amount)
        return True


    def _invoice_payment_totals(self, invoice_id: int) -> tuple[float, float]:
        cur = self.conn.cursor()
        cur.execute("SELECT amount FROM invoices WHERE id = ?", (invoice_id,))
        r = cur.fetchone()
        inv_amt = float((r["amount"] if isinstance(r, sqlite3.Row) else r[0]) or 0.0) if r else 0.0

        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?", (invoice_id,))
        r2 = cur.fetchone()
        paid_amt = float((r2[0] if r2 else 0.0) or 0.0)
        return inv_amt, paid_amt

    def _remaining_amount_for_invoice(self, invoice_id: int) -> float:
        inv_amt, paid_amt = self._invoice_payment_totals(invoice_id)
        return max(inv_amt - paid_amt, 0.0)

    def _on_order_booker_changed(self, index: int):
        order_booker_id = self.combo_order_booker.itemData(index)
        self._sticky_order_booker_id = order_booker_id
        self._clear_invoice_fields(clear_invoice_input=False)

        if order_booker_id is not None:
            self._focus_invoice_input()

    def _on_invoice_code_changed(self, _text: str):
        self._clear_invoice_fields(clear_invoice_input=False)

    def _populate_invoice_fields(self, invoice_id: int):
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
                    ob.id AS ob_id,
                    ob.name AS ob_name,
                    pj.pjp_name
                FROM invoices i
                LEFT JOIN customers c      ON c.id = i.customer_id
                LEFT JOIN order_bookers ob ON ob.id = i.order_booker_id
                LEFT JOIN pjps pj          ON pj.id = i.pjp_id
                WHERE i.id = ?
                """,
                (invoice_id,),
            )
            row = cur.fetchone()
        except Exception:
            self._clear_invoice_fields(clear_invoice_input=False)
            return

        if not row:
            self._clear_invoice_fields(clear_invoice_input=False)
            return

        if isinstance(row, sqlite3.Row):
            invoice_id = row["id"]
            invoice_date = row["invoice_date"]
            invoice_amount = row["amount"]
            customer_name = row["customer_name"]
            ob_id = row["ob_id"]
            pjp_name = row["pjp_name"]
        else:
            invoice_id, _invoice_code, invoice_date, invoice_amount, customer_name, ob_id, _ob_name, pjp_name = row

        self._current_invoice_id = invoice_id
        self._current_invoice_amount = float(invoice_amount or 0.0)
        self._current_remaining_amount = self._remaining_amount_for_invoice(invoice_id)
        self._invoice_resolved = True

        try:
            dti = datetime.strptime(invoice_date, "%Y-%m-%d")
            display_date = QDate(dti.year, dti.month, dti.day).toString("dd/MM/yyyy")
        except Exception:
            display_date = invoice_date or ""

        self.edit_customer.setText(customer_name or "-")
        self.edit_pjp.setText(pjp_name or "-")
        self.edit_invoice_date.setText(display_date)
        self.edit_invoice_amount.setText(f"{self._current_invoice_amount:,.0f}")
        self.edit_remaining_amount.setText(f"{self._current_remaining_amount:,.0f}")

        if ob_id is not None:
            self.combo_order_booker.blockSignals(True)
            for i in range(self.combo_order_booker.count()):
                if self.combo_order_booker.itemData(i) == ob_id:
                    self.combo_order_booker.setCurrentIndex(i)
                    break
            self.combo_order_booker.blockSignals(False)

    def _clear_invoice_fields(self, clear_invoice_input: bool = True):
        self._current_invoice_id = None
        self._current_invoice_amount = 0.0
        self._current_remaining_amount = 0.0
        self._invoice_resolved = False
        self.edit_customer.clear()
        self.edit_pjp.clear()
        self.edit_invoice_date.clear()
        self.edit_invoice_amount.clear()
        self.edit_remaining_amount.clear()

        if clear_invoice_input:
            self.edit_invoice_code.clear()

    # --------------------------- save logic ---------------------------

    def _on_add_clicked(self):
        if not self._resolve_invoice_from_input(show_error=True):
            QMessageBox.warning(
                self,
                "Validation error",
                "Please enter a valid Invoice ID for the selected Order Booker.",
            )
            return

        payment_date_iso = self.date_payment.date().toString("yyyy-MM-dd")
        amount_text = self.edit_amount.text().strip()
        amount = float(amount_text) if amount_text else 0.0

        if amount <= 0:
            QMessageBox.warning(self, "Validation error", "Payment amount must be greater than zero.")
            return

        inv_amt, paid_amt = self._invoice_payment_totals(self._current_invoice_id)

        if inv_amt > 0 and paid_amt >= inv_amt:
            QMessageBox.warning(
                self,
                "Not allowed",
                f"This invoice is already fully paid.\n\n"
                f"Total Invoice Amount: {inv_amt:,.0f} PKR\n"
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

        cur = self.conn.cursor()
        cur.execute("SELECT value FROM payment_meta WHERE key = 'payment_last_number'")
        last_no = cur.fetchone()[0]
        new_no = last_no + 1
        payment_code = new_no

        cur.execute(
            "UPDATE payment_meta SET value = ? WHERE key = 'payment_last_number'",
            (new_no,),
        )

        self.edit_payment_code.setText(str(payment_code))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
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
                f"Could not add payment. It may already exist for this Invoice ID or the Payment ID is not unique.\n\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error while saving payment:\n\n{e}")
            return

        self._show_success_banner("Payment added successfully")
        self.payment_added.emit()
        self.reset_form(auto_open_order_booker=True, preserve_order_booker=True)
