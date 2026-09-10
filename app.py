import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import os
import calendar

# --- CONFIGURATION ---
st.set_page_config(
    page_title="OOS AQUA Management",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE SETUP ---
DB_FILE = "water_supplier.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Create customers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT DEFAULT '',
            price_per_jar REAL NOT NULL,
            jar_security_deposit REAL DEFAULT 0,
            jars_holding INTEGER DEFAULT 0,
            previous_dues REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Try adding new columns if they don't exist (for backward compatibility)
    try:
        c.execute("ALTER TABLE customers ADD COLUMN address TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE customers ADD COLUMN jar_security_deposit REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE customers ADD COLUMN jars_holding INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE customers ADD COLUMN previous_dues REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE customers ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    # Create entries table
    c.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            date TEXT NOT NULL,
            jars_delivered INTEGER DEFAULT 0,
            jars_returned INTEGER DEFAULT 0,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- CSS STYLING ---
st.markdown("""
<style>
    /* Custom Styling */
    .stApp {
        background-color: #f8fafc;
    }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #0284c7;
    }
    .metric-label {
        color: #64748b;
        font-size: 1rem;
        font-weight: 500;
    }
    .customer-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border-left: 4px solid #0ea5e9;
    }
    .logo-container {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 20px;
    }
    .logo-text {
        font-size: 2.5rem;
        font-weight: 800;
        background: -webkit-linear-gradient(#06b6d4, #2563eb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=80)
    else:
        st.markdown('<div style="font-size: 4rem;">💧</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="logo-container"><div class="logo-text">OOS AQUA</div></div>', unsafe_allow_html=True)
    st.markdown("**Mineral Water Supplier Management**")

# --- HELPER FUNCTIONS ---
def get_customers():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM customers ORDER BY name", conn)
    conn.close()
    return df

def get_entries(customer_id=None, month=None, year=None, date_exact=None):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT e.*, c.name as customer_name, c.price_per_jar FROM entries e JOIN customers c ON e.customer_id = c.id WHERE 1=1"
    params = []
    
    if customer_id:
        query += " AND e.customer_id = ?"
        params.append(customer_id)
        
    if month and year:
        month_str = f"{year}-{month:02d}"
        query += " AND e.date LIKE ?"
        params.append(f"{month_str}%")
        
    if date_exact:
        query += " AND e.date = ?"
        params.append(date_exact)
        
    query += " ORDER BY e.date DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def generate_bill_html(customer_row, entries_df, month_str, bill_number):
    name = customer_row['name']
    address = customer_row['address']
    jars_holding = customer_row['jars_holding']
    price_per_jar = customer_row['price_per_jar']
    security_deposit = customer_row['jar_security_deposit']
    previous_dues = customer_row['previous_dues']
    
    total_delivered = entries_df['jars_delivered'].sum() if not entries_df.empty else 0
    total_returned = entries_df['jars_returned'].sum() if not entries_df.empty else 0
    pending_jars = total_delivered - total_returned
    
    current_bill_amount = total_delivered * price_per_jar
    total_payable = current_bill_amount + previous_dues
    
    # Generate table rows
    table_rows = ""
    for i, row in entries_df.sort_values(by='date').iterrows():
        date_obj = datetime.strptime(row['date'], '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d %b %Y')
        deliv = row['jars_delivered']
        ret = row['jars_returned']
        
        status = "Verified" if (deliv > 0 and ret > 0) else "Delivered"
        status_class = "bg-green-100 text-green-700" if status == "Verified" else "bg-blue-100 text-blue-700"
        
        table_rows += f"""
        <tr class="border-b border-slate-100 text-sm">
            <td class="py-3 px-4 font-mono text-slate-500">{i+1}</td>
            <td class="py-3 px-4 text-slate-700">{formatted_date}</td>
            <td class="py-3 px-4 text-slate-500">20L Mineral Jar Delivery</td>
            <td class="py-3 px-4 text-slate-700 font-semibold">{deliv}</td>
            <td class="py-3 px-4 text-slate-700">{ret}</td>
            <td class="py-3 px-4"><span class="px-2 py-1 rounded-full text-xs font-medium {status_class}">{status}</span></td>
        </tr>
        """
        
    if entries_df.empty:
        table_rows = """<tr><td colspan="6" class="py-4 text-center text-slate-500">No deliveries found for this billing cycle.</td></tr>"""

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Invoice {bill_number}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f1f5f9; color: #0f172a; }}
            .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
            @media print {{
                body {{ background-color: white; }}
                .no-print {{ display: none !important; }}
                .print-container {{ padding: 0; box-shadow: none; margin: 0; max-width: 100%; }}
            }}
        </style>
    </head>
    <body class="py-8">
        <div class="max-w-4xl mx-auto bg-white rounded-xl shadow-sm overflow-hidden print-container">
            <!-- Accent Top Bar -->
            <div class="h-3 w-full bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600"></div>
            
            <div class="p-8 pb-4">
                <!-- Header -->
                <div class="flex justify-between items-start border-b border-slate-100 pb-6 mb-6">
                    <div class="flex items-center gap-4">
                        <div>
                            <div class="flex items-center gap-3">
                                <h1 class="text-3xl font-extrabold tracking-tight text-slate-800">OOS AQUA</h1>
                                <span class="bg-cyan-50 text-cyan-700 border border-cyan-100 text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded">NATURAL MINERAL WATER</span>
                            </div>
                            <p class="text-sm font-semibold text-slate-700 mt-1">M/S CROSS LIGHT</p>
                            <p class="text-sm text-slate-500">Ranchi, Jharkhand</p>
                            <p class="text-sm text-slate-500">Phone: +91 9117456957</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="inline-block bg-slate-50 text-slate-600 border border-slate-200 text-xs font-bold uppercase tracking-widest px-3 py-1 rounded mb-3">MONTHLY JAR DELIVERY CHALLAN</div>
                        <p class="text-slate-500 text-sm">Bill/Card No.</p>
                        <p class="text-lg font-bold font-mono text-slate-800">{bill_number}</p>
                        <p class="text-slate-500 text-sm mt-2">Billing Cycle</p>
                        <p class="font-medium text-slate-700">{month_str}</p>
                    </div>
                </div>

                <!-- Customer Info -->
                <div class="bg-slate-50 p-5 rounded-lg mb-6 border border-slate-100">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <p class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Billed To</p>
                            <h2 class="text-xl font-bold text-slate-800">{name}</h2>
                            <p class="text-sm text-slate-600 mt-1">{address if address else "Address not provided"}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Customer Stats</p>
                            <div class="inline-block bg-white px-4 py-2 rounded shadow-sm border border-slate-100 mt-1">
                                <span class="text-xs text-slate-500">Current Jars Holding:</span>
                                <span class="ml-2 font-bold text-cyan-600">{jars_holding}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Summary Metrics -->
                <div class="grid grid-cols-3 gap-4 mb-8">
                    <div class="bg-white border border-slate-200 p-4 rounded-lg text-center">
                        <p class="text-xs font-semibold text-slate-500 uppercase">Total Filled Delivered</p>
                        <p class="text-2xl font-bold text-slate-800 mt-1">{total_delivered}</p>
                    </div>
                    <div class="bg-white border border-slate-200 p-4 rounded-lg text-center">
                        <p class="text-xs font-semibold text-slate-500 uppercase">Total Empty Received</p>
                        <p class="text-2xl font-bold text-slate-800 mt-1">{total_returned}</p>
                    </div>
                    <div class="bg-white border border-slate-200 p-4 rounded-lg text-center bg-cyan-50 border-cyan-100">
                        <p class="text-xs font-semibold text-cyan-700 uppercase">Pending Empty Jars</p>
                        <p class="text-2xl font-bold text-cyan-700 mt-1">{pending_jars}</p>
                    </div>
                </div>

                <!-- Delivery Table -->
                <div class="mb-8">
                    <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">Delivery Log</h3>
                    <div class="overflow-x-auto border border-slate-200 rounded-lg">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                                    <th class="py-3 px-4">#</th>
                                    <th class="py-3 px-4">Date</th>
                                    <th class="py-3 px-4">Description/Batch</th>
                                    <th class="py-3 px-4">Delivered Filled</th>
                                    <th class="py-3 px-4">Received Empty</th>
                                    <th class="py-3 px-4">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                            <tfoot>
                                <tr class="bg-slate-50 text-sm font-bold text-slate-700">
                                    <td colspan="3" class="py-3 px-4 text-right">TOTALS:</td>
                                    <td class="py-3 px-4">{total_delivered}</td>
                                    <td class="py-3 px-4">{total_returned}</td>
                                    <td class="py-3 px-4">Balance: {pending_jars}</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                </div>

                <!-- Financial Section -->
                <div class="grid grid-cols-2 gap-8 mb-8">
                    <!-- Terms -->
                    <div>
                        <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">Terms & Payment Modes</h3>
                        <ul class="text-xs text-slate-600 space-y-2 mb-4 list-disc pl-4">
                            <li>We accept UPI, Cash, and Net Banking.</li>
                            <li>Payment is due within 7 days of invoice generation.</li>
                            <li>Please return empty jars in good condition. Damaged/lost jars will be charged.</li>
                        </ul>
                        <div class="bg-slate-50 p-3 rounded border border-slate-200">
                            <p class="text-xs font-semibold text-slate-700 mb-1">GPay/PhonePe UPI ID:</p>
                            <p class="text-sm font-mono font-bold text-slate-800">9117456957@ybl</p>
                        </div>
                    </div>
                    
                    <!-- Breakdown -->
                    <div class="bg-slate-50 p-5 rounded-lg border border-slate-200">
                        <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4 border-b border-slate-200 pb-2">Billing Breakdown</h3>
                        
                        <div class="flex justify-between text-sm mb-2 text-slate-600">
                            <span>20L Mineral Jars Delivered</span>
                            <span class="font-medium">{total_delivered} Jars</span>
                        </div>
                        <div class="flex justify-between text-sm mb-2 text-slate-600">
                            <span>Rate per Jar</span>
                            <span class="font-medium font-mono">₹{price_per_jar:.2f}</span>
                        </div>
                        <div class="flex justify-between text-sm mb-4 text-slate-600">
                            <span>Empty Jar Security Deposit</span>
                            <span class="font-medium {'text-green-600' if security_deposit > 0 else ''}">{ 'Adjusted' if security_deposit > 0 else '₹0.00' }</span>
                        </div>
                        
                        <div class="border-t border-slate-200 pt-3 mb-2 flex justify-between text-sm">
                            <span class="font-semibold text-slate-700">Current Bill Amount</span>
                            <span class="font-bold font-mono text-slate-800">₹{current_bill_amount:.2f}</span>
                        </div>
                        <div class="flex justify-between text-sm mb-3">
                            <span class="font-semibold text-slate-700">Previous Dues / Balance</span>
                            <span class="font-bold font-mono text-slate-800">₹{previous_dues:.2f}</span>
                        </div>
                        
                        <div class="border-t-2 border-slate-300 pt-3 flex justify-between items-center">
                            <span class="font-extrabold text-slate-900 text-base">TOTAL NET PAYABLE</span>
                            <span class="font-extrabold text-xl font-mono text-cyan-700 bg-cyan-50 px-3 py-1 rounded border border-cyan-100">₹{total_payable:.2f}</span>
                        </div>
                    </div>
                </div>

                <!-- Signatures -->
                <div class="grid grid-cols-2 gap-8 mt-12 pt-8 border-t border-slate-100">
                    <div>
                        <div class="border-b border-slate-300 w-48 mb-2"></div>
                        <p class="text-xs font-semibold text-slate-500 uppercase">Customer Confirmation</p>
                        <p class="text-[10px] text-slate-400 mt-1">Signature & Date</p>
                    </div>
                    <div class="text-right">
                        <div class="border-b border-slate-300 w-48 mb-2 ml-auto"></div>
                        <p class="text-xs font-semibold text-slate-500 uppercase">Authorized Dispatch Manager</p>
                        <p class="text-[10px] text-slate-400 mt-1">For M/S CROSS LIGHT</p>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="bg-slate-800 text-slate-300 p-4 text-center text-xs">
                <p>Thank you for choosing OOS AQUA – Pure Natural Mineral Water.</p>
                <p class="mt-1 font-medium text-slate-100">Helpline: +91 9608107897</p>
            </div>
        </div>
        
        <!-- Print Button (Hidden when printing) -->
        <div class="max-w-4xl mx-auto mt-6 text-center no-print pb-8">
            <button onclick="window.print()" class="bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-2 px-6 rounded-lg shadow-sm transition duration-150 ease-in-out flex items-center justify-center mx-auto gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                Print Invoice
            </button>
        </div>
        
        <!-- Auto Print Script -->
        <script>
            // Uncomment below line to auto-print on open
            window.onload = function() {{ window.print(); }}
        </script>
    </body>
    </html>
    """
    return html


# --- APP TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Daily Entry", "🧾 Monthly Billing", "👥 Customers", "⚙️ Dues & Security"])

# Fetch customers
customers_df = get_customers()

with tab1:
    st.header("Daily Entry")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        entry_date = st.date_input("Date", datetime.today())
        
        if not customers_df.empty:
            customer_options = {row['id']: f"{row['name']} ({row['phone']})" for _, row in customers_df.iterrows()}
            selected_customer = st.selectbox("Select Customer", options=list(customer_options.keys()), format_func=lambda x: customer_options[x])
            
            jars_delivered = st.number_input("Jars Delivered", min_value=0, value=0, step=1)
            jars_returned = st.number_input("Jars Returned", min_value=0, value=0, step=1)
            
            if st.button("Save Entry", type="primary"):
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO entries (customer_id, date, jars_delivered, jars_returned) VALUES (?, ?, ?, ?)",
                    (selected_customer, entry_date.strftime("%Y-%m-%d"), jars_delivered, jars_returned)
                )
                conn.commit()
                conn.close()
                st.success("Entry saved successfully!")
                st.rerun()
        else:
            st.warning("Please add customers first in the 'Customers' tab.")
            
    with col2:
        st.subheader(f"Entries for {entry_date.strftime('%d %b %Y')}")
        today_entries = get_entries(date_exact=entry_date.strftime("%Y-%m-%d"))
        
        if not today_entries.empty:
            # Metrics
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.markdown(f'<div class="metric-card"><div class="metric-label">Total Delivered</div><div class="metric-value">{today_entries["jars_delivered"].sum()}</div></div>', unsafe_allow_html=True)
            with m_col2:
                st.markdown(f'<div class="metric-card"><div class="metric-label">Total Returned</div><div class="metric-value">{today_entries["jars_returned"].sum()}</div></div>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Display entries table
            display_df = today_entries[['customer_name', 'jars_delivered', 'jars_returned']].rename(
                columns={'customer_name': 'Customer', 'jars_delivered': 'Delivered', 'jars_returned': 'Returned'}
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No entries for this date.")

with tab2:
    st.header("Monthly Billing")
    
    col1, col2 = st.columns(2)
    with col1:
        years = list(range(2023, datetime.now().year + 2))
        selected_year = st.selectbox("Select Year", years, index=years.index(datetime.now().year))
    with col2:
        months = {i: calendar.month_name[i] for i in range(1, 13)}
        selected_month = st.selectbox("Select Month", options=list(months.keys()), format_func=lambda x: months[x], index=datetime.now().month - 1)
        
    month_str = f"{calendar.month_name[selected_month]} {selected_year}"
    
    st.markdown("---")
    
    if not customers_df.empty:
        for _, customer in customers_df.iterrows():
            customer_entries = get_entries(customer_id=customer['id'], month=selected_month, year=selected_year)
            
            total_deliv = customer_entries['jars_delivered'].sum() if not customer_entries.empty else 0
            total_ret = customer_entries['jars_returned'].sum() if not customer_entries.empty else 0
            pending = total_deliv - total_ret
            current_bill = total_deliv * customer['price_per_jar']
            total_due = current_bill + customer['previous_dues']
            
            with st.container():
                st.markdown(f"""
                <div class="customer-card">
                    <h3 style="margin-top:0; color:#0f172a;">{customer['name']}</h3>
                    <p style="color:#64748b; margin-bottom:15px; font-size:0.9rem;">Rate: ₹{customer['price_per_jar']} | Prev Dues: ₹{customer['previous_dues']}</p>
                    <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                        <div style="background:#f1f5f9; padding:10px; border-radius:5px; flex:1; min-width:120px;">
                            <div style="font-size:0.8rem; color:#64748b;">Delivered</div>
                            <div style="font-size:1.2rem; font-weight:bold; color:#0f172a;">{total_deliv}</div>
                        </div>
                        <div style="background:#f1f5f9; padding:10px; border-radius:5px; flex:1; min-width:120px;">
                            <div style="font-size:0.8rem; color:#64748b;">Returned</div>
                            <div style="font-size:1.2rem; font-weight:bold; color:#0f172a;">{total_ret}</div>
                        </div>
                        <div style="background:#f1f5f9; padding:10px; border-radius:5px; flex:1; min-width:120px;">
                            <div style="font-size:0.8rem; color:#64748b;">Pending</div>
                            <div style="font-size:1.2rem; font-weight:bold; color:#0284c7;">{pending}</div>
                        </div>
                        <div style="background:#e0f2fe; padding:10px; border-radius:5px; flex:1; min-width:150px; border:1px solid #bae6fd;">
                            <div style="font-size:0.8rem; color:#0369a1;">Total Due</div>
                            <div style="font-size:1.4rem; font-weight:bold; color:#0c4a6e;">₹{total_due:.2f}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # HTML Bill generation
                bill_number = f"OA-{selected_year}/{customer['id']:03d}"
                html_string = generate_bill_html(customer, customer_entries, month_str, bill_number)
                
                st.download_button(
                    label="📄 Download PDF Bill",
                    data=html_string,
                    file_name=f"Bill_{customer['name'].replace(' ', '_')}_{month_str}.html",
                    mime="text/html",
                    use_container_width=True,
                    key=f"dl_bill_{customer['id']}"
                )
                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No customers found.")

with tab3:
    st.header("Customers")
    
    with st.expander("➕ Add New Customer", expanded=False):
        with st.form("add_customer_form"):
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                new_name = st.text_input("Name*")
                new_phone = st.text_input("Phone*")
                new_address = st.text_area("Address")
            with c_col2:
                new_price = st.number_input("Price per Jar (₹)*", min_value=0.0, value=20.0, step=1.0)
                new_security = st.number_input("Jar Security Deposit (₹)", min_value=0.0, value=0.0, step=50.0)
                new_holding = st.number_input("Jars Holding", min_value=0, value=0, step=1)
                
            submit_customer = st.form_submit_button("Add Customer")
            
            if submit_customer:
                if new_name and new_phone and new_price is not None:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO customers (name, phone, address, price_per_jar, jar_security_deposit, jars_holding) VALUES (?, ?, ?, ?, ?, ?)",
                        (new_name, new_phone, new_address, new_price, new_security, new_holding)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Customer {new_name} added!")
                    st.rerun()
                else:
                    st.error("Please fill all required fields marked with *")
    
    st.subheader("Customer List")
    if not customers_df.empty:
        # Display as a dataframe
        display_cols = ['id', 'name', 'phone', 'address', 'price_per_jar', 'jars_holding', 'previous_dues']
        st.dataframe(customers_df[display_cols], hide_index=True, use_container_width=True)
        
        st.subheader("Manage Customers")
        for _, cust in customers_df.iterrows():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{cust['name']}** - {cust['phone']}")
            with col2:
                if st.button("Delete", key=f"del_cust_{cust['id']}", type="secondary"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    # Delete entries first
                    c.execute("DELETE FROM entries WHERE customer_id = ?", (cust['id'],))
                    # Delete customer
                    c.execute("DELETE FROM customers WHERE id = ?", (cust['id'],))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted {cust['name']}")
                    st.rerun()
            st.divider()
    else:
        st.info("No customers added yet.")

with tab4:
    st.header("Dues & Security Deposit")
    st.markdown("Manage previous dues and jar security deposits for each customer.")
    
    if not customers_df.empty:
        for _, cust in customers_df.iterrows():
            with st.expander(f"{cust['name']} - Current Dues: ₹{cust['previous_dues']} | Sec. Deposit: ₹{cust['jar_security_deposit']}", expanded=False):
                with st.form(f"dues_form_{cust['id']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        update_dues = st.number_input("Previous Dues (₹)", value=float(cust['previous_dues']), step=10.0, key=f"dues_input_{cust['id']}")
                    with col2:
                        update_security = st.number_input("Security Deposit (₹)", value=float(cust['jar_security_deposit']), step=50.0, key=f"sec_input_{cust['id']}")
                    with col3:
                        update_holding = st.number_input("Jars Holding", value=int(cust['jars_holding']), step=1, key=f"hold_input_{cust['id']}")
                    
                    if st.form_submit_button("Save Updates"):
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE customers 
                            SET previous_dues = ?, jar_security_deposit = ?, jars_holding = ?
                            WHERE id = ?
                        """, (update_dues, update_security, update_holding, cust['id']))
                        conn.commit()
                        conn.close()
                        st.success("Updated successfully!")
                        st.rerun()
    else:
        st.info("No customers available.")
