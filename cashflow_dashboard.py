import sys
import os
import shutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QToolButton, QMenu, QSizePolicy, QWidgetAction,
    QMessageBox
)
from PySide6.QtGui import QAction, QIcon, QFont, QCursor, QGuiApplication
from PySide6.QtCore import Qt, QSize, QEvent, Signal, QTimer, QPoint

from users.add_user import AddUserDialog
from db import get_connection, DB_PATH
from order_booker.add_order_booker import AddOrderBookerDialog
from pjp.add_pjp import AddPJPDialog
from customer.add_customer import AddCustomerDialog
from invoices.add_invoice import AddInvoiceDialog
from payments.add_payment import AddPaymentDialog
from ledger.ledger_dialog import LedgerDialog
from settings_dialog import SettingsDialog


# ---------- LIGHT THEME ----------

LIGHT_QSS = """

* {
    font-family: "Geist", "Geist Fallback", system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #f4f5fb;
}

QWidget#MainContainer {
    background-color: #f4f5fb;
}

/* arar */

QFrame#Sidebar {
    background-color: rgb(238, 238, 238);
    border: 1px solid rgb(206, 206, 206);
}

QFrame#SidebarHeader {
    background-color: transparent;
    border-bottom: 1px solid #e2e8f0;
}

QLabel#LogoText {
    font-size: 18px;
    font-weight: 700;
}

QLabel#LogoIcon {
    background-color: #1d4ed8;
    color: white;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 700;
}

QPushButton#SidebarButton {
    text-align: left;
    padding: 8px 16px;
    padding-left: 22px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: #0f172a;
    font-size: 14px;
    icon-size: 18px 18px;
}

QPushButton#SidebarButton::hover {
    background-color: #e5e7eb;
}

QPushButton#SidebarButton:checked {
    background-color: rgb(37, 79, 167);
    color: white;
}

/* Header */

QFrame#Header {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

QLabel#HeaderTitle {
    font-size: 18px;
    font-weight: 600;
}

/* Dashboard */

QWidget#DashboardPage {
    background-color: #ffffff;
}

QLabel#WelcomeTitle {
    font-size: 28px;
    font-weight: 700;
}

QLabel#WelcomeSubtitle {
    color: #64748b;
    font-size: 14px;
}

/* Cards */

QFrame#Card {
    background-color: rgb(238, 238, 238);
    border-radius: 16px;
    border: 1px solid rgb(206, 206, 206);
}

QLabel#CardTitle {
    font-size: 18px;
    font-weight: 600;
}

QLabel#CardSubtitle {
    font-size: 13px;
    color: #64748b;
}

/* icon in cards */
QLabel#CardIcon {
    margin-right: 4px;
}

QPushButton#PrimaryButton {
    background-color: rgb(37, 79, 167);
    color: white;
    border-radius: 8px;
    padding: 6px 16px;
    border: none;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#PrimaryButton::hover {
    background-color: rgb(30, 64, 140);
}

QPushButton#SecondaryButton {
    background-color: #ffffff;
    color: #0f172a;
    border-radius: 8px;
    padding: 6px 16px;
    border: 1px solid #e2e8f0;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#SecondaryButton:hover {
    background-color: rgb(37, 79, 167);
    color: white;
    border: 1px solid rgb(37, 79, 167);
}

/* Account button (avatar) */
QToolButton#AccountButton {
    background-color: rgb(37, 79, 167);
    color: white;
    border-radius: 20px;
    padding: 0;
    border: none;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
}

QToolButton#AccountButton::menu-indicator {
    image: none;
    width: 0px;
}


QMenu {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 8px 0;
}


QMenu::item {
    padding: 6px 18px;      
    font-size: 14px;
    color: #0f172a;
}


QMenu::item:selected {
    background-color: #f3f4f6;
    color: #0f172a;
}


QMenu::item#logout_action {
    color: #ef4444;                  
}


QMenu::item#logout_action:selected {
    background-color: #fee2e2;       
    color: #b91c1c;                 
}

/* Icon spacing */
QMenu::icon {
    margin-left: 4px;
    margin-right: 8px;
}

/* Separator line between header and items */
QMenu::separator {
    height: 1px;
    background: #e5e7eb;
    margin: 4px 0;
}



/* Custom logout button inside menu */
QPushButton#LogoutMenuButton {
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 4px 18px;
    color: #ef4444;
    font-size: 14px;
    font-weight: 400;
}
QPushButton#LogoutMenuButton:hover {
    background-color: #fee2e2;
}

"""


# ---------- DARK THEME ----------

