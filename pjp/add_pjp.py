# pjp/add_pjp.py
import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QSizePolicy,
    QMessageBox,
    QWidget,
    QComboBox,
)
from PySide6.QtCore import Qt,QTimer, Signal


class AddPJPDialog(QDialog):
    """
    Dialog for adding a new PJP.
    Fields:
      - Order Booker (dropdown)
      - PJP Name
      - Day of Week (dropdown)
    """

    pjp_added = Signal()

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        self.setWindowTitle("Add PJP")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._build_ui()
        self._apply_local_styles()
        self._load_order_bookers()

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

        title_label = QLabel("Add PJP")
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
        body_layout.setSpacing(8)

        # Order Booker
        lbl_ob = QLabel("Order Booker")
        lbl_ob.setCursor(Qt.PointingHandCursor)
        self.combo_ob = QComboBox()
        self.combo_ob.setMinimumHeight(36)
        self.combo_ob.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_ob)
        body_layout.addWidget(self.combo_ob)

        # PJP Name
        lbl_pjp_name = QLabel("PJP Name")
        lbl_pjp_name.setCursor(Qt.PointingHandCursor)
        self.edit_pjp_name = QLineEdit()
        self.edit_pjp_name.setPlaceholderText("Enter PJP name / route name")
        self.edit_pjp_name.setMinimumHeight(36)
        self.edit_pjp_name.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_pjp_name)
        body_layout.addWidget(self.edit_pjp_name)

        # Day of Week
        lbl_day = QLabel("Day of Week")
        lbl_day.setCursor(Qt.PointingHandCursor)
        self.combo_day = QComboBox()
        self.combo_day.setMinimumHeight(36)
        self.combo_day.setCursor(Qt.PointingHandCursor)
        self.combo_day.addItems(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
        body_layout.addWidget(lbl_day)
        body_layout.addWidget(self.combo_day)

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

    # ------------------ Data loading ------------------

    def _load_order_bookers(self):
        """Populate Order Booker combo."""
        self.combo_ob.clear()

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, name
                FROM order_bookers
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
            self.combo_ob.addItem(row["name"], row["id"])

    # ------------------------- Styles -------------------------

    def _apply_local_styles(self):
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
                /* Text fields & combos */
                QLineEdit, QComboBox {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
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
                QLineEdit, QComboBox {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
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
                INSERT INTO pjps (order_booker_id, pjp_name, day_of_week)
                VALUES (?, ?, ?)
                """,
                (order_booker_id, pjp_name, day_of_week),
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving PJP:\n\n{e}",
            )
            return

        self._show_success_banner("PJP added successfully")
        self.pjp_added.emit()

        # Reset form for next PJP
        self.edit_pjp_name.clear()
        # keep same OB and day if you want, or reset:
        self.combo_ob.setCurrentIndex(0)
        self.combo_day.setCurrentIndex(0)

        self.edit_pjp_name.setFocus()
