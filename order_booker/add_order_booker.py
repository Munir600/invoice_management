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
)
from PySide6.QtCore import Qt, QRegularExpression, QTimer, Signal
from PySide6.QtGui import QRegularExpressionValidator


class AddOrderBookerDialog(QDialog):

    order_booker_added = Signal(int, str)
    """
    Dialog for adding a new Order Booker.
    Matches the style/colors of AddUserDialog (light & dark).
    """

    def __init__(self, db_conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = db_conn
        self.dark_mode = (
            parent.dark_mode if parent and hasattr(parent, "dark_mode") else False
        )

        self.setWindowTitle("Add Order Booker")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._build_ui()
        self._apply_local_styles()


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

        title_label = QLabel("Add Order Booker")
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

        # Name
        lbl_name = QLabel("Name")
        lbl_name.setCursor(Qt.PointingHandCursor)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Enter order booker name")
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

        # ✅ Only allow digits, up to 15 digits (adjust if you want)
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

    # ------------------------- Styles (same as AddUserDialog) -------------------------

    def _apply_local_styles(self):
        """
        Local QSS for the dialog – mirrors AddUserDialog so colors match
        for both light and dark modes.
        """
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
                /* Text fields */
                QLineEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #1a1a1a;
                    min-height: 36px;
                    background-color: #1E1E1E;
                    color: #e5e7eb;
                }
                QLineEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                /* Primary / Cancel buttons */
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
                /* Text fields */
                QLineEdit {
                    padding: 8px;
                    border-radius: 8px;
                    border: 1px solid #d1d5db;
                    min-height: 36px;
                }
                QLineEdit:focus {
                    border: 1px solid rgb(37, 79, 167);
                }
                /* Primary / Cancel buttons */
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
        name = self.edit_name.text().strip()
        contact = self.edit_contact.text().strip()
        address = self.edit_address.text().strip()

        # All fields are compulsory
        if not name:
            QMessageBox.warning(
                self,
                "Validation error",
                "Name is required.",
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO order_bookers (name, contact, address)
                VALUES (?, ?, ?)
                """,
                (name, contact, address),
            )
            self.conn.commit()
            new_id = int(cur.lastrowid)
            self.order_booker_added.emit(new_id, name)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error while saving order booker:\n\n{e}",
            )
            return

        self._show_success_banner("Order Booker added successfully")
        # Reset form
        self.edit_name.clear()
        self.edit_contact.clear()
        self.edit_address.clear()
        self.edit_name.setFocus()