DARK_QSS = """

* {
    font-family: "Geist", "Geist Fallback", system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #000000;
}

QWidget#MainContainer {
    background-color: #000000;
}

/* Sidebar */

QFrame#Sidebar {
    background-color: rgb(30, 30, 30);
    border-right: 1px solid #1a1a1a;
}

QFrame#SidebarHeader {
    background-color: transparent;
    border-bottom: 1px solid #1a1a1a;
}

QLabel#LogoText {
    font-size: 18px;
    font-weight: 700;
    color: #e5e7eb;
}

QLabel#LogoIcon {
    background-color: #1d4ed8;
    color: white;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 700;
}

QPushButton#SidebarButton {
    text-align: left;
    padding: 8px 16px;
    padding-left: 22px;
    border-radius: 8px;
    border: none;
    background: transparent;
    color: #e5e7eb;
    font-size: 14px;
    icon-size: 18px 18px;
}

QPushButton#SidebarButton::hover {
    background-color: #1a1a1a;
}

QPushButton#SidebarButton:checked {
    background-color: rgb(37, 79, 167);
    color: white;
}

/* Header */

QFrame#Header {
    background-color: #000000;
    border-bottom: 1px solid #1a1a1a;
}

QLabel#HeaderTitle {
    font-size: 18px;
    font-weight: 600;
    color: #e5e7eb;
}

/* Dashboard */

QWidget#DashboardPage {
    background-color: #000000;
}

QLabel#WelcomeTitle {
    font-size: 28px;
    font-weight: 700;
    color: #f9fafb;
}

QLabel#WelcomeSubtitle {
    color: #9ca3af;
    font-size: 14px;
}

/* Cards */

QFrame#Card {
    background-color: rgb(30, 30, 30);
    border-radius: 16px;
    border: 1px solid #1a1a1a;
}

QLabel#CardTitle {
    font-size: 18px;
    font-weight: 600;
    color: #f9fafb;
}

QLabel#CardSubtitle {
    font-size: 14px;
    color: #9ca3af;
}

QLabel#CardIcon {
    margin-right: 4px;
}

QPushButton#PrimaryButton {
    background-color: rgb(37, 79, 167);
    color: white;
    border-radius: 8px;
    padding: 6px 16px;
    border: none;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#PrimaryButton::hover {
    background-color: rgb(30, 64, 140);
}

QPushButton#SecondaryButton {
    background-color: #0c0c0c;
    color: white;
    border-radius: 8px;
    padding: 6px 16px;
    border: 1px solid #1a1a1a;
    font-weight: 500;
    font-size: 12px;
}

QPushButton#SecondaryButton:hover {
    background-color: rgb(37, 79, 167);
    color: white;
    border: 1px solid rgb(37, 79, 167);
}

/* Account button */

QToolButton#AccountButton {
    background-color: #1d4ed8;
    color: white;
    border-radius: 20px;
    padding: 0;
    border: none;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
}

QToolButton#AccountButton::menu-indicator {
    image: none;
    width: 0px;
}


QMenu {
    background-color: #0c0c0c;
    border: 1px solid #1a1a1a;
    border-radius: 12px;
    padding: 8px 0;
}

QMenu::item {
    padding: 6px 18px;       
    font-size: 14px;
    color: #e5e7eb;
}

QMenu::item:selected {
    background-color: #1a1a1a;
    color: #ffffff;
}


QMenu::item#logout_action {
    color: #fecaca;                 
}
QMenu::item#logout_action:selected {
    background-color: #7f1d1d;      
    color: #fee2e2;                 
}

/* Icon spacing */
QMenu::icon {
    margin-left: 4px;
    margin-right: 8px;
}


QMenu::separator {
    height: 1px;
    background: #1a1a1a;
    margin: 4px 0;
}


/* Custom logout button inside menu */
QPushButton#LogoutMenuButton {
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 4px 18px;
    color: #fecaca;
    font-size: 14px;
    font-weight: 400;
}
QPushButton#LogoutMenuButton:hover {
    background-color: #7f1d1d;
}

"""


# ---------- ICON HELPERS (SVGs) ----------

def _resource_base_dir() -> str:
    # In PyInstaller --onefile, data is extracted to sys._MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = _resource_base_dir()
ICON_DIR = os.path.join(BASE_DIR, "icons")


def app_icon(name: str) -> QIcon:
    """Return QIcon from icons/<name>.svg"""
    return QIcon(os.path.join(ICON_DIR, f"{name}.svg"))


# Sidebar icons (base names, white variants)
SIDEBAR_ICONS = {
    "Dashboard": "dashboard",
    "Invoices": "file",
    "Payments": "credit",
    "Manage": "book",
    "Ledger": "bar",
    "Settings": "settings",
}

# Card icons
CARD_ICONS = {
    "Invoices": "file",
    "Payments": "credit",
    "Order Booker": "book",
    "PJPs": "package",
    "Customers": "users",
    "Users": "user",
}

# Background color behind card icons (small rounded square)
CARD_ICON_BG = {
    "Invoices": "rgb(37, 99, 235)",
    "Payments": "rgb(34, 197, 94)",
    "Order Booker": "rgb(168, 85, 247)",
    "PJPs": "rgb(249, 115, 22)",
    "Customers": "rgb(239, 68, 68)",
    "Users": "rgb(59, 130, 246)",
}


# ---------- WIDGETS ----------

