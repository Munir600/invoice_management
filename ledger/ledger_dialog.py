# ledger/ledger_dialog.py

import os
import sys
import sqlite3
from datetime import datetime
import subprocess

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
    QComboBox,
    QDateEdit,
    QLineEdit,
    QListView,
    QAbstractItemView,
    QFileDialog,
)

from PySide6.QtCore import (
    Qt,
    QDate,
    QSortFilterProxyModel,
    QPoint,
    QRegularExpression,
    QEvent,
    QUrl,
    QTimer,
)

from PySide6.QtGui import QCursor, QIcon, QStandardItemModel, QStandardItem, QDesktopServices, QAction

import tempfile
import zipfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

from PySide6.QtPrintSupport import QPrinterInfo
import html

from datetime import datetime

# --------------------------------------------------------------------
#  ICON HELPERS (re-use same icons folder)
# --------------------------------------------------------------------

def _resource_base_dir() -> str:
    # In PyInstaller --onefile, data is extracted to sys._MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    # ledger_dialog.py lives in ledger/, so go one folder up
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _resource_base_dir()
ICON_DIR = os.path.join(BASE_DIR, "icons")


def app_icon(name: str) -> QIcon:
    return QIcon(os.path.join(ICON_DIR, f"{name}.svg"))


def _to_number(x, default=0.0):
    """
    Converts values like None, "", "1,234", " 500 ", "Rs 1,200" into a float.
    Safe for PDF formatting.
    """
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if not s:
        return default

    # remove common non-numeric clutter (currency, spaces)
    s = s.replace(",", "")
    # keep digits, minus, dot only
    cleaned = "".join(ch for ch in s if (ch.isdigit() or ch in ".-"))
    if cleaned in ("", "-", ".", "-."):
        return default

    try:
        return float(cleaned)
    except ValueError:
        return default


# --------------------------------------------------------------------
#  LEDGER ROW WIDGET
# --------------------------------------------------------------------


class LedgerRowWidget(QFrame):
    """
    Single transaction row in the ledger table.

    Columns:
      Date | Time | Type | Ref ID | Order Booker | PJP | Customer
      | Debit (Invoice) | Credit (Payment) | Balance
    """

    def __init__(self, tx: dict, parent_dialog: "LedgerDialog"):
        super().__init__()
        self.tx = tx
        self.parent_dialog = parent_dialog

        self.setObjectName("LedgerRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(16)

        def make_label(width: int, obj_name: str | None = None, align_right=False):
            lbl = QLabel()
            if obj_name:
                lbl.setObjectName(obj_name)
            lbl.setAlignment(
                Qt.AlignVCenter | (Qt.AlignRight if align_right else Qt.AlignLeft)
            )
            lbl.setFixedWidth(width)
            return lbl

        # Date
        date_lbl = make_label(90, "CellLabel")
        date_lbl.setText(tx["date_str"])
        layout.addWidget(date_lbl)

        time_lbl = make_label(70, "CellLabel")
        time_lbl.setText(tx.get("time_str", ""))
        layout.addWidget(time_lbl)

        # Type
        type_lbl = make_label(80, "CellLabel")
        type_lbl.setText("Invoice" if tx["kind"] == "INVOICE" else "Payment")
        layout.addWidget(type_lbl)

        # Ref ID (invoice or payment code)
        ref_lbl = make_label(140, "CellLabel")
        fm = ref_lbl.fontMetrics()
        ref_code = "" if tx.get("ref_code") is None else str(tx.get("ref_code"))
        ref_lbl.setText(fm.elidedText(ref_code, Qt.ElideRight, ref_lbl.width()))
        layout.addWidget(ref_lbl)

        # Order Booker
        ob_lbl = make_label(140, "CellLabel")
        fm = ob_lbl.fontMetrics()
        ob_lbl.setText(fm.elidedText(tx["ob_name"], Qt.ElideRight, ob_lbl.width()))
        layout.addWidget(ob_lbl)

        # PJP
        pjp_lbl = make_label(140, "CellLabel")
        fm = pjp_lbl.fontMetrics()
        pjp_lbl.setText(fm.elidedText(tx["pjp_name"], Qt.ElideRight, pjp_lbl.width()))
        layout.addWidget(pjp_lbl)

        # Customer
        cust_lbl = make_label(140, "CellLabel")
        fm = cust_lbl.fontMetrics()
        cust_lbl.setText(
            fm.elidedText(tx["customer_name"], Qt.ElideRight, cust_lbl.width())
        )
        layout.addWidget(cust_lbl)

        # Debit (invoice amount)
        debit_lbl = make_label(80, "AmountLabel", align_right=True)
        debit_lbl.setText(f"{tx['debit']:,.0f}" if tx["debit"] else "")
        layout.addWidget(debit_lbl)

        # Credit (payment amount)
        credit_lbl = make_label(80, "AmountLabel", align_right=True)
        credit_lbl.setText(f"{tx['credit']:,.0f}" if tx["credit"] else "")
        layout.addWidget(credit_lbl)

        # Running balance
        bal_lbl = make_label(90, "AmountLabel", align_right=True)
        bal_lbl.setText(f"{tx['balance']:,.0f}")
        layout.addWidget(bal_lbl)


# --------------------------------------------------------------------
#  POPUP SEARCH COMBOBOX (same look/UX as your uploaded version)
# --------------------------------------------------------------------


class _ComboFilterProxy(QSortFilterProxyModel):
    """Filter proxy that always keeps the first row visible (e.g., 'All ...')."""

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        if source_row == 0:
            return True

        rx = self.filterRegularExpression()
        if not rx.pattern():
            return True

        idx = self.sourceModel().index(source_row, 0, source_parent)
        text = self.sourceModel().data(idx, Qt.DisplayRole) or ""
        return rx.match(str(text)).hasMatch()


class SearchablePopupComboBox(QComboBox):
    """
    QComboBox whose dropdown is a custom popup with:
    - a search field on top
    - a list view below
    """

    def __init__(self, label_for_search: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        self._source_model = QStandardItemModel(self)

        self._proxy = _ComboFilterProxy(self)
        self._proxy.setSourceModel(self._source_model)
        self._proxy.setFilterKeyColumn(0)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._list_view = QListView()
        self._list_view.setObjectName("ComboPopupList")
        self._list_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list_view.clicked.connect(self._on_item_clicked)

        self._search = QLineEdit()
        self._search.setObjectName("ComboPopupSearch")
        self._search.setPlaceholderText(f"Search {label_for_search}...")
        self._remote_fetcher = None
        self._remote_min_chars = 0
        self._remote_query = ""
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._run_remote_search)

        self._search.textChanged.connect(self._on_search_text_changed)

        self._popup = QFrame(None, Qt.Popup)
        self._popup.setObjectName("ComboPopupFrame")
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(8)
        popup_layout.addWidget(self._search)
        popup_layout.addWidget(self._list_view)

        self.setModel(self._proxy)
        self._list_view.setModel(self._proxy)
        self.view().setModel(self._proxy)

        self._popup.installEventFilter(self)
        self._search.installEventFilter(self)
        self._list_view.installEventFilter(self)

    def clear(self) -> None:  # type: ignore[override]
        # Don’t change selection here; callers set index after repopulating.
        self.blockSignals(True)
        self._source_model.clear()
        self._proxy.invalidateFilter()
        self.blockSignals(False)


    def addItem(self, text: str, userData=None) -> None:  # type: ignore[override]
        item = QStandardItem(str(text))
        item.setData(userData, Qt.UserRole)
        self._source_model.appendRow(item)


    def set_remote_fetcher(self, fetcher, *, min_chars: int = 0, debounce_ms: int = 150) -> None:
        """Enable DB-backed searching instead of in-model filtering.

        `fetcher` must be a callable that takes a single `query: str` and returns
        a list of (display_text, userData) tuples.
        """
        self._remote_fetcher = fetcher
        self._remote_min_chars = max(0, int(min_chars))
        self._debounce.setInterval(max(0, int(debounce_ms)))

    def _on_search_text_changed(self, text: str) -> None:
        if self._remote_fetcher is None:
            self._apply_filter(text)
            return

        self._remote_query = text or ""
        # Avoid hammering the DB on every keystroke.
        self._debounce.start()

    def _run_remote_search(self) -> None:
        if self._remote_fetcher is None:
            return

        q = (self._remote_query or "").strip()
        if len(q) < self._remote_min_chars:
            q = ""

        try:
            items = self._remote_fetcher(q) or []
        except Exception:
            # If the fetcher errors, keep whatever is currently shown.
            return

        self._set_items(items, preserve_selection=True)

    def _set_items(self, items: list[tuple[str, object]], preserve_selection: bool = True) -> None:
        cur_data = self.currentData(Qt.UserRole) if preserve_selection else None

        self.blockSignals(True)
        self._source_model.clear()

        for t, d in items:
            it = QStandardItem(str(t))
            it.setData(d, Qt.UserRole)
            self._source_model.appendRow(it)

        self._proxy.invalidateFilter()
        self.blockSignals(False)

        # Restore selection by data if possible
        if preserve_selection:
            target = cur_data
            if target is None:
                self.setCurrentIndex(0)
                return
            for i in range(self.count()):
                if self.itemData(i, Qt.UserRole) == target:
                    self.setCurrentIndex(i)
                    return
            self.setCurrentIndex(0)

    def showPopup(self) -> None:  # type: ignore[override]
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)

        # Local filter vs remote (DB-backed) search
        if self._remote_fetcher is None:
            self._apply_filter("")
        else:
            # Populate initial items when opening the popup
            self._remote_query = ""
            self._run_remote_search()
            self._apply_filter("")

        popup_width = max(self.width(), 260)
        self._popup.setFixedWidth(popup_width)

        rows = self._proxy.rowCount()
        row_h = self._list_view.sizeHintForRow(0) if rows else 24
        visible_rows = min(max(rows, 1), 10)
        list_h = row_h * visible_rows + 12
        self._list_view.setMinimumHeight(min(list_h, 320))
        self._list_view.setMaximumHeight(320)

        top_left = self.mapToGlobal(QPoint(0, self.height()))
        self._popup.move(top_left)
        self._popup.show()
        self._search.setFocus()

        cur = self.currentIndex()
        if cur >= 0:
            idx = self.model().index(cur, 0)
            self._list_view.scrollTo(idx, QListView.PositionAtCenter)

    def hidePopup(self) -> None:  # type: ignore[override]
        self._popup.hide()
        self._apply_filter("")

    def eventFilter(self, obj, event):  # type: ignore[override]
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hidePopup()
            return True
        return super().eventFilter(obj, event)

    def _apply_filter(self, text: str) -> None:
        if text:
            safe = QRegularExpression.escape(text)
            reg = QRegularExpression(safe, QRegularExpression.CaseInsensitiveOption)
            self._proxy.setFilterRegularExpression(reg)
        else:
            self._proxy.setFilterRegularExpression(QRegularExpression(""))

    def _on_item_clicked(self, proxy_index) -> None:
        if not proxy_index.isValid():
            return
        self.setCurrentIndex(proxy_index.row())
        self.hidePopup()


