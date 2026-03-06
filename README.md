# CashFlow POS System

CashFlow POS System is a Python-based desktop business management application built with **PySide6** and **SQLite**. It is designed for invoice handling, payment tracking, ledger reporting, and user-controlled access to business entities such as **Order Bookers**, **PJPs**, **Customers**, and **Users**.

The application supports both **development mode** (running directly from Python) and **Windows packaged mode** (running as an easy-to-use `.exe` build).

---

## Features

- **Secure login system** with user-level permissions
- **Role-based access control** for different modules
- **Invoice management**
- **Payment management**
- **Ledger and running balance reporting**
- **Customer management**
- **Order Booker management**
- **PJP management**
- **User management**
- **Light and dark theme support**
- **PDF export / print workflows**
- **SQLite local database**
- **PyInstaller-based Windows `.exe` packaging**

---

## Modules

The system is organized into multiple functional modules:

- **Login Page**
- **Dashboard**
- **Invoices**
- **Payments**
- **Ledger**
- **Customers**
- **Order Bookers**
- **PJPs**
- **Users**
- **Settings**

---

## Project Structure

```text
.
│   cashflow_dashboard.py
│   command.txt
│   db.py
│   login_page.py
│   requirements.txt
│   seed_ledger_perf_data.py
│   settings_dialog.py
│
├── customer/
│   ├── add_customer.py
│   ├── edit_customer.py
│   └── __init__.py
│
├── icons/
│   └── *.svg
│
├── invoices/
│   ├── add_invoice.py
│   ├── edit_invoice.py
│   └── __init__.py
│
├── ledger/
│   ├── ledger_dialog.py
│   └── __init__.py
│
├── order_booker/
│   ├── add_order_booker.py
│   ├── edit_order_booker.py
│   └── __init__.py
│
├── payments/
│   ├── add_payment.py
│   ├── edit_payment.py
│   └── __init__.py
│
├── pjp/
│   ├── add_pjp.py
│   ├── edit_pjp.py
│   └── __init__.py
│
├── POS Others/
│   ├── generate_svg.py
│   ├── import_universe_store.py
│   └── make_black_icons.py
│
├── tools/
│   └── SumatraPDF.exe
│
└── users/
    ├── add_user.py
    ├── edit_user.py
    └── __init__.py
```

---

## Tech Stack

- **Python**
- **PySide6** for the desktop GUI
- **SQLite** for local data storage
- **ReportLab** for PDF generation/reporting
- **PyInstaller** for Windows executable packaging

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/alyan-ahmad/CashIn-POS.git
cd CashIn-POS
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install requirements

Install all required dependencies using:

```bash
pip install -r requirements.txt
```

This command installs the Python packages required to run the application from source code.

If needed, the common core packages for this project may include:

```bash
pip install PySide6 reportlab pyinstaller
```

> It is recommended to always use `requirements.txt` so all dependencies stay consistent with the repository.

---

## Running the Project from Source

After installing the requirements, run the application with:

```bash
python login_page.py
```

This starts the login page and then opens the main dashboard after successful authentication.

## Default Login

On first run, the system seeds a default administrator account:

- **Username:** `admin`
- **Password:** `admin`

> For security, change the default credentials after the first login.

---

## Building the Windows `.exe`

This repository includes a file named **`command.txt`** that contains the PowerShell commands used to package the application into a Windows executable.

The goal of this build process is to make the software easy to use for end users who do not want to run Python manually.

---


## Database Overview

The project uses a local SQLite database stored in the `data/` directory.

### Main tables

- `users`
- `order_bookers`
- `pjps`
- `customers`
- `invoices`
- `payments`
- `app_settings`
- `invoice_meta`
- `payment_meta`

### Relationships

- One **Order Booker** can have many **PJPs**
- One **PJP** can have many **Customers**
- One **Customer** can have many **Invoices**
- One **Invoice** can have many **Payments**

---

## Printing and Reporting

The system includes ledger/reporting workflows and supports desktop-friendly output operations.

Typical supported actions include:

- Invoice PDF generation
- Pending report generation
- ZIP export of grouped files/documents
- Printing support in the packaged Windows application

### SumatraPDF helper

The file `tools/SumatraPDF.exe` is included in the release structure to make PDF printing/report workflows easier in the `.exe` version.

---

## Development Notes

This project is well suited for:

- local desktop business deployment
- distributor or sales workflows
- invoice and payment management
- ledger and customer-account reporting

## License

This project is licensed under the MIT License. You are free to use, modify, distribute, and adapt this software for personal, academic, and commercial purposes, provided that the original copyright and license notice are included in all copies or substantial portions of the software.