class SidebarButton(QPushButton):
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__("  " + text, parent)
        self.setObjectName("SidebarButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.icon_base_name = icon_name
        if icon_name:
            self.setIconSize(QSize(18, 18))


class SidebarManageRow(QWidget):
    def __init__(self, text: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._menu = None
        self._icon_name = icon_name  # base name e.g. "book"

        # IMPORTANT: give this widget a real layout so it gets height in QVBoxLayout
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.button = QPushButton("  " + text, self)
        self.button.setObjectName("SidebarButton")
        self.button.setCheckable(False)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.button.setIconSize(QSize(18, 18))
        self.button.clicked.connect(self._show_menu)
        self.setCursor(Qt.PointingHandCursor)

        root.addWidget(self.button)

        # Make wrapper height match the button height (prevents collapsing)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(self.button.sizeHint().height())

    def apply_theme_icon(self, dark_mode: bool):
        if dark_mode:
            self.button.setIcon(app_icon(self._icon_name))
        else:
            self.button.setIcon(app_icon(self._icon_name + "-black"))

    def setMenu(self, menu: QMenu):
        self._menu = menu

    def enterEvent(self, event):
        self._show_menu()
        super().enterEvent(event)

    def _show_menu(self):
        if not self._menu:
            return
        pos = self.button.mapToGlobal(QPoint(0, self.button.height()))
        self._menu.popup(pos)



class MainWindow(QMainWindow):

    logout_requested = Signal()

    def __init__(self, username: str):
        super().__init__()
        self.setWindowTitle("CashFlow")
        self.resize(1280, 720)

        self.dark_mode = False
        self.conn = get_connection()
        self.current_user = username

        self.backup_enabled: bool = False
        self.backup_dir: str | None = None
        self.last_backup_date: str | None = None
        self.backup_timer: QTimer | None = None
        self.report_title: str = "AK ENTERPRISES"
        self.manage_invoices_dialog = None
        self.add_invoice_dialog = None
        self.add_payment_dialog = None
        self.manage_payments_dialog = None
        self.edit_invoices_dialog = None
        self.edit_payments_dialog = None
        
        
        # permission info
        self.is_superuser = False

        # granular permissions (match DB column names)
        self.perms = {
            # invoices
            "can_add_invoices": 0,
            "can_edit_invoices": 0,
            "can_manage_invoices": 0,

            # payments
            "can_add_payments": 0,
            "can_edit_payments": 0,
            "can_manage_payments": 0,

            # order booker
            "can_add_order_booker": 0,
            "can_edit_order_booker": 0,

            # pjps
            "can_add_pjp": 0,
            "can_edit_pjp": 0,

            # customers
            "can_add_customer": 0,
            "can_edit_customer": 0,

            # ledger
            "can_ledger": 0,
            "can_settings": 0,
        }

        self._load_user_permissions()
        # High-level perms for UI tags + sidebar filtering (SettingsDialog expects this)
        self.user_perms = {
            "Invoices": self._has_any(["can_add_invoices", "can_edit_invoices", "can_manage_invoices"]),
            "Payments": self._has_any(["can_add_payments", "can_edit_payments", "can_manage_payments"]),
            "Order Booker": self._has_any(["can_add_order_booker", "can_edit_order_booker"]),
            "PJPs": self._has_any(["can_add_pjp", "can_edit_pjp"]),
            "Customers": self._has_any(["can_add_customer", "can_edit_customer"]),
            "Ledger": self._has_perm("can_ledger"),
            "Settings": self._has_perm("can_settings"),
        }

        self._load_app_settings()
        self._setup_backup_schedule(initial_check=True)

        # track Edit buttons to theme/hover-update their icons
        self.edit_buttons = []
        # track card widgets for permission styling
        self.cards = []

        container = QWidget()
        container.setObjectName("MainContainer")
        self.setCentralWidget(container)

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = self._build_sidebar()
        main_layout.addWidget(self.sidebar)

        # Right side: header + dashboard
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.header = self._build_header()
        right_layout.addWidget(self.header)

        self.dashboard_page = self._build_dashboard()
        right_layout.addWidget(self.dashboard_page)

        main_layout.addWidget(right)

        self.apply_theme()



    def closeEvent(self, event):
        dlg = getattr(self, "ledger_dialog", None)
        if dlg is not None:
            try:
                dlg.close()
            except Exception:
                pass
        super().closeEvent(event)


    # ----- permissions -----

    def reset_active_state(self, button):
        """Removes the 'active' property from a given button to reset its style."""
        button.setProperty("active", False)
        self.style().polish(button)

    def _load_user_permissions(self):
        """Load is_superuser and granular permission flags for the current user."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    is_superuser,

                    can_add_invoices,  can_edit_invoices,  can_manage_invoices,
                    can_add_payments,  can_edit_payments,  can_manage_payments,

                    can_add_order_booker, can_edit_order_booker,
                    can_add_pjp,          can_edit_pjp,
                    can_add_customer,     can_edit_customer,

                    can_ledger,
                    can_settings
                FROM users
                WHERE username = ?
                """,
                (self.current_user,),
            )
            row = cur.fetchone()
            if row:
                self.is_superuser = bool(row["is_superuser"])

                # keep perms dict in sync with DB
                for k in self.perms.keys():
                    self.perms[k] = int(row[k]) if k in row.keys() else 0

        except Exception as e:
            print("Failed to load user permissions:", e)


    def _has_perm(self, perm_name: str) -> bool:
        """Superuser bypass + safe permission lookup."""
        if getattr(self, "is_superuser", False):
            return True
        return bool(getattr(self, "perms", {}).get(perm_name, 0))

    def _has_any(self, perm_names) -> bool:
        if getattr(self, "is_superuser", False):
            return True
        p = getattr(self, "perms", {})
        return any(bool(p.get(name, 0)) for name in perm_names)

    def _deny_access(self, feature_name: str):
        # Silent deny (no popup). If user doesn't have permission, nothing happens.
        return

    def _card_button_perms(self, title_text: str):
        """Return (can_add, can_edit) for a dashboard card."""
        if title_text == "Invoices":
            return (self._has_perm("can_add_invoices"), self._has_perm("can_edit_invoices"))
        if title_text == "Payments":
            return (self._has_perm("can_add_payments"), self._has_perm("can_edit_payments"))
        if title_text == "Order Booker":
            return (self._has_perm("can_add_order_booker"), self._has_perm("can_edit_order_booker"))
        if title_text == "PJPs":
            return (self._has_perm("can_add_pjp"), self._has_perm("can_edit_pjp"))
        if title_text == "Customers":
            return (self._has_perm("can_add_customer"), self._has_perm("can_edit_customer"))
        if title_text == "Users":
            return (bool(getattr(self, "is_superuser", False)), bool(getattr(self, "is_superuser", False)))
        return (False, False)

    def _can_access_card(self, title: str) -> bool:
        """True if any action on that card is allowed (used for styling)."""
        can_add, can_edit = self._card_button_perms(title)
        return bool(can_add or can_edit)

# ----- sidebar -----

    def _build_sidebar(self):
        frame = QFrame()
        frame.setObjectName("Sidebar")
        frame.setFixedWidth(220)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Sidebar header
        header_frame = QFrame()
        header_frame.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 12)
        header_layout.setSpacing(8)

        logo_icon = QLabel("₹")
        logo_icon.setObjectName("LogoIcon")
        logo_icon.setAlignment(Qt.AlignCenter)

        logo_text = QLabel("CashFlow")
        logo_text.setObjectName("LogoText")

        header_layout.addWidget(logo_icon)
        header_layout.addWidget(logo_text)
        header_layout.addStretch()

        layout.addWidget(header_frame)


        
        self.sidebar_buttons = []

        # helper: decide which main modules should appear in the sidebar
        show_invoices = self._has_any(["can_add_invoices", "can_edit_invoices", "can_manage_invoices"])
        show_payments = self._has_any(["can_add_payments", "can_edit_payments", "can_manage_payments"])
        show_ledger   = self._has_perm("can_ledger")
        show_settings = self._has_perm("can_settings")

        # 1) Standard buttons
        for name, should_show in [
            ("Dashboard", True),
            ("Invoices", show_invoices),
            ("Payments", show_payments),
        ]:
            if not should_show:
                continue
            icon_name = SIDEBAR_ICONS.get(name)
            btn = SidebarButton(name, icon_name)
            layout.addWidget(btn)
            self.sidebar_buttons.append(btn)
            btn.clicked.connect(lambda checked, b=btn: self.on_sidebar_clicked(b))

        # 2) Manage row (submenu; no '>' indicator)
        manage_row = SidebarManageRow("Manage", SIDEBAR_ICONS["Manage"])
        manage_row.apply_theme_icon(self.dark_mode)
        self._manage_row = manage_row

        manage_menu = QMenu(manage_row)

        # Add only what the user is allowed to manage
        if self._has_perm("can_manage_invoices"):
            act_manage_invoices = QAction("Manage Invoices", manage_menu)
            act_manage_invoices.triggered.connect(lambda: self._open_manage_from_menu("invoices"))
            manage_menu.addAction(act_manage_invoices)

        if self._has_perm("can_manage_payments"):
            act_manage_payments = QAction("Manage Payments", manage_menu)
            act_manage_payments.triggered.connect(lambda: self._open_manage_from_menu("payments"))
            manage_menu.addAction(act_manage_payments)

        # If user has no manage permissions, don't show the Manage row at all
        if manage_menu.actions():
            manage_row.setMenu(manage_menu)
            layout.addWidget(manage_row)

        # 3) Remaining standard buttons
        for name, should_show in [
            ("Ledger", show_ledger),
            ("Settings", show_settings),
        ]:
            if not should_show:
                continue
            icon_name = SIDEBAR_ICONS.get(name)
            btn = SidebarButton(name, icon_name)
            layout.addWidget(btn)
            self.sidebar_buttons.append(btn)
            btn.clicked.connect(lambda checked, b=btn: self.on_sidebar_clicked(b))


        # Default selection: Dashboard
        for btn in getattr(self, "sidebar_buttons", []):
            if btn.text().strip() == "Dashboard":
                btn.setChecked(True)
                break

        self._update_sidebar_icons()


        layout.addStretch()
        return frame

    def _select_dashboard(self):
        """Select 'Dashboard' in sidebar and update header/icons."""
        for btn in getattr(self, "sidebar_buttons", []):
            label = btn.text().strip()
            btn.setChecked(label == "Dashboard")
        self._update_sidebar_icons()
        header_title = self.header.findChild(QLabel, "HeaderTitle")
        if header_title:
            header_title.setText("Dashboard")
    def on_sidebar_clicked(self, clicked_btn: QPushButton):
        # keep single selection & icons
        for btn in self.sidebar_buttons:
            btn.setChecked(btn is clicked_btn)
        self._update_sidebar_icons()

        label = clicked_btn.text().strip()

        # update header title
        header_title = self.header.findChild(QLabel, "HeaderTitle")
        if header_title:
            header_title.setText(label)

        # open the corresponding section (route to the best allowed action)
        if label == "Dashboard":
            self._select_dashboard()
            return

        if label == "Invoices":
            if self._has_perm("can_edit_invoices"):
                self.open_edit_invoices()
            elif self._has_perm("can_add_invoices"):
                self.open_add_invoice()
            elif self._has_perm("can_manage_invoices"):
                self.open_manage_invoices()
            else:
                self._deny_access("Invoices")
            return

        if label == "Payments":
            if self._has_perm("can_edit_payments"):
                self.open_edit_payments()
            elif self._has_perm("can_add_payments"):
                self.open_add_payment()
            elif self._has_perm("can_manage_payments"):
                self.open_manage_payments()
            else:
                self._deny_access("Payments")
            return

        if label == "Ledger":
            if self._has_perm("can_ledger"):
                self.open_ledger()
            else:
                self._deny_access("Ledger")
            return

        if label == "Settings":
            if self._has_perm("can_settings"):
                self.open_settings()
            else:
                self._deny_access("Settings")
            return


    def _open_manage_from_menu(self, which: str):
        # clear selection (Manage isn’t a checkable sidebar button)
        for btn in getattr(self, "sidebar_buttons", []):
            btn.setChecked(False)
        self._update_sidebar_icons()

        header_title = self.header.findChild(QLabel, "HeaderTitle")

        if which == "invoices":
            if not self._has_perm("can_manage_invoices"):
                self._deny_access("Manage Invoices")
                return
            if header_title:
                header_title.setText("Manage Invoices")
            self.open_manage_invoices()
            return

        if which == "payments":
            if not self._has_perm("can_manage_payments"):
                self._deny_access("Manage Payments")
                return
            if header_title:
                header_title.setText("Manage Payments")
            self.open_manage_payments()
            return

    def _update_sidebar_icons(self):
        for btn in getattr(self, "sidebar_buttons", []):
            base = getattr(btn, "icon_base_name", None)
            if not base:
                continue

            if self.dark_mode:
                btn.setIcon(app_icon(base))
            else:
                if btn.isChecked():
                    btn.setIcon(app_icon(base))
                else:
                    btn.setIcon(app_icon(base + "-black"))

        if hasattr(self, "_manage_row") and self._manage_row is not None:
            self._manage_row.apply_theme_icon(self.dark_mode)


    # ----- header -----

    def _build_header(self):
        frame = QFrame()
        frame.setObjectName("Header")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)

        # Page title
        title = QLabel("Dashboard")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)
        layout.addStretch()

        # Account avatar button
        account_btn = QToolButton()
        account_btn.setObjectName("AccountButton")
        account_btn.setIcon(app_icon("user"))
        account_btn.setIconSize(QSize(24, 24))
        account_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        account_btn.setPopupMode(QToolButton.InstantPopup)
        account_btn.setCursor(QCursor(Qt.PointingHandCursor))

        # === MENU ===
        menu = QMenu(account_btn)

        # Username header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(4)

        # store as attributes so apply_theme can style them
        self.name_label = QLabel(self.current_user)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.email_label = QLabel(f"{self.current_user.lower()}@cashflow.com")
        self.email_label.setStyleSheet("font-size: 12px; color: #94a3b8;")

        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.email_label)

        header_action = QWidgetAction(menu)
        header_action.setDefaultWidget(header_widget)
        menu.addAction(header_action)
        menu.addSeparator()

        # Dark Mode item
        theme_action = QAction("Dark Mode", menu)
        theme_action.setIcon(app_icon("moon-black"))
        theme_action.triggered.connect(self.toggle_theme)
        menu.addAction(theme_action)

        # Logout item (styled via QSS with red hover)
        logout_action = QAction("Logout", menu)
        logout_action.setObjectName("logout_action")  # <-- important for QSS
        logout_action.setIcon(app_icon("logout-black"))
        logout_action.triggered.connect(self.logout)
        menu.addAction(logout_action)

        # Store references for theme switching
        self.theme_menu_action = theme_action
        self.logout_menu_action = logout_action

        account_btn.setMenu(menu)
        layout.addWidget(account_btn)

        return frame

    # ----- dashboard -----

    def _build_dashboard(self):
        page = QWidget()
        page.setObjectName("DashboardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(24)

        # Welcome text
        title = QLabel("Welcome Back")
        title.setObjectName("WelcomeTitle")
        subtitle = QLabel("Manage your business operations across all categories")
        subtitle.setObjectName("WelcomeSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Cards grid
        grid = QGridLayout()
        grid.setSpacing(20)

        cards = [
            ("Invoices", "Manage and track all your invoices"),
            ("Payments", "Process and record payments"),
            ("Order Booker", "Manage order booking details"),
            ("PJPs", "Handle journey plans for order bookers"),
            ("Customers", "Manage customer information"),
            ("Users", "Control user accounts and access"),
        ]

        for index, (card_title, card_subtitle) in enumerate(cards):
            row = index // 3
            col = index % 3
            card = self._build_card(card_title, card_subtitle)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)
        layout.addStretch()
        return page

    def _style_card(self, frame: QFrame, title_label: QLabel,
                    subtitle_label: QLabel, enabled: bool):
        """Apply visual style for enabled/disabled state."""
        if enabled:
            # let global QSS handle it
            frame.setStyleSheet("")
            title_label.setStyleSheet("")
            subtitle_label.setStyleSheet("")
        else:
            if self.dark_mode:
                frame.setStyleSheet(
                    "background-color: #030712; "
                    "border: 1px dashed #1f2937; "
                    "border-radius: 16px;"
                )
                title_label.setStyleSheet("color: #6b7280;")
                subtitle_label.setStyleSheet("color: #6b7280;")
            else:
                frame.setStyleSheet(
                    "background-color: #e5e7eb; "
                    "border: 1px dashed #cbd5f5; "
                    "border-radius: 16px;"
                )
                title_label.setStyleSheet("color: #9ca3af;")
                subtitle_label.setStyleSheet("color: #9ca3af;")

    def _build_card(self, title_text, subtitle_text):
        frame = QFrame()
        frame.setObjectName("Card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        # Top: icon + title
        top_row = QHBoxLayout()

        icon_label = QLabel()
        icon_label.setObjectName("CardIcon")

        icon_name = CARD_ICONS.get(title_text)
        if icon_name:
            icon_label.setPixmap(app_icon(icon_name).pixmap(QSize(20, 20)))

        bg = CARD_ICON_BG.get(title_text)
        if bg:
            icon_label.setStyleSheet(
                f"background-color: {bg}; border-radius: 8px; padding: 4px;"
            )

        title = QLabel(title_text)
        title.setObjectName("CardTitle")

        top_row.addWidget(icon_label)
        top_row.addWidget(title)
        top_row.addStretch()

        v.addLayout(top_row)

        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("CardSubtitle")
        subtitle.setWordWrap(True)

        v.addWidget(subtitle)
        v.addStretch()

        # Buttons row
        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_add.setObjectName("PrimaryButton")
        btn_add.setIcon(app_icon("plus"))
        btn_add.setIconSize(QSize(16, 16))

        btn_edit = QPushButton("Edit")
        btn_edit.setObjectName("SecondaryButton")
        btn_edit.setIconSize(QSize(12, 12))
        btn_add.setCursor(QCursor(Qt.PointingHandCursor))
        btn_edit.setCursor(QCursor(Qt.PointingHandCursor))

        # Track edit buttons and handle hover via eventFilter
        self.edit_buttons.append(btn_edit)
        btn_edit.installEventFilter(self)
        self._update_edit_button_icon(btn_edit, hover=False)

        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addStretch()

        v.addLayout(btn_row)

        # Hook up actions
        if title_text == "Users":
            btn_add.clicked.connect(self.open_add_user_dialog)
            btn_edit.clicked.connect(self.open_manage_users)

        elif title_text == "Order Booker":
            btn_add.clicked.connect(self.open_add_order_booker)
            btn_edit.clicked.connect(self.open_manage_order_bookers)

        elif title_text == "PJPs":
            btn_add.clicked.connect(self.open_add_pjp)
            btn_edit.clicked.connect(self.open_manage_pjps)

        elif title_text == "Customers":
            btn_add.clicked.connect(self.open_add_customer)
            btn_edit.clicked.connect(self.open_manage_customers)

        elif title_text == "Invoices":
            btn_add.clicked.connect(self.open_add_invoice)
            btn_edit.clicked.connect(self.open_edit_invoices)

        elif title_text == "Payments":
            btn_add.clicked.connect(self.open_add_payment)
            btn_edit.clicked.connect(self.open_edit_payments)
        # Permission logic (separate Add vs Edit)
        can_add, can_edit = self._card_button_perms(title_text)
        btn_add.setEnabled(can_add)
        btn_edit.setEnabled(can_edit)
        allowed = bool(can_add or can_edit)
        self._style_card(frame, title, subtitle, allowed)

        # store for later theme refresh
        self.cards.append(
            {
                "title": title_text,
                "frame": frame,
                "title_label": title,
                "subtitle_label": subtitle,
                "btn_add": btn_add,
                "btn_edit": btn_edit,
            }
        )

        return frame

    def _refresh_cards_for_theme(self):
        """Re-apply disabled/enabled visual style after theme change."""
        for card in self.cards:
            can_add, can_edit = self._card_button_perms(card["title"])
            card["btn_add"].setEnabled(can_add)
            card["btn_edit"].setEnabled(can_edit)
            allowed = bool(can_add or can_edit)
            self._style_card(
                card["frame"],
                card["title_label"],
                card["subtitle_label"],
                allowed,
            )

    # ----- edit button icon logic -----

    def _update_edit_button_icon(self, button: QPushButton, hover: bool = False):
        if self.dark_mode:
            button.setIcon(app_icon("edit"))
        else:
            if hover:
                button.setIcon(app_icon("edit"))
            else:
                button.setIcon(app_icon("edit-black"))

    def eventFilter(self, obj, event):
        if obj in getattr(self, "edit_buttons", []):
            if event.type() == QEvent.Enter:
                self._update_edit_button_icon(obj, hover=True)
            elif event.type() == QEvent.Leave:
                self._update_edit_button_icon(obj, hover=False)

        return super().eventFilter(obj, event)

    # ----- theme + logout -----

    def apply_theme(self):
        app = QApplication.instance()
        if app is None:
            return

        if self.dark_mode:
            # Apply dark theme
            app.setStyleSheet(DARK_QSS)

            # Menu text + icons
            if hasattr(self, "theme_menu_action"):
                self.theme_menu_action.setText("Light Mode")
                self.theme_menu_action.setIcon(app_icon("moon"))          # white moon
            if hasattr(self, "logout_menu_action"):
                self.logout_menu_action.setIcon(app_icon("logout"))       # white logout

            # Header username colours
            if hasattr(self, "name_label"):
                self.name_label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 14px;")
            if hasattr(self, "email_label"):
                self.email_label.setStyleSheet("color: #9ca3af; font-size: 12px;")

        else:
            # Apply light theme
            app.setStyleSheet(LIGHT_QSS)

            if hasattr(self, "theme_menu_action"):
                self.theme_menu_action.setText("Dark Mode")
                self.theme_menu_action.setIcon(app_icon("moon-black"))    # black moon
            if hasattr(self, "logout_menu_action"):
                self.logout_menu_action.setIcon(app_icon("logout-black")) # black logout

            if hasattr(self, "name_label"):
                self.name_label.setStyleSheet("color: #111827; font-weight: 600; font-size: 14px;")
            if hasattr(self, "email_label"):
                self.email_label.setStyleSheet("color: #64748b; font-size: 12px;")

        # Update Edit buttons
        if hasattr(self, "edit_buttons"):
            for btn in self.edit_buttons:
                self._update_edit_button_icon(btn, hover=False)

        # Update sidebar icons
        self._update_sidebar_icons()

        # Re-style cards (enabled/disabled) for current theme
        self._refresh_cards_for_theme()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def logout(self):
        self.logout_requested.emit()
        self.close()

    def show_success_message(self, message="New user added successfully"):
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
        y = 50
        notification.move(x, y)
        notification.show()
        QTimer.singleShot(2000, notification.deleteLater)

    # ----- Users -----

    def open_add_user_dialog(self):
        if not getattr(self, "is_superuser", False):
            self._deny_access("Add User")
            return

        if not hasattr(self, "conn") or self.conn is None:
            self.conn = get_connection()

        dlg = AddUserDialog(self.conn, self)
        result = dlg.exec()

        if result:
            self.show_success_message()

    def open_manage_users(self):
        if not getattr(self, "is_superuser", False):
            self._deny_access("Manage Users")
            return

        try:
            from users.edit_user import ManageUsersDialog
        except ImportError:
            print("Error: users.edit_user not found. Skipping Manage Users dialog.")
            return

        dlg = ManageUsersDialog(self.conn, self)
        dlg.exec()
        self._select_dashboard()

    # ----- Order Bookers -----

    def open_add_order_booker(self):
        if not self._has_perm("can_add_order_booker"):
            self._deny_access("Add Order Booker")
            return

        if not hasattr(self, "conn") or self.conn is None:
            self.conn = get_connection()

        dlg = AddOrderBookerDialog(self.conn, self)
        result = dlg.exec()

        if result:
            self.show_success_message("Order booker added successfully")

    def open_manage_order_bookers(self):
        if not self._has_perm("can_edit_order_booker"):
            self._deny_access("Edit Order Booker")
            return

        try:
            from order_booker.edit_order_booker import ManageOrderBookersDialog
        except ImportError:
            print("Error: order_booker.edit_order_booker not found. Skipping Manage Order Bookers dialog.")
            return

        dlg = ManageOrderBookersDialog(self.conn, self)
        dlg.exec()
        self._select_dashboard()

    # ----- PJPs -----

    def open_add_pjp(self):
        if not self._has_perm("can_add_pjp"):
            self._deny_access("Add PJP")
            return

        if not hasattr(self, "conn") or self.conn is None:
            self.conn = get_connection()

        dlg = AddPJPDialog(self.conn, self)
        result = dlg.exec()

        if result:
            self.show_success_message("PJP added successfully")

    def open_manage_pjps(self):
        if not self._has_perm("can_edit_pjp"):
            self._deny_access("Edit PJP")
            return

        try:
            from pjp.edit_pjp import ManagePJPsDialog
        except ImportError:
            print("Error: pjp.edit_pjp not found. Skipping Manage PJPs dialog.")
            return

        dlg = ManagePJPsDialog(self.conn, self)
        dlg.exec()
        self._select_dashboard()

    # ----- Customers -----

    def open_add_customer(self):
        if not self._has_perm("can_add_customer"):
            self._deny_access("Add Customer")
            return

        if not hasattr(self, "conn") or self.conn is None:
            self.conn = get_connection()

        dlg = AddCustomerDialog(self.conn, self)
        result = dlg.exec()

        if result:
            self.show_success_message("Customer added successfully")

    def open_manage_customers(self):
        if not self._has_perm("can_edit_customer"):
            self._deny_access("Edit Customer")
            return

        try:
            from customer.edit_customer import ManageCustomersDialog
        except ImportError:
            print("Error: customer.edit_customer not found. Skipping Manage Customers dialog.")
            return

        dlg = ManageCustomersDialog(self.conn, self)
        dlg.exec()
        self._select_dashboard()

    # ----- Invoices -----

    def open_add_invoice(self):
        if not self._has_perm("can_add_invoices"):
            self._deny_access("Add Invoices")
            return

        if not hasattr(self, "conn") or self.conn is None:
            self.conn = get_connection()

        # Reuse the same Add dialog if it already exists and is visible
        if self.add_invoice_dialog is None or not self.add_invoice_dialog.isVisible():
            self.add_invoice_dialog = AddInvoiceDialog(self.conn, self)
            
            if hasattr(self.add_invoice_dialog, "finished"):
                 self.add_invoice_dialog.finished.connect(lambda *_: self._select_dashboard())
        

            def handle_invoice_created():
                # If Manage dialog is already open, just refresh it
                if getattr(self, "edit_invoices_dialog", None) is not None and self.edit_invoices_dialog.isVisible():
                    self.edit_invoices_dialog.load_invoices()
                else:
                    self.open_edit_invoices(from_add=True)


                # After a new invoice, keep them side by side
                QTimer.singleShot(0, self._position_invoice_windows)


                self.add_invoice_dialog.raise_()
                self.add_invoice_dialog.activateWindow()

            self.add_invoice_dialog.invoice_created.connect(handle_invoice_created)

        self.add_invoice_dialog.show()
        self.add_invoice_dialog.raise_()
        self.add_invoice_dialog.activateWindow()

        # If Manage is already open, arrange side by side now
        QTimer.singleShot(0, self._position_invoice_windows)




    def open_manage_invoices(self, from_add: bool = False):
        if not self._has_perm("can_manage_invoices"):
            self._deny_access("Manage Invoices")
            return

        try:
            from invoices.edit_invoice import ManageInvoicesDialog
        except ImportError as e:
            print(f"Error importing ManageInvoicesDialog: {e}")
            return

        # Create (or re-create) dialog if missing / closed
        dlg = getattr(self, "manage_invoices_dialog", None)
        if dlg is None or not dlg.isVisible():
            dlg = ManageInvoicesDialog(self.conn, parent=self, mode="manage")
            self.manage_invoices_dialog = dlg

            dlg.destroyed.connect(lambda: setattr(self, "manage_invoices_dialog", None))
            if hasattr(dlg, "finished"):
                dlg.finished.connect(lambda *_: self._select_dashboard())

        # IMPORTANT: Only show if dlg exists
        if self.manage_invoices_dialog is None:
            return

        self.manage_invoices_dialog.show()

        if not from_add:
            self.manage_invoices_dialog.raise_()
            self.manage_invoices_dialog.activateWindow()


    def open_edit_invoices(self, from_add: bool = False):
        if not self._has_perm("can_edit_invoices"):
            self._deny_access("Edit Invoices")
            return

        try:
            from invoices.edit_invoice import ManageInvoicesDialog
        except ImportError:
            print("Error: invoices.edit_invoice not found. Skipping Edit Invoices dialog.")
            return

        # Ensure attribute exists (safe even if already exists)
        if not hasattr(self, "edit_invoices_dialog"):
            self.edit_invoices_dialog = None

        # Reuse if already open
        if self.edit_invoices_dialog is None or not self.edit_invoices_dialog.isVisible():
            # IMPORTANT: mode="edit" -> shows only in_ledger=0 invoices and title "Edit Invoices"
            self.edit_invoices_dialog = ManageInvoicesDialog(self.conn, self, mode="edit")

            self.edit_invoices_dialog.destroyed.connect(
                lambda: setattr(self, "edit_invoices_dialog", None)
            )

            if hasattr(self.edit_invoices_dialog, "finished"):
                self.edit_invoices_dialog.finished.connect(lambda *_: self._select_dashboard())

        self.edit_invoices_dialog.show()

        if not from_add:
            self.edit_invoices_dialog.raise_()
            self.edit_invoices_dialog.activateWindow()

        # Arrange side-by-side AFTER the window is actually visible/sized
        QTimer.singleShot(0, self._position_invoice_windows)


    def _position_invoice_windows(self):
        """
        Position ManageInvoicesDialog (left) and AddInvoiceDialog (right)
        side by side, each using ~50% of the screen height/width.

        The main dashboard window is NOT resized.
        """
        add = getattr(self, "add_invoice_dialog", None)
        edit = getattr(self, "edit_invoices_dialog", None)


        if not add or not edit:
            return
        if not add.isVisible() or not edit.isVisible():
            return


        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()
        half_width = avail.width() // 2

        # Common height, clamped to screen
        desired_height = max(add.height(), edit.height(), 500)
        desired_height = min(desired_height, avail.height() - 80)
        top = avail.y() + (avail.height() - desired_height) // 2

        # Left: ManageInvoicesDialog
        edit.resize(half_width, desired_height)
        edit.move(avail.x(), top)

        # Right: AddInvoiceDialog
        add.resize(half_width, desired_height)
        add.move(avail.x() + half_width, top)


    def _position_payment_windows(self):
        """
        Position ManagePaymentsDialog (left) and AddPaymentDialog (right)
        side by side, each using ~50% of the screen.

        The main dashboard window is NOT resized.
        """
        add = getattr(self, "add_payment_dialog", None)
        edit = getattr(self, "edit_payments_dialog", None)

        if not add or not edit:
            return
        if not add.isVisible() or not edit.isVisible():
            return


        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()

        # Each dialog uses half of the available screen width
        half_width = avail.width() // 2

        # Decide a reasonable height for both dialogs
        desired_height = max(add.height(), edit.height(), 500)
        # leave some space at the bottom so buttons are never hidden
        desired_height = min(desired_height, avail.height() - 80)

        # Align near the top instead of vertical centring
        top = avail.y() + 20   # 20 px from top edge of the screen

        # Left: ManagePaymentsDialog
        edit.resize(half_width, desired_height)
        edit.move(avail.x(), top)

        # Right: AddPaymentDialog
        add.resize(half_width, desired_height)
        add.move(avail.x() + half_width, top)

    # ----- Payments -----
    def open_add_payment(self):
        if not self._has_perm("can_add_payments"):
            self._deny_access("Add Payments")
            return

        """Open the Add Payment dialog from the Dashboard."""
        if getattr(self, "add_payment_dialog", None) is None:
            # create the dialog once and reuse it
            self.add_payment_dialog = AddPaymentDialog(self.conn, self)
                    # reset sidebar when AddPaymentDialog closes
            if hasattr(self.add_payment_dialog, "finished"):
                self.add_payment_dialog.finished.connect(lambda *_: self._select_dashboard())

            def _on_payment_added():
                edit = getattr(self, "edit_payments_dialog", None)
                if edit is not None and edit.isVisible():
                    edit.load_payments()
                else:
                    self.open_edit_payments(from_add=True)

                QTimer.singleShot(0, self._position_payment_windows)

                if self.add_payment_dialog is not None:
                    self.add_payment_dialog.raise_()
                    self.add_payment_dialog.activateWindow()

            # CONNECT ONCE (here)
            self.add_payment_dialog.payment_added.connect(_on_payment_added)

        dlg = self.add_payment_dialog

        # Center on screen
        w = dlg.width()
        h = dlg.height()
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = avail.x() + (avail.width() - w) // 2
            y = avail.y() + (avail.height() - h) // 2
            dlg.move(x, y)

        dlg.show()
        dlg.raise_()
        dlg.activateWindow()


    def open_manage_payments(self, from_add: bool = False):
        if not self._has_perm("can_manage_payments"):
            self._deny_access("Manage Payments")
            return

        try:
            from payments.edit_payment import ManagePaymentsDialog
        except ImportError:
            print("Error: payments.edit_payment not found. Skipping Manage Payments dialog.")
            return

        # Reuse if already open
        if getattr(self, "manage_payments_dialog", None) is None or not self.manage_payments_dialog.isVisible():
            self.manage_payments_dialog = ManagePaymentsDialog(self.conn, self)

            # When it’s destroyed, clear the reference
            self.manage_payments_dialog.destroyed.connect(
                lambda: setattr(self, "manage_payments_dialog", None)
            )

            # When user closes it, reset sidebar selection to Dashboard
            if hasattr(self.manage_payments_dialog, "finished"):
                self.manage_payments_dialog.finished.connect(lambda *_: self._select_dashboard())

        self.manage_payments_dialog.show()

        # If user opened Manage explicitly, bring it to front.
        # If it was opened because Add saved, keep Add on top.
        if not from_add:
            self.manage_payments_dialog.raise_()
            self.manage_payments_dialog.activateWindow()


    def open_edit_payments(self, from_add: bool = False):
        if not self._has_perm("can_edit_payments"):
            self._deny_access("Edit Payments")
            return

        try:
            from payments.edit_payment import ManagePaymentsDialog
        except ImportError:
            print("Error: payments.edit_payment not found. Skipping Edit Payments dialog.")
            return

        if getattr(self, "edit_payments_dialog", None) is None or not self.edit_payments_dialog.isVisible():
            # IMPORTANT: mode="edit"
            self.edit_payments_dialog = ManagePaymentsDialog(self.conn, self, mode="edit")

            self.edit_payments_dialog.destroyed.connect(
                lambda: setattr(self, "edit_payments_dialog", None)
            )

            if hasattr(self.edit_payments_dialog, "finished"):
                self.edit_payments_dialog.finished.connect(lambda *_: self._select_dashboard())

        self.edit_payments_dialog.show()

        if not from_add:
            self.edit_payments_dialog.raise_()
            self.edit_payments_dialog.activateWindow()

        # Arrange side-by-side AFTER visible/sized
        QTimer.singleShot(0, self._position_payment_windows)


    # ----- Ledger -----

    def open_ledger(self):
        if not self._has_perm("can_ledger"):
            self._deny_access("Ledger")
            return

        # Create only once, keep reference
        if getattr(self, "ledger_dialog", None) is None:
            
            self.ledger_dialog = LedgerDialog(self.conn, parent=None, host=self)
            self.ledger_dialog.setWindowIcon(self.windowIcon())  # optional: match app icon



            # Make sure it behaves as a normal top-level window
            self.ledger_dialog.setWindowModality(Qt.NonModal)
            self.ledger_dialog.setWindowFlags(
                Qt.Window
                | Qt.WindowMinimizeButtonHint
                | Qt.WindowMaximizeButtonHint
                | Qt.WindowCloseButtonHint
            )

            # When user closes it, clear reference
            self.ledger_dialog.setAttribute(Qt.WA_DeleteOnClose, True)
            def _on_ledger_closed(*_):
                setattr(self, "ledger_dialog", None)
                self._select_dashboard()

            self.ledger_dialog.destroyed.connect(_on_ledger_closed)

        self.ledger_dialog.show()
        self.ledger_dialog.raise_()
        self.ledger_dialog.activateWindow()

    def open_settings(self):
        if not self._has_perm("can_settings"):
            self._deny_access("Settings")
            return

        dlg = SettingsDialog(self, self)
        dlg.exec()
        self._select_dashboard()

    # ----- app settings / backup -----

    def _load_app_settings(self):
        """Load backup settings from the app_settings table."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT backup_enabled, backup_dir, last_backup_date, report_title "
                "FROM app_settings WHERE id = 1"
            )

            row = cur.fetchone()
            if row:
                self.backup_enabled = bool(row["backup_enabled"])
                self.backup_dir = row["backup_dir"]
                self.last_backup_date = row["last_backup_date"]
                self.report_title = row["report_title"] or "AK ENTERPRISES"

        except Exception as e:
            print("Failed to load app settings:", e)

    def _save_app_settings(self):
        """Persist backup settings to the database."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO app_settings
                    (id, backup_enabled, backup_dir, last_backup_date, report_title)
                VALUES
                    (1, ?, ?, ?, ?)

                """,
            (
                1 if self.backup_enabled else 0,
                self.backup_dir,
                self.last_backup_date,
                getattr(self, "report_title", "AK ENTERPRISES"),
            ),

            )
            self.conn.commit()
        except Exception as e:
            print("Failed to save app settings:", e)


    def _setup_backup_schedule(self, initial_check: bool = False):
        """
        Start/stop the daily backup timer based on current settings.

        We only care about the date now: once per calendar day.
        """
        if not self.backup_enabled or not self.backup_dir:
            if self.backup_timer is not None:
                self.backup_timer.stop()
            return

        if self.backup_timer is None:
            self.backup_timer = QTimer(self)
            # check once per hour
            self.backup_timer.setInterval(60 * 60 * 1000)
            self.backup_timer.timeout.connect(self._check_backup_time)

        self.backup_timer.start()

        if initial_check:
            self._check_backup_time()

    def _check_backup_time(self):
        """
        Creates a backup once per calendar day.

        If:
          - backup is enabled
          - we haven't backed up yet for today
        then it calls _perform_backup().
        """
        from datetime import date

        if not self.backup_enabled or not self.backup_dir:
            return

        today_str = date.today().strftime("%Y-%m-%d")

        # already backed up today
        if self.last_backup_date == today_str:
            return

        # not backed up yet today -> create today's backup now
        self._perform_backup()

    def _perform_backup(self):
        """Copy the DB file into the backup folder with timestamp in name."""
        from datetime import datetime

        if not self.backup_enabled or not self.backup_dir:
            return

        try:
            now = datetime.now()
            fname = f"DB-backup_{now.strftime('%d_%m_%Y_%H%M%S')}.db"
            dest_path = os.path.join(self.backup_dir, fname)

            shutil.copy2(DB_PATH, dest_path)

            # remember that we've backed up today
            self.last_backup_date = now.strftime("%Y-%m-%d")
            self._save_app_settings()

            self.show_success_message("Database backup created.")
        except Exception as e:
            print("Backup failed:", e)
            self.show_success_message("Backup failed. See console for details.")


def main():
    app = QApplication(sys.argv)
    # For manual testing, pass some username; in real app, login_page passes it.
    window = MainWindow("admin")
    window.apply_theme()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
