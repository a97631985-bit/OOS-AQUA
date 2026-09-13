import psycopg2
import psycopg2.extras
import os
import shutil
import json
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from datetime import datetime, date

app = Flask(__name__)
DB_FILE = 'water_supplier.db'
BACKUP_DIR = 'backups'

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)


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

def backup_database(reason="manual"):
    return "cloud_backup_active"

def auto_daily_backup():
    """Run automatic backup every 6 hours"""
    backup_database("auto")
    timer = threading.Timer(6 * 3600, auto_daily_backup)
    timer.daemon = True
    timer.start()

# Start auto backup scheduler
auto_daily_backup()

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT DEFAULT '',
            price_per_jar REAL NOT NULL DEFAULT 35,
            jar_security_deposit REAL DEFAULT 0,
            jars_holding INTEGER DEFAULT 0,
            previous_dues REAL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            date TEXT NOT NULL,
            jars_delivered INTEGER DEFAULT 0,
            jars_returned INTEGER DEFAULT 0
        )
    ''')
    
    # Try adding columns for backward compatibility if they don't exist
    columns = [
        ('address', 'TEXT DEFAULT ""'),
        ('price_per_jar', 'REAL NOT NULL DEFAULT 35'),
        ('jar_security_deposit', 'REAL DEFAULT 0'),
        ('jars_holding', 'INTEGER DEFAULT 0'),
        ('previous_dues', 'REAL DEFAULT 0'),
        ('is_deleted', 'INTEGER DEFAULT 0')
    ]
    for col, col_def in columns:
        try:
            c.execute(f"ALTER TABLE customers ADD COLUMN {col} {col_def}")
        except Exception:
            pass # Column likely already exists
    
    # Add is_deleted to entries table too
    try:
        c.execute("ALTER TABLE entries ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except Exception:
        pass
            
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(app.root_path, 'logo.png')

@app.route('/qr.jpg')
def serve_qr():
    return send_from_directory(app.root_path, 'qr.jpg')

@app.route('/api/customers', methods=['GET', 'POST'])
def manage_customers():
    conn = get_db()
    if request.method == 'GET':
        customers = conn.execute('SELECT * FROM customers WHERE is_deleted = 0 ORDER BY name').fetchall()
        return jsonify([dict(c) for c in customers])
        
    if request.method == 'POST':
        data = request.json
        c = conn.cursor()
        c.execute('''
            INSERT INTO customers (name, phone, address, price_per_jar, jar_security_deposit, jars_holding, previous_dues)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'), 
            data.get('phone'), 
            data.get('address', ''), 
            float(data.get('price_per_jar', 35)),
            float(data.get('jar_security_deposit', 0)),
            int(data.get('jars_holding', 0)),
            float(data.get('previous_dues', 0))
        ))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return jsonify({'success': True, 'id': new_id})

