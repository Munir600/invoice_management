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
    QApplication,
    QToolTip,
    QToolButton,
    QMenu,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QCursor, QIcon

from invoices.add_invoice import AddInvoiceDialog

# --------------------------------------------------------------------
#  ICON HELPERS
# --------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ICON_DIR = os.path.join(BASE_DIR, "icons")


def app_icon(name: str) -> QIcon:
    return QIcon(os.path.join(ICON_DIR, f"{name}.svg"))


# --------------------------------------------------------------------
#  EDIT INVOICE DIALOG (reuses AddInvoiceDialog layout)
# --------------------------------------------------------------------


class EditInvoiceDialog(AddInvoiceDialog):
    """
    Reuse AddInvoiceDialog UI to edit an existing invoice.

    - Invoice code is read-only.
    - Date / OB / PJP / Customer / Amount are editable.
    """

    def __init__(self, db_conn: sqlite3.Connection, invoice_id: int, parent=None):
        self.invoice_id = invoice_id
        super().__init__(db_conn, parent)

        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit Invoice")

        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "DialogPrimaryButton":
                btn.setText("Save")
                break

        self._load_invoice_data()

    def _on_add_clicked(self):
        code = self.edit_code.text().strip()
        invoice_date_iso = self.date_edit.date().toString("yyyy-MM-dd")

        ob_index = self.combo_ob.currentIndex()
        pjp_index = self.combo_pjp.currentIndex()
        cust_index = self.combo_customer.currentIndex()

        order_booker_id = self.combo_ob.itemData(ob_index) if ob_index >= 0 else None
        pjp_id = self.combo_pjp.itemData(pjp_index) if pjp_index >= 0 else None
        customer_id = self.combo_customer.itemData(cust_index) if cust_index >= 0 else None

        amount_text = self.edit_amount.text().strip()
        amount = float(amount_text) if amount_text else 0.0

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
                UPDATE invoices
                SET invoice_date = ?,
                    order_booker_id = ?,
                    pjp_id = ?,
                    customer_id = ?,
                    amount = ?
                WHERE id = ?
                """,
                (
                    invoice_date_iso,
                    order_booker_id,
                    pjp_id,
                    customer_id,
                    amount,
                    self.invoice_id,
                ),
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update invoice:\n\n{e}")
            return

        self.accept()

    def _load_invoice_data(self):
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    invoice_code,
                    invoice_date,
                    order_booker_id,
                    pjp_id,
                    customer_id,
                    amount
                FROM invoices
                WHERE id = ?
                """,
                (self.invoice_id,),
            )
            row = cur.fetchone()
            if not row:
                QMessageBox.critical(self, "Error", "Invoice not found.")
                self.reject()
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load invoice:\n\n{e}")
            self.reject()
            return

        if isinstance(row, sqlite3.Row):
            code = row["invoice_code"]
            date_str = row["invoice_date"]
            ob_id = row["order_booker_id"]
            pjp_id = row["pjp_id"]
            customer_id = row["customer_id"]
            amount = row["amount"]
        else:
            code, date_str, ob_id, pjp_id, customer_id, amount = row

        self.edit_code.setText(str(code))

        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        except Exception:
            self.date_edit.setDate(QDate.currentDate())

        index_ob = self.combo_ob.findData(ob_id)
        if index_ob >= 0:
            self.combo_ob.setCurrentIndex(index_ob)

        self._load_pjps_for_ob(ob_id)
        index_pjp = self.combo_pjp.findData(pjp_id)
        if index_pjp >= 0:
            self.combo_pjp.setCurrentIndex(index_pjp)

        self._load_customers_for_pjp(pjp_id)
        index_cust = self.combo_customer.findData(customer_id)
        if index_cust >= 0:
            self.combo_customer.setCurrentIndex(index_cust)

        if amount is not None:
            self.edit_amount.setText(str(amount))


# --------------------------------------------------------------------
#  INVOICE ROW WIDGET
# --------------------------------------------------------------------


