# db.py
import os
import sqlite3
import hashlib
import sys


def _get_app_data_dir() -> str:
    """
    Return a writable folder for the app data.

    - In development: inside the project folder (./data)
    - In a frozen EXE (PyInstaller): next to the .exe in a "data" folder
    """
    if getattr(sys, "frozen", False):
        # Running from PyInstaller EXE
        base_dir = os.path.dirname(sys.executable)
    else:
        # Normal Python run
        base_dir = os.path.dirname(os.path.abspath(__file__))

    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# Path to your SQLite file (NOT inside the exe, but in a normal folder)
DB_PATH = os.path.join(_get_app_data_dir(), "cashflow.db")


def hash_password(password: str) -> str:
    """Very simple SHA-256 hash used for the seeded admin user."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection() -> sqlite3.Connection:
    """Return a connection with the schema ensured + admin user seeded."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enable foreign key constraints in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")

    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ---------- USERS ----------
    cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        username         TEXT UNIQUE NOT NULL,
        password_hash    TEXT NOT NULL,
        is_superuser     INTEGER NOT NULL DEFAULT 0,

        -- OLD (keep for backward-compat if other code still uses them)
        can_invoices     INTEGER NOT NULL DEFAULT 0,
        can_payments     INTEGER NOT NULL DEFAULT 0,
        can_order_booker INTEGER NOT NULL DEFAULT 0,
        can_pjps         INTEGER NOT NULL DEFAULT 0,
        can_customers    INTEGER NOT NULL DEFAULT 0,

        -- NEW granular permissions
        can_add_invoices      INTEGER NOT NULL DEFAULT 0,
        can_edit_invoices     INTEGER NOT NULL DEFAULT 0,
        can_manage_invoices   INTEGER NOT NULL DEFAULT 0,

        can_add_payments      INTEGER NOT NULL DEFAULT 0,
        can_edit_payments     INTEGER NOT NULL DEFAULT 0,
        can_manage_payments   INTEGER NOT NULL DEFAULT 0,

        can_add_order_booker  INTEGER NOT NULL DEFAULT 0,
        can_edit_order_booker INTEGER NOT NULL DEFAULT 0,

        can_add_pjp           INTEGER NOT NULL DEFAULT 0,
        can_edit_pjp          INTEGER NOT NULL DEFAULT 0,

        can_add_customer      INTEGER NOT NULL DEFAULT 0,
        can_edit_customer     INTEGER NOT NULL DEFAULT 0,

        can_ledger            INTEGER NOT NULL DEFAULT 0,
        can_settings          INTEGER NOT NULL DEFAULT 0

    )
    """)

    

    # For OLD databases: add missing permission columns
    cur.execute("PRAGMA table_info(users)")
    user_cols = {r[1] for r in cur.fetchall()}

    new_cols = [
        "can_add_invoices", "can_edit_invoices", "can_manage_invoices",
        "can_add_payments", "can_edit_payments", "can_manage_payments",
        "can_add_order_booker", "can_edit_order_booker",
        "can_add_pjp", "can_edit_pjp",
        "can_add_customer", "can_edit_customer",
        "can_ledger",
        "can_settings",
    ]

    for c in new_cols:
        if c not in user_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {c} INTEGER NOT NULL DEFAULT 0")

    
    

    # ---------- ORDER BOOKERS ----------
    # One Order Booker -> many PJPs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_bookers (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            contact   TEXT NOT NULL,
            address   TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # ---------- PJPs ----------
    # Each PJP belongs to one Order Booker
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pjps (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            order_booker_id  INTEGER NOT NULL,
            pjp_name         TEXT NOT NULL,
            day_of_week      TEXT NOT NULL,
            is_active        INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (order_booker_id)
                REFERENCES order_bookers(id)
                ON DELETE RESTRICT
                ON UPDATE CASCADE
        )
        """
    )

    # ---------- CUSTOMERS ----------
    # Each Customer belongs to one PJP
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            pjp_id    INTEGER NOT NULL,
            name      TEXT NOT NULL,
            contact   TEXT NOT NULL,
            address   TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (pjp_id)
                REFERENCES pjps(id)
                ON DELETE RESTRICT
                ON UPDATE CASCADE
        )
        """
    )

    # ---------- SEED ADMIN USER ----------
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                is_superuser,
                can_invoices,
                can_payments,
                can_order_booker,
                can_pjps,
                can_customers,

                can_add_invoices,
                can_edit_invoices,
                can_manage_invoices,

                can_add_payments,
                can_edit_payments,
                can_manage_payments,

                can_add_order_booker,
                can_edit_order_booker,

                can_add_pjp,
                can_edit_pjp,

                can_add_customer,
                can_edit_customer,

                can_ledger,
                can_settings
            )
            VALUES (
                ?, ?, 1,
                1, 1, 1, 1, 1,
                1, 1, 1,
                1, 1, 1,
                1, 1,
                1, 1,
                1, 1,
                1, 1
            )
            """,
            ("admin", hash_password("admin")),
        )


    # Ensure admin always has all permissions (even if admin already existed)
    cur.execute(
        """
        UPDATE users SET
        can_add_invoices=1, can_edit_invoices=1, can_manage_invoices=1,
        can_add_payments=1, can_edit_payments=1, can_manage_payments=1,
        can_add_order_booker=1, can_edit_order_booker=1,
        can_add_pjp=1, can_edit_pjp=1,
        can_add_customer=1, can_edit_customer=1,
        can_ledger=1, can_settings=1
        WHERE username='admin'
        """
    )


    # --- invoices ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_code INTEGER NOT NULL UNIQUE CHECK(typeof(invoice_code) = 'integer'),
            invoice_date    TEXT    NOT NULL,
            order_booker_id INTEGER NOT NULL,
            pjp_id          INTEGER NOT NULL,
            customer_id     INTEGER NOT NULL,
            amount          REAL    NOT NULL,
            in_ledger       INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_booker_id) REFERENCES order_bookers(id),
            FOREIGN KEY(pjp_id)        REFERENCES pjps(id),
            FOREIGN KEY(customer_id)   REFERENCES customers(id)
        )
        """
    )

    # For OLD databases: add column *without* default
    cur.execute("PRAGMA table_info(invoices)")
    inv_cols = [r[1] for r in cur.fetchall()]
    if "created_at" not in inv_cols:
        cur.execute(
            "ALTER TABLE invoices ADD COLUMN created_at TEXT"
        )
        # Optional: initialize from invoice_date
        cur.execute(
            "UPDATE invoices SET created_at = invoice_date || ' 00:00:00' WHERE created_at IS NULL"
        )

    # --- payments ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_code INTEGER NOT NULL UNIQUE CHECK(typeof(payment_code) = 'integer'),
            payment_date TEXT    NOT NULL,
            invoice_id   INTEGER NOT NULL,
            amount       REAL    NOT NULL,
            in_ledger    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id)
        )
        """
    )

    # For OLD databases: add column *without* default
    cur.execute("PRAGMA table_info(payments)")
    pay_cols = [r[1] for r in cur.fetchall()]
    if "created_at" not in pay_cols:
        cur.execute(
            "ALTER TABLE payments ADD COLUMN created_at TEXT"
        )
        # Optional: initialize from payment_date
        cur.execute(
            "UPDATE payments SET created_at = payment_date || ' 00:00:00' WHERE created_at IS NULL"
        )


    # ---------- APP SETTINGS ----------
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            backup_enabled  INTEGER NOT NULL DEFAULT 0,
            backup_dir      TEXT,
            last_backup_date TEXT,
            report_title TEXT
        )
        """

    )

    cur.execute("PRAGMA table_info(app_settings)")
    cols = [r[1] for r in cur.fetchall()]
    if "backup_enabled" not in cols:
        cur.execute("ALTER TABLE app_settings ADD COLUMN backup_enabled INTEGER NOT NULL DEFAULT 0")
    if "backup_dir" not in cols:
        cur.execute("ALTER TABLE app_settings ADD COLUMN backup_dir TEXT")
    if "last_backup_date" not in cols:
        cur.execute("ALTER TABLE app_settings ADD COLUMN last_backup_date TEXT")
    if "report_title" not in cols:
        cur.execute("ALTER TABLE app_settings ADD COLUMN report_title TEXT")


    # Ensure exactly one row with id=1 exists
    cur.execute(
        """
        INSERT OR IGNORE INTO app_settings (id, backup_enabled, backup_dir, last_backup_date)
        VALUES (1, 0, NULL, NULL)
        """
    )

    cur.execute(
    """
    UPDATE app_settings
    SET report_title = COALESCE(report_title, 'AK ENTERPRISES')
    WHERE id = 1
    """
)


    # ---------- INVOICE META (for invoice number sequence) ----------
    # This table keeps track of the last invoice number used for invoice codes.
    # It lets us always move forward (no reuse), even if invoices are deleted.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS invoice_meta (
            key   TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
        """
    )

    # Seed the counter row used for invoice numbering
    cur.execute(
        """
        INSERT OR IGNORE INTO invoice_meta (key, value)
        VALUES ('invoice_last_number', 0)
        """
    )

    cur.execute(
        """
        UPDATE invoice_meta
        SET value = COALESCE(
            (
                -- invoice_code is stored as a pure INTEGER (no prefixes)
                SELECT MAX(CAST(invoice_code AS INTEGER))
                FROM invoices
                WHERE invoice_code IS NOT NULL
            ),
            0
        )
        WHERE key = 'invoice_last_number'
          AND value = 0
        """
    )

    # ---------- PAYMENT META (for payment number sequence) ----------
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_meta (
            key   TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
        """
    )

    # Seed the counter row used for payment numbering
    cur.execute(
        """
        INSERT OR IGNORE INTO payment_meta (key, value)
        VALUES ('payment_last_number', 0)
        """
    )

    # Sync counter from existing payments (only if still 0)
    # payment_code is a pure INTEGER sequence: 1, 2, 3, .....
    cur.execute(
        """
        UPDATE payment_meta
        SET value = COALESCE(
            (
                                -- payment_code is stored as a pure INTEGER (no prefixes)
                SELECT MAX(CAST(payment_code AS INTEGER))
                FROM payments
                WHERE payment_code IS NOT NULL
            ),
            0
        )
        WHERE key = 'payment_last_number'
        AND value = 0
        """
    )


    # Fast filters for ledger
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_inledger_date ON invoices(in_ledger, invoice_date, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_inledger_date ON payments(in_ledger, payment_date, created_at)")

    # Fast joins / filters
    cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_customer_id ON invoices(customer_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_pjp_id ON invoices(pjp_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pjps_order_booker_id ON pjps(order_booker_id)")

    # Dropdown/filter performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_bookers_active_name ON order_bookers(is_active, name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pjps_active_ob_name ON pjps(is_active, order_booker_id, pjp_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_customers_active_pjp_name ON customers(is_active, pjp_id, name)")



    conn.commit()
