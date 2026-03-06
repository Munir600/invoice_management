import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFrame,
    QLabel, QLineEdit, QPushButton, QSpacerItem, QSizePolicy, QMessageBox
)
from PySide6.QtGui import QFont, QCursor
from PySide6.QtCore import Qt, QTimer

# Import the dashboard window
from cashflow_dashboard import MainWindow as DashboardWindow
from db import get_connection, hash_password  # Reuse from db.py


# ----------------- LOGIN QSS (LIGHT & DARK) -----------------

PRIMARY_COLOR_LIGHT = "rgb(37, 79, 167)"
PRIMARY_COLOR_DARK = "#1d4ed8"

LIGHT_LOGIN_QSS = f"""
* {{
    font-family: "Geist", system-ui, sans-serif;
    font-size: 14px;
}}

QMainWindow {{
    background-color: #f4f5fb;
}}

QFrame#LoginCard {{
    background-color: #ffffff;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
}}

QLabel#LoginTitle {{
    font-size: 24px;
    font-weight: 700;
    color: #0f172a;
}}

QLabel#LoginSubtitle {{
    color: #64748b;
    font-size: 14px;
}}

QLabel#LogoIcon {{
    background-color: #1d4ed8;
    color: white;
    border-radius: 999px;
    padding: 18px 22px;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 10px;
}}

QLineEdit {{
    padding: 12px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 14px;
    color: #0f172a;
    background-color: #ffffff;
}}

QLineEdit:focus {{
    border: 1px solid {PRIMARY_COLOR_LIGHT};
}}

QPushButton#SignInButton {{
    background-color: {PRIMARY_COLOR_LIGHT};
    color: white;
    border-radius: 8px;
    padding: 12px 20px;
    border: none;
    font-weight: 600;
    font-size: 16px;
    margin-top: 20px;
}}

QPushButton#SignInButton:hover {{
    background-color: rgb(30, 64, 140);
}}
"""

DARK_LOGIN_QSS = f"""
* {{
    font-family: "Geist", system-ui, sans-serif;
    font-size: 14px;
}}

QMainWindow {{
    background-color: #020617;
}}

QFrame#LoginCard {{
    background-color: #1E1E1E;      /* same as dashboard card */
    border-radius: 12px;
    border: 1px solid #1A1A1A;      /* same border as dashboard card */
}}

QLabel#LoginTitle {{
    font-size: 24px;
    font-weight: 700;
    color: #f9fafb;
}}

QLabel#LoginSubtitle {{
    color: #9ca3af;
    font-size: 14px;
}}

QLabel#LogoIcon {{
    background-color: #1d4ed8;
    color: white;
    border-radius: 999px;
    padding: 18px 22px;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 10px;
}}

QLineEdit {{
    padding: 12px;
    border: 1px solid #374151;      /* slightly lighter so border is visible */
    border-radius: 8px;
    font-size: 14px;
    color: #e5e7eb;
    background-color: #1E1E1E;      /* keep same as card/sidebar */
}}


QLineEdit:focus {{
    border: 1px solid {PRIMARY_COLOR_DARK};
}}

QPushButton#SignInButton {{
    background-color: {PRIMARY_COLOR_DARK};
    color: white;
    border-radius: 8px;
    padding: 12px 20px;
    border: none;
    font-weight: 600;
    font-size: 16px;
    margin-top: 20px;
}}

QPushButton#SignInButton:hover {{
    background-color: rgb(30, 64, 140);
}}
"""


# ----------------- LOGIN WINDOW -----------------