class InvoiceRowWidget(QFrame):
    def __init__(self, invoice_data: dict, parent_dialog: "ManageInvoicesDialog"):
        super().__init__()
        self.invoice_data = invoice_data
        self.parent_dialog = parent_dialog
        self.full_code = str(invoice_data.get("invoice_code", "") or "")

        self.setObjectName("InvoiceRow")
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        self.chk = QCheckBox()
        self.chk.setCursor(QCursor(Qt.PointingHandCursor))
        self.chk.stateChanged.connect(self.parent_dialog.on_row_checkbox_changed)
        self.chk.setFixedWidth(40)
        layout.addWidget(self.chk, alignment=Qt.AlignHCenter | Qt.AlignVCenter)

        row_no = invoice_data.get("row_number")
        self.lbl_rownum = QLabel(str(row_no) if row_no is not None else "")
        self.lbl_rownum.setObjectName("RowNumberLabel")
        self.lbl_rownum.setAlignment(Qt.AlignCenter)
        self.lbl_rownum.setFixedWidth(40)
        layout.addWidget(self.lbl_rownum)

        def make_label(obj_name=None, align_left=True, bold=False, rich=False):
            lbl = QLabel()
            if obj_name:
                lbl.setObjectName(obj_name)
            if bold:
                f = lbl.font()
                f.setBold(True)
                lbl.setFont(f)
            lbl.setAlignment(Qt.AlignVCenter | (Qt.AlignLeft if align_left else Qt.AlignRight))
            if rich:
                lbl.setTextFormat(Qt.RichText)
            return lbl

        code_lbl = make_label("CellLabel")
        code_lbl.setFixedWidth(90)
        code_lbl.setAlignment(Qt.AlignCenter)
        fm = code_lbl.fontMetrics()
        code_lbl.setText(fm.elidedText(self.full_code, Qt.ElideRight, code_lbl.width()))
        code_lbl.setCursor(QCursor(Qt.PointingHandCursor))
        code_lbl.setToolTip("Click to copy Invoice ID")
        code_lbl.mousePressEvent = self._on_code_clicked
        layout.addWidget(code_lbl)

        date_lbl = make_label("CellLabel")
        date_lbl.setFixedWidth(80)
        date_lbl.setText(date_lbl.fontMetrics().elidedText(invoice_data.get("date_str", ""), Qt.ElideRight, date_lbl.width()))
        layout.addWidget(date_lbl)

        time_lbl = make_label("CellLabel")
        time_lbl.setFixedWidth(70)
        time_lbl.setText(time_lbl.fontMetrics().elidedText(invoice_data.get("time_str", ""), Qt.ElideRight, time_lbl.width()))
        layout.addWidget(time_lbl)

        ob_lbl = make_label("CellLabel")
        ob_lbl.setFixedWidth(100)
        ob_lbl.setText(ob_lbl.fontMetrics().elidedText(invoice_data.get("ob_name", "-"), Qt.ElideRight, ob_lbl.width()))
        layout.addWidget(ob_lbl)

        pjp_lbl = make_label("CellLabel")
        pjp_lbl.setFixedWidth(150)
        pjp_lbl.setText(pjp_lbl.fontMetrics().elidedText(invoice_data.get("pjp_name", "-"), Qt.ElideRight, pjp_lbl.width()))
        layout.addWidget(pjp_lbl)

        customer_lbl = make_label("CellLabel")
        customer_lbl.setFixedWidth(130)
        customer_lbl.setText(customer_lbl.fontMetrics().elidedText(invoice_data.get("customer_name", "-"), Qt.ElideRight, customer_lbl.width()))
        layout.addWidget(customer_lbl)

        amount_val = invoice_data.get("amount") if invoice_data.get("amount") is not None else 0
        amount_html = f"<b>PKR</b> {amount_val:,.0f}"
        self.lbl_amount = make_label("AmountLabel", align_left=True, rich=True)
        self.lbl_amount.setFixedWidth(100)
        self.lbl_amount.setText(amount_html)
        layout.addWidget(self.lbl_amount)

        self.lbl_ledger = QLabel()
        self.lbl_ledger.setObjectName("LedgerPill")
        self.lbl_ledger.setFixedWidth(60)
        self.lbl_ledger.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ledger)
        self.update_ledger_pill(int(invoice_data.get("in_ledger") or 0))

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
        layout.addWidget(actions_frame)

    def _on_code_clicked(self, event):
        if event.button() == Qt.LeftButton and self.full_code:
            app = QApplication.instance()
            if app is not None:
                app.clipboard().setText(self.full_code)
                QToolTip.showText(event.globalPos(), "Invoice ID copied", self)

    def _update_button_icons(self):
        dark = bool(getattr(self.parent_dialog, "dark_mode", False))
        if dark:
            edit_name = "edit-black"
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
        self.parent_dialog.edit_invoice(self.invoice_data["id"])

    def on_delete_clicked(self):
        self.parent_dialog.delete_invoice(self.invoice_data["id"], self.invoice_data.get("invoice_code", ""))


