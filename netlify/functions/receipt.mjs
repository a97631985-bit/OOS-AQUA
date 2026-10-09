import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { html, error } from './_lib/http.mjs';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function rup(n) {
  return '\u20B9' + Number(n || 0).toFixed(2);
}

export default async (req) => {
  await ensureSchema();
  if (req.method !== 'GET') return error(405, 'Method not allowed');

  const url = new URL(req.url);
  const id = url.searchParams.get('id');
  if (!id) return error(400, 'Missing payment id');

  try {
    const rows = await query(
      `SELECT pm.*, c.name AS customer_name, c.phone AS customer_phone, c.address AS customer_address,
              'OA-R-' || LPAD(pm.id::text, 5, '0') AS receipt_no
       FROM payments pm
       JOIN customers c ON c.id = pm.customer_id
       WHERE pm.id = $1`,
      [Number(id)]
    );
    if (!rows.length) return error(404, 'Payment not found');
    const p = rows[0];

    const paidOn = new Date(p.created_at);
    const paidDateStr = paidOn.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'long', year: 'numeric',
    });
    const paidTimeStr = paidOn.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    const monthName = MONTH_NAMES[Number(p.bill_month) - 1] || '';
    const cycle = p.bill_month ? `${monthName} ${p.bill_year}` : '\u2013';
    const typeLabel = p.payment_type === 'full' ? 'Full & Final' : 'Partial';

    const doc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OOS AQUA - Receipt ${p.receipt_no}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f1f5f9; color: #0f172a; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .mono { font-family: 'JetBrains Mono', monospace; }
    @media print {
      body { background: white; padding: 0; }
      .no-print { display: none !important; }
      .print-shadow-none { box-shadow: none !important; border: 1px solid #e2e8f0; }
      @page { size: A4 portrait; margin: 12mm; }
    }
  </style>
</head>
<body class="p-3 sm:p-6 md:p-8 flex flex-col items-center min-h-screen">

  <div class="w-full max-w-2xl mb-4 flex items-center justify-between no-print bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700">
        <span class="material-symbols-outlined text-[18px]">receipt_long</span>
      </span>
      <div>
        <p class="text-xs font-semibold text-slate-900">Payment Receipt Ready</p>
        <p class="text-[11px] text-slate-500">A4 &amp; Mobile Print Optimized</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <button onclick="window.print()" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg shadow-sm transition">Print / Save PDF</button>
      <a href="/" class="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-200 transition">\u2190 Back</a>
    </div>
  </div>

  <div class="w-full max-w-2xl bg-white rounded-2xl border border-slate-200/90 shadow-xl overflow-hidden print-shadow-none">
    <div class="h-2.5 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-600"></div>

    <div class="p-5 sm:p-7 border-b border-slate-100">
      <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
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
            <p class="text-[12px] text-slate-600 mt-1">Helpline: +91 9117456957</p>
          </div>
        </div>
        <div class="sm:text-right">
          <div class="inline-block bg-emerald-600 text-white px-3 py-1 rounded-lg text-xs font-bold tracking-wider uppercase">Payment Receipt</div>
          <div class="mt-2.5 space-y-0.5 text-xs text-slate-500">
            <p><span class="text-slate-400">Receipt No:</span> <span class="font-semibold text-slate-800 mono">${p.receipt_no}</span></p>
            <p><span class="text-slate-400">Date:</span> <span class="font-semibold text-slate-800">${paidDateStr}, ${paidTimeStr}</span></p>
            <p><span class="text-slate-400">Billing Cycle:</span> <span class="font-semibold text-slate-800">${cycle}</span></p>
          </div>
        </div>
      </div>

      <div class="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/70">
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Received From</span>
          <p class="text-sm font-bold text-slate-800 mt-0.5">${p.customer_name}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Phone</span>
          <p class="text-sm font-semibold text-slate-700 mt-0.5">${p.customer_phone || 'N/A'}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Address</span>
          <p class="text-sm font-semibold text-slate-700 mt-0.5">${p.customer_address || 'N/A'}</p>
        </div>
      </div>
    </div>

    <div class="p-5 sm:p-7">
      <div class="bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-emerald-200 rounded-2xl p-6 text-center mb-6">
        <p class="text-[11px] font-bold text-emerald-700 uppercase tracking-wider mb-1">Amount Received (${typeLabel})</p>
        <p class="text-4xl font-black text-emerald-800 mono">${rup(p.amount)}</p>
      </div>

      <div class="rounded-xl border border-slate-200 overflow-hidden">
        <div class="flex justify-between px-4 py-2.5 text-sm border-b border-slate-100 bg-slate-50/60">
          <span class="text-slate-500">Current Month Bill</span>
          <span class="font-semibold text-slate-800 mono">${rup(p.current_bill)}</span>
        </div>
        <div class="flex justify-between px-4 py-2.5 text-sm border-b border-slate-100">
          <span class="text-slate-500">Previous Dues</span>
          <span class="font-semibold text-slate-800 mono">${rup(p.previous_dues)}</span>
        </div>
        <div class="flex justify-between px-4 py-2.5 text-sm border-b border-slate-100 bg-slate-50/60">
          <span class="font-semibold text-slate-700">Total Payable</span>
          <span class="font-bold text-slate-900 mono">${rup(p.total_payable)}</span>
        </div>
        <div class="flex justify-between px-4 py-2.5 text-sm border-b border-slate-100">
          <span class="font-semibold text-emerald-700">Amount Paid Now</span>
          <span class="font-bold text-emerald-700 mono">${rup(p.amount)}</span>
        </div>
        <div class="flex justify-between px-4 py-3 text-sm bg-amber-50/50">
          <span class="font-bold text-slate-800">Remaining Dues (carried forward)</span>
          <span class="font-black text-amber-700 mono">${rup(p.remaining_dues)}</span>
        </div>
      </div>

      <div class="mt-8 pt-5 border-t border-slate-200 grid grid-cols-2 gap-6 text-center">
        <div>
          <div class="h-12 flex items-center justify-center">
            <div class="px-3 py-1 rounded border border-dashed border-slate-300 text-slate-400 text-[11px] uppercase tracking-wider">Customer Confirmation</div>
          </div>
          <p class="text-xs font-semibold text-slate-700 mt-1">Customer Acknowledgment</p>
        </div>
        <div>
          <div class="h-12 flex items-center justify-center">
            <div class="px-3 py-1 rounded border border-dashed border-slate-300 text-slate-400 text-[11px] uppercase tracking-wider">For OOS AQUA</div>
          </div>
          <p class="text-xs font-semibold text-slate-700 mt-1">Authorized Signatory</p>
        </div>
      </div>
    </div>

    <div class="bg-slate-900 text-slate-400 px-6 py-3 text-center text-[11px]">
      <span>This is a computer-generated receipt. Thank you for choosing <strong>OOS AQUA</strong>.</span>
    </div>
  </div>

</body>
</html>`;

    return html(doc);
  } catch (err) {
    console.error('[receipt] failed', err);
    return error(500, 'Failed to generate receipt');
  }
};

export const config = { path: '/api/payment/receipt', method: ['GET'] };