class LoginWindow(QMainWindow):
    """
    - Shows centered login card that matches the screenshots.
    - Uses SQLite users table with admin/admin as default superuser.
    - Does NOT have its own theme toggle.
      Theme is controlled by the Dashboard only.
    - When dashboard logs out, this window is shown again and
      theme is matched to the dashboard's current dark_mode.
    """

    def __init__(self, dark_mode: bool = False):
        super().__init__()
        self.setWindowTitle("POS Cash Management Login")

        # Theme state (shared with dashboard)
        self.dark_mode = dark_mode

        # Reference to dashboard window
        self.dashboard: DashboardWindow | None = None

        # inputs
        self.username_input: QLineEdit | None = None
        self.password_input: QLineEdit | None = None
        self.sign_in_button: QPushButton | None = None

        self.setup_ui()
        self._setup_shortcuts()
        self.apply_theme()
        self.showMaximized()

    # ---- UI setup ----


    def _focus_username(self):
        if not self.username_input:
            return
        # Run after the window is shown/activated so it always wins focus
        QTimer.singleShot(0, self.username_input.setFocus)


    def showEvent(self, event):
        super().showEvent(event)
        self._focus_username()



    def setup_ui(self):
        central_widget = QWidget()
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setAlignment(Qt.AlignCenter)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # main vertical stack
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignCenter)

        # Logo (blue circle)
        logo_icon = QLabel("⌘")
        logo_icon.setObjectName("LogoIcon")
        logo_icon.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo_icon, alignment=Qt.AlignCenter)

        # Title / subtitle
        title = QLabel("POS Cash Management")
        title.setObjectName("LoginTitle")

        subtitle = QLabel("Sign in to your account")
        subtitle.setObjectName("LoginSubtitle")

        main_layout.addWidget(title, alignment=Qt.AlignCenter)
        main_layout.addWidget(subtitle, alignment=Qt.AlignCenter)
        main_layout.addSpacing(20)

        # Form card
        form_card = QFrame()
        form_card.setObjectName("LoginCard")
        form_card.setFixedWidth(420)

        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(10)

        # Username
        form_layout.addWidget(self._create_label("Username"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        form_layout.addWidget(self.username_input)

        # Password
        form_layout.addWidget(self._create_label("Password"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        form_layout.addWidget(self.password_input)

        # Sign in button
        self.sign_in_button = QPushButton("→  Sign In")
        self.sign_in_button.setObjectName("SignInButton")
        self.sign_in_button.setCursor(QCursor(Qt.PointingHandCursor))  # pointer cursor
        self.sign_in_button.clicked.connect(self.handle_login)
        self.sign_in_button.setDefault(True)  # Enter triggers this by default
        form_layout.addWidget(self.sign_in_button)

        # attach form card
        main_layout.addWidget(form_card, alignment=Qt.AlignCenter)

        # top & bottom spacers
        outer_layout.addSpacerItem(
            QSpacerItem(20, 50, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        outer_layout.addLayout(main_layout)
        outer_layout.addSpacerItem(
            QSpacerItem(20, 50, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self.setCentralWidget(central_widget)

    def _create_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Arial", 10, QFont.DemiBold))
        label.setObjectName("FormLabel")
        return label

    def _setup_shortcuts(self):
        """Wire Enter key behaviour for keyboard-only login."""
        # Enter in username -> move to password
        if self.username_input and self.password_input:
            self.username_input.returnPressed.connect(self.password_input.setFocus)

        # Enter in password -> perform login
        if self.password_input:
            self.password_input.returnPressed.connect(self.handle_login)


    # ---- Theme handling (no button, just called based on dashboard state) ----

    def apply_theme(self):
        app = QApplication.instance()
        if self.dark_mode:
            app.setStyleSheet(DARK_LOGIN_QSS)
            for label in self.findChildren(QLabel, "FormLabel"):
                label.setStyleSheet("color: #e5e7eb;")
        else:
            app.setStyleSheet(LIGHT_LOGIN_QSS)
            for label in self.findChildren(QLabel, "FormLabel"):
                label.setStyleSheet("color: #0f172a;")

    # ---- Login / dashboard wiring ----

    def handle_login(self):
        username = (self.username_input.text().strip()
                    if self.username_input else "")
        password = (self.password_input.text()
                    if self.password_input else "")

        if not username or not password:
            QMessageBox.warning(self, "Missing Data",
                                "Please enter both username and password.")
            return

        ok, is_superuser = self.check_credentials(username, password)
        if not ok:
            QMessageBox.warning(self, "Login Failed",
                                "Invalid username or password.")
            return

        # open dashboard
        self.open_dashboard(username)

    def check_credentials(self, username: str, password: str):
        """
        Returns (ok, is_superuser)
        ok          -> True if username/password correct
        is_superuser -> True if that user has is_superuser=1
        """
        conn = get_connection()  # Reuse from db.py (creates schema if needed)
        cur = conn.cursor()
        cur.execute(
            "SELECT password_hash, is_superuser FROM users WHERE username = ?", (username,)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return False, False

        stored_hash, is_super = row
        if stored_hash != hash_password(password):
            return False, False

        return True, bool(is_super)

    def open_dashboard(self, username: str):
        self.dashboard = DashboardWindow(username)

        # listen for logout (only this)
        try:
            self.dashboard.logout_requested.connect(self.on_dashboard_logout)
        except AttributeError:
            pass

        self.dashboard.show()
        self.hide()


    def on_dashboard_logout(self):
        """Called when dashboard emits logout_requested."""
        if self.dashboard is not None:
            try:
                self.dark_mode = self.dashboard.dark_mode
            except Exception:
                pass

            try:
                self.dashboard.logout_requested.disconnect(self.on_dashboard_logout)
            except Exception:
                pass

            self.dashboard.close()
            self.dashboard = None

        # reset login fields
        if self.username_input:
            self.username_input.clear()
        if self.password_input:
            self.password_input.clear()

        # re-apply theme based on last dashboard state
        self.apply_theme()
        self.show()
        self.raise_()
        self.activateWindow()
        self._focus_username()



# ----------------- ENTRY POINT -----------------

def main():
    app = QApplication(sys.argv)
    conn = get_connection()
    conn.close()  
    window = LoginWindow(dark_mode=False)  # initial theme: light
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