# --------------------------------------------------------------------
#  MANAGE INVOICES DIALOG
# --------------------------------------------------------------------


class ManageInvoicesDialog(QDialog):
    def __init__(self, db_conn: sqlite3.Connection, parent=None, mode: str = "edit"):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = bool(getattr(parent, "dark_mode", False))
        self.mode = mode  # "edit" or "manage"
        self.sort_mode = "oldest"

        title_text = "Edit Invoices" if self.mode == "edit" else "Manage Invoices"
        self.setWindowTitle(title_text)

        self.resize(680, 550)
        self.setMinimumWidth(640)

        self.rows: list[InvoiceRowWidget] = []

        # --- lazy loading / keyset pagination ---
        self.page_size = 25
        self._cursor_key = None  # tuple(sort_value, id)
        self._has_more = True
        self._is_loading = False

        self._total_count = 0
        self._total_amount = 0.0

        self._build_ui()
        self._apply_styles()
        self.load_invoices()

    # ---------------- UI ----------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("InvoicesHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        h_layout.setSpacing(8)

        title_text = "Edit Invoices" if self.mode == "edit" else "Manage Invoices"
        title = QLabel(title_text)
        title.setObjectName("InvoicesTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()
        main_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("InvoicesScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFocusPolicy(Qt.StrongFocus)

        self.scroll_area = scroll

        container = QWidget()
        container.setObjectName("InvoicesContainer")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        self.container_layout.setContentsMargins(24, 20, 24, 20)
        self.container_layout.setSpacing(0)

        self._build_table_header()
        self.container_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # lazy loading trigger
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)

        totals_bar = QFrame()
        totals_bar.setObjectName("InvoicesTotalsBar")
        totals_layout = QHBoxLayout(totals_bar)
        totals_layout.setContentsMargins(24, 8, 24, 8)
        totals_layout.setSpacing(12)

        self.lbl_total_count = QLabel("No invoices")
        self.lbl_total_count.setObjectName("InvoicesTotalCount")
        totals_layout.addWidget(self.lbl_total_count)
        totals_layout.addStretch()

        self.lbl_total_caption = QLabel("Total Amount:")
        self.lbl_total_caption.setObjectName("InvoicesTotalCaption")
        self.lbl_total_amount = QLabel("0 PKR")
        self.lbl_total_amount.setObjectName("InvoicesTotalAmount")

        totals_layout.addWidget(self.lbl_total_caption)
        totals_layout.addWidget(self.lbl_total_amount)
        main_layout.addWidget(totals_bar)

        footer = QFrame()
        footer.setObjectName("InvoicesFooter")
        footer.setFixedHeight(80)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(24, 16, 24, 16)
        f_layout.setSpacing(12)

        self.btn_add_invoice = QPushButton("+ Add Invoice")
        self.btn_add_invoice.setObjectName("AddInvoiceBtn")
        self.btn_add_invoice.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_add_invoice.clicked.connect(self.add_invoice)

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

        f_layout.addWidget(self.btn_add_invoice)
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

        self.header_checkbox = QCheckBox()
        self.header_checkbox.setTristate(True)
        self.header_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.header_checkbox.stateChanged.connect(self._on_header_checkbox_changed)
        self.header_checkbox.setFixedWidth(40)
        header_layout.addWidget(self.header_checkbox, alignment=Qt.AlignHCenter | Qt.AlignVCenter)

        self.sort_button = QToolButton()
        self.sort_button.setObjectName("SortButton")
        icon_name = "sort" if self.dark_mode else "sort-black"
        self.sort_button.setIcon(app_icon(icon_name))
        self.sort_button.setIconSize(QSize(16, 16))
        self.sort_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.sort_button.setToolTip("Sort invoices")
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

        header_layout.addWidget(self.sort_button, alignment=Qt.AlignHCenter | Qt.AlignVCenter)

        def add_header_label(text, align_right=False):
            lbl = QLabel(text)
            lbl.setObjectName("HeaderLabel")
            if align_right:
                lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            header_layout.addWidget(lbl)
            return lbl

        id_lbl = add_header_label("Invoice ID")
        id_lbl.setFixedWidth(90)

        date_lbl = add_header_label("Date")
        date_lbl.setFixedWidth(80)

        time_hdr = add_header_label("Time")
        time_hdr.setFixedWidth(70)

        ob_lbl = add_header_label("Order Booker")
        ob_lbl.setFixedWidth(100)

        pjp_lbl = add_header_label("PJP")
        pjp_lbl.setFixedWidth(150)

        customer_lbl = add_header_label("Customer")
        customer_lbl.setFixedWidth(130)

        amount_lbl = add_header_label("Amount")
        amount_lbl.setFixedWidth(100)

        ledger_lbl = add_header_label("Ledger")
        ledger_lbl.setFixedWidth(60)

        actions_lbl = add_header_label("Actions", align_right=True)
        actions_lbl.setFixedWidth(80)

        self.container_layout.addWidget(header_row)

    # ---------------- data load ----------------

    def _set_sort_mode(self, mode: str):
        self.sort_mode = mode
        self.load_invoices()

    def load_invoices(self):
       
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


        self._reset_pagination()

        # Totals across all invoices (no filter UI in this dialog)
        self._total_count, self._total_amount = self._compute_totals()
        self._update_totals(self._total_amount, self._total_count)

        self._load_next_page(reset_scroll=True)

    def _reset_pagination(self):
        self._cursor_key = None
        self._has_more = True
        self._is_loading = False

    def _compute_totals(self) -> tuple[int, float]:
        # No UI filters exist in this dialog; keep it simple + fast
        if self.mode == "edit":

            query = """
                SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total_amount
                FROM invoices
                WHERE COALESCE(in_ledger, 0) = 0
            """
        else:
            query = """
                SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total_amount
                FROM invoices
                WHERE COALESCE(in_ledger, 0) = 1
            """

        try:
            cur = self.conn.cursor()
            cur.execute(query)
            r = cur.fetchone()
            cnt = int(r["cnt"] or 0) if r else 0
            total = float(r["total_amount"] or 0) if r else 0.0
            return cnt, total
        except Exception:
            return 0, 0.0

    def _fetch_invoice_page(self, cursor_key):
        query = """
            SELECT
                i.id AS invoice_id,
                i.invoice_code,
                i.invoice_date,
                i.created_at,
                i.amount,
                i.in_ledger,
                c.name AS customer_name,
                ob.name AS ob_name,
                pj.pjp_name AS pjp_name
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE 1=1
        """

        # filter by ledger membership based on mode
        if self.mode == "edit":
            query += " AND COALESCE(i.in_ledger, 0) = 0"
        else:  # manage
            query += " AND COALESCE(i.in_ledger, 0) = 1"

        params = []

        sort_mode = getattr(self, "sort_mode", "newest")

        def add_keyset_clause_date(is_desc: bool):
            nonlocal query, params
            if not cursor_key:
                return
            last_date, last_id = cursor_key
            if is_desc:
                query += " AND (i.invoice_date < ? OR (i.invoice_date = ? AND i.id < ?))"
                params.extend([last_date, last_date, last_id])
            else:
                query += " AND (i.invoice_date > ? OR (i.invoice_date = ? AND i.id > ?))"
                params.extend([last_date, last_date, last_id])

        def add_keyset_clause_amount(is_desc: bool):
            nonlocal query, params
            if not cursor_key:
                return
            last_amt, last_id = cursor_key
            if is_desc:
                query += " AND (i.amount < ? OR (i.amount = ? AND i.id < ?))"
                params.extend([last_amt, last_amt, last_id])
            else:
                query += " AND (i.amount > ? OR (i.amount = ? AND i.id > ?))"
                params.extend([last_amt, last_amt, last_id])

        if sort_mode == "oldest":
            add_keyset_clause_date(is_desc=False)
            query += " ORDER BY i.invoice_date ASC, i.id ASC"
        elif sort_mode == "newest":
            add_keyset_clause_date(is_desc=True)
            query += " ORDER BY i.invoice_date DESC, i.id DESC"
        elif sort_mode == "amount_high":
            add_keyset_clause_amount(is_desc=True)
            query += " ORDER BY i.amount DESC, i.id DESC"
        elif sort_mode == "amount_low":
            add_keyset_clause_amount(is_desc=False)
            query += " ORDER BY i.amount ASC, i.id ASC"
        else:
            add_keyset_clause_date(is_desc=True)
            query += " ORDER BY i.invoice_date DESC, i.id DESC"

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
            if reset_scroll and self.scroll_area:
                self.scroll_area.verticalScrollBar().setValue(0)

            rows = self._fetch_invoice_page(self._cursor_key)

            if not rows and not self.rows:
                empty = QLabel("No invoices found.")
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
                invoice_id = row["invoice_id"]
                code = row["invoice_code"] or ""
                date_str = row["invoice_date"] or ""
                created_at = row["created_at"]
                amount = float(row["amount"] or 0)
                in_ledger = int(row["in_ledger"] or 0)
                customer_name = row["customer_name"] or "-"
                ob_name = row["ob_name"] or "-"
                pjp_name = row["pjp_name"] or "-"

                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    display_date = dt.strftime("%d/%m/%Y")
                except Exception:
                    display_date = date_str or ""

                time_str = ""
                if created_at:
                    try:
                        dt_full = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
                        time_str = dt_full.strftime("%I:%M %p")
                    except Exception:
                        parts = str(created_at).split()
                        if len(parts) > 1:
                            time_str = parts[1]

                invoice_data = {
                    "id": invoice_id,
                    "invoice_code": code,
                    "date_str": display_date,
                    "time_str": time_str,
                    "amount": amount,
                    "in_ledger": in_ledger,
                    "customer_name": customer_name,
                    "ob_name": ob_name,
                    "pjp_name": pjp_name,
                    "row_number": start_idx + off,
                }

                row_widget = InvoiceRowWidget(invoice_data, self)
                # insert above the final stretch item
                insert_at = self.container_layout.count() - 1
                self.container_layout.insertWidget(insert_at, row_widget)

                self.rows.append(row_widget)

            last = rows[-1]
            sort_mode = getattr(self, "sort_mode", "newest")
            if sort_mode in ("oldest", "newest"):
                self._cursor_key = (last["invoice_date"], int(last["invoice_id"]))
            else:
                self._cursor_key = (float(last["amount"] or 0), int(last["invoice_id"]))

            if len(rows) < int(self.page_size):
                self._has_more = False

            self._update_bulk_buttons_state()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load invoices:\n{e}")
            self._has_more = False
        finally:
            self._is_loading = False

    def _on_scroll(self, value: int):
        if not self.scroll_area:
            return
        sb = self.scroll_area.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        if value >= sb.maximum() - 150:
            self._load_next_page()

    # ---------------- checkbox helpers ----------------

    def _get_selected_ids(self):
        return [row.invoice_data["id"] for row in self.rows if row.chk.isChecked()]

    def _update_totals(self, total_amount: float, count: int):
        if hasattr(self, "lbl_total_count"):
            if count == 0:
                self.lbl_total_count.setText("No invoices")
            elif count == 1:
                self.lbl_total_count.setText("1 invoice")
            else:
                self.lbl_total_count.setText(f"{count} invoices")

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

    def add_invoice(self):
        main = self.parent()
        while main is not None and not hasattr(main, "open_add_invoice"):
            main = main.parent()

        if main is not None and hasattr(main, "open_add_invoice"):
            main.open_add_invoice()
            if hasattr(main, "_position_invoice_windows"):
                main._position_invoice_windows()
            return

        dlg = AddInvoiceDialog(self.conn, self)
        dlg.invoice_created.connect(self.load_invoices)
        dlg.show()

    def edit_invoice(self, invoice_id: int):
        dlg = EditInvoiceDialog(self.conn, invoice_id, self)
        if dlg.exec():
            self.load_invoices()

    def delete_invoice(self, invoice_id: int, invoice_code: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete invoice <b>{invoice_code}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cur = self.conn.cursor()

            cur.execute("SELECT COUNT(1) FROM payments WHERE invoice_id = ?", (invoice_id,))
            pay_count = int(cur.fetchone()[0] or 0)
            if pay_count > 0:
                QMessageBox.warning(
                    self,
                    "Cannot Delete Invoice",
                    "This invoice has an assigned payment(s). Delete payment(s) to delete invoice.",
                )
                return

            cur.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            self.conn.commit()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete invoice:\n{e}")
            return

        self.load_invoices()

    def delete_selected(self):
        ids = self._get_selected_ids()
        count = len(ids)
        if count == 0:
            QMessageBox.information(self, "No selection", "Please select at least one invoice.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete <b>{count}</b> selected invoice(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cur = self.conn.cursor()
            placeholders = ",".join("?" for _ in ids)

            cur.execute(f"SELECT COUNT(1) FROM payments WHERE invoice_id IN ({placeholders})", ids)
            linked = int(cur.fetchone()[0] or 0)
            if linked > 0:
                QMessageBox.warning(
                    self,
                    "Cannot Delete Invoices",
                    "One or more selected invoices have assigned payment(s). Delete payment(s) to delete invoice(s).",
                )
                return

            cur.execute(f"DELETE FROM invoices WHERE id IN ({placeholders})", ids)
            self.conn.commit()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete selected invoices:\n{e}")
            return

        self.load_invoices()

    def add_selected_to_ledger(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(self, "No selection", "Please select at least one invoice.")
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                UPDATE invoices
                SET in_ledger = 1
                WHERE id IN ({",".join("?" for _ in ids)})
                  AND in_ledger = 0
                """,
                ids,
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add selected invoices to ledger:\n{e}")
            return

        self.load_invoices()

    def remove_selected_from_ledger(self):
        ids = self._get_selected_ids()
        if not ids:
            QMessageBox.information(self, "No selection", "Please select at least one invoice.")
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                UPDATE invoices
                SET in_ledger = 0
                WHERE id IN ({",".join("?" for _ in ids)})
                  AND in_ledger = 1
                """,
                ids,
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove selected invoices from ledger:\n{e}")
            return

        self.load_invoices()

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

            #InvoicesHeader {{
                background-color: {header_bg};
            }}

            #InvoicesTitle {{
                font-size: 20px;
                font-weight: 600;
                color: {text};
            }}

            #InvoicesScroll, #InvoicesContainer {{
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

            #InvoiceRow {{
                background-color: {table_bg};
                border-bottom: 1px solid {border};
            }}

            #CellLabel {{
                color: {text};
                font-size: 12px;
            }}

            #AmountLabel {{
                color: {text};
                font-size: 12px;
            }}

            #RowNumberLabel {{
                color: {muted};
                font-size: 11px;
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

            #AddInvoiceBtn {{
                background-color: {primary};
                color: white;
                border-radius: 8px;
                padding: 10px 22px;
                border: none;
                font-weight: 500;
            }}
            #AddInvoiceBtn:hover {{
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

            #InvoicesTotalsBar {{
                background-color: {header_bg};
                border-top: 1px solid {border};
            }}

            #InvoicesTotalCount {{
                color: {muted};
                font-size: 12px;
            }}

            #InvoicesTotalCaption {{
                color: {muted};
                font-size: 12px;
            }}

            #InvoicesTotalAmount {{
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
