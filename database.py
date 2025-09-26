import hashlib
import os
import sqlite3
from datetime import datetime
from typing import Optional
 
import pandas as pd
 
# SQLite database file
DB_NAME = 'client_queries.db'
 
 
def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_NAME)
 
 
def create_tables() -> None:
    conn = get_connection()
    cur = conn.cursor()
 
    # Passwords are stored in hashed.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
 
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            query_id TEXT PRIMARY KEY,
            mail_id TEXT,
            mobile_number TEXT,
            query_heading TEXT,
            query_description TEXT,
            status TEXT,
            query_created_time TEXT,
            query_closed_time TEXT,
            image BLOB
        )
        """
    )
 
    conn.commit()
    conn.close()
 
 
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()
 
def add_user(username: str, password: str, role: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute(
        "INSERT OR IGNORE INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
        (username, hashed, role),
    )
    conn.commit()
    conn.close()
 
 
def create_default_users() -> None:
    # Create default support user
    add_user('support', 'support123', 'Support')
   
    # Create default client user
    add_user('client', 'client123', 'Client')
 
 
def authenticate_user(username: str, password: str) -> Optional[str]:
    conn = get_connection()
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute(
        "SELECT role FROM users WHERE username = ? AND hashed_password = ?",
        (username, hashed),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None
 
 
def authenticate_by_role_and_username(role: str, username: str, password: str) -> bool:
    # Default credentials
    default_credentials = {
        'Support': {'username': 'support', 'password': 'support123'},
        'Client': {'username': 'client', 'password': 'client123'}
    }
   
    if role in default_credentials:
        role_creds = default_credentials[role]
        return (username == role_creds['username'] and
                password == role_creds['password'])
   
    return False
 
 
def import_csv(csv_path: str) -> None:
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file {csv_path} not found")
    df = pd.read_csv(csv_path)
    # Align column names with the database schema
    df = df.rename(
        columns={
            'client_email': 'mail_id',
            'client_mobile': 'mobile_number',
            'date_raised': 'query_created_time',
            'date_closed': 'query_closed_time',
        }
    )
    conn = get_connection()
    cur = conn.cursor()
    for _, row in df.iterrows():
        # Convert NaN to None for null values
        values = (
            row['query_id'],
            row['mail_id'],
            row['mobile_number'],
            row['query_heading'],
            row['query_description'],
            row['status'],
            row['query_created_time'],
            row['query_closed_time'],
            None,  # image
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO queries (
                query_id, mail_id, mobile_number, query_heading,
                query_description, status, query_created_time,
                query_closed_time, image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
    conn.commit()
    conn.close()
 
 
def get_next_query_id() -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT query_id FROM queries ORDER BY query_id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        last_id = row[0]
        try:
            num = int(last_id[1:])
            new_num = num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1
    return f"Q{new_num:04d}"
 
 
def insert_query(
    mail_id: str,
    mobile_number: str,
    query_heading: str,
    query_description: str,
    image_bytes: Optional[bytes] = None,
) -> str:
    query_id = get_next_query_id()
    created_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO queries (
            query_id, mail_id, mobile_number, query_heading,
            query_description, status, query_created_time,
            query_closed_time, image
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            query_id,
            mail_id,
            mobile_number,
            query_heading,
            query_description,
            'Opened',
            created_time,
            None,
            image_bytes,
        ),
    )
    conn.commit()
    conn.close()
    return query_id
 
 
def close_query(query_id: str) -> None:
    """Mark a query as closed by setting its status and close time.
 
    Args:
        query_id: The identifier of the query to close.
    """
    closed_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE queries SET status = ?, query_closed_time = ? WHERE query_id = ?",
        ('Closed', closed_time, query_id),
    )
    conn.commit()
    conn.close()
 
 
def fetch_queries(status: Optional[str] = None) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    if status is None or status.lower() == 'all':
        cur.execute(
            "SELECT query_id, mail_id, mobile_number, query_heading, query_description, status, query_created_time, query_closed_time FROM queries ORDER BY query_created_time DESC"
        )
    else:
        cur.execute(
            "SELECT query_id, mail_id, mobile_number, query_heading, query_description, status, query_created_time, query_closed_time FROM queries WHERE status = ? ORDER BY query_created_time DESC",
            (status,),
        )
    rows = cur.fetchall()
    conn.close()
    columns = [
        'query_id',
        'mail_id',
        'mobile_number',
        'query_heading',
        'query_description',
        'status',
        'query_created_time',
        'query_closed_time',
    ]
    return pd.DataFrame(rows, columns=columns)
 
 
def get_query_image(query_id: str) -> Optional[bytes]:
    """Fetch the image bytes for a given query identifier.
 
    Args:
        query_id: The identifier of the query whose image is desired.
 
    Returns:
        The raw image data if present, otherwise ``None``.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT image FROM queries WHERE query_id = ?", (query_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None
 