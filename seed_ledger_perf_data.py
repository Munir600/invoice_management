"""
seed_ledger_perf_data.py
------------------------
Creates one Order Booker + PJP + Customer, then inserts invoices and payments
into the SQLite DB so the Ledger view shows ~5000 rows (transactions).

Default: 2500 invoices + 2500 payments = 5000 ledger rows.

Run:
  python seed_ledger_perf_data.py

Optional:
  python seed_ledger_perf_data.py --rows 5000
  python seed_ledger_perf_data.py --rows 8000 --ratio 0.5   # 50% invoices, 50% payments
  python seed_ledger_perf_data.py --cleanup                # remove previously seeded test data
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from db import get_connection  # uses DB_PATH and ensures schema exists


SEED_OB_NAME = "Perf Test OB"
SEED_PJP_NAME = "Perf Test PJP"
SEED_CUSTOMER_NAME = "Perf Test Customer"


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_or_create_seed_entities(conn):
    cur = conn.cursor()

    # Order Booker
    cur.execute("SELECT id FROM order_bookers WHERE name = ? LIMIT 1", (SEED_OB_NAME,))
    r = cur.fetchone()
    if r:
        ob_id = r["id"]
    else:
        cur.execute(
            """
            INSERT INTO order_bookers (name, contact, address, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (SEED_OB_NAME, "0300-0000000", "Perf Street, Test City"),
        )
        ob_id = cur.lastrowid

    # PJP
    cur.execute(
        """
        SELECT id FROM pjps
        WHERE order_booker_id = ? AND pjp_name = ?
        LIMIT 1
        """,
        (ob_id, SEED_PJP_NAME),
    )
    r = cur.fetchone()
    if r:
        pjp_id = r["id"]
    else:
        cur.execute(
            """
            INSERT INTO pjps (order_booker_id, pjp_name, day_of_week, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (ob_id, SEED_PJP_NAME, "Monday"),
        )
        pjp_id = cur.lastrowid

    # Customer
    cur.execute(
        """
        SELECT id FROM customers
        WHERE pjp_id = ? AND name = ?
        LIMIT 1
        """,
        (pjp_id, SEED_CUSTOMER_NAME),
    )
    r = cur.fetchone()
    if r:
        customer_id = r["id"]
    else:
        cur.execute(
            """
            INSERT INTO customers (pjp_id, name, contact, address, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (pjp_id, SEED_CUSTOMER_NAME, "0311-1111111", "Perf Lane, Test City"),
        )
        customer_id = cur.lastrowid

    return ob_id, pjp_id, customer_id


def _get_next_sequence(conn, table: str) -> int:
    """
    Reads the meta table (invoice_meta/payment_meta) to find the next integer code.
    Falls back to MAX() if meta row missing (shouldn't happen because db.py seeds it).
    """
    cur = conn.cursor()
    if table == "invoice":
        cur.execute("SELECT value FROM invoice_meta WHERE key='invoice_last_number'")
        r = cur.fetchone()
        if r and r["value"] is not None:
            return int(r["value"]) + 1
        cur.execute("SELECT COALESCE(MAX(CAST(invoice_code AS INTEGER)), 0) AS m FROM invoices")
        return int(cur.fetchone()["m"]) + 1

    if table == "payment":
        cur.execute("SELECT value FROM payment_meta WHERE key='payment_last_number'")
        r = cur.fetchone()
        if r and r["value"] is not None:
            return int(r["value"]) + 1
        cur.execute("SELECT COALESCE(MAX(CAST(payment_code AS INTEGER)), 0) AS m FROM payments")
        return int(cur.fetchone()["m"]) + 1

    raise ValueError("table must be 'invoice' or 'payment'")


def _update_sequence(conn, table: str, last_value: int) -> None:
    cur = conn.cursor()
    if table == "invoice":
        cur.execute(
            "UPDATE invoice_meta SET value = ? WHERE key='invoice_last_number'",
            (int(last_value),),
        )
    elif table == "payment":
        cur.execute(
            "UPDATE payment_meta SET value = ? WHERE key='payment_last_number'",
            (int(last_value),),
        )
    else:
        raise ValueError("table must be 'invoice' or 'payment'")


def cleanup_seed_data(conn) -> None:
    """
    Removes only the seeded Perf Test rows (invoices, payments, customer, pjp, order_booker).
    Safe to run repeatedly.
    """
    cur = conn.cursor()

    # Find seeded IDs
    cur.execute("SELECT id FROM order_bookers WHERE name = ? LIMIT 1", (SEED_OB_NAME,))
    ob = cur.fetchone()
    if not ob:
        print("No seeded Order Booker found. Nothing to clean.")
        return

    ob_id = ob["id"]

    cur.execute(
        "SELECT id FROM pjps WHERE order_booker_id = ? AND pjp_name = ? LIMIT 1",
        (ob_id, SEED_PJP_NAME),
    )
    pjp = cur.fetchone()
    pjp_id = pjp["id"] if pjp else None

    customer_id = None
    if pjp_id is not None:
        cur.execute(
            "SELECT id FROM customers WHERE pjp_id = ? AND name = ? LIMIT 1",
            (pjp_id, SEED_CUSTOMER_NAME),
        )
        cust = cur.fetchone()
        customer_id = cust["id"] if cust else None

    # Delete payments that belong to invoices under this customer/PJP
    if customer_id is not None:
        cur.execute("SELECT id FROM invoices WHERE customer_id = ?", (customer_id,))
        inv_ids = [r["id"] for r in cur.fetchall() or []]
        if inv_ids:
            # chunk deletes for SQLite parameter limit
            for i in range(0, len(inv_ids), 900):
                chunk = inv_ids[i : i + 900]
                qmarks = ",".join("?" for _ in chunk)
                cur.execute(f"DELETE FROM payments WHERE invoice_id IN ({qmarks})", chunk)
            # delete invoices
            cur.execute("DELETE FROM invoices WHERE customer_id = ?", (customer_id,))

    # Delete customer, pjp, order booker (in that order to satisfy FKs)
    if customer_id is not None:
        cur.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    if pjp_id is not None:
        cur.execute("DELETE FROM pjps WHERE id = ?", (pjp_id,))
    cur.execute("DELETE FROM order_bookers WHERE id = ?", (ob_id,))

    conn.commit()
    print("Seed data removed.")


def seed_ledger_rows(conn, total_rows: int, invoice_ratio: float) -> None:
    """
    Inserts invoices first, then payments, all with in_ledger=1.
    total_rows = invoices + payments.
    invoice_ratio = fraction of total_rows that are invoices (0..1).
    """
    if total_rows <= 0:
        raise ValueError("--rows must be > 0")
    if not (0.0 < invoice_ratio < 1.0):
        raise ValueError("--ratio must be between 0 and 1 (exclusive)")

    n_invoices = int(round(total_rows * invoice_ratio))
    n_payments = total_rows - n_invoices
    if n_invoices == 0 or n_payments == 0:
        raise ValueError("ratio produced 0 invoices or 0 payments; choose a different --ratio")

    # Speed pragmas (OK for local perf test)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = OFF;")

    ob_id, pjp_id, customer_id = _get_or_create_seed_entities(conn)

    invoice_code = _get_next_sequence(conn, "invoice")
    payment_code = _get_next_sequence(conn, "payment")

    start_date = datetime.now().date() - timedelta(days=30)
    base_dt = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    # -------------------------
    # Insert invoices (bulk)
    # -------------------------
    invoices = []
    for i in range(n_invoices):
        code = invoice_code + i
        inv_date = (start_date + timedelta(days=(i % 30))).strftime("%Y-%m-%d")
        created_at = (base_dt + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        amount = float(random.randint(500, 5000))  # PKR-ish
        invoices.append(
            (code, inv_date, ob_id, pjp_id, customer_id, amount, 1, created_at)
        )

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO invoices (
            invoice_code, invoice_date, order_booker_id, pjp_id, customer_id,
            amount, in_ledger, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        invoices,
    )

    last_invoice_code = invoice_code + n_invoices - 1

    # Fetch invoice ids for the inserted range
    cur.execute(
        """
        SELECT id, invoice_code, amount, invoice_date
        FROM invoices
        WHERE invoice_code BETWEEN ? AND ?
        ORDER BY invoice_code ASC
        """,
        (invoice_code, last_invoice_code),
    )
    inv_rows = cur.fetchall()
    if not inv_rows or len(inv_rows) != n_invoices:
        raise RuntimeError("Inserted invoices count mismatch; cannot proceed to payments.")

    # -------------------------
    # Insert payments (bulk)
    # -------------------------
    payments = []
    for j in range(n_payments):
        code = payment_code + j

        # Cycle through invoices so payments distribute evenly
        inv = inv_rows[j % len(inv_rows)]
        inv_id = inv["id"]
        inv_amount = float(inv["amount"] or 0)

        # Payment date on/after invoice date
        try:
            inv_date_dt = datetime.strptime(inv["invoice_date"], "%Y-%m-%d")
        except Exception:
            inv_date_dt = datetime.now()
        pay_date = (inv_date_dt + timedelta(days=(j % 7))).strftime("%Y-%m-%d")

        # partial-to-full payment amount (keep >0)
        amt = max(1.0, round(inv_amount * random.uniform(0.2, 1.0), 2))

        created_at = (base_dt + timedelta(seconds=n_invoices + j)).strftime("%Y-%m-%d %H:%M:%S")

        payments.append((code, pay_date, inv_id, amt, 1, created_at))

    cur.executemany(
        """
        INSERT INTO payments (
            payment_code, payment_date, invoice_id, amount, in_ledger, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        payments,
    )

    last_payment_code = payment_code + n_payments - 1

    # Update meta sequences so your normal UI-generated codes continue correctly
    _update_sequence(conn, "invoice", last_invoice_code)
    _update_sequence(conn, "payment", last_payment_code)

    conn.commit()

    # Report counts
    cur.execute("SELECT COUNT(*) AS c FROM invoices WHERE in_ledger = 1")
    inv_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM payments WHERE in_ledger = 1")
    pay_count = cur.fetchone()["c"]

    print("Inserted:")
    print(f"  Order Booker: {SEED_OB_NAME}")
    print(f"  PJP:          {SEED_PJP_NAME}")
    print(f"  Customer:     {SEED_CUSTOMER_NAME}")
    print(f"  Invoices:     {n_invoices} (ledger invoices total now: {inv_count})")
    print(f"  Payments:     {n_payments} (ledger payments total now: {pay_count})")
    print(f"  Ledger rows added (transactions): {n_invoices + n_payments}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=5000, help="Total ledger rows (invoices + payments). Default 5000.")
    ap.add_argument("--ratio", type=float, default=0.5, help="Invoice ratio (0..1). Default 0.5 (half invoices).")
    ap.add_argument("--cleanup", action="store_true", help="Remove previously seeded Perf Test data and exit.")
    args = ap.parse_args()

    conn = get_connection()
    try:
        if args.cleanup:
            cleanup_seed_data(conn)
            return

        seed_ledger_rows(conn, total_rows=args.rows, invoice_ratio=args.ratio)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
