import psycopg2
import psycopg2.extras
import json

DB_URL = "postgresql://neondb_owner:npg_GHinScwVu39X@ep-weathered-wind-azs32eox-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

class DBConnection:
    def __init__(self):
        self.conn = psycopg2.connect(DB_URL)
        self.conn.autocommit = False
    
    def execute(self, query, params=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = query.replace('?', '%s')
        cur.execute(query, params)
        return cur

    def cursor(self):
        return self.execute_cursor(self.conn)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
        
    class execute_cursor:
        def __init__(self, conn):
            self.conn = conn
            self.cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self._lastrowid = None
            
        def execute(self, query, params=None):
            query = query.replace('?', '%s')
            if query.strip().upper().startswith("INSERT") and "RETURNING" not in query.upper():
                query = query.rstrip(';') + " RETURNING id"
                self.cur.execute(query, params)
                res = self.cur.fetchone()
                if res:
                    self._lastrowid = res['id']
            else:
                self.cur.execute(query, params)
            return self.cur
            
        @property
        def lastrowid(self):
            return self._lastrowid

try:
    db = DBConnection()
    res = db.execute("SELECT * FROM customers WHERE id = %s", (1,)).fetchone()
    print("Fetchone:", dict(res) if res else None)
    
    c = db.cursor()
    c.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", ("Test", "123"))
    print("Lastrowid:", c.lastrowid)
    db.conn.rollback()
    
    print("Wrapper works perfectly!")
except Exception as e:
    print("Error:", e)