# --------------------------------------------------------------------
#  LEDGER DIALOG
# --------------------------------------------------------------------

class LedgerDialog(QDialog):



    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None, host: QWidget | None = None):
        super().__init__(parent)
        self.host = host or parent  # keep a reference to the main window even if parent=None

        self.conn = db_conn
        self.dark_mode = bool(getattr(self.host, "dark_mode", False))

        self.setWindowTitle("Ledger")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)

        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        self.resize(1100, 650)
        self.setMinimumWidth(950)

        # cache of rows
        self.rows: list[LedgerRowWidget] = []

        # --- lazy loading / keyset pagination (WIDGET UI, but paged) ---
        self.page_size = 10
        self._cursor_key = None  # (tx_date, tx_created_at, kind_sort, tx_id)
        self._has_more = True
        self._is_loading = False
        self._running_balance = 0.0

        # cache of current data
        self.current_transactions: list[dict] = []
        self.current_initial_balance: float = 0.0
        self.current_total_invoiced: float = 0.0
        self.current_total_paid: float = 0.0
        self.current_outstanding: float = 0.0

        self._build_ui()
        self._apply_styles()

        # Customer dropdown: DB-backed search (avoid loading all customers on open)
        self._customer_pjp_filter: int | None = None
        self.combo_customer.set_remote_fetcher(self._remote_fetch_customers, debounce_ms=150)

        # Defer initial data load to keep UI responsive
        QTimer.singleShot(0, self._initial_load)


    def _initial_load(self) -> None:
        # Populate filters first, then load ledger rows.
        self._load_filter_data()
        self._refresh_ledger()

    def _remote_fetch_customers(self, query: str):
        """Return list of (name, id) tuples for the Customer combo popup."""
        items: list[tuple[str, object]] = [("All Customers", None)]

        q = (query or "").strip()
        sql = """
            SELECT id, name
            FROM customers
            WHERE is_active = 1
        """
        params: list[object] = []

        if self._customer_pjp_filter is not None:
            sql += " AND pjp_id = ?"
            params.append(self._customer_pjp_filter)
        if q:
            sql += " AND name LIKE ?"
            params.append(f"%{q}%")

        sql += " ORDER BY name ASC LIMIT 200"

        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall() or []
        for r in rows:
            items.append((r["name"], r["id"]))

        # Ensure the currently-selected customer stays visible in the list
        selected_id = self.combo_customer.currentData(Qt.UserRole)
        if selected_id is not None and all(d != selected_id for _, d in items):
            try:
                cur.execute("SELECT id, name FROM customers WHERE id = ?", (selected_id,))
                r0 = cur.fetchone()
                if r0:
                    items.insert(1, (r0["name"], r0["id"]))
            except Exception:
                pass

        return items


    def _get_report_title(self) -> str:
        p = self.host
        return getattr(p, "report_title", getattr(p, "report_name", "AK ENTERPRISES"))



    def _is_virtual_printer_name(self, name: str) -> bool:
        n = (name or "").strip().lower()
        virtual = {
            "microsoft print to pdf",
            "microsoft xps document writer",
            "fax",
            "onenote (desktop)",
            "send to onenote 2016",
        }
        if n in virtual:
            return True
        if "print to pdf" in n:
            return True
        if "onenote" in n:
            return True
        return False


    def _get_physical_printer_name(self) -> str | None:
        default = QPrinterInfo.defaultPrinter()
        if default and not default.isNull() and not self._is_virtual_printer_name(default.printerName()):
            return default.printerName()

        for p in QPrinterInfo.availablePrinters():
            if not self._is_virtual_printer_name(p.printerName()):
                return p.printerName()

        return None


    def _silent_print_pdf(self, pdf_path: str, printer_name: str | None = None) -> bool:
        """
        Deterministic printing:
        - Prefer SumatraPDF.exe (supports selecting a printer, truly silent).
        - If not available, fall back to OS "print" verb, but never fail silently.
        Returns True if the command was launched successfully.
        """

        abs_path = os.path.abspath(pdf_path)


        try:
            
            # Prefer Sumatra (ship it beside the EXE in /tools)
            if getattr(sys, "frozen", False):
                base = os.path.dirname(sys.executable)   # folder containing CashInPOS.exe
            else:
                base = BASE_DIR                          # project root during development

            sumatra = os.path.join(base, "tools", "SumatraPDF.exe")

            if os.path.exists(sumatra) and sys.platform.startswith("win"):
                cmd = [sumatra, "-silent"]
                if printer_name:
                    cmd += ["-print-to", printer_name]          # prints to the physical printer you detected
                else:
                    cmd += ["-print-to-default"]
                cmd.append(abs_path)

                # Use run() so you can detect failures (Popen() hides everything)
                p = subprocess.run(cmd, capture_output=True, text=True)
                if p.returncode != 0:
                    raise RuntimeError((p.stderr or p.stdout or "").strip() or f"Sumatra return code: {p.returncode}")
                return True

            # Fallback (Windows): prints to DEFAULT printer only (cannot force printer_name here)
            if sys.platform.startswith("win"):
                # If default printer is virtual, warn explicitly (this is the common “nothing happens” case)
                default = QPrinterInfo.defaultPrinter()
                if default and not default.isNull() and self._is_virtual_printer_name(default.printerName()):
                    QMessageBox.warning(
                        self,
                        "Default printer is virtual",
                        f"Windows default printer is set to:\n\n{default.printerName()}\n\n"
                        "Printing via the OS fallback will not go to the physical printer.\n"
                        "Set your physical printer as default OR bundle SumatraPDF.exe for silent printing."
                    )

                os.startfile(abs_path, "print")
                return True

            # macOS/Linux
            subprocess.run(["lp", abs_path], check=True)
            return True

        except Exception as e:
            QMessageBox.warning(
                self,
                "Print failed",
                "Could not send the report to the printer.\n\n"
                f"Printer (selected): {printer_name or '(default)'}\n"
                f"File: {abs_path}\n\n"
                f"Error: {e}\n\n"
                "Fix: bundle SumatraPDF.exe with the app (recommended) or set Adobe Reader as the default PDF app."
            )
            return False


    def _validate_pdf_or_raise(self, pdf_path: str) -> None:
        import os
        if (not os.path.exists(pdf_path)) or os.path.getsize(pdf_path) < 100:  # size guard
            raise RuntimeError("PDF file was not written or is too small.")

        with open(pdf_path, "rb") as f:
            if f.read(5) != b"%PDF-":
                raise RuntimeError("File is not a valid PDF (missing %PDF- header).")


    
    def _download_invoices(self):
        """
        Download Invoice logic:
        - If exactly 1 invoice matches current filters -> save a single PDF
        - If >1 invoices match -> save a ZIP containing multiple PDFs
        """
        ob_id = self.combo_ob.currentData(Qt.UserRole)
        pjp_id = self.combo_pjp.currentData(Qt.UserRole)
        customer_id = self.combo_customer.currentData(Qt.UserRole)

        from_date_q = self.date_from.date()
        from_date = None if from_date_q == self.date_from.minimumDate() else from_date_q.toString("yyyy-MM-dd")

        to_date_q = self.date_to.date()
        to_date = None if to_date_q == self.date_to.minimumDate() else to_date_q.toString("yyyy-MM-dd")

        invoices = self._fetch_invoices_for_export(ob_id, pjp_id, customer_id, from_date, to_date)
        if not invoices:
            QMessageBox.information(self, "No Invoices", "No unpaid/partially-paid invoices found for the selected filters.")
            return

        # If one invoice -> PDF
        if len(invoices) == 1:
            inv = invoices[0]
            default_name = f"{inv['invoice_code']}_{inv['customer_name']}.pdf".replace("/", "-")
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Invoice (PDF)", default_name, "PDF Files (*.pdf)")
            if not file_path:
                return
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"

            self._render_invoice_pdf(inv, file_path)
            try:
                self._validate_pdf_or_raise(file_path)
            except Exception as e:
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                QMessageBox.warning(self, "PDF generation failed", f"Saved file is not a valid PDF.\n\n{e}")
                return

            QMessageBox.information(self, "Saved", f"Invoice saved:\n{file_path}")
            # # Optional: auto-open
            # try:
            #     QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            # except Exception:
            #     pass
            return

        # Multiple invoices -> ZIP
        default_zip = f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path, _ = QFileDialog.getSaveFileName(self, "Save Invoices (ZIP)", default_zip, "ZIP Files (*.zip)")
        if not zip_path:
            return
        if not zip_path.lower().endswith(".zip"):
            zip_path += ".zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_paths = []
            for inv in invoices:
                safe_customer = (inv["customer_name"] or "Customer").replace("/", "-").replace("\\", "-")
                pdf_name = f"{inv['invoice_code']}_{safe_customer}.pdf"
                pdf_file = os.path.join(tmpdir, pdf_name)
                self._render_invoice_pdf(inv, pdf_file)
                pdf_paths.append((pdf_file, pdf_name))

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for full_path, arc_name in pdf_paths:
                    zf.write(full_path, arcname=arc_name)

        QMessageBox.information(self, "Saved", f"{len(invoices)} invoices exported:\n{zip_path}")
        # Optional: auto-open
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(zip_path))
        except Exception:
            pass


    def _fetch_invoices_for_export(self, ob_id, pjp_id, customer_id, from_date, to_date):
        
        query = """
            SELECT
                i.id AS invoice_id,
                i.invoice_code,
                i.invoice_date,
                i.amount,

                ob.name AS ob_name,
                ob.contact AS ob_contact,
                ob.address AS ob_address,

                pj.pjp_name AS pjp_name,

                c.name AS customer_name,
                c.contact AS customer_contact,
                c.address AS customer_address
            FROM invoices i
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            LEFT JOIN customers c ON c.id = i.customer_id
            WHERE i.in_ledger = 1
        """

        params = []

        if customer_id:
            query += " AND i.customer_id = ?"
            params.append(customer_id)
        elif pjp_id:
            query += " AND i.pjp_id = ?"
            params.append(pjp_id)
        elif ob_id:
            query += " AND ob.id = ?"
            params.append(ob_id)


        if from_date:
            query += " AND i.invoice_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND i.invoice_date <= ?"
            params.append(to_date)

        query += " ORDER BY i.invoice_date ASC, i.invoice_code ASC"

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        invoices = []
        for r in rows:
            paid = self._sum_paid_for_invoice(r["invoice_id"], from_date, to_date)
            total = float(r["amount"] or 0)

            # tolerance for rounding
            eps = 0.01

            balance = total - paid

            # ✅ SKIP fully paid invoices
            if balance <= eps:
                continue

            # Don't allow negative
            if balance < 0:
                balance = 0.0

            invoices.append({
                "invoice_id": r["invoice_id"],
                "invoice_code": r["invoice_code"],
                "invoice_date": r["invoice_date"],
                "amount": total,
                "paid_amount": paid,
                "balance_amount": balance,

                "ob_name": r["ob_name"] or "-",
                "ob_contact": r["ob_contact"] or "-",
                "ob_address": r["ob_address"] or "-",

                "pjp_name": r["pjp_name"] or "-",

                "customer_name": r["customer_name"] or "-",
                "customer_contact": r["customer_contact"] or "-",
                "customer_address": r["customer_address"] or "-",
            })


        return invoices




    def _fetch_pending_invoices(self, ob_id, pjp_id, customer_id, from_date, to_date):
        """
        Returns dict grouped by (ob_name, pjp_name):
        {
            (ob_name, pjp_name): [
                {
                "invoice_id": ..,
                "invoice_code": ..,
                "invoice_date": ..,
                "customer": ..,
                "amount": ..,
                "received": ..,
                "pending": ..
                }, ...
            ]
        }
        Only includes invoices where pending > 0 (after considering payments in range).
        """
        query = """
            SELECT
                i.id AS invoice_id,
                i.invoice_code,
                i.invoice_date,
                i.amount,

                c.name AS customer_name,
                pj.pjp_name AS pjp_name,
                ob.name AS ob_name
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE i.in_ledger = 1
        """
        params = []

        # Keep SAME filter priority as your other export methods (customer > pjp > ob)
        if customer_id:
            query += " AND i.customer_id = ?"
            params.append(customer_id)
        elif pjp_id:
            query += " AND i.pjp_id = ?"
            params.append(pjp_id)
        elif ob_id:
            query += " AND pj.order_booker_id = ?"
            params.append(ob_id)

        # Invoice date filter (matches your invoice-side filtering style)
        if from_date:
            query += " AND i.invoice_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND i.invoice_date <= ?"
            params.append(to_date)

        query += " ORDER BY ob.name ASC, pj.pjp_name ASC, i.invoice_date ASC, i.invoice_code ASC"

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        pending_map = {}
        eps = 0.01  # tolerance for rounding

        for r in rows:
            amount = float(r["amount"] or 0.0)

            # Received is sum of payments for this invoice, respecting payment_date filter
            received = float(self._sum_paid_for_invoice(r["invoice_id"], from_date, to_date) or 0.0)

            pending = amount - received
            if pending <= eps:
                continue
            if pending < 0:
                pending = 0.0

            ob_name = r["ob_name"] or "-"
            pjp_name = r["pjp_name"] or "-"
            key = (ob_name, pjp_name)

            pending_map.setdefault(key, []).append({
                "invoice_id": r["invoice_id"],
                "invoice_code": r["invoice_code"],
                "invoice_date": r["invoice_date"],
                "customer": r["customer_name"] or "-",
                "amount": amount,
                "received": received,
                "pending": pending,
            })

        return pending_map



    def _sum_paid_for_invoice(self, invoice_id: int, from_date=None, to_date=None) -> float:
        cur = self.conn.cursor()

        query = """
            SELECT COALESCE(SUM(amount), 0) AS paid
            FROM payments
            WHERE invoice_id = ?
            AND in_ledger = 1
        """
        params = [invoice_id]

        if from_date:
            query += " AND payment_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND payment_date <= ?"
            params.append(to_date)

        cur.execute(query, params)
        row = cur.fetchone()
        return float(row["paid"] if row else 0)


    def _render_invoice_pdf(self, inv: dict, file_path: str):
        """
        Creates a summary-style invoice PDF (since no items table exists).
        Layout inspired by your sample: header + meta blocks + table + totals.
        """
        c = canvas.Canvas(file_path, pagesize=A4)
        W, H = A4

        left = 18 * mm
        right = W - 18 * mm
        y = H - 20 * mm

        # Header
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(W / 2, y, self._get_report_title())
        y -= 6 * mm

        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawCentredString(W / 2, y, "Invoice")
        c.setFillColor(colors.black)
        y -= 10 * mm

        # Left block (Customer)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, y, "Customer")
        c.setFont("Helvetica", 9)
        y -= 5 * mm
        c.drawString(left, y, f"Name: {inv['customer_name']}")
        y -= 5 * mm
        c.drawString(left, y, f"Contact: {inv['customer_contact']}")
        y -= 5 * mm
        c.drawString(left, y, f"Address: {inv['customer_address']}")
        y -= 8 * mm

        # Right block (Invoice meta)
        meta_x = W / 2 + 20 * mm
        meta_y = H - 36 * mm
        c.setFont("Helvetica", 9)
        c.drawString(meta_x, meta_y, f"Invoice ID: {inv['invoice_code']}")
        c.drawString(meta_x, meta_y - 5 * mm, f"Invoice Date: {inv['invoice_date']}")
        c.drawString(meta_x, meta_y - 10 * mm, f"Order Booker: {inv['ob_name']}")
        c.drawString(meta_x, meta_y - 15 * mm, f"PJP: {inv['pjp_name']}")

        # Table (since no items table, we show a summary row)
        table_y = y - 5 * mm
        data = [
            ["Sr#", "Description", "Amount"],
            ["1", "Invoice Amount", f"{inv['amount']:,.0f}"],
            ["", "Paid", f"{inv['paid_amount']:,.0f}"],
            ["", "Balance", f"{inv['balance_amount']:,.0f}"],
        ]

        tbl = Table(data, colWidths=[15 * mm, 110 * mm, 40 * mm])
        tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )

        tw, th = tbl.wrapOn(c, right - left, H)
        tbl.drawOn(c, left, table_y - th)

        # Footer signature lines
        y2 = table_y - th - 18 * mm
        c.setFont("Helvetica", 9)
        c.drawString(left, y2, "Signature: _______________________")
        c.drawString(W / 2 + 10 * mm, y2, "Received By: _______________________")

        c.showPage()
        c.save()



    def _render_pending_report_pdf(self, ob_name, pjp_name, invoices, file_path):
        """Generate the 'Pending Report' PDF.

        Columns:
          - Amount: remaining/pending (invoice amount - payments)
          - Received/Pending columns intentionally left blank
        """
        c = canvas.Canvas(file_path, pagesize=A4)
        W, H = A4

        try:
            left_margin = 15 * mm
            right_margin = 15 * mm
            top_margin = 25 * mm
            bottom_margin = 15 * mm
            usable_width = W - left_margin - right_margin

            # Column widths
            col_weights = [0.7, 1.0, 1.1, 3.8, 1.2, 1.0, 1.0]
            total_w = sum(col_weights)
            col_widths = [usable_width * w / total_w for w in col_weights]

            table_style = TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (3, -1), "LEFT"),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])

            header_row = ["Sr No.", "Invoice #", "Invoice Date", "Name", "Amount", "Received", "Pending"]

            # Build body rows (Amount shows remaining/pending; Received/Pending left empty)
            body_rows = []
            for idx, inv in enumerate(invoices, start=1):
                if isinstance(inv, sqlite3.Row):
                    inv = dict(inv)

                raw_date = str(inv.get("invoice_date", "") or "")
                inv_date_fmt = raw_date
                try:
                    inv_date_fmt = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%y")
                except Exception:
                    pass  # keep raw_date

                body_rows.append([
                    str(idx),
                    str(inv.get("invoice_code", "")),
                    inv_date_fmt,
                    str(inv.get("customer", "")),
                    f"{_to_number(inv.get('pending')):,.0f}",
                    "",
                    "",
                ])

            total_pending = sum(float((inv.get("pending") if isinstance(inv, dict) else dict(inv).get("pending")) or 0) for inv in invoices)
            total_pending_str = f"{total_pending:,.0f}"

            def draw_header():
                c.setFont("Times-Bold", 24)
                c.drawCentredString(W / 2, H - top_margin, self._get_report_title())

                label_font = "Times-Bold"
                label_size = 9
                value_font = "Times-Roman"
                value_size = 9

                col_width = usable_width / 3.0
                x1 = left_margin
                x2 = left_margin + col_width
                x3 = left_margin + 2 * col_width
                y = H - top_margin - 40

                # Row 1
                c.setFont(label_font, label_size)
                c.drawString(x1, y, "Order Booker:")
                c.setFont(value_font, value_size)
                c.drawString(x1 + 70, y, str(ob_name))

                c.setFont(label_font, label_size)
                c.drawString(x2, y, "Date:")
                c.setFont(value_font, value_size)
                c.drawString(x2 + 30, y, datetime.now().strftime("%d/%m/%y"))

                c.setFont(label_font, label_size)
                c.drawString(x3, y, "PJP Name:")
                c.setFont(value_font, value_size)
                c.drawString(x3 + 55, y, str(pjp_name))

                # Row 2
                y2 = y - 14
                c.setFont(label_font, label_size)
                c.drawString(x1, y2, "Total Pending Amount:")
                c.setFont(value_font, value_size)
                c.drawString(x1 + 110, y2, total_pending_str)

                c.setFont(label_font, label_size)
                c.drawString(x2, y2, "Day Assign:")
                c.setFont(value_font, value_size)
                c.drawString(x2 + 55, y2, "_____________________")

                c.setFont(label_font, label_size)
                c.drawString(x3, y2, "Received:")
                c.setFont(value_font, value_size)
                c.drawString(x3 + 50, y2, "_____________________")

                return y2 - 26  # start Y for table

            remaining = body_rows[:]
            while remaining:
                table_top_y = draw_header()

                available_h = table_top_y - bottom_margin
                approx_row_h = 18
                max_rows = max(1, int(available_h // approx_row_h) - 1)
                page_rows = remaining[:max_rows]

                data = [header_row] + page_rows
                table = Table(data, colWidths=col_widths)
                table.setStyle(table_style)
                _, th = table.wrapOn(c, usable_width, H)
                table.drawOn(c, left_margin, table_top_y - th)

                remaining = remaining[len(page_rows):]
                if remaining:
                    c.showPage()
        finally:
            # Always finalise the PDF so Windows doesn't see it as "corrupted"
            c.save()
    def _download_pending_reports(self):
        ob_id = self.combo_ob.currentData(Qt.UserRole)
        pjp_id = self.combo_pjp.currentData(Qt.UserRole)
        customer_id = self.combo_customer.currentData(Qt.UserRole)

        from_date_q = self.date_from.date()
        from_date = None if from_date_q == self.date_from.minimumDate() else from_date_q.toString("yyyy-MM-dd")

        to_date_q = self.date_to.date()
        to_date = None if to_date_q == self.date_to.minimumDate() else to_date_q.toString("yyyy-MM-dd")

        pending = self._fetch_pending_invoices(ob_id, pjp_id, customer_id, from_date, to_date)

        if not pending:
            QMessageBox.information(
                self, "No Pending", "No partially-paid invoices found."
            )
            return

        # ---------- Case 3: OB and PJP both selected -> single PDF ----------
        # If user selected a single OB+PJP OR the data only contains one OB+PJP pair,
        # export a single PDF (no ZIP).
        if (ob_id and pjp_id) or (len(pending) == 1):
            (ob_name, pjp_name), invoices = next(iter(pending.items()))
            default_name = f"{ob_name}__{pjp_name}.pdf".replace("/", "-").replace("\\", "-")

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Pending Report", default_name, "PDF Files (*.pdf)"
            )
            if not file_path:
                return
            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"

            self._render_pending_report_pdf(ob_name, pjp_name, invoices, file_path)
            QMessageBox.information(self, "Done", f"Pending report saved:\n{file_path}")
            return


        # ---------- Cases 1 & 2: need a ZIP ----------
        # No OB → "All Order Bookers" structure
        # OB selected (no PJP) → PDFs at root of zip

        default_zip = "pending_reports.zip"
        zip_name, _ = QFileDialog.getSaveFileName(
            self, "Save Pending Reports (ZIP)", default_zip, "Zip Files (*.zip)"
        )
        if not zip_name:
            return
        if not zip_name.lower().endswith(".zip"):
            zip_name += ".zip"

        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
                for (ob_name, pjp_name), invoices in pending.items():
                    safe_ob = ob_name.replace("/", "-").replace("\\", "-")
                    safe_pjp = pjp_name.replace("/", "-").replace("\\", "-")
                    pdf_name = f"{safe_ob}__{safe_pjp}.pdf"

                    # temp file path
                    pdf_path = os.path.join(tmp, pdf_name)
                    self._render_pending_report_pdf(ob_name, pjp_name, invoices, pdf_path)

                    if ob_id is None:
                        # Case 1: All OBs -> <OB>/<OB__PJP>.pdf   (NO "All Order Bookers" folder)
                        arcname = os.path.join(safe_ob, pdf_name)
                    else:
                        # Case 2: single OB -> just <OB__PJP>.pdf at root
                        arcname = pdf_name

                    z.write(pdf_path, arcname)

        QMessageBox.information(
            self, "Done", f"Pending reports exported successfully:\n{zip_name}"
        )


    def _send_pdf_to_default_printer(self, pdf_path: str):
        """Send a PDF to the default printer via the OS print pipeline."""
        try:
            abs_path = os.path.abspath(pdf_path)

            # Windows: prints using default PDF app to the default printer
            if sys.platform.startswith("win"):
                os.startfile(abs_path, "print")

            # macOS/Linux: uses CUPS default printer
            elif sys.platform == "darwin":
                subprocess.run(["lp", abs_path], check=True)
            else:
                subprocess.run(["lp", abs_path], check=True)

        except Exception as e:
            QMessageBox.warning(self, "Print failed", f"Could not print:\n{pdf_path}\n\n{e}")



    def _build_pending_report_html(self, pending, ob_label="All", pjp_label="All",
                                customer_label="All", from_date=None, to_date=None) -> str:
        def esc(x):
            return html.escape("" if x is None else str(x))

        def money(v):
            try:
                return f"PKR {float(v):,.0f}"
            except Exception:
                return "PKR 0"

        generated_at = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        report_title = getattr(self.parent(), "report_title",
               getattr(self.parent(), "report_name", "AK ENTERPRISES"))


        # totals
        total_amount = total_received = total_pending = 0.0
        for _, items in pending.items():
            for it in items:
                total_amount += float(it.get("amount") or 0)
                total_received += float(it.get("received") or 0)
                total_pending += float(it.get("pending") or 0)

        if from_date and to_date:
            date_range = f"{from_date} → {to_date}"
        elif from_date:
            date_range = f"From {from_date}"
        elif to_date:
            date_range = f"Up to {to_date}"
        else:
            date_range = "All dates"

        out = f"""
        <html><head><meta charset="utf-8">
        <style>
        body {{ font-family: Arial, sans-serif; font-size: 11pt; }}
        h1 {{ font-size: 16pt; margin: 0 0 8px 0; }}
        .meta {{ font-size: 10pt; color: #444; margin: 0 0 12px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 6px 8px; }}
        th {{ background: #f2f2f2; text-align: left; }}
        .right {{ text-align: right; }}
        .group {{ margin-top: 14px; font-weight: bold; }}
        </style></head><body>
        <h1>{esc(report_title)}</h1>
        <div class="small" style="margin-bottom:8px;"><b>Pending Report</b></div>

        <div class="meta">
            Generated: {esc(generated_at)}<br/>
            Order Booker: {esc(ob_label)} | PJP: {esc(pjp_label)} | Customer: {esc(customer_label)}<br/>
            Date range: {esc(date_range)}<br/><br/>
            <b>Total Invoiced:</b> {esc(money(total_amount))} &nbsp;&nbsp;
            <b>Received:</b> {esc(money(total_received))} &nbsp;&nbsp;
            <b>Pending:</b> {esc(money(total_pending))}
        </div>
        """

        for (ob_name, pjp_name), items in pending.items():
            group_pending = sum(float(it.get("pending") or 0) for it in items)
            out += f"""
            <div class="group">{esc(ob_name)} — {esc(pjp_name)} (Pending: {esc(money(group_pending))})</div>
            <table>
            <thead>
                <tr>
                <th style="width:14%;">Invoice</th>
                <th style="width:12%;">Date</th>
                <th>Customer</th>
                <th class="right" style="width:14%;">Total</th>
                <th class="right" style="width:14%;">Received</th>
                <th class="right" style="width:14%;">Pending</th>
                </tr>
            </thead>
            <tbody>
            """
            for it in items:
                out += f"""
                <tr>
                <td>{esc(it.get("invoice_code",""))}</td>
                <td>{esc(it.get("invoice_date",""))}</td>
                <td>{esc(it.get("customer",""))}</td>
                <td class="right">{esc(money(it.get("amount",0)))}</td>
                <td class="right">{esc(money(it.get("received",0)))}</td>
                <td class="right">{esc(money(it.get("pending",0)))}</td>
                </tr>
                """
            out += "</tbody></table>"

        out += "</body></html>"
        return out



    def _print_pending_reports(self):
        printer_name = self._get_physical_printer_name()
        if not printer_name:
            QMessageBox.information(self, "No printer", "No physical printer is installed/configured on this PC.")
            return

        ob_id = self.combo_ob.currentData(Qt.UserRole)
        pjp_id = self.combo_pjp.currentData(Qt.UserRole)
        customer_id = self.combo_customer.currentData(Qt.UserRole)

        from_date_q = self.date_from.date()
        from_date = None if from_date_q == self.date_from.minimumDate() else from_date_q.toString("yyyy-MM-dd")

        to_date_q = self.date_to.date()
        to_date = None if to_date_q == self.date_to.minimumDate() else to_date_q.toString("yyyy-MM-dd")

        pending = self._fetch_pending_invoices(ob_id, pjp_id, customer_id, from_date, to_date)
        if not pending:
            QMessageBox.information(self, "No Pending", "No partially-paid invoices found.")
            return

        printed_paths = []
        failed = []

        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for (ob_name, pjp_name), invoices in pending.items():
            safe_ob = str(ob_name).replace("/", "-").replace("\\", "-")
            safe_pjp = str(pjp_name).replace("/", "-").replace("\\", "-")

            tmp_pdf = tempfile.NamedTemporaryFile(
                prefix=f"pending_{safe_ob}__{safe_pjp}_{run_stamp}_",
                suffix=".pdf",
                delete=False
            )
            pdf_path = tmp_pdf.name
            tmp_pdf.close()

            self._render_pending_report_pdf(ob_name, pjp_name, invoices, pdf_path)

            # Validate PDF header
            try:
                with open(pdf_path, "rb") as f:
                    if f.read(5) != b"%PDF-":
                        failed.append((ob_name, pjp_name, pdf_path, "Not a valid PDF"))
                        continue
            except Exception as e:
                failed.append((ob_name, pjp_name, pdf_path, str(e)))
                continue

            ok = self._silent_print_pdf(pdf_path, printer_name=printer_name)
            if ok:
                printed_paths.append(pdf_path)
            else:
                failed.append((ob_name, pjp_name, pdf_path, "Print command failed"))

        # Final user message based on outcomes
        if printed_paths and not failed:
            QMessageBox.information(self, "Print", "Report sent to printer.")
        elif printed_paths and failed:
            msg = "Some reports were sent to the printer, but some failed:\n\n"
            msg += "\n".join([f"- {ob} / {pjp}" for (ob, pjp, _, __) in failed[:10]])
            if len(failed) > 10:
                msg += f"\n...and {len(failed) - 10} more."
            QMessageBox.warning(self, "Partial print", msg)
        else:
            msg = "Printing failed for all reports.\n\n"
            msg += "\n".join([f"- {ob} / {pjp}" for (ob, pjp, _, __) in failed[:10]])
            QMessageBox.warning(self, "Print failed", msg)

        # Cleanup (optional): only delete successfully printed PDFs after 2 minutes
        try:
            from PySide6.QtCore import QTimer
            def _cleanup(paths):
                for p in paths:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
            if printed_paths:
                QTimer.singleShot(120_000, lambda: _cleanup(printed_paths))
        except Exception:
            pass


    # ---------------- UI BUILDING ----------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setObjectName("LedgerHeader")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        h_layout.setSpacing(8)

        title = QLabel("Ledger")
        title.setObjectName("LedgerTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # Filters block
        filters_frame = QFrame()
        filters_frame.setObjectName("FiltersFrame")
        filters_frame.setFixedHeight(120)
        f_layout = QVBoxLayout(filters_frame)
        f_layout.setContentsMargins(24, 16, 24, 16)
        f_layout.setSpacing(12)

        filters_title = QLabel("Filters")
        filters_title.setObjectName("FiltersTitle")
        f_layout.addWidget(filters_title)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(12)

        # Order Booker / PJP / Customer
        self.combo_ob = SearchablePopupComboBox("Order Booker", self)
        self.combo_ob.setPlaceholderText("Select Order Booker")
        self.combo_ob.currentIndexChanged.connect(self._on_ob_changed)
        filters_row.addWidget(self.combo_ob)

        self.combo_pjp = SearchablePopupComboBox("PJP", self)
        self.combo_pjp.setPlaceholderText("Select PJP")
        self.combo_pjp.currentIndexChanged.connect(self._on_pjp_changed)
        filters_row.addWidget(self.combo_pjp)

        self.combo_customer = SearchablePopupComboBox("Customer", self)
        self.combo_customer.setPlaceholderText("Select Customer")
        self.combo_customer.currentIndexChanged.connect(self._refresh_ledger)
        filters_row.addWidget(self.combo_customer)

        # From Date
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setSpecialValueText("From")
        self.date_from.setDate(self.date_from.minimumDate())
        self.date_from.setMinimumDate(QDate(1900, 1, 1))
        self.date_from.dateChanged.connect(self._refresh_ledger)
        filters_row.addWidget(self.date_from)

        # To Date
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setSpecialValueText("To")
        self.date_to.setDate(self.date_to.minimumDate())
        self.date_to.setMinimumDate(QDate(1900, 1, 1))
        self.date_to.dateChanged.connect(self._refresh_ledger)
        filters_row.addWidget(self.date_to)

        # Apply / Reset
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_apply = QPushButton("Apply Filters")
        self.btn_apply.setObjectName("ApplyFilterBtn")
        self.btn_apply.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_apply.clicked.connect(self._refresh_ledger)
        btn_layout.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("ResetFilterBtn")
        self.btn_reset.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_reset.clicked.connect(self._reset_filters)
        btn_layout.addWidget(self.btn_reset)

        filters_row.addLayout(btn_layout)

        f_layout.addLayout(filters_row)
        main_layout.addWidget(filters_frame)

        # Summary cards
        self._build_summary_cards()
        main_layout.addWidget(self.summary_frame)

        # Table outer frame
        table_outer = QFrame()
        table_outer.setObjectName("TableOuterFrame")
        table_outer_layout = QVBoxLayout(table_outer)
        table_outer_layout.setContentsMargins(24, 16, 24, 16)
        table_outer_layout.setSpacing(12)

        # Table title + right actions
        table_header_row = QHBoxLayout()
        table_header_row.setSpacing(12)

        table_title = QLabel("Transactions")
        table_title.setObjectName("LedgerSectionTitle")
        table_header_row.addWidget(table_title)

        # Right-side actions
        self.btn_download_invoice = QPushButton("Download Invoice")
        self.btn_download_invoice.setObjectName("DownloadInvoiceBtn")
        self.btn_download_invoice.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_download_invoice.clicked.connect(self._download_invoices)

        self.btn_download_report = QPushButton("Download Report")
        self.btn_download_report.setObjectName("DownloadReportBtn")
        self.btn_download_report.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_download_report.clicked.connect(self._download_pending_reports)

        self.btn_print_report = QPushButton("Print Report")
        self.btn_print_report.setObjectName("PrintReportBtn")
        self.btn_print_report.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_print_report.clicked.connect(self._print_pending_reports)


        table_header_row.addStretch()

        self.edit_ref_search = QLineEdit()
        self.edit_ref_search.setObjectName("LedgerRefSearch")
        self.edit_ref_search.setPlaceholderText("Search Invoice/Payment ID")
        self.edit_ref_search.setClearButtonEnabled(True)
        self.edit_ref_search.setFixedWidth(260)
        self.edit_ref_search.returnPressed.connect(self._refresh_ledger)
        self.edit_ref_search.textChanged.connect(self._on_ref_search_changed)

        search_action = QAction("🔍", self.edit_ref_search)
        self.edit_ref_search.addAction(search_action, QLineEdit.LeadingPosition)

        table_header_row.addWidget(self.edit_ref_search)
        table_header_row.addWidget(self.btn_download_invoice)
        table_header_row.addWidget(self.btn_download_report)
        table_header_row.addWidget(self.btn_print_report)


        table_outer_layout.addLayout(table_header_row)

        # Scroll area for table
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("LedgerScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container.setObjectName("LedgerContainer")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)

        self._build_table_header()
        # Empty state label (must exist before _clear_rows/_refresh_ledger runs)
        self.empty_label = QLabel("No transactions found.")
        self.empty_label.setObjectName("EmptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        self.container_layout.addWidget(self.empty_label)

        scroll.setWidget(container)

        self.ledger_scroll = scroll
        self.ledger_scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        table_outer_layout.addWidget(scroll)

        main_layout.addWidget(table_outer)

    def _build_summary_cards(self):
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("SummaryFrame")
        self.summary_frame.setFixedHeight(120)
        s_layout = QHBoxLayout(self.summary_frame)
        s_layout.setContentsMargins(24, 16, 24, 16)
        s_layout.setSpacing(12)

        self.card_invoiced = self._make_summary_card("Total Invoiced", 0, "invoiced")
        s_layout.addWidget(self.card_invoiced)

        self.card_paid = self._make_summary_card("Received Payments", 0, "paid")
        s_layout.addWidget(self.card_paid)

        self.card_balance = self._make_summary_card("In the market", 0, "balance")
        s_layout.addWidget(self.card_balance)

    def _make_summary_card(self, title: str, value: float, card_type: str) -> QFrame:
        if card_type == "invoiced":
            obj_name = "SummaryCardInvoiced"
            title_obj = "CardInvoicedTitle"
            value_obj = "CardInvoicedValue"
        elif card_type == "paid":
            obj_name = "SummaryCardPaid"
            title_obj = "CardPaidTitle"
            value_obj = "CardPaidValue"
        else:
            obj_name = "SummaryCardBalance"
            title_obj = "CardBalanceTitle"
            value_obj = "CardBalanceValue"

        card = QFrame()
        card.setObjectName(obj_name)
        card.setFixedWidth(320)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 12, 16, 12)
        c_layout.setSpacing(4)

        card_title = QLabel(title)
        card_title.setObjectName(title_obj)
        c_layout.addWidget(card_title)

        card_value = QLabel()
        card_value.setObjectName(value_obj)
        card_value.setWordWrap(True)
        c_layout.addWidget(card_value)

        return card

    def _build_table_header(self):
        header_row = QFrame()
        header_row.setObjectName("LedgerTableHeader")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(16)

        def add_header_label(text: str, width: int, align_right=False):
            lbl = QLabel(text)
            lbl.setObjectName("LedgerHeaderLabel")
            if align_right:
                lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            lbl.setFixedWidth(width)
            header_layout.addWidget(lbl)

        add_header_label("Date", 90)
        add_header_label("Time", 70)
        add_header_label("Type", 80)
        add_header_label("Ref ID", 140)
        add_header_label("Order Booker", 140)
        add_header_label("PJP", 140)
        add_header_label("Customer", 140)
        add_header_label("Debit", 80, align_right=True)
        add_header_label("Credit", 80, align_right=True)
        add_header_label("Balance", 90, align_right=True)

        self.container_layout.addWidget(header_row)

    # ---------------- FILTER LOAD ----------------

    def _load_filter_data(self):
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
            QMessageBox.critical(self, "Error", f"Failed to load order bookers:\n{e}")
            return

        self.combo_ob.blockSignals(True)
        self.combo_ob.clear()
        self.combo_ob.addItem("All Order Bookers", None)

        for row in rows:
            self.combo_ob.addItem(row["name"], row["id"])

        if self.combo_ob.count() > 0:
            self.combo_ob.setCurrentIndex(0)

        self.combo_ob.blockSignals(False)

        self._load_pjps(None)


    def _on_ob_changed(self, index: int):
        ob_id = self.combo_ob.itemData(index, Qt.UserRole)
        self._load_pjps(ob_id)
        self._refresh_ledger()

    def _load_pjps(self, ob_id: int | None):
        self.combo_pjp.blockSignals(True)
        self.combo_pjp.clear()
        self.combo_pjp.addItem("All PJPs", None)

        query = """
            SELECT id, pjp_name
            FROM pjps
            WHERE is_active = 1
        """
        params = []

        if ob_id is not None:
            query += " AND order_booker_id = ?"
            params.append(ob_id)

        query += " ORDER BY pjp_name ASC"

        try:
            cur = self.conn.cursor()
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load PJPs:\n{e}")
            self.combo_pjp.blockSignals(False)
            return

        for row in rows:
            self.combo_pjp.addItem(row["pjp_name"], row["id"])

        self.combo_pjp.setCurrentIndex(0)
        self.combo_pjp.blockSignals(False)

        self._load_customers(None)

    def _normalize_ref_search(self, raw: str) -> str:
        s = (raw or "").strip().upper()
        if s.startswith("INV"):
            s = s[3:]
        elif s.startswith("PAY"):
            s = s[3:]
        s = "".join(ch for ch in s if ch.isdigit())
        return s

    def _on_ref_search_changed(self, text: str):
        text = (text or "").strip()
        if not text:
            self._refresh_ledger()

    def _on_pjp_changed(self, index: int):
        pjp_id = self.combo_pjp.itemData(index, Qt.UserRole)
        self._load_customers(pjp_id)
        self._refresh_ledger()

    def _load_customers(self, pjp_id: int | None):
        # Do NOT load all customers into the combo on dialog open (can be thousands).
        # We instead use DB-backed search in the popup (see combo_customer.set_remote_fetcher).
        self._customer_pjp_filter = pjp_id

        self.combo_customer.blockSignals(True)
        self.combo_customer.clear()
        self.combo_customer.addItem("All Customers", None)
        self.combo_customer.setCurrentIndex(0)
        self.combo_customer.blockSignals(False)

    def _reset_filters(self):
        # Reset dates back to "no date" (lifetime)
        self.date_from.blockSignals(True)
        self.date_to.blockSignals(True)
        self.date_from.setDate(self.date_from.minimumDate())
        self.date_to.setDate(self.date_to.minimumDate())
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(False)

        # Reset Order Booker to "All" (even if it was already All)
        self.combo_ob.blockSignals(True)

        if self.combo_ob.count() > 0:
            self.combo_ob.setCurrentIndex(0)
        self.combo_ob.blockSignals(False)

        # Force reload dependent dropdowns (PJP + Customer) back to full lists
        self._load_pjps(None)  # also reloads customers

        if hasattr(self, "edit_ref_search"):
            self.edit_ref_search.clear()

        # Refresh the ledger
        self._refresh_ledger()

    def _download_invoice_placeholder(self):
        QMessageBox.information(
            self,
            "Coming Soon",
            "Download Invoice will be added next. For now, use Download Report.",
        )


    # ---------------- LEDGER LOAD ----------------


    def _refresh_ledger(self):
        """Refresh the ledger view with keyset-pagination lazy loading.

        This keeps the QWidget-based row UI but avoids creating thousands of widgets at once.
        """
        # Clear existing rows (keep header row)
        self._clear_rows()

        # Reset paging state
        self._reset_pagination()

        # Recompute summary totals for the *full filtered set*
        invoiced, paid, outstanding = self._compute_summary_totals()
        self._update_summary_cards(invoiced or 0, paid or 0, outstanding or 0)


        # Load first page
        self._load_next_page(reset_scroll=True)


    def _current_filters(self):
        ob_id = self.combo_ob.currentData()
        pjp_id = self.combo_pjp.currentData()
        customer_id = self.combo_customer.currentData()

        from_q = self.date_from.date()
        from_date = None if from_q == self.date_from.minimumDate() else from_q.toString("yyyy-MM-dd")
        to_q = self.date_to.date()
        to_date = None if to_q == self.date_to.minimumDate() else to_q.toString("yyyy-MM-dd")

        ref_search = None
        if hasattr(self, "edit_ref_search"):
            ref_search = self._normalize_ref_search(self.edit_ref_search.text())

        return ob_id, pjp_id, customer_id, from_date, to_date, ref_search

    def _reset_pagination(self):
        self._cursor_key = None
        self._has_more = True
        self._is_loading = False
        self._running_balance = 0.0

    def _clear_rows(self):
        # Keep:
        #   index 0 = table header
        #   index 1 = empty_label
        while self.container_layout.count() > 2:
            item = self.container_layout.takeAt(2)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.rows = []

        if hasattr(self, "empty_label") and self.empty_label is not None:
            self.empty_label.setVisible(False)


    def _compute_summary_totals(self) -> tuple[float, float, float]:
        """
        Returns:
        - invoiced_in_period  : invoices whose invoice_date is within From..To
        - paid_in_period      : payments whose payment_date is within From..To
        - outstanding_as_of_to: all invoices <= To minus all payments <= To
        """
        ob_id, pjp_id, customer_id, from_date, to_date, ref_search = self._current_filters()
        cur = self.conn.cursor()

        # -----------------------------
        # 1) Invoiced in selected period
        # -----------------------------
        inv_q = "SELECT COALESCE(SUM(i.amount), 0) FROM invoices i WHERE i.in_ledger = 1"
        inv_p = []
        

        if customer_id:
            inv_q += " AND i.customer_id = ?"
            inv_p.append(customer_id)
        elif pjp_id:
            inv_q += " AND i.pjp_id = ?"
            inv_p.append(pjp_id)
        elif ob_id:
            inv_q += " AND i.pjp_id IN (SELECT id FROM pjps WHERE order_booker_id = ?)"
            inv_p.append(ob_id)

        if ref_search:
            inv_q += " AND CAST(i.invoice_code AS TEXT) = ?"
            inv_p.append(ref_search)

        if from_date:
            inv_q += " AND i.invoice_date >= ?"
            inv_p.append(from_date)
        if to_date:
            inv_q += " AND i.invoice_date <= ?"
            inv_p.append(to_date)

        # -----------------------------
        # 2) Payments in selected period
        # -----------------------------
        pay_q = """
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            WHERE p.in_ledger = 1 AND i.in_ledger = 1
        """
        pay_p = []

        if customer_id:
            pay_q += " AND i.customer_id = ?"
            pay_p.append(customer_id)
        elif pjp_id:
            pay_q += " AND i.pjp_id = ?"
            pay_p.append(pjp_id)
        elif ob_id:
            pay_q += " AND pj.order_booker_id = ?"
            pay_p.append(ob_id)

        if ref_search:
            pay_q += " AND CAST(p.payment_code AS TEXT) = ?"
            pay_p.append(ref_search)
            
        if from_date:
            pay_q += " AND p.payment_date >= ?"
            pay_p.append(from_date)
        if to_date:
            pay_q += " AND p.payment_date <= ?"
            pay_p.append(to_date)

        # -----------------------------
        # 3) Outstanding as of TO date
        #    = all invoices <= To - all payments <= To
        # -----------------------------
        close_inv_q = "SELECT COALESCE(SUM(i.amount), 0) FROM invoices i WHERE i.in_ledger = 1"
        close_inv_p = []

        if customer_id:
            close_inv_q += " AND i.customer_id = ?"
            close_inv_p.append(customer_id)
        elif pjp_id:
            close_inv_q += " AND i.pjp_id = ?"
            close_inv_p.append(pjp_id)
        elif ob_id:
            close_inv_q += " AND i.pjp_id IN (SELECT id FROM pjps WHERE order_booker_id = ?)"
            close_inv_p.append(ob_id)

        if ref_search:
            close_inv_q += " AND CAST(i.invoice_code AS TEXT) = ?"
            close_inv_p.append(ref_search)

        if to_date:
            close_inv_q += " AND i.invoice_date <= ?"
            close_inv_p.append(to_date)

        close_pay_q = """
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            WHERE p.in_ledger = 1 AND i.in_ledger = 1
        """
        close_pay_p = []

        if customer_id:
            close_pay_q += " AND i.customer_id = ?"
            close_pay_p.append(customer_id)
        elif pjp_id:
            close_pay_q += " AND i.pjp_id = ?"
            close_pay_p.append(pjp_id)
        elif ob_id:
            close_pay_q += " AND pj.order_booker_id = ?"
            close_pay_p.append(ob_id)

        if ref_search:
            close_pay_q += " AND CAST(p.payment_code AS TEXT) = ?"
            close_pay_p.append(ref_search)

        if to_date:
            close_pay_q += " AND p.payment_date <= ?"
            close_pay_p.append(to_date)

        try:
            cur.execute(inv_q, inv_p)
            invoiced = float((cur.fetchone() or [0])[0] or 0.0)
        except Exception:
            invoiced = 0.0

        try:
            cur.execute(pay_q, pay_p)
            paid = float((cur.fetchone() or [0])[0] or 0.0)
        except Exception:
            paid = 0.0

        try:
            cur.execute(close_inv_q, close_inv_p)
            closing_invoiced = float((cur.fetchone() or [0])[0] or 0.0)
        except Exception:
            closing_invoiced = 0.0

        try:
            cur.execute(close_pay_q, close_pay_p)
            closing_paid = float((cur.fetchone() or [0])[0] or 0.0)
        except Exception:
            closing_paid = 0.0

        outstanding = closing_invoiced - closing_paid
        return invoiced, paid, outstanding

    def _fetch_transactions_page(self, cursor_key):
        """Fetch a single page of transactions using keyset pagination."""
        ob_id, pjp_id, customer_id, from_date, to_date, ref_search = self._current_filters()

        inv_query = """
            SELECT
                'INVOICE' AS kind,
                1         AS kind_sort,
                i.id AS tx_id,
                i.invoice_code AS ref_code,
                i.invoice_date AS tx_date,
                i.created_at   AS tx_created_at,
                i.amount,
                c.name AS customer_name,
                pj.pjp_name AS pjp_name,
                ob.name AS ob_name
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE i.in_ledger = 1
        """
        inv_params = []

        if customer_id:
            inv_query += " AND i.customer_id = ?"
            inv_params.append(customer_id)
        elif pjp_id:
            inv_query += " AND i.pjp_id = ?"
            inv_params.append(pjp_id)
        elif ob_id:
            inv_query += " AND pj.order_booker_id = ?"
            inv_params.append(ob_id)

        if ref_search:
            inv_query += " AND CAST(i.invoice_code AS TEXT) = ?"
            inv_params.append(ref_search)

        if from_date:
            inv_query += " AND i.invoice_date >= ?"
            inv_params.append(from_date)
        if to_date:
            inv_query += " AND i.invoice_date <= ?"
            inv_params.append(to_date)

        pay_query = """
            SELECT
                'PAYMENT' AS kind,
                0         AS kind_sort,
                p.id AS tx_id,
                p.payment_code AS ref_code,
                p.payment_date AS tx_date,
                p.created_at   AS tx_created_at,
                p.amount,
                c.name AS customer_name,
                pj.pjp_name AS pjp_name,
                ob.name AS ob_name
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE p.in_ledger = 1 AND i.in_ledger = 1
        """
        pay_params = []

        if customer_id:
            pay_query += " AND i.customer_id = ?"
            pay_params.append(customer_id)
        elif pjp_id:
            pay_query += " AND i.pjp_id = ?"
            pay_params.append(pjp_id)
        elif ob_id:
            pay_query += " AND pj.order_booker_id = ?"
            pay_params.append(ob_id)

        if ref_search:
            pay_query += " AND (CAST(p.payment_code AS TEXT) = ? OR CAST(i.invoice_code AS TEXT) = ?)"
            pay_params.extend([ref_search, ref_search])

        if from_date:

            pay_query += " AND p.payment_date >= ?"
            pay_params.append(from_date)
        if to_date:
            pay_query += " AND p.payment_date <= ?"
            pay_params.append(to_date)

        outer = f"""
            SELECT * FROM (
                {inv_query}
                UNION ALL
                {pay_query}
            ) t
            WHERE 1=1
        """
        params = inv_params + pay_params

        if cursor_key:
            last_date, last_created, last_kind_sort, last_id = cursor_key
            outer += """
                AND (
                    t.tx_date > ?
                    OR (t.tx_date = ? AND t.tx_created_at > ?)
                    OR (t.tx_date = ? AND t.tx_created_at = ? AND t.kind_sort > ?)
                    OR (t.tx_date = ? AND t.tx_created_at = ? AND t.kind_sort = ? AND t.tx_id > ?)
                )
            """
            params.extend([
                last_date,
                last_date, last_created,
                last_date, last_created, last_kind_sort,
                last_date, last_created, last_kind_sort, last_id,
            ])

        outer += """
            ORDER BY
                t.tx_date ASC,
                t.tx_created_at ASC,
                t.kind_sort ASC,
                t.tx_id ASC
            LIMIT ?
        """
        params.append(int(self.page_size))

        cur = self.conn.cursor()
        cur.execute(outer, params)
        rows = cur.fetchall() or []

        txs = []
        for r in rows:
            txs.append(
                {
                    "kind": r["kind"],
                    "kind_sort": int(r["kind_sort"] or 0),
                    "tx_id": int(r["tx_id"]),
                    "ref_code": r["ref_code"],
                    "tx_date": r["tx_date"],
                    "tx_created_at": r["tx_created_at"],
                    "amount": float(r["amount"] or 0),
                    "customer_name": r["customer_name"] or "-",
                    "pjp_name": r["pjp_name"] or "-",
                    "ob_name": r["ob_name"] or "-",
                }
            )
        return txs

    def _load_next_page(self, *, reset_scroll: bool = False):
        if self._is_loading or not self._has_more:
            return
        self._is_loading = True
        try:
            if reset_scroll and hasattr(self, "ledger_scroll") and self.ledger_scroll:
                self.ledger_scroll.verticalScrollBar().setValue(0)

            txs = self._fetch_transactions_page(self._cursor_key)

            if not txs and not self.rows:
                self.empty_label.setVisible(True)
                self._has_more = False
                return

            if not txs:
                self._has_more = False
                return

            for tx in txs:
                # Format date
                tx_date = tx.get("tx_date") or ""
                try:
                    dt = datetime.strptime(tx_date, "%Y-%m-%d")
                    tx["date_str"] = dt.strftime("%d/%m/%Y")
                except Exception:
                    tx["date_str"] = tx_date

                # Format time from created_at
                created_at = tx.get("tx_created_at")
                time_str = ""
                if created_at:
                    try:
                        dt_full = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
                        time_str = dt_full.strftime("%I:%M %p")
                    except Exception:
                        parts = str(created_at).split()
                        if len(parts) > 1:
                            time_str = parts[1]
                tx["time_str"] = time_str

                amt = float(tx.get("amount") or 0)
                if tx["kind"] == "INVOICE":
                    tx["debit"] = amt
                    tx["credit"] = 0.0
                    self._running_balance += amt
                else:
                    tx["debit"] = 0.0
                    tx["credit"] = amt
                    self._running_balance -= amt

                tx["balance"] = self._running_balance

                row_widget = LedgerRowWidget(tx, self)
                self.container_layout.addWidget(row_widget)
                self.rows.append(row_widget)

            last = txs[-1]
            self._cursor_key = (last["tx_date"], last["tx_created_at"], last["kind_sort"], last["tx_id"])
            if len(txs) < int(self.page_size):
                self._has_more = False

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ledger:\n{e}")
            self._has_more = False
        finally:
            self._is_loading = False

    def _on_scroll(self, value: int):
        if not hasattr(self, "ledger_scroll") or not self.ledger_scroll:
            return
        sb = self.ledger_scroll.verticalScrollBar()
        if sb.maximum() <= 0:
            return
        if value >= sb.maximum() - 150:
            self._load_next_page()

    def _fetch_transactions_page(self, cursor_key):
        """Fetch one page of ledger transactions using keyset pagination.

        Ordering (ASC) is stable:
          tx_date, tx_created_at, kind_sort (payment=0, invoice=1), tx_id
        cursor_key is a tuple: (tx_date, tx_created_at, kind_sort, tx_id)
        """
        ob_id, pjp_id, customer_id, from_date, to_date, ref_search = self._current_filters()

        inv_query = """
            SELECT
                'INVOICE' AS kind,
                1         AS kind_sort,
                i.id AS tx_id,
                i.invoice_code AS ref_code,
                i.invoice_date AS tx_date,
                i.created_at   AS tx_created_at,
                i.amount,
                c.name AS customer_name,
                pj.pjp_name AS pjp_name,
                ob.name AS ob_name
            FROM invoices i
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE i.in_ledger = 1
        """
        inv_params: list = []

        # Filters for invoices
        if customer_id:
            inv_query += " AND i.customer_id = ?"
            inv_params.append(customer_id)
        elif pjp_id:
            inv_query += " AND i.pjp_id = ?"
            inv_params.append(pjp_id)
        elif ob_id:
            inv_query += " AND pj.order_booker_id = ?"
            inv_params.append(ob_id)

        if ref_search:
            inv_query += " AND CAST(i.invoice_code AS TEXT) = ?"
            inv_params.append(ref_search)

        if from_date:
            inv_query += " AND i.invoice_date >= ?"
            inv_params.append(from_date)
        if to_date:
            inv_query += " AND i.invoice_date <= ?"
            inv_params.append(to_date)

        pay_query = """
            SELECT
                'PAYMENT' AS kind,
                0         AS kind_sort,
                p.id AS tx_id,
                p.payment_code AS ref_code,
                p.payment_date AS tx_date,
                p.created_at   AS tx_created_at,
                p.amount,
                c.name AS customer_name,
                pj.pjp_name AS pjp_name,
                ob.name AS ob_name
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            LEFT JOIN customers c ON c.id = i.customer_id
            LEFT JOIN pjps pj ON pj.id = i.pjp_id
            LEFT JOIN order_bookers ob ON ob.id = pj.order_booker_id
            WHERE p.in_ledger = 1
              AND i.in_ledger = 1
        """
        pay_params: list = []

        # Filters for payments (based on linked invoice)
        if customer_id:
            pay_query += " AND i.customer_id = ?"
            pay_params.append(customer_id)
        elif pjp_id:
            pay_query += " AND i.pjp_id = ?"
            pay_params.append(pjp_id)
        elif ob_id:
            pay_query += " AND pj.order_booker_id = ?"
            pay_params.append(ob_id)

        if ref_search:
            pay_query += " AND CAST(p.payment_code AS TEXT) = ?"
            pay_params.append(ref_search)

        if from_date:
            pay_query += " AND p.payment_date >= ?"
            pay_params.append(from_date)
        if to_date:
            pay_query += " AND p.payment_date <= ?"
            pay_params.append(to_date)

        outer = f"""
            SELECT * FROM (
                {inv_query}
                UNION ALL
                {pay_query}
            ) t
            WHERE 1=1
        """
        params = inv_params + pay_params

        # Keyset continuation (ASC)
        if cursor_key:
            last_date, last_created, last_kind_sort, last_id = cursor_key
            outer += """
                AND (
                    t.tx_date > ?
                    OR (t.tx_date = ? AND t.tx_created_at > ?)
                    OR (t.tx_date = ? AND t.tx_created_at = ? AND t.kind_sort > ?)
                    OR (t.tx_date = ? AND t.tx_created_at = ? AND t.kind_sort = ? AND t.tx_id > ?)
                )
            """
            params.extend([
                last_date,
                last_date, last_created,
                last_date, last_created, last_kind_sort,
                last_date, last_created, last_kind_sort, last_id,
            ])

        outer += """
            ORDER BY
                t.tx_date ASC,
                t.tx_created_at ASC,
                t.kind_sort ASC,
                t.tx_id ASC
            LIMIT ?
        """
        params.append(int(self.page_size))

        cur = self.conn.cursor()
        cur.execute(outer, params)
        rows = cur.fetchall() or []

        txs = []
        for row in rows:
            txs.append(
                {
                    "kind": row["kind"],
                    "kind_sort": int(row["kind_sort"] or 0),
                    "tx_id": int(row["tx_id"]),
                    "ref_code": row["ref_code"],
                    "tx_date": row["tx_date"],
                    "tx_created_at": row["tx_created_at"],
                    "amount": float(row["amount"] or 0),
                    "customer_name": row["customer_name"] or "-",
                    "pjp_name": row["pjp_name"] or "-",
                    "ob_name": row["ob_name"] or "-",
                }
            )
        return txs

    def _update_summary_cards(self, total_invoiced: float, total_paid: float, outstanding: float):
        def update_card(card: QFrame, value: float):
            value_lbl = (
                card.findChild(QLabel, "CardInvoicedValue")
                or card.findChild(QLabel, "CardPaidValue")
                or card.findChild(QLabel, "CardBalanceValue")
            )
            if value_lbl:
                value_lbl.setText(f"<b>PKR</b> {value:,.0f}")

        update_card(self.card_invoiced, total_invoiced)
        update_card(self.card_paid, total_paid)
        update_card(self.card_balance, outstanding)

    # ---------------- styles ----------------

    def _apply_styles(self):
        dark = self.dark_mode

        bg = "#000000" if dark else "#ffffff"
        header_bg = "#020617" if dark else "#f8fafc"
        header_text = "#e5e7eb" if dark else "#0f172a"
        table_header_bg = "#111827" if dark else "#e5e7eb"
        table_bg = "#000000" if dark else "#ffffff"
        border = "#1f2937" if dark else "#e2e8f0"
        text = "#e5e7eb" if dark else "#0f172a"
        muted = "#9ca3af" if dark else "#64748b"
        primary = "rgb(37, 79, 167)"
        primary_hover = "rgb(30, 64, 140)"

        invoiced_card_bg = "#020617" if dark else "#eef2ff"
        paid_card_bg = "#022c22" if dark else "#ecfdf3"
        balance_card_bg = "#3f0f12" if dark else "#fef2f2"

        close_btn_hover = "#1f2937" if dark else "#e2e8f0"

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg};
            }}

            #LedgerHeader {{
                background-color: {header_bg};
            }}

            #LedgerTitle {{
                font-size: 20px;
                font-weight: 600;
                color: {header_text};
            }}

            #FiltersFrame {{
                background-color: {table_bg};
                border-bottom: 1px solid {border};
            }}

            #FiltersTitle {{
                font-size: 14px;
                font-weight: 600;
                color: {text};
                margin-bottom: 4px;
            }}

            #SummaryFrame {{
                background-color: {table_bg};
            }}

            #SummaryCardInvoiced {{
                background-color: {invoiced_card_bg};
                border-radius: 12px;
                border: 1px solid {border};
            }}

            #SummaryCardPaid {{
                background-color: {paid_card_bg};
                border-radius: 12px;
                border: 1px solid {border};
            }}

            #SummaryCardBalance {{
                background-color: {balance_card_bg};
                border-radius: 12px;
                border: 1px solid {border};
            }}

            #CardInvoicedTitle, #CardPaidTitle, #CardBalanceTitle {{
                font-size: 13px;
                font-weight: 500;
                color: {muted};
            }}

            #CardInvoicedValue, #CardPaidValue, #CardBalanceValue {{
                font-size: 22px;
                font-weight: 600;
                color: {text};
            }}

            #TableOuterFrame {{
                background-color: {table_bg};
            }}

            #LedgerSectionTitle {{
                font-size: 14px;
                font-weight: 600;
                color: {text};
            }}

            #LedgerTableHeader {{
                background-color: {table_header_bg};
                border-radius: 10px;
            }}

            #LedgerHeaderLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {text};
            }}

            QScrollArea#LedgerScroll {{
                background-color: {table_bg};
                border: none;
            }}

            QScrollArea#LedgerScroll > QWidget {{
                background-color: {table_bg};
            }}

            QScrollArea#LedgerScroll > QWidget > QWidget {{
                background-color: {table_bg};
            }}

            #LedgerRow {{
                background-color: {table_bg};
                border-bottom: 1px solid {border};
            }}

            #CellLabel, #AmountLabel {{
                color: {text};
                font-size: 12px;
            }}

            #EmptyLabel {{
                color: {muted};
                font-size: 14px;
            }}

            QComboBox, QDateEdit {{
                padding: 6px 8px;
                border-radius: 8px;
                border: 1px solid {border};
                background-color: {bg};
                color: {text};
            }}

            QComboBox:focus, QDateEdit:focus {{
                border: 1px solid {primary};
            }}

            QPushButton#ApplyFilterBtn {{
                background-color: {primary};
                color: white;
                border-radius: 8px;
                padding: 8px 12px;
                border: none;
                font-weight: 500;


            }}
            QPushButton#ApplyFilterBtn:hover {{
                background-color: {primary_hover};
            }}

            QPushButton#ResetFilterBtn {{
                background-color: transparent;
                color: {text};
                border-radius: 8px;
                padding: 8px 20px;
                border: 1px solid {border};
                font-weight: 500;
            }}
            QPushButton#ResetFilterBtn:hover {{
                background-color: {close_btn_hover};
            }}

            QPushButton#DownloadReportBtn {{
                background-color: {primary};
                color: white;
                border-radius: 8px;
                padding: 8px 14px;
                border: none;
                font-weight: 500;
                min-width: 140px;
            }}
            QPushButton#DownloadReportBtn:hover {{
                background-color: {primary_hover};
            }}


            QPushButton#PrintReportBtn {{
            background-color: {primary};
            color: white;
            border-radius: 8px;
            padding: 8px 14px;
            border: none;
            font-weight: 500;
            min-width: 140px;
        }}

        QPushButton#PrintReportBtn:hover {{
            background-color: {primary_hover};
        }}


            QPushButton#DownloadInvoiceBtn {{
                background-color: transparent;
                color: {text};
                border-radius: 8px;
                padding: 8px 14px;
                border: 1px solid {border};
                font-weight: 500;
                min-width: 140px;
            }}
            QPushButton#DownloadInvoiceBtn:hover {{
                background-color: {close_btn_hover};
            }}

            /* Popup search dropdown styling */
            QFrame#ComboPopupFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}

            QLineEdit#ComboPopupSearch {{
                padding: 6px 8px;
                border-radius: 8px;
                border: 1px solid {border};
                background-color: {bg};
                color: {text};
            }}

            QLineEdit#LedgerRefSearch {{
                min-height: 36px;
                padding: 8px 10px;
                padding-left: 34px;
                border-radius: 8px;
                border: 1px solid {border};
                background-color: {bg};
                color: {text};
            }}

            QLineEdit#LedgerRefSearch:focus {{
                border: 1px solid {primary};
            }}
            QListView#ComboPopupList {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px;
            }}

            QListView#ComboPopupList::item:selected {{
                background-color: {primary};
                color: white;
            }}
            """
        )
