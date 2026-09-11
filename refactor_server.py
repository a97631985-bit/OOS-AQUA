import re

with open('server.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
code = code.replace("import sqlite3", "import psycopg2\nimport psycopg2.extras")

# 2. Add DB_URL and Wrapper
wrapper = """
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

def get_db():
    return DBConnection()
"""

# Replace get_db
get_db_pattern = re.compile(r'def get_db\(\):.*?return conn\n', re.DOTALL)
code = get_db_pattern.sub(wrapper, code)

# Replace PRAGMAs and AUTOINCREMENT
code = code.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

# Replace sqlite3.OperationalError with psycopg2.errors.DuplicateColumn
# (Wait, actually we can just catch Exception in the ALTER TABLE)
code = code.replace("except sqlite3.OperationalError:", "except Exception:")

# Fix backup_database
backup_pattern = re.compile(r'def backup_database\(reason="manual"\):.*?return backup_path\n', re.DOTALL)
code = backup_pattern.sub('def backup_database(reason="manual"):\n    return "cloud_backup_active"\n', code)

with open('server.py', 'w', encoding='utf-8') as f:
    f.write(code)