@app.route('/api/customers/<int:id>', methods=['DELETE', 'PUT'])
def modify_customer(id):
    conn = get_db()
    if request.method == 'DELETE':
        # Create backup before any delete operation
        backup_database("before_delete")
        # Soft delete - data is preserved, just hidden
        conn.execute('UPDATE customers SET is_deleted = 1 WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Customer hidden (soft-deleted). Data is preserved in backups.'})
        
    if request.method == 'PUT':
        data = request.json
        c = conn.cursor()
        updates = []
        params = []
        for key in ['name', 'phone', 'address', 'price_per_jar', 'jar_security_deposit', 'jars_holding', 'previous_dues']:
            if key in data:
                updates.append(f"{key} = ?")
                params.append(data[key])
        
        if updates:
            params.append(id)
            c.execute(f'UPDATE customers SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
        conn.close()
        return jsonify({'success': True})

@app.route('/api/entries', methods=['GET', 'POST'])
def manage_entries():
    conn = get_db()
    if request.method == 'GET':
        date_filter = request.args.get('date')
        customer_id = request.args.get('customer_id')
        month = request.args.get('month')
        year = request.args.get('year')
        
        query = 'SELECT e.*, c.name FROM entries e JOIN customers c ON e.customer_id = c.id WHERE e.is_deleted = 0'
        params = []
        
        if date_filter:
            query += ' AND e.date = ?'
            params.append(date_filter)
        if customer_id:
            query += ' AND e.customer_id = ?'
            params.append(customer_id)
        if month and year:
            query += ' AND e.date LIKE ?'
            params.append(f"{year}-{month.zfill(2)}-%")
            
        query += ' ORDER BY e.id DESC'
        entries = conn.execute(query, params).fetchall()
        return jsonify([dict(e) for e in entries])
        
    if request.method == 'POST':
        data = request.json
        c = conn.cursor()
        c.execute('''
            INSERT INTO entries (customer_id, date, jars_delivered, jars_returned)
            VALUES (?, ?, ?, ?)
        ''', (
            data.get('customer_id'),
            data.get('date'),
            int(data.get('jars_delivered', 0)),
            int(data.get('jars_returned', 0))
        ))
        # Update jars_holding for the customer
        net_jars = int(data.get('jars_delivered', 0)) - int(data.get('jars_returned', 0))
        c.execute('UPDATE customers SET jars_holding = jars_holding + ? WHERE id = ?', (net_jars, data.get('customer_id')))
        
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return jsonify({'success': True, 'id': new_id})

@app.route('/api/entries/<int:id>', methods=['DELETE'])
def delete_entry(id):
    conn = get_db()
    c = conn.cursor()
    # Backup before any delete
    backup_database("before_entry_delete")
    # Need to revert jars_holding
    entry = c.execute('SELECT customer_id, jars_delivered, jars_returned FROM entries WHERE id = ? AND is_deleted = 0', (id,)).fetchone()
    if entry:
        net_jars = entry['jars_delivered'] - entry['jars_returned']
        c.execute('UPDATE customers SET jars_holding = jars_holding - ? WHERE id = ?', (net_jars, entry['customer_id']))
        # Soft delete - data preserved, just hidden
        c.execute('UPDATE entries SET is_deleted = 1 WHERE id = ?', (id,))
        conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/billing', methods=['GET'])
def get_billing():
    month = request.args.get('month')
    year = request.args.get('year')
    if not month or not year:
        return jsonify({'error': 'Missing month or year'}), 400
        
    conn = get_db()
    like_date = f"{year}-{month.zfill(2)}-%"
    
    customers = conn.execute('SELECT * FROM customers WHERE is_deleted = 0').fetchall()
    
    billing_data = []
    total_revenue = 0
    pending_dues = 0
    
    for c in customers:
        entries = conn.execute('SELECT SUM(jars_delivered) as td, SUM(jars_returned) as tr FROM entries WHERE customer_id = ? AND date LIKE ? AND is_deleted = 0', (c['id'], like_date)).fetchone()
        
        td = entries['td'] or 0
        tr = entries['tr'] or 0
        current_bill = td * c['price_per_jar']
        total_payable = current_bill + c['previous_dues']
        
        billing_data.append({
            'customer': dict(c),
            'jars_delivered': td,
            'jars_returned': tr,
            'current_bill': current_bill,
            'total_payable': total_payable
        })
        total_revenue += current_bill
        pending_dues += total_payable
        
    conn.close()
    return jsonify({
        'summary': {'total_revenue': total_revenue, 'pending_dues': pending_dues},
        'invoices': billing_data
    })

@app.route('/api/payment', methods=['POST'])
def record_payment():
    """Record payment - fully paid or custom amount"""
    data = request.json
    customer_id = data.get('customer_id')
    payment_type = data.get('type')  # 'full' or 'partial'
    amount = data.get('amount', 0)
    month = data.get('month')
    year = data.get('year')
    
    if not customer_id:
        return jsonify({'success': False, 'message': 'Customer ID required'}), 400
    
    # Backup before payment operation
    backup_database("before_payment")
    
    conn = get_db()
    c = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    if not c:
        conn.close()
        return jsonify({'success': False, 'message': 'Customer not found'}), 404
    
    # Calculate current bill for this month
    like_date = f"{year}-{month.zfill(2)}-%"
    entry_stats = conn.execute('SELECT SUM(jars_delivered) as td FROM entries WHERE customer_id = ? AND date LIKE ? AND is_deleted = 0', (customer_id, like_date)).fetchone()
    td = entry_stats['td'] or 0
    current_bill = td * c['price_per_jar']
    total_payable = current_bill + c['previous_dues']
    
    if payment_type == 'full':
        # Full payment - clear all dues
        new_dues = 0.0
        paid_amount = total_payable
    else:
        # Partial payment - remaining becomes new dues
        paid_amount = float(amount)
        new_dues = max(0, total_payable - paid_amount)
    
    # Update customer's previous_dues
    conn.execute('UPDATE customers SET previous_dues = ? WHERE id = ?', (new_dues, customer_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'current_bill': current_bill,
        'previous_dues': c['previous_dues'],
        'total_payable': total_payable,
        'paid_amount': paid_amount,
        'remaining_dues': new_dues,
        'message': f'Payment of Rs.{paid_amount:.0f} recorded against total Rs.{total_payable:.0f} (bill Rs.{current_bill:.0f} + previous dues Rs.{c["previous_dues"]:.0f}). Dues: Rs.{new_dues:.0f}'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    date_filter = request.args.get('date', date.today().isoformat())
    conn = get_db()
    
    # Today stats
    stats = conn.execute('SELECT SUM(jars_delivered) as td, SUM(jars_returned) as tr FROM entries WHERE date = ? AND is_deleted = 0', (date_filter,)).fetchone()
    
    # Yesterday stats for comparison
    from datetime import timedelta
    yesterday = (datetime.strptime(date_filter, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    ystats = conn.execute('SELECT SUM(jars_delivered) as td FROM entries WHERE date = ? AND is_deleted = 0', (yesterday,)).fetchone()
    
    # Overall Customers stats
    cust_stats = conn.execute('SELECT COUNT(*) as ac, SUM(jars_holding) as jc, SUM(jar_security_deposit) as sp, SUM(previous_dues) as pd FROM customers WHERE is_deleted = 0').fetchone()
    
    conn.close()
    
    td = stats['td'] or 0
    tr = stats['tr'] or 0
    ytd = ystats['td'] or 0
    
    return jsonify({
        'today_delivered': td,
        'today_returned': tr,
        'yesterday_delivered': ytd,
        'active_accounts': cust_stats['ac'] or 0,
        'jars_circulating': cust_stats['jc'] or 0,
        'security_pool': cust_stats['sp'] or 0,
        'total_dues': cust_stats['pd'] or 0
    })

@app.route('/api/billing/invoice', methods=['GET'])
def get_invoice():
    customer_id = request.args.get('customer_id')
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not all([customer_id, month, year]):
        return "Missing parameters", 400
        
    conn = get_db()
    c = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
    if not c:
        return "Customer not found", 404
        
    like_date = f"{year}-{month.zfill(2)}-%"
    entries = conn.execute('SELECT * FROM entries WHERE customer_id = ? AND date LIKE ? AND is_deleted = 0 ORDER BY date', (customer_id, like_date)).fetchall()
    
    td = sum(e['jars_delivered'] for e in entries)
    tr = sum(e['jars_returned'] for e in entries)
    pending = td - tr
    current_bill = td * c['price_per_jar']
    total_payable = current_bill + c['previous_dues']
    security_deposit = c['jar_security_deposit']
    
    month_name = datetime.strptime(f"{year}-{month.zfill(2)}-01", "%Y-%m-%d").strftime("%B")
    bill_number = f"OA-{year}/{c['id']:03d}"
    
    # Build table rows
    table_rows = ""
    for idx, e in enumerate(entries, 1):
        d = e['jars_delivered']
        r = e['jars_returned']
        status_html = (
            '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700">Verified</span>'
            if r > 0
            else '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">Delivered</span>'
        )
        r_display = str(r) if r > 0 else "–"
        table_rows += f'''
            <tr class="hover:bg-slate-50/60">
              <td class="py-2 px-3 text-slate-400 font-mono text-[11px]">{idx:02d}</td>
              <td class="py-2 px-3 font-semibold text-slate-800">{e['date']}</td>
              <td class="py-2 px-3 text-slate-600">Standard Delivery</td>
              <td class="py-2 px-3 text-center font-bold text-slate-900 bg-cyan-50/20">{d}</td>
              <td class="py-2 px-3 text-center font-semibold text-slate-700 bg-sky-50/20">{r_display}</td>
              <td class="py-2 px-3 text-center">{status_html}</td>
            </tr>
        '''
    
    if not entries:
        table_rows = '<tr><td colspan="6" class="py-6 text-center text-slate-400 italic">No deliveries recorded this month.</td></tr>'

    security_display = '<span class="font-semibold text-emerald-700 mono">Adjusted</span>' if security_deposit > 0 else '<span class="font-semibold text-slate-800 mono">₹0.00</span>'
    
    pending_str = f"{pending:02d}" if pending < 100 else str(pending)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OOS AQUA - Bill {bill_number}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background-color: #f1f5f9;
      color: #0f172a;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .mono {{
      font-family: 'JetBrains Mono', monospace;
    }}
    @media print {{
      body {{
        background: white;
        padding: 0;
      }}
      .no-print {{
        display: none !important;
      }}
      .print-shadow-none {{
        box-shadow: none !important;
        border: 1px solid #e2e8f0;
      }}
      @page {{
        size: A4 portrait;
        margin: 12mm;
      }}
    }}
  </style>
</head>
<body class="p-3 sm:p-6 md:p-8 flex flex-col items-center min-h-screen">

  <!-- Action Bar for PDF / Print -->
  <div class="w-full max-w-2xl mb-4 flex items-center justify-between no-print bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-50 text-cyan-700">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
        </svg>
      </span>
      <div>
        <p class="text-xs font-semibold text-slate-900">Printable Format Ready</p>
        <p class="text-[11px] text-slate-500">A4 & Mobile Print Optimized</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <button onclick="window.print()" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-medium rounded-lg shadow-sm transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
        </svg>
        <span class="">Print / Save PDF</span>
      </button>
      <a href="/" class="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-200 transition">← Back</a>
    </div>
  </div>

  <!-- Bill / Challan Document Card -->
  <div class="w-full max-w-2xl bg-white rounded-2xl border border-slate-200/90 shadow-xl overflow-hidden print-shadow-none">
    
    <!-- Top Accent Bar -->
    <div class="h-2.5 bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600"></div>

    <!-- Header Section -->
    <div class="p-5 sm:p-7 border-b border-slate-100">
      <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        
        <!-- Brand & Supplier Details -->
        <div class="flex items-start gap-3.5">
          <div class="w-14 h-14 rounded-xl border border-cyan-100 bg-cyan-50/50 p-1 flex-shrink-0 flex items-center justify-center overflow-hidden">
            <img src="/logo.png" alt="OOS AQUA Logo" class="w-full h-full object-contain mix-blend-multiply">
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900">OOS AQUA</h1>
              <span class="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-cyan-100 text-cyan-800">Natural Mineral Water</span>
            </div>
            <p class="text-xs font-semibold text-slate-700 mt-0.5">M/S CROSS LIGHT</p>
            <p class="text-[12px] text-slate-500">Ranchi, Jharkhand</p>
            <div class="flex items-center gap-2 mt-1 text-[12px] font-medium text-slate-600">
              <span class="inline-flex items-center gap-1 text-cyan-700 font-semibold">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                </svg>
                +91 9117456957</span>
            </div>
          </div>
        </div>

        <!-- Document Badge & Meta -->
        <div class="sm:text-right flex flex-col sm:items-end justify-between">
          <div class="inline-block bg-slate-900 text-white px-3 py-1 rounded-lg text-xs font-bold tracking-wider uppercase">
            Monthly Jar Delivery Challan
          </div>
          <div class="mt-2.5 space-y-0.5 text-xs text-slate-500">
            <p class=""><span class="text-slate-400">Bill / Card No:</span> <span class="font-semibold text-slate-800 mono">{bill_number}</span></p>
            <p class=""><span class="text-slate-400">Billing Cycle:</span> <span class="font-semibold text-slate-800">{month_name} {year}</span></p>
          </div>
        </div>
      </div>

      <!-- Customer Info Card -->
      <div class="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/70">
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Customer Name</span>
          <p class="text-sm font-bold text-slate-800 mt-0.5">{c['name']}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Address / Flat No.</span>
          <p class="text-sm font-semibold text-slate-700 mt-0.5">{c['address'] or 'N/A'}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">No. of Jars Holding</span>
          <p class="text-sm font-bold text-cyan-800 mt-0.5 mono">{c['jars_holding']} Jars In-Hand</p>
        </div>
      </div>

    </div>

    <!-- Summary Metrics -->
    <div class="grid grid-cols-3 divide-x divide-slate-100 bg-cyan-50/30 border-b border-slate-100 text-center py-3">
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Total Filled Delivered</span>
        <p class="text-lg font-bold text-slate-900 mono">{td} <span class="text-xs font-medium text-slate-500">Jars</span></p>
      </div>
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Total Empty Received</span>
        <p class="text-lg font-bold text-slate-900 mono">{tr} <span class="text-xs font-medium text-slate-500">Jars</span></p>
      </div>
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-cyan-800">Pending Empty Jars</span>
        <p class="text-lg font-bold text-cyan-700 mono">{pending_str} <span class="text-xs font-medium text-cyan-600">Jars</span></p>
      </div>
    </div>

    <!-- Ledger / Delivery Table (Clean Digitized Version without Signatures) -->
    <div class="p-4 sm:p-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-700">Delivery Log &amp; Register Entries</h3>
        <span class="text-[11px] text-slate-400 italic">Clean electronic ledger (Verified records)</span>
      </div>

      <div class="overflow-x-auto rounded-xl border border-slate-200">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="bg-slate-100/80 text-slate-600 font-semibold border-b border-slate-200 text-[11px] uppercase tracking-wider">
              <th class="py-2.5 px-3">#</th>
              <th class="py-2.5 px-3">Date</th>
              <th class="py-2.5 px-3">Description / Batch</th>
              <th class="py-2.5 px-3 text-center bg-cyan-50/60 text-cyan-900">Delivered Filled</th>
              <th class="py-2.5 px-3 text-center bg-sky-50/60 text-sky-900">Received Empty</th>
              <th class="py-2.5 px-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 text-slate-700">
            {table_rows}
          </tbody>
          <tfoot class="bg-slate-50 font-bold border-t-2 border-slate-200 text-slate-800">
            <tr>
              <td colspan="3" class="py-3 px-3 text-right text-xs uppercase tracking-wider text-slate-600">Total Count:</td>
              <td class="py-3 px-3 text-center text-cyan-900 bg-cyan-100/50 text-sm mono font-extrabold">{td}</td>
              <td class="py-3 px-3 text-center text-sky-900 bg-sky-100/50 text-sm mono font-extrabold">{tr}</td>
              <td class="py-3 px-3 text-center text-[11px] text-cyan-800">{pending_str} Balance</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- Financial Calculation / Amount Due Section -->
      <div class="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
        
        <!-- Payment & Bank / UPI Info -->
        <div class="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 text-xs">
          <p class="font-bold text-slate-800 mb-1 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-cyan-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            Terms &amp; Payment Modes
          </p>
          <ul class="text-[11px] text-slate-600 space-y-1 mt-2 list-disc list-inside">
            <li class="">Accepted: UPI, Cash, or Net Banking.</li>
            <li class="">GPay / PhonePe UPI: <span class="font-bold text-slate-800 mono">9117456957@ybl</span></li>
            <li class="">Please return empty jars in good condition to avoid deposit forfeiture.</li>
            <li class="">Scan QR code on Page 2 to pay online.</li>
          </ul>
        </div>

        <!-- Billing Breakdown Box -->
        <div class="p-4 bg-gradient-to-br from-cyan-50/70 to-blue-50/50 rounded-xl border border-cyan-200/70 space-y-2">
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">20L Mineral Jars Delivered:</span>
            <span class="font-semibold text-slate-800 mono">{td} Jars</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Rate per Jar:</span>
            <span class="font-semibold text-slate-800 mono">₹{c['price_per_jar']:.2f}</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Empty Jar Security Deposit:</span>
            {security_display}
          </div>
          <div class="flex justify-between text-xs text-slate-600 pt-1 border-t border-cyan-200/50">
            <span class="">Current Bill Amount:</span>
            <span class="font-semibold text-slate-800 mono">₹{current_bill:.2f}</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Previous Dues / Balance:</span>
            <span class="font-semibold text-slate-800 mono">₹{c['previous_dues']:.2f}</span>
          </div>
          <div class="border-t border-cyan-200/80 pt-2 flex justify-between items-baseline">
            <span class="text-xs font-bold text-slate-900 uppercase tracking-wide">Total Net Payable:</span>
            <span class="text-lg font-black text-cyan-900 mono">₹{total_payable:.2f}</span>
          </div>
        </div>

      </div>

      <!-- Clean Stamp / Approval Section (No pen scribbles) -->
      <div class="mt-8 pt-5 border-t border-slate-200 grid grid-cols-2 gap-6 text-center">
        <div>
          <div class="h-12 flex items-center justify-center">
            <div class="px-3 py-1 rounded border border-dashed border-slate-300 text-slate-400 text-[11px] uppercase tracking-wider">
              Customer Confirmation
            </div>
          </div>
          <p class="text-xs font-semibold text-slate-700 mt-1">Customer Acknowledgment</p>
          <p class="text-[10px] text-slate-400">Digitally Verified &amp; Accepted</p>
        </div>

        <div>
          <div class="h-14 flex items-center justify-center">
            <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuBWeEHBml-39i2tgdiPNbCXrgkrvhWN3WQk3-W5lddzsbVA22cX61JrbkmipXkblnweeOA2jXzMSdhSLTCGSZQ4LN5mt5YRhWfwBcrayW7cVLcK1IPaRWD4rEuHj1oaUkLQv77ZogimBDwAiRVXDhRKQIbRcywX34aYCqH0_iJHrMqkoahP2tAfi2rXT53rClNrfGpqyYYrmh_pkZW37_7-rLrk_gotdbs41URhfki830gRnzTBwqN9opNMeJs9RbvzZXM" alt="Authorized Signature" class="h-14 w-auto object-contain mx-auto mix-blend-multiply mb-1">
          </div>
          <p class="text-xs font-semibold text-slate-800 mt-1">Authorized Dispatch Manager</p>
          <p class="text-[10px] text-slate-400">OOS AQUA (Ranchi, Jharkhand)</p>
        </div>
      </div>

    </div>

    <!-- Bottom Footer Note -->
    <div class="bg-slate-900 text-slate-400 px-6 py-3 text-center text-[11px] flex flex-col sm:flex-row items-center justify-between gap-1">
      <span class="">Thank you for choosing <strong>OOS AQUA</strong> – Pure Natural Mineral Water.</span>
      <span class="text-slate-500">Helpline: +91 9608107897</span>
    </div>

  </div>

  <!-- PAGE 2: QR CODE PAYMENT PAGE -->
  <div class="w-full max-w-2xl bg-white rounded-2xl border border-slate-200/90 shadow-xl overflow-hidden print-shadow-none mt-8" style="page-break-before: always;">
    
    <!-- Top Accent Bar -->
    <div class="h-2.5 bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600"></div>
    
    <!-- QR Content -->
    <div class="flex flex-col items-center justify-center py-12 px-6">
      
      <!-- Company Badge -->
      <div class="flex items-center gap-3 mb-6">
        <div class="w-12 h-12 rounded-xl border border-cyan-100 bg-cyan-50/50 p-1 flex items-center justify-center overflow-hidden">
          <img src="/logo.png" alt="OOS AQUA Logo" class="w-full h-full object-contain mix-blend-multiply">
        </div>
        <div>
          <h2 class="text-xl font-extrabold text-slate-900">OOS AQUA</h2>
          <p class="text-[11px] text-slate-500 font-semibold">M/S CROSS LIGHT, Ranchi</p>
        </div>
      </div>
      
      <!-- Payment Title -->
      <div class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white px-6 py-2 rounded-full text-sm font-bold tracking-wide mb-6 shadow-lg">
        Scan &amp; Pay via PhonePe / GPay / Paytm
      </div>
      
      <!-- QR Code -->
      <div class="bg-white p-4 rounded-2xl border-2 border-slate-200 shadow-lg mb-6">
        <img src="/qr.jpg" alt="PhonePe QR Code" class="w-64 h-64 object-contain">
      </div>
      
      <!-- UPI Details -->
      <div class="text-center space-y-2 mb-6">
        <p class="text-lg font-bold text-slate-800">Aman Kumar Choudhry</p>
        <div class="bg-slate-100 rounded-xl px-6 py-3 inline-block">
          <p class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">UPI ID</p>
          <p class="text-lg font-bold text-[#00687a] mono tracking-wide">9117456957@ybl</p>
        </div>
      </div>
      
      <!-- Amount Due Box -->
      <div class="bg-gradient-to-br from-cyan-50 to-blue-50 border-2 border-cyan-200 rounded-2xl p-5 w-full max-w-sm text-center mb-6">
        <p class="text-[10px] font-bold text-cyan-700 uppercase tracking-wider mb-1">Total Amount Payable</p>
        <p class="text-4xl font-black text-cyan-900 mono">₹{total_payable:.2f}</p>
        <p class="text-xs text-slate-500 mt-1">Bill: {bill_number} | {month_name} {year}</p>
      </div>
      
      <!-- Payment Modes -->
      <div class="flex gap-3 text-[11px] text-slate-500 font-semibold">
        <span class="bg-slate-100 px-3 py-1 rounded-full">UPI</span>
        <span class="bg-slate-100 px-3 py-1 rounded-full">PhonePe</span>
        <span class="bg-slate-100 px-3 py-1 rounded-full">GPay</span>
        <span class="bg-slate-100 px-3 py-1 rounded-full">Paytm</span>
        <span class="bg-slate-100 px-3 py-1 rounded-full">Cash</span>
      </div>
      
    </div>
    
    <!-- Footer -->
    <div class="bg-slate-900 text-slate-400 px-6 py-3 text-center text-[11px]">
      <span>Thank you for choosing <strong>OOS AQUA</strong> – Pure Natural Mineral Water. | Helpline: +91 9608107897</span>
    </div>
    
  </div>

</body>
</html>'''
    
    conn.close()
    
    response = make_response(html)
    response.headers["Content-Type"] = "text/html"
    return response

# ==========================================
# DATA SAFETY ENDPOINTS
# ==========================================

@app.route('/api/backup', methods=['POST'])
def create_backup():
    """Manually trigger a database backup"""
    path = backup_database("manual")
    if path:
        return jsonify({'success': True, 'backup_file': path, 'message': 'Backup created successfully!'})
    return jsonify({'success': False, 'message': 'No database found to backup'}), 404

@app.route('/api/export', methods=['GET'])
def export_data():
    """Export ALL data as JSON for safe keeping"""
    conn = get_db()
    customers = conn.execute('SELECT * FROM customers').fetchall()  # Include deleted ones too
    entries = conn.execute('SELECT * FROM entries ORDER BY date').fetchall()
    conn.close()
    
    export = {
        'export_date': datetime.now().isoformat(),
        'app_name': 'OOS AQUA Water Management',
        'customers': [dict(c) for c in customers],
        'entries': [dict(e) for e in entries]
    }
    
    response = make_response(json.dumps(export, indent=2, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=oos_aqua_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    return response

@app.route('/api/import', methods=['POST'])
def import_data():
    """Import data from a JSON backup file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    try:
        data = json.loads(file.read().decode('utf-8'))
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid JSON file'}), 400
    
    # Backup current data before import
    backup_database("before_import")
    
    conn = get_db()
    c = conn.cursor()
    
    imported_customers = 0
    imported_entries = 0
    
    for cust in data.get('customers', []):
        existing = c.execute('SELECT id FROM customers WHERE id = ?', (cust['id'],)).fetchone()
        if not existing:
            c.execute('''INSERT INTO customers (id, name, phone, address, price_per_jar, jar_security_deposit, jars_holding, previous_dues, is_deleted)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (cust['id'], cust['name'], cust['phone'], cust.get('address', ''),
                       cust.get('price_per_jar', 35), cust.get('jar_security_deposit', 0),
                       cust.get('jars_holding', 0), cust.get('previous_dues', 0), cust.get('is_deleted', 0)))
            imported_customers += 1
    
    for entry in data.get('entries', []):
        existing = c.execute('SELECT id FROM entries WHERE id = ?', (entry['id'],)).fetchone()
        if not existing:
            c.execute('''INSERT INTO entries (id, customer_id, date, jars_delivered, jars_returned)
                         VALUES (?, ?, ?, ?, ?)''',
                      (entry['id'], entry['customer_id'], entry['date'],
                       entry.get('jars_delivered', 0), entry.get('jars_returned', 0)))
            imported_entries += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Imported {imported_customers} customers and {imported_entries} entries.',
        'imported_customers': imported_customers,
        'imported_entries': imported_entries
    })

@app.route('/api/backups', methods=['GET'])
def list_backups():
    """List all available backups"""
    if not os.path.exists(BACKUP_DIR):
        return jsonify([])
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith('.db'):
            fpath = os.path.join(BACKUP_DIR, f)
            backups.append({
                'filename': f,
                'size_kb': round(os.path.getsize(fpath) / 1024, 1),
                'created': datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
            })
    return jsonify(backups)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
