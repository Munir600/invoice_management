# pjp/edit_pjp.py
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


from pjp.add_pjp import AddPJPDialog


class ClickableFrame(QFrame):
    """A frame that behaves like a clickable row."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------- EDIT PJP DIALOG (reuses AddPJPDialog layout) ----------

class EditPJPDialog(AddPJPDialog):
    """
    Uses the same UI as AddPJPDialog but:
      - Title = "Edit PJP"
      - Primary button text = "Save Changes"
      - Fields pre-filled from pjp_data
      - Updates existing row instead of inserting a new one
    """

    def __init__(self, db_conn: sqlite3.Connection, pjp_data: dict, parent=None):
        self.pjp_data = pjp_data  # id, order_booker_id, pjp_name, day_of_week
        super().__init__(db_conn, parent)

        # change heading & primary button text
        title_lbl = self.findChild(QLabel, "DialogTitle")
        if title_lbl:
            title_lbl.setText("Edit PJP")

        self.primary_btn = self.findChild(QPushButton, "DialogPrimaryButton")
        if self.primary_btn:
            self.primary_btn.setText("Save Changes")

        self._load_pjp_data()

    def _set_combo_by_data(self, combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def _load_pjp_data(self):
        p = self.pjp_data
        # Set order booker combo
        self._set_combo_by_data(self.combo_ob, p["order_booker_id"])
        # Name & day
        self.edit_pjp_name.setText(p["pjp_name"])
        # Set day combo (if present)
        idx = self.combo_day.findText(p["day_of_week"])
        if idx >= 0:
            self.combo_day.setCurrentIndex(idx)

    def _on_add_clicked(self):
        """Override to update instead of insert."""
        pjp_id = self.pjp_data["id"]

        ob_index = self.combo_ob.currentIndex()
        order_booker_id = self.combo_ob.itemData(ob_index) if ob_index >= 0 else None
        pjp_name = self.edit_pjp_name.text().strip()
        day_of_week = self.combo_day.currentText().strip()

        if not order_booker_id or not pjp_name or not day_of_week:
            QMessageBox.warning(
                self,
                "Validation error",
                "Order Booker, PJP Name and Day of Week are all required.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                UPDATE pjps
                SET order_booker_id = ?, pjp_name = ?, day_of_week = ?
                WHERE id = ?
                """,
                (order_booker_id, pjp_name, day_of_week, pjp_id),
            )
            self.conn.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to update PJP:\n{e}"
            )


# ---------- MANAGE PJPs LIST DIALOG ----------

class ManagePJPsDialog(QDialog):
    """
    Shows the list of PJPs with Edit/Delete buttons,
    and an Add PJP button. Respects parent.dark_mode.
    """

    def __init__(self, db_conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = bool(getattr(parent, "dark_mode", False))

        self.setWindowTitle("Manage PJPs")
        self.setModal(True)
        self.resize(700, 600)
        self.setMinimumWidth(650)

        self._build_ui()
        self._apply_styles()

        self.rows = []
        self.page_size = 50

        self.load_pjps()

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
        title = QLabel("Manage PJPs")
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

        add_btn = QPushButton("+ Add PJP")
        add_btn.setObjectName("AddPJPBtn")
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.clicked.connect(self.open_add_pjp)

        close_footer = QPushButton("Close")
        close_footer.setObjectName("CloseBtn")
        close_footer.setCursor(QCursor(Qt.PointingHandCursor))
        close_footer.clicked.connect(self.reject)

        f_layout.addWidget(add_btn)
        f_layout.addStretch()
        f_layout.addWidget(close_footer)
        layout.addWidget(footer)

    # ----- load + build rows -----------------------------------------

    def load_pjps(self):
        """Reload PJPs with lazy loading (keyset pagination)."""
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
            SELECT p.id, p.pjp_name, p.order_booker_id, ob.name AS ob_name
            FROM pjps p
            LEFT JOIN order_bookers ob ON ob.id = p.order_booker_id
        """
        params = []
        if cursor_key:
            last_ob, last_pjp, last_id = cursor_key
            query += """ WHERE (
                ob.name > ?
                OR (ob.name = ? AND p.pjp_name > ?)
                OR (ob.name = ? AND p.pjp_name = ? AND p.id > ?)
            ) """
            params.extend([last_ob, last_ob, last_pjp, last_ob, last_pjp, last_id])

        query += " ORDER BY ob.name ASC, p.pjp_name ASC, p.id ASC LIMIT ?"
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
                lbl = QLabel("No PJPs found.")
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
                    "id": row[0], "pjp_name": row[1], "order_booker_id": row[2], "ob_name": row[3]
                }
                data["row_number"] = start_idx + off
                self._add_pjp_row(data)
                self.rows.append(data)  # store data, not widgets


            last = rows[-1]
            if isinstance(last, sqlite3.Row):
                self._cursor_key = (last["ob_name"] or "", last["pjp_name"] or "", int(last["id"]))
            else:
                self._cursor_key = (last[3] or "", last[1] or "", int(last[0]))

            if len(rows) < int(self.page_size):
                self._has_more = False
        finally:
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


    def _add_pjp_row(self, pjp_data: dict):
        row = ClickableFrame()
        row.setObjectName("PJPRow")
        row.setCursor(QCursor(Qt.PointingHandCursor))
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(20, 16, 20, 16)
        row_layout.setSpacing(16)

        # Left: OB name + PJP name
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        pjp_label = QLabel(pjp_data.get("pjp_name", ""))
        pjp_label.setObjectName("PJPNameLabel")

        ob_label = QLabel(pjp_data.get("ob_name", ""))
        ob_label.setObjectName("OBNameLabel")

        left_layout.addWidget(pjp_label)
        left_layout.addWidget(ob_label)

        row_layout.addLayout(left_layout, 1)

        # Right: Edit / Delete
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("EditBtn")
        edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        edit_btn.clicked.connect(lambda _, p=pjp_data: self.open_edit_pjp(p))

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DeleteBtn")
        delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        delete_btn.clicked.connect(lambda _, p=pjp_data: self.confirm_delete(p["id"], p["pjp_name"]))

        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        row_layout.addLayout(btn_layout)

        row.clicked.connect(lambda p=pjp_data: self.open_edit_pjp(p))

        self.content_layout.addWidget(row)

    # ----- actions ----------------------------------------------------

    def open_add_pjp(self):
        dlg = AddPJPDialog(self.conn, self)
        dlg.pjp_added.connect(self.load_pjps)
        dlg.exec()


    def open_edit_pjp(self, pjp_data: dict):
        dlg = EditPJPDialog(self.conn, pjp_data, self)
        if dlg.exec():
            self.load_pjps()

    def confirm_delete(self, pjp_id: int, pjp_name: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete PJP <b>{pjp_name}</b>?<br><br>"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                cur = self.conn.cursor()
                cur.execute("DELETE FROM pjps WHERE id = ?", (pjp_id,))
                self.conn.commit()
                self.load_pjps()
            except sqlite3.IntegrityError as e:
                # Probably customers referencing this PJP (FK RESTRICT)
                QMessageBox.warning(
                    self,
                    "Cannot Delete",
                    "This PJP has customers assigned and cannot be deleted.\n\n"
                    "Remove or reassign those customers first, then try deleting this PJP again.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete PJP:\n{e}")

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

            #PJPRow {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}

            #PJPNameLabel {{
                font-weight: 600;
                font-size: 15px;
                color: {text};
            }}

            #OBNameLabel {{
                font-size: 12px;
                color: {muted};
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

            #AddPJPBtn {{
                background-color: {primary};
                color: white;
            }}
            #AddPJPBtn:hover {{
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
