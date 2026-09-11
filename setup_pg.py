import sqlite3
import psycopg2
import psycopg2.extras
import os

DB_URL = "postgresql://neondb_owner:npg_GHinScwVu39X@ep-weathered-wind-azs32eox-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

print("Connecting to Neon...")
pg_conn = psycopg2.connect(DB_URL)
pg_cur = pg_conn.cursor()

# Create tables in Neon
pg_cur.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT DEFAULT '',
    price_per_jar REAL NOT NULL DEFAULT 35,
    jar_security_deposit REAL DEFAULT 0,
    jars_holding INTEGER DEFAULT 0,
    previous_dues REAL DEFAULT 0,
    is_deleted INTEGER DEFAULT 0
);
""")

pg_cur.execute("""
CREATE TABLE IF NOT EXISTS entries (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    date TEXT NOT NULL,
    jars_delivered INTEGER DEFAULT 0,
    jars_returned INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0
);
""")
pg_conn.commit()

print("Checking local SQLite data...")
if os.path.exists('water_supplier.db'):
    sl_conn = sqlite3.connect('water_supplier.db')
    sl_conn.row_factory = sqlite3.Row
    
    customers = sl_conn.execute("SELECT * FROM customers").fetchall()
    print(f"Found {len(customers)} customers.")
    for c in customers:
        # Check if exists
        pg_cur.execute("SELECT id FROM customers WHERE id = %s", (c['id'],))
        if not pg_cur.fetchone():
            is_deleted = c['is_deleted'] if 'is_deleted' in c.keys() else 0
            pg_cur.execute("""
                INSERT INTO customers (id, name, phone, address, price_per_jar, jar_security_deposit, jars_holding, previous_dues, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (c['id'], c['name'], c['phone'], c['address'], c['price_per_jar'], c['jar_security_deposit'], c['jars_holding'], c['previous_dues'], is_deleted))
    
    entries = sl_conn.execute("SELECT * FROM entries").fetchall()
    print(f"Found {len(entries)} entries.")
    for e in entries:
        pg_cur.execute("SELECT id FROM entries WHERE id = %s", (e['id'],))
        if not pg_cur.fetchone():
            is_deleted = e['is_deleted'] if 'is_deleted' in e.keys() else 0
            pg_cur.execute("""
                INSERT INTO entries (id, customer_id, date, jars_delivered, jars_returned, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (e['id'], e['customer_id'], e['date'], e['jars_delivered'], e['jars_returned'], is_deleted))
            
    # Reset sequences so new inserts don't fail
    if customers:
        pg_cur.execute("SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers))")
    if entries:
        pg_cur.execute("SELECT setval('entries_id_seq', (SELECT MAX(id) FROM entries))")
        
    pg_conn.commit()
    sl_conn.close()
    print("Data migration complete!")
else:
    print("No local DB found to migrate.")

pg_conn.close()
