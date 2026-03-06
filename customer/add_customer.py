# customer/add_customer.py
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
from PySide6.QtCore import Qt, QRegularExpression, QTimer, Signal
from PySide6.QtGui import QRegularExpressionValidator


class AddCustomerDialog(QDialog):
    """
    Dialog for adding a new Customer.
    Fields:
      - Order Booker (dropdown)
      - PJP (dropdown, filtered by OB)
      - Name
      - Contact (digits only)
      - Address
    """

    customer_added = Signal()


    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        self.setWindowTitle("Add Customer")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._build_ui()
        self._apply_local_styles()

        self._load_order_bookers()
        self._load_initial_pjps()


    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            
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

        title_label = QLabel("Add Customer")
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
        self.combo_ob.currentIndexChanged.connect(self._on_ob_changed)
        body_layout.addWidget(lbl_ob)
        body_layout.addWidget(self.combo_ob)

        # PJP
        lbl_pjp = QLabel("PJP")
        lbl_pjp.setCursor(Qt.PointingHandCursor)
        self.combo_pjp = QComboBox()
        self.combo_pjp.setMinimumHeight(36)
        self.combo_pjp.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_pjp)
        body_layout.addWidget(self.combo_pjp)

        # Name
        lbl_name = QLabel("Name")
        lbl_name.setCursor(Qt.PointingHandCursor)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Enter customer name")
        self.edit_name.setMinimumHeight(36)
        self.edit_name.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_name)
        body_layout.addWidget(self.edit_name)

        # Contact
        lbl_contact = QLabel("Contact")
        lbl_contact.setCursor(Qt.PointingHandCursor)
        self.edit_contact = QLineEdit()
        self.edit_contact.setPlaceholderText("Enter contact number")
        self.edit_contact.setMinimumHeight(36)
        self.edit_contact.setCursor(Qt.PointingHandCursor)
        regex = QRegularExpression(r"\d{0,15}")
        validator = QRegularExpressionValidator(regex, self)
        self.edit_contact.setValidator(validator)
        self.edit_contact.setMaxLength(15)
        body_layout.addWidget(lbl_contact)
        body_layout.addWidget(self.edit_contact)

        # Address
        lbl_address = QLabel("Address")
        lbl_address.setCursor(Qt.PointingHandCursor)
        self.edit_address = QLineEdit()
        self.edit_address.setPlaceholderText("Enter address")
        self.edit_address.setMinimumHeight(36)
        self.edit_address.setCursor(Qt.PointingHandCursor)
        body_layout.addWidget(lbl_address)
        body_layout.addWidget(self.edit_address)

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
        self.combo_ob.clear()

        # Default placeholder
        self.combo_ob.addItem("Select Order Booker", None)

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

        # Ensure we start on the placeholder
        self.combo_ob.setCurrentIndex(0)

    def _load_pjps_for_ob(self, order_booker_id: int | None):
        self.combo_pjp.clear()

        # Default placeholder
        self.combo_pjp.addItem("Select PJP", None)

        if not order_booker_id:
            # Keep only the placeholder if no OB selected
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, pjp_name
                FROM pjps
                WHERE order_booker_id = ?
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
            self.combo_pjp.addItem(row["pjp_name"], row["id"])

        # Optional: keep placeholder selected initially
        self.combo_pjp.setCurrentIndex(0)


    def _load_initial_pjps(self):
        self.combo_pjp.clear()
        self.combo_pjp.addItem("Select PJP", None)

    def _on_ob_changed(self, index: int):
        ob_id = self.combo_ob.itemData(index) if index >= 0 else None
        # Always reload PJPs based on the current OB selection
        self._load_pjps_for_ob(ob_id)


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
                INSERT INTO customers (pjp_id, name, contact, address)
                VALUES (?, ?, ?, ?)
                """,
                (pjp_id, name, contact, address),
            )
            self.conn.commit()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving customer:\n\n{e}",
            )
            return

        self._show_success_banner("Customer added successfully")
        self.customer_added.emit()
        # Reset fields; you can keep OB/PJP selection to speed up entry
        self.edit_name.clear()
        self.edit_contact.clear()
        self.edit_address.clear()
        self.edit_name.setFocus()
