import sqlite3
import os
from datetime import datetime

DB_FILE = "hr_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            email TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')

    # Mock Employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            email TEXT PRIMARY KEY,
            pto_balance INTEGER NOT NULL
        )
    ''')

    # Mock Leave Requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')

    # Seed mock data if empty
    cursor.execute('SELECT COUNT(*) FROM employees')
    if cursor.fetchone()[0] == 0:
        # Default user with 15 days PTO
        mock_email = os.getenv("EMAIL_USER", "employee@example.com")
        cursor.execute('INSERT INTO employees (email, pto_balance) VALUES (?, ?)', (mock_email, 15))
        
        # Test employee
        cursor.execute('INSERT INTO employees (email, pto_balance) VALUES (?, ?)', ("mridul@example.com", 20))

    conn.commit()
    conn.close()


def log_interaction(email: str, question: str, answer: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    tz = datetime.now().isoformat()
    cursor.execute(
        'INSERT INTO analytics (timestamp, email, question, answer) VALUES (?, ?, ?, ?)',
        (tz, email, question, answer)
    )
    conn.commit()
    conn.close()


def get_pto_balance(email: str) -> str:
    """
    Retrieves the remaining PTO balance for a given email address.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT pto_balance FROM employees WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return f"Employee {email} has {row[0]} PTO days remaining."
    return f"We could not find an employee record for {email}. Please contact HR directly."


def submit_leave_request(email: str, start_date: str, end_date: str) -> str:
    """
    Submits a leave request for the employee into the database.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # First check if they have a mock employee record (to simulate validation)
    cursor.execute('SELECT pto_balance FROM employees WHERE email = ?', (email,))
    if not cursor.fetchone():
        conn.close()
        return f"We could not find an employee record for {email}. Cannot submit leave request."

    cursor.execute(
        'INSERT INTO leave_requests (email, start_date, end_date, status) VALUES (?, ?, ?, ?)',
        (email, start_date, end_date, 'PENDING')
    )
    conn.commit()
    conn.close()
    
    return f"Leave request from {start_date} to {end_date} has been successfully submitted and is PENDING approval."

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
