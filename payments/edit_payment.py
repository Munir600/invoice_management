# payments/edit_payment.py
import os
import sqlite3
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QMessageBox,
    QWidget,
    QScrollArea,
    QCheckBox,
    QToolButton,
    QMenu,
    QApplication,
    QToolTip,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QCursor, QIcon

from .add_payment import AddPaymentDialog

# --------------------------------------------------------------------
#  ICON HELPERS
# --------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")


def app_icon(name: str) -> QIcon:
    return QIcon(os.path.join(ICON_DIR, f"{name}.svg"))


# --------------------------------------------------------------------
#  EDIT PAYMENT DIALOG
# --------------------------------------------------------------------


class EditPaymentDialog(AddPaymentDialog):
    """
    Reuse AddPaymentDialog UI to edit an existing payment.
    """

    def __init__(self, db_conn: sqlite3.Connection, payment_id: int, parent=None):
        self.payment_id = payment_id
        super().__init__(db_conn, parent)

        # change title
        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit Payment")

        # change primary button text
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "DialogPrimaryButton":
                btn.setText("Save")
                break

        # load existing data
        self._load_payment_data()
        self.edit_invoice_code.setReadOnly(True)
        self.edit_invoice_code.setCursor(Qt.ArrowCursor)


    def _load_payment_data(self):
        """Populate fields from DB for the given payment_id."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    p.payment_code,
                    p.payment_date,
                    p.amount,
                    i.id AS invoice_id,
                    i.invoice_code,
                    i.invoice_date,
                    i.amount AS invoice_amount,
                    c.name AS customer_name,
                    ob.name AS ob_name,
                    pj.pjp_name
                FROM payments p
                JOIN invoices i ON i.id = p.invoice_id
                LEFT JOIN customers c ON c.id = i.customer_id
                LEFT JOIN order_bookers ob ON ob.id = i.order_booker_id
                LEFT JOIN pjps pj ON pj.id = i.pjp_id
                WHERE p.id = ?
                """,
                (self.payment_id,),
            )
            row = cur.fetchone()
            if not row:
                QMessageBox.critical(self, "Error", "Payment not found.")
                self.reject()
                return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load payment:\n\n{e}",
            )
            self.reject()
            return

        if isinstance(row, sqlite3.Row):
            payment_code = row["payment_code"]
            payment_date = row["payment_date"]
            amount = row["amount"]
            invoice_code = row["invoice_code"]
            invoice_date = row["invoice_date"]
            invoice_amount = row["invoice_amount"]
            customer_name = row["customer_name"] or "-"
            ob_name = row["ob_name"] or "-"
            pjp_name = row["pjp_name"] or "-"
        else:
            (
                payment_code,
                payment_date,
                amount,
                _invoice_id,
                invoice_code,
                invoice_date,
                invoice_amount,
                customer_name,
                ob_name,
                pjp_name,
            ) = row
            customer_name = customer_name or "-"
            ob_name = ob_name or "-"
            pjp_name = pjp_name or "-"

        if hasattr(self, "edit_invoice_amount"):
            self.edit_invoice_amount.setText(f"{float(invoice_amount or 0):,.0f}")



        # fill fields
        self.edit_payment_code.setText(str(payment_code) if payment_code is not None else "")

        try:
            dt_pay = datetime.strptime(payment_date, "%Y-%m-%d")
            self.date_payment.setDate(QDate(dt_pay.year, dt_pay.month, dt_pay.day))
        except Exception:
            self.date_payment.setDate(QDate.currentDate())

        self.edit_invoice_code.setText(str(invoice_code) if invoice_code is not None else "")

        # invoice date
        try:
            dt_inv = datetime.strptime(invoice_date, "%Y-%m-%d")
            self.edit_invoice_date.setText(
                QDate(dt_inv.year, dt_inv.month, dt_inv.day).toString("dd/MM/yyyy")
            )
        except Exception:
            self.edit_invoice_date.setText(invoice_date or "")

        self.edit_customer.setText(customer_name)
        self.edit_ob.setText(ob_name)
        self.edit_pjp.setText(pjp_name)

        if amount is not None:
            self.edit_amount.setText(str(amount))


    def _invoice_payment_totals_excluding_self(self, invoice_id: int) -> tuple[float, float]:
        """
        Returns (invoice_amount, total_paid_excluding_this_payment)
        so edits don't count the current payment twice.
        """
        cur = self.conn.cursor()

        cur.execute("SELECT amount FROM invoices WHERE id = ?", (invoice_id,))
        r = cur.fetchone()
        inv_amt = float((r["amount"] if isinstance(r, sqlite3.Row) else r[0]) or 0.0) if r else 0.0

        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ? AND id <> ?",
            (invoice_id, self.payment_id),
        )
        r2 = cur.fetchone()
        paid_amt = float((r2[0] if r2 else 0.0) or 0.0)

        return inv_amt, paid_amt


    # override AddPaymentDialog save handler
    def _on_add_clicked(self):
        invoice_code_str = self._normalize_numeric_code(self.edit_invoice_code.text())
        invoice_code = int(invoice_code_str) if invoice_code_str.isdigit() else None
        payment_date_iso = self.date_payment.date().toString("yyyy-MM-dd")
        amount_text = self.edit_amount.text().strip()
        amount = float(amount_text) if amount_text else 0.0

        if not invoice_code or amount <= 0:
            QMessageBox.warning(
                self,
                "Validation error",
                "Invoice ID and a positive amount are required.",
            )
            return

        # resolve invoice_id
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT id FROM invoices WHERE invoice_code = ?",
                (invoice_code,),
            )
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(
                    self,
                    "Validation error",
                    "No invoice found with this Invoice ID.",
                )
                return
            invoice_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
            # ---- prevent extra payment if invoice already fully paid / overpayment (edit-safe) ----
            inv_amt, paid_amt = self._invoice_payment_totals_excluding_self(invoice_id)

            if inv_amt > 0 and paid_amt >= inv_amt:
                QMessageBox.warning(
                    self,
                    "Not allowed",
                    f"This invoice is already fully paid.\n\n"
                    f"Invoice Amount: {inv_amt:,.0f} PKR\n"
                    f"Paid (excluding this): {paid_amt:,.0f} PKR",
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

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to look up invoice:\n\n{e}",
            )
            return

        payment_code_str = self._normalize_numeric_code(self.edit_payment_code.text())
        if not payment_code_str.isdigit():
            QMessageBox.warning(self, 'Validation error', 'Payment ID must be numeric (e.g., 1, 2, 3...).')
            return
        payment_code = int(payment_code_str)
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE payments
                SET payment_code = ?,
                    payment_date = ?,
                    invoice_id   = ?,
                    amount       = ?
                WHERE id = ?
                """,
                (payment_code, payment_date_iso, invoice_id, amount, self.payment_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not update payment. Payment code may clash with another payment.\n\n{e}",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to update payment:\n\n{e}",
            )
            return

        self.accept()


# --------------------------------------------------------------------
#  PAYMENT ROW WIDGET
# --------------------------------------------------------------------


class PaymentRowWidget(QFrame):
    """
    One row in the ManagePaymentsDialog list.
    """

    def __init__(self, payment_data: dict, parent_dialog: "ManagePaymentsDialog"):
        super().__init__()
        self.payment_data = payment_data
        self.parent_dialog = parent_dialog
        
        self.full_code = str(payment_data.get("payment_code") or "")

        self.setObjectName("PaymentRow")
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        # 1. Checkbox (40px)
        self.chk = QCheckBox()
        self.chk.setCursor(QCursor(Qt.PointingHandCursor))
        self.chk.stateChanged.connect(self.parent_dialog.on_row_checkbox_changed)
        self.chk.setFixedWidth(40)
        layout.addWidget(self.chk, alignment=Qt.AlignHCenter | Qt.AlignVCenter)

        # 2. Row Number (40px) - This was missing causing misalignment!
        row_no = payment_data.get("row_number")
        self.lbl_rownum = QLabel(str(row_no) if row_no is not None else "")
        self.lbl_rownum.setObjectName("RowNumberLabel")
        self.lbl_rownum.setAlignment(Qt.AlignCenter)
        self.lbl_rownum.setFixedWidth(40)
        layout.addWidget(self.lbl_rownum)

        def make_label(width: int | None = None, obj_name: str | None = None, rich=False):
            lbl = QLabel()
            if obj_name:
                lbl.setObjectName(obj_name)
            lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if rich:
                lbl.setTextFormat(Qt.RichText)
            if width:
                lbl.setFixedWidth(width)
            return lbl

        # 3. Payment ID (180px)
        pay_lbl = make_label(90, "CellLabel")
        pay_lbl.setAlignment(Qt.AlignCenter)
        pay_lbl.setText(
            pay_lbl.fontMetrics().elidedText(
                self.full_code, Qt.ElideRight, pay_lbl.width()
            )
        )
        pay_lbl.setCursor(QCursor(Qt.PointingHandCursor))
        pay_lbl.setToolTip("Click to copy Payment ID")
        pay_lbl.mousePressEvent = self._on_code_clicked
        layout.addWidget(pay_lbl)

        # 4. Invoice ID (140px)  -- NEW
        inv_code = str(payment_data.get("invoice_code") or "")
        inv_lbl = make_label(90, "CellLabel")
        inv_lbl.setAlignment(Qt.AlignCenter)
        inv_lbl.setText(inv_lbl.fontMetrics().elidedText(inv_code, Qt.ElideRight, inv_lbl.width()))
        layout.addWidget(inv_lbl)


        # 4. Date (80px)
        date_lbl = make_label(80, "CellLabel")
        date_lbl.setText(
            date_lbl.fontMetrics().elidedText(
                payment_data["date_str"], Qt.ElideRight, date_lbl.width()
            )
        )
        layout.addWidget(date_lbl)


        # 5. Time (70px) – 12h string
        time_lbl = make_label(70, "CellLabel")
        time_lbl.setText(
            time_lbl.fontMetrics().elidedText(
                payment_data.get("time_str", ""), Qt.ElideRight, time_lbl.width()
            )
        )
        layout.addWidget(time_lbl)

        # 5. OB (100px)
        ob_lbl = make_label(100, "CellLabel")
        ob_lbl.setText(
            ob_lbl.fontMetrics().elidedText(
                payment_data["ob_name"], Qt.ElideRight, ob_lbl.width()
            )
        )
        layout.addWidget(ob_lbl)

        # 6. PJP (150px)
        pjp_lbl = make_label(150, "CellLabel")
        pjp_lbl.setText(
            pjp_lbl.fontMetrics().elidedText(
                payment_data["pjp_name"], Qt.ElideRight, pjp_lbl.width()
            )
        )
        layout.addWidget(pjp_lbl)

        # 7. Customer (130px)
        customer_lbl = make_label(130, "CellLabel")
        customer_lbl.setText(
            customer_lbl.fontMetrics().elidedText(
                payment_data["customer_name"], Qt.ElideRight, customer_lbl.width()
            )
        )
        layout.addWidget(customer_lbl)

        # 8. Amount (100px)
        amount_val = payment_data["amount"] if payment_data["amount"] is not None else 0
        amount_html = f"<b>PKR</b> {amount_val:,.0f}"
        self.lbl_amount = make_label(100, "AmountLabel", rich=True)
        self.lbl_amount.setText(amount_html)
        layout.addWidget(self.lbl_amount)

        # 9. Ledger (60px)
        self.lbl_ledger = QLabel()
        self.lbl_ledger.setObjectName("LedgerPill")
        self.lbl_ledger.setFixedWidth(60)
        self.lbl_ledger.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ledger)
        self.update_ledger_pill(payment_data["in_ledger"])

        # 10. Actions (80px)
        actions_frame = QFrame()
        actions_frame.setFixedWidth(80)
        btn_layout = QHBoxLayout(actions_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        self.btn_edit = QPushButton()
        self.btn_edit.setObjectName("EditBtn")
        self.btn_edit.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_edit.setFixedSize(32, 24)
        self.btn_edit.setIconSize(QSize(14, 14))
        self.btn_edit.clicked.connect(self.on_edit_clicked)

        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("DeleteBtn")
        self.btn_delete.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_delete.setFixedSize(32, 24)
        self.btn_delete.setIconSize(QSize(14, 14))
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        self._update_button_icons()

        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        
        # Add stretch to push everything left if needed, but fixed widths usually suffice
        # layout.addStretch() 
        # (In Invoices we didn't use addStretch at the end of row because fixed widths sum up well)
        
        layout.addWidget(actions_frame)

    def _on_code_clicked(self, event):
        """Copy payment code to clipboard."""
        if event.button() == Qt.LeftButton and self.full_code:
            app = QApplication.instance()
            if app is not None:
                app.clipboard().setText(self.full_code)
                QToolTip.showText(event.globalPos(), "Payment ID copied", self)

    def _update_button_icons(self):
        dark = bool(getattr(self.parent_dialog, "dark_mode", False))

        if dark:
            edit_name = "edit"
            trash_name = "trash"

        else:
            edit_name = "edit-black"
            trash_name = "trash-black"

        self.btn_edit.setIcon(app_icon(edit_name))
        self.btn_delete.setIcon(app_icon(trash_name))

    def update_ledger_pill(self, in_ledger: int):
        if in_ledger:
            self.lbl_ledger.setText("Yes")
            self.lbl_ledger.setProperty("ledgerState", "yes")
        else:
            self.lbl_ledger.setText("No")
            self.lbl_ledger.setProperty("ledgerState", "no")
        self.lbl_ledger.style().unpolish(self.lbl_ledger)
        self.lbl_ledger.style().polish(self.lbl_ledger)

    def on_edit_clicked(self):
        self.parent_dialog.edit_payment(self.payment_data["id"])

    def on_delete_clicked(self):
        self.parent_dialog.delete_payment(self.payment_data["id"], str(self.payment_data["payment_code"]))



# --------------------------------------------------------------------
#  MANAGE PAYMENTS DIALOG
# --------------------------------------------------------------------


class ManagePaymentsDialog(QDialog):
    """
    Shows the list of payments.
    """

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None, mode: str = "manage"):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = bool(getattr(parent, "dark_mode", False))

        self.sort_mode = "oldest"
        self.mode = mode  # "manage" or "edit"
        self.setWindowTitle("Edit Payments" if self.mode == "edit" else "Manage Payments")

        self.resize(950, 550)
        self.setMinimumWidth(850)

        self.rows: list[PaymentRowWidget] = []

        # --- lazy loading / keyset pagination ---
        self.page_size = 25
        self._cursor_key = None  # tuple(sort_value, id)
        self._has_more = True
        self._is_loading = False
        self._total_count = 0
        self._total_amount = 0.0

        self._build_ui()
        self._apply_styles()
        self.load_payments()

    # ---------------- UI ----------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # header
        header = QFrame()
        header.setObjectName("PaymentsHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        h_layout.setSpacing(8)

        title_text = "Edit Payments" if self.mode == "edit" else "Manage Payments"
        title = QLabel(title_text)

        title.setObjectName("PaymentsTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # table area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("PaymentsScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFocusPolicy(Qt.StrongFocus)

        # lazy loading trigger
        self.scroll_area = scroll
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

        container = QWidget()
        container.setObjectName("PaymentsContainer")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        self.container_layout.setContentsMargins(24, 20, 24, 20)
        self.container_layout.setSpacing(0)

        self._build_table_header()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)


        # --- totals bar (matches invoices layout) ---
        totals_bar = QFrame()
        totals_bar.setObjectName("PaymentsTotalsBar")
        totals_layout = QHBoxLayout(totals_bar)
        totals_layout.setContentsMargins(24, 8, 24, 8)
        totals_layout.setSpacing(12)

        # left: count label
        self.lbl_total_count = QLabel("No payments")
        self.lbl_total_count.setObjectName("PaymentsTotalCount")
        totals_layout.addWidget(self.lbl_total_count)

        totals_layout.addStretch()

        # right: total amount
        self.lbl_total_caption = QLabel("Total Amount:")
        self.lbl_total_caption.setObjectName("PaymentsTotalCaption")
        self.lbl_total_amount = QLabel("0 PKR")
        self.lbl_total_amount.setObjectName("PaymentsTotalAmount")

        totals_layout.addWidget(self.lbl_total_caption)
        totals_layout.addWidget(self.lbl_total_amount)

        main_layout.addWidget(totals_bar)


        # footer
        footer = QFrame()
        footer.setObjectName("PaymentsFooter")
        footer.setFixedHeight(80)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(24, 16, 24, 16)
        f_layout.setSpacing(12)

        self.btn_add_payment = QPushButton("+ Add Payment")
        self.btn_add_payment.setObjectName("AddPaymentBtn")
        self.btn_add_payment.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_add_payment.clicked.connect(self.add_payment)

        self.btn_delete_selected = QPushButton("Delete Selected")
        self.btn_delete_selected.setObjectName("DeleteSelectedBtn")
        self.btn_delete_selected.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_delete_selected.clicked.connect(self.delete_selected)
        self.btn_delete_selected.setEnabled(False)

        self.btn_add_to_ledger = QPushButton("Add to Ledger" if self.mode == "edit" else "Remove from Ledger")
        self.btn_add_to_ledger.setObjectName("AddToLedgerBtn")
        self.btn_add_to_ledger.setCursor(QCursor(Qt.PointingHandCursor))
        if self.mode == "edit":
            self.btn_add_to_ledger.clicked.connect(self.add_selected_to_ledger)
        else:
            self.btn_add_to_ledger.clicked.connect(self.remove_selected_from_ledger)
        self.btn_add_to_ledger.setEnabled(False)


        f_layout.addWidget(self.btn_add_payment)
        f_layout.addWidget(self.btn_delete_selected)
        f_layout.addWidget(self.btn_add_to_ledger)
        f_layout.addStretch()

        close_bottom = QPushButton("Close")
        close_bottom.setObjectName("FooterCloseBtn")
        close_bottom.setCursor(QCursor(Qt.PointingHandCursor))
        close_bottom.clicked.connect(self.reject)
        close_bottom.setMinimumWidth(120)
        f_layout.addWidget(close_bottom)

        main_layout.addWidget(footer)

    def _build_table_header(self):
        header_row = QFrame()
        header_row.setObjectName("TableHeaderRow")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(16)

        # 1. Header Checkbox (40px)
        self.header_checkbox = QCheckBox()
        self.header_checkbox.setTristate(True)
        self.header_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.header_checkbox.stateChanged.connect(self._on_header_checkbox_changed)
        self.header_checkbox.setFixedWidth(40)
        header_layout.addWidget(
            self.header_checkbox,
            alignment=Qt.AlignHCenter | Qt.AlignVCenter,
        )

        # 2. Sort Button (40px) - Acts as header for the Number column
        self.sort_button = QToolButton()
        self.sort_button.setObjectName("SortButton")
        icon_name = "sort" if self.dark_mode else "sort-black"
        self.sort_button.setIcon(app_icon(icon_name))
        self.sort_button.setIconSize(QSize(16, 16))
        self.sort_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.sort_button.setToolTip("Sort payments")
        self.sort_button.setPopupMode(QToolButton.InstantPopup)
        self.sort_button.setAutoRaise(True)
        self.sort_button.setFixedWidth(40)

        sort_menu = QMenu(self)
        newest_action = sort_menu.addAction("Newest first")
        oldest_action = sort_menu.addAction("Oldest first")
        amount_high_action = sort_menu.addAction("Amount – highest first")
        amount_low_action = sort_menu.addAction("Amount – lowest first")

        newest_action.triggered.connect(lambda: self._set_sort_mode("newest"))
        oldest_action.triggered.connect(lambda: self._set_sort_mode("oldest"))
        amount_high_action.triggered.connect(lambda: self._set_sort_mode("amount_high"))
        amount_low_action.triggered.connect(lambda: self._set_sort_mode("amount_low"))

        self.sort_button.setMenu(sort_menu)
        header_layout.addWidget(
            self.sort_button,
            alignment=Qt.AlignHCenter | Qt.AlignVCenter,
        )

        def add_header_label(text, width):
            lbl = QLabel(text)
            lbl.setObjectName("HeaderLabel")
            lbl.setFixedWidth(width)
            header_layout.addWidget(lbl)
            return lbl

        # The widths here MUST match the fixed widths in PaymentRowWidget
        add_header_label("Payment ID", 90)
        add_header_label("Invoice ID", 90)
        add_header_label("Date", 80)
        add_header_label("Time", 70)
        add_header_label("Order Booker", 100)
        add_header_label("PJP", 150)
        add_header_label("Customer", 130)
        add_header_label("Amount", 100)
        add_header_label("Ledger", 60)
        add_header_label("Actions", 80)

        self.container_layout.addWidget(header_row)

    # ---------------- data load ----------------

    def _set_sort_mode(self, mode: str):
        self.sort_mode = mode
        self.load_payments()

    
    def load_payments(self):
        """Reload payments using keyset pagination (lazy loading)."""

        # Clear ALL widgets (header + rows + empty label etc.)
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.rows.clear()

        # Rebuild header
        self._build_table_header()

        # Add stretch to keep rows compact (prevents vertical expansion)
        self.container_layout.addStretch()

        # Reset paging state
        self._reset_pagination()

        # Compute totals for the *full set* (fast aggregate query)
        self._total_count, self._total_amount = self._compute_totals()

        # Prime UI totals immediately
        self._update_totals(self._total_amount, self._total_count)

        # Load first page
        self._load_next_page(reset_scroll=True)


    def _reset_pagination(self):
        self._cursor_key = None
        self._has_more = True
        self._is_loading = False

    def _ledger_flag(self) -> int:
        """Return which ledger state this dialog is currently browsing."""
        return 0 if getattr(self, "mode", "edit") == "edit" else 1

    def _compute_totals(self) -> tuple[int, float]:
        """Return (count, sum_amount) for current ledger flag without joins."""
        ledger_flag = self._ledger_flag()
        query = "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total_amount FROM payments WHERE in_ledger = ?"
        try:
            cur = self.conn.cursor()
            cur.execute(query, (ledger_flag,))
            r = cur.fetchone()
            cnt = int(r["cnt"] or 0) if r else 0
            total = float(r["total_amount"] or 0) if r else 0.0
            return cnt, total
        except Exception:
            return 0, 0.0

    def _fetch_payment_page(self, cursor_key):
        """Fetch one page using keyset pagination."""
        ledger_flag = self._ledger_flag()

        query = """
            SELECT
                p.id AS payment_id,
                p.payment_code,
                p.payment_date,
                p.created_at,
                p.amount,
                p.in_ledger,
                i.invoice_code,
                c.name AS customer_name,
                ob.name AS ob_name,
                pj.pjp_name AS pjp_name
            FROM payments p
            LEFT JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE p.in_ledger = ?
        """
        params = [ledger_flag]

        sort_mode = getattr(self, "sort_mode", "newest")

        def add_keyset_clause_date(is_desc: bool):
            nonlocal query, params
            if not cursor_key:
                return
            last_date, last_id = cursor_key
            if is_desc:
                query += " AND (p.payment_date < ? OR (p.payment_date = ? AND p.id < ?))"
                params.extend([last_date, last_date, last_id])
            else:
                query += " AND (p.payment_date > ? OR (p.payment_date = ? AND p.id > ?))"
                params.extend([last_date, last_date, last_id])

        def add_keyset_clause_amount(is_desc: bool):
            nonlocal query, params
            if not cursor_key:
                return
            last_amt, last_id = cursor_key
            if is_desc:
                query += " AND (p.amount < ? OR (p.amount = ? AND p.id < ?))"
                params.extend([last_amt, last_amt, last_id])
            else:
                query += " AND (p.amount > ? OR (p.amount = ? AND p.id > ?))"
                params.extend([last_amt, last_amt, last_id])

        if sort_mode == "oldest":
            add_keyset_clause_date(is_desc=False)
            query += " ORDER BY p.payment_date ASC, p.id ASC"
        elif sort_mode == "newest":
            add_keyset_clause_date(is_desc=True)
            query += " ORDER BY p.payment_date DESC, p.id DESC"
        elif sort_mode == "amount_high":
            add_keyset_clause_amount(is_desc=True)
            query += " ORDER BY p.amount DESC, p.id DESC"
        elif sort_mode == "amount_low":
            add_keyset_clause_amount(is_desc=False)
            query += " ORDER BY p.amount ASC, p.id ASC"
        else:
            add_keyset_clause_date(is_desc=True)
            query += " ORDER BY p.payment_date DESC, p.id DESC"

        query += " LIMIT ?"
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

            rows = self._fetch_payment_page(self._cursor_key)

            # First load and no results -> show empty state
            if not rows and not self.rows:
                empty = QLabel("No payments found.")
                empty.setObjectName("EmptyLabel")
                empty.setAlignment(Qt.AlignCenter)
                insert_at = self.container_layout.count() - 1
                self.container_layout.insertWidget(insert_at, empty)

                self._update_bulk_buttons_state()
                self._has_more = False
                return

            if not rows:
                self._has_more = False
                self._update_bulk_buttons_state()
                return

            start_idx = len(self.rows) + 1
            for off, row in enumerate(rows):
                pay_id = row["payment_id"]
                code = row["payment_code"] or ""
                date_str = row["payment_date"] or ""
                created_at = row["created_at"]
                amount = float(row["amount"] or 0)
                in_ledger = int(row["in_ledger"] or 0)
                inv_code = row["invoice_code"] or "-"
                customer_name = row["customer_name"] or "-"
                ob_name = row["ob_name"] or "-"
                pjp_name = row["pjp_name"] or "-"

                # date display
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    display_date = dt.strftime("%d/%m/%Y")
                except Exception:
                    display_date = date_str or ""

                # time display from created_at
                time_str = ""
                if created_at:
                    try:
                        dt_full = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
                        time_str = dt_full.strftime("%I:%M %p")
                    except Exception:
                        parts = str(created_at).split()
                        if len(parts) > 1:
                            time_str = parts[1]

                payment_data = {
                    "id": pay_id,
                    "payment_code": code,
                    "invoice_code": inv_code,
                    "date_str": display_date,
                    "time_str": time_str,
                    "amount": amount,
                    "in_ledger": in_ledger,
                    "customer_name": customer_name,
                    "ob_name": ob_name,
                    "pjp_name": pjp_name,
                    "row_number": start_idx + off,
                }

                row_widget = PaymentRowWidget(payment_data, self)
                insert_at = self.container_layout.count() - 1
                self.container_layout.insertWidget(insert_at, row_widget)

                self.rows.append(row_widget)

            # Update cursor
            last = rows[-1]
            sort_mode = getattr(self, "sort_mode", "newest")
            if sort_mode in ("oldest", "newest"):
                self._cursor_key = (last["payment_date"], int(last["payment_id"]))
            else:
                self._cursor_key = (float(last["amount"] or 0), int(last["payment_id"]))

            if len(rows) < int(self.page_size):
                self._has_more = False

            self._update_bulk_buttons_state()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load payments:\n{e}",
            )
            self._has_more = False
        finally:
            self._is_loading = False

    def _on_scroll(self, value: int):
        """Triggered on scroll; loads next page near the bottom."""
        if not hasattr(self, "scroll_area") or not self.scroll_area:
            return
        sb = self.scroll_area.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        if value >= sb.maximum() - 150:
            self._load_next_page()

    # ---------------- checkbox helpers ----------------


    def _get_selected_ids(self):
        return [row.payment_data["id"] for row in self.rows if row.chk.isChecked()]
    
    def _update_totals(self, total_amount: float, count: int):
        # count label
        if hasattr(self, "lbl_total_count"):
            if count == 0:
                self.lbl_total_count.setText("No payments")
            elif count == 1:
                self.lbl_total_count.setText("1 payment")
            else:
                self.lbl_total_count.setText(f"{count} payments")

        # amount label
        if hasattr(self, "lbl_total_amount"):
            self.lbl_total_amount.setText(f"{total_amount:,.0f} PKR")


    def _update_bulk_buttons_state(self):
        count = len(self._get_selected_ids())
        if count > 0:
            self.btn_delete_selected.setEnabled(True)
            self.btn_add_to_ledger.setEnabled(True)
            self.btn_delete_selected.setText(f"Delete Selected ({count})")
        else:
            self.btn_delete_selected.setEnabled(False)
            self.btn_add_to_ledger.setEnabled(False)
            self.btn_delete_selected.setText("Delete Selected")

    def _sync_header_checkbox(self):
        total = len(self.rows)
        if total == 0:
            self.header_checkbox.blockSignals(True)
            self.header_checkbox.setCheckState(Qt.Unchecked)
            self.header_checkbox.blockSignals(False)
            return

        selected = sum(1 for r in self.rows if r.chk.isChecked())
        self.header_checkbox.blockSignals(True)
        if selected == 0:
            self.header_checkbox.setCheckState(Qt.Unchecked)
        elif selected == total:
            self.header_checkbox.setCheckState(Qt.Checked)
        else:
            self.header_checkbox.setCheckState(Qt.PartiallyChecked)
        self.header_checkbox.blockSignals(False)

    def on_row_checkbox_changed(self, state: int):
        self._sync_header_checkbox()
        self._update_bulk_buttons_state()

    def _on_header_checkbox_changed(self, state: int):
        all_checked = all(r.chk.isChecked() for r in self.rows)
        new_checked = not all_checked

        for row in self.rows:
            row.chk.blockSignals(True)
            row.chk.setChecked(new_checked)
            row.chk.blockSignals(False)

        self._sync_header_checkbox()
        self._update_bulk_buttons_state()

    # ---------------- actions ----------------

    def add_payment(self):
        """
        When '+ Add Payment' is clicked inside Manage Payments, reuse the
        MainWindow logic so Add + Manage are 50/50 side by side.
        """
        main = self.parent()
        while main is not None and not hasattr(main, "open_add_payment"):
            main = main.parent()

        if main is not None and hasattr(main, "open_add_payment"):
            # Use existing main-window behaviour (reused dialog, signal wiring)
            main.open_add_payment()
            # Force the side-by-side layout when both dialogs are visible
            if hasattr(main, "_position_payment_windows"):
                main._position_payment_windows()
            return

        # Fallback (normally not used)
        dlg = AddPaymentDialog(self.conn, self)
        dlg.payment_added.connect(self.load_payments)
        dlg.show()


    def edit_payment(self, payment_id: int):
        dlg = EditPaymentDialog(self.conn, payment_id, self)
        if dlg.exec():
            self.load_payments()

    def delete_payment(self, payment_id: int, payment_code: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete payment <b>{payment_code}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete payment:\n{e}")
            return

        self.load_payments()

    def delete_selected(self):
        ids = self._get_selected_ids()
        count = len(ids)
        if count == 0:
            QMessageBox.information(
                self,
                "No selection",
                "Please select at least one payment.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete <b>{count}</b> selected payment(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"DELETE FROM payments WHERE id IN ({','.join('?' for _ in ids)})",
                ids,
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete selected payments:\n{e}",
            )
            return

        self.load_payments()

    def add_selected_to_ledger(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(
                self,
                "No selection",
                "Please select at least one payment.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                UPDATE payments
                SET in_ledger = 1
                WHERE id IN ({",".join("?" for _ in ids)})
                  AND in_ledger = 0
                """,
                ids,
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to add selected payments to ledger:\n{e}"
            )
            return

        self.load_payments()


    def remove_selected_from_ledger(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(
                self,
                "No selection",
                "Please select at least one payment.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                UPDATE payments
                SET in_ledger = 0
                WHERE id IN ({",".join("?" for _ in ids)})
                AND in_ledger = 1
                """,
                ids,
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to remove selected payments from ledger:\n{e}"
            )
            return

        self.load_payments()


    # ---------------- styles ----------------

    def _apply_styles(self):
        dark = self.dark_mode

        bg = "#000000" if dark else "#ffffff"
        header_bg = "#020617" if dark else "#f8fafc"
        table_header_bg = "#111827" if dark else "#e5e7eb"
        table_bg = "#000000" if dark else "#ffffff"
        border = "#1f2937" if dark else "#e2e8f0"
        text = "#e5e7eb" if dark else "#0f172a"
        muted = "#9ca3af" if dark else "#64748b"
        primary = "rgb(37, 79, 167)"
        danger = "#ef4444"

        ledger_yes_bg = "#22c55e" if dark else "#bbf7d0"
        ledger_yes_fg = "#052e16" if dark else "#166534"
        ledger_no_bg = "#facc15" if dark else "#fef9c3"
        ledger_no_fg = "#422006" if dark else "#854d0e"

        close_btn_bg = "#111827" if dark else "#f1f5f9"
        close_btn_fg = text
        close_btn_border = border
        close_btn_hover = "#1f2937" if dark else "#e2e8f0"

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg};
            }}

            #PaymentsHeader {{
                background-color: {header_bg};
            }}

            #PaymentsTitle {{
                font-size: 20px;
                font-weight: 600;
                color: {text};
            }}

            #PaymentsScroll, #PaymentsContainer {{
                background-color: {table_bg};
            }}

            #TableHeaderRow {{
                background-color: {table_header_bg};
                border-bottom: 1px solid {border};
            }}

            #HeaderLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {text};
            }}

            #PaymentRow {{
                background-color: {table_bg};
                border-bottom: 1px solid {border};
            }}

            #CellLabel {{
                color: {text};
                font-size: 12px;
            }}
            
            #RowNumberLabel {{
                color: {muted};
                font-size: 11px;
            }}

            #AmountLabel {{
                color: {text};
                font-size: 12px;
            }}

            #LedgerPill {{
                padding: 4px 10px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 500;
            }}
            #LedgerPill[ledgerState="yes"] {{
                background-color: {ledger_yes_bg};
                color: {ledger_yes_fg};
            }}
            #LedgerPill[ledgerState="no"] {{
                background-color: {ledger_no_bg};
                color: {ledger_no_fg};
            }}

            #EditBtn {{
                background-color: #f3f4f6;
                color: {text};
                border-radius: 6px;
                border: 1px solid {border};
                padding: 0px;
                font-size: 12px;
            }}
            #EditBtn:hover {{
                background-color: #e5e7eb;
            }}

            #DeleteBtn {{
                background-color: {danger};
                color: white;
                border-radius: 6px;
                border: none;
                padding: 0px;
                font-size: 12px;
            }}
            #DeleteBtn:hover {{
                background-color: #dc2626;
            }}

            #AddPaymentBtn {{
                background-color: {primary};
                color: white;
                border-radius: 8px;
                padding: 10px 22px;
                border: none;
                font-weight: 500;
            }}
            #AddPaymentBtn:hover {{
                background-color: rgb(30, 64, 140);
            }}

            #DeleteSelectedBtn {{
                background-color: {danger};
                color: white;
                border-radius: 8px;
                padding: 10px 22px;
                border: none;
                font-weight: 500;
            }}
            #DeleteSelectedBtn:disabled {{
                background-color: #9ca3af;
                color: #f9fafb;
            }}
            #DeleteSelectedBtn:hover:enabled {{
                background-color: #dc2626;
            }}

            #AddToLedgerBtn {{
                background-color: {primary};
                color: white;
                border-radius: 8px;
                padding: 10px 22px;
                border: none;
                font-weight: 500;
            }}
            #AddToLedgerBtn:disabled {{
                background-color: #9ca3af;
                color: #f9fafb;
            }}
            #AddToLedgerBtn:hover:enabled {{
                background-color: rgb(30, 64, 140);
            }}

            #FooterCloseBtn {{
                background-color: {close_btn_bg};
                color: {close_btn_fg};
                border-radius: 8px;
                border: 1px solid {close_btn_border};
                padding: 8px 20px;
                font-weight: 500;
            }}
            #FooterCloseBtn:hover {{
                background-color: {close_btn_hover};
            }}


            #PaymentsTotalsBar {{
                background-color: {header_bg};
                border-top: 1px solid {border};
            }}

            #PaymentsTotalCount {{
                color: {muted};
                font-size: 12px;
            }}

            #PaymentsTotalCaption {{
                color: {muted};
                font-size: 12px;
            }}

            #PaymentsTotalAmount {{
                color: {text};
                font-size: 14px;
                font-weight: 600;
            }}

            #EmptyLabel {{
                color: {muted};
                font-size: 14px;
            }}

            QCheckBox {{
                color: {text};
            }}

            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
            }}

            QToolTip {{
                background-color: {table_header_bg};
                color: {text};
                border: 1px solid {border};
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 11px;
            }}
            """
        )