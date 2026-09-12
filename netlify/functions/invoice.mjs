import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { html, error } from './_lib/http.mjs';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

export default async (req) => {
  await ensureSchema();

  const url = new URL(req.url);
  const customerId = url.searchParams.get('customer_id');
  const month = url.searchParams.get('month');
  const year = url.searchParams.get('year');

  if (!customerId || !month || !year) return error(400, 'Missing parameters');

  try {
    const crows = await query('SELECT * FROM customers WHERE id = $1', [Number(customerId)]);
    if (!crows.length) return error(404, 'Customer not found');
    const c = crows[0];

    const likeDate = `${year}-${String(month).padStart(2, '0')}-%`;
    const entries = await query(
      `SELECT * FROM entries
       WHERE customer_id = $1 AND date LIKE $2 AND is_deleted = 0
       ORDER BY date`,
      [Number(customerId), likeDate]
    );

    const td = entries.reduce((sum, e) => sum + Number(e.jars_delivered), 0);
    const tr = entries.reduce((sum, e) => sum + Number(e.jars_returned), 0);
    const pending = td - tr;
    const currentBill = td * c.price_per_jar;
    const totalPayable = currentBill + c.previous_dues;
    const securityDeposit = Number(c.jar_security_deposit);

    const monthName = MONTH_NAMES[Number(month) - 1] || month;
    const billNumber = `OA-${year}/${String(c.id).padStart(3, '0')}`;

    let tableRows = '';
    entries.forEach((e, idx) => {
      const d = Number(e.jars_delivered);
      const r = Number(e.jars_returned);
      const statusHtml = r > 0
        ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700">Verified</span>'
        : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">Delivered</span>';
      const rDisplay = r > 0 ? String(r) : '\u2013';
      const n = String(idx + 1).padStart(2, '0');
      tableRows += `
            <tr class="hover:bg-slate-50/60">
              <td class="py-2 px-3 text-slate-400 font-mono text-[11px]">${n}</td>
              <td class="py-2 px-3 font-semibold text-slate-800">${e.date}</td>
              <td class="py-2 px-3 text-slate-600">Standard Delivery</td>
              <td class="py-2 px-3 text-center font-bold text-slate-900 bg-cyan-50/20">${d}</td>
              <td class="py-2 px-3 text-center font-semibold text-slate-700 bg-sky-50/20">${rDisplay}</td>
              <td class="py-2 px-3 text-center">${statusHtml}</td>
            </tr>`;
    });

    if (!entries.length) {
      tableRows = '<tr><td colspan="6" class="py-6 text-center text-slate-400 italic">No deliveries recorded this month.</td></tr>';
    }

    const securityDisplay = securityDeposit > 0
      ? '<span class="font-semibold text-emerald-700 mono">Adjusted</span>'
      : '<span class="font-semibold text-slate-800 mono">\u20B90.00</span>';

    const pendingStr = pending < 100 ? String(pending).padStart(2, '0') : String(pending);

    const page2 = buildPaymentPage(totalPayable, billNumber, monthName, year);

    const doc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OOS AQUA - Bill ${billNumber}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Plus Jakarta Sans', sans-serif;
      background-color: #f1f5f9;
      color: #0f172a;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .mono {
      font-family: 'JetBrains Mono', monospace;
    }
    @media print {
      body {
        background: white;
        padding: 0;
      }
      .no-print {
        display: none !important;
      }
      .print-shadow-none {
        box-shadow: none !important;
        border: 1px solid #e2e8f0;
      }
      @page {
        size: A4 portrait;
        margin: 12mm;
      }
    }
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
        <p class="text-[11px] text-slate-500">A4 &amp; Mobile Print Optimized</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <button onclick="window.print()" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-medium rounded-lg shadow-sm transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
        </svg>
        <span class="">Print / Save PDF</span>
      </button>
      <a href="/" class="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 text-slate-700 text-xs font-medium rounded-lg hover:bg-slate-200 transition">\u2190 Back</a>
    </div>
  </div>

  <!-- Bill / Challan Document Card -->
  <div class="w-full max-w-2xl bg-white rounded-2xl border border-slate-200/90 shadow-xl overflow-hidden print-shadow-none">

    <!-- Top Accent Bar -->
    <div class="h-2.5 bg-gradient-to-r from-cyan-500 via-sky-500 to-blue-600"></div>

    <!-- Header Section -->
    <div class="p-5 sm:p-7 border-b border-slate-100">
      <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">

        <!-- Brand &amp; Supplier Details -->
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

        <!-- Document Badge &amp; Meta -->
        <div class="sm:text-right flex flex-col sm:items-end justify-between">
          <div class="inline-block bg-slate-900 text-white px-3 py-1 rounded-lg text-xs font-bold tracking-wider uppercase">
            Monthly Jar Delivery Challan
          </div>
          <div class="mt-2.5 space-y-0.5 text-xs text-slate-500">
            <p class=""><span class="text-slate-400">Bill / Card No:</span> <span class="font-semibold text-slate-800 mono">${billNumber}</span></p>
            <p class=""><span class="text-slate-400">Billing Cycle:</span> <span class="font-semibold text-slate-800">${monthName} ${year}</span></p>
          </div>
        </div>
      </div>

      <!-- Customer Info Card -->
      <div class="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/70">
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Customer Name</span>
          <p class="text-sm font-bold text-slate-800 mt-0.5">${c.name}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Address / Flat No.</span>
          <p class="text-sm font-semibold text-slate-700 mt-0.5">${c.address || 'N/A'}</p>
        </div>
        <div>
          <span class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">No. of Jars Holding</span>
          <p class="text-sm font-bold text-cyan-800 mt-0.5 mono">${c.jars_holding} Jars In-Hand</p>
        </div>
      </div>

    </div>

    <!-- Summary Metrics -->
    <div class="grid grid-cols-3 divide-x divide-slate-100 bg-cyan-50/30 border-b border-slate-100 text-center py-3">
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Total Filled Delivered</span>
        <p class="text-lg font-bold text-slate-900 mono">${td} <span class="text-xs font-medium text-slate-500">Jars</span></p>
      </div>
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-slate-500">Total Empty Received</span>
        <p class="text-lg font-bold text-slate-900 mono">${tr} <span class="text-xs font-medium text-slate-500">Jars</span></p>
      </div>
      <div>
        <span class="text-[10px] uppercase tracking-wider font-semibold text-cyan-800">Pending Empty Jars</span>
        <p class="text-lg font-bold text-cyan-700 mono">${pendingStr} <span class="text-xs font-medium text-cyan-600">Jars</span></p>
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
            ${tableRows}
          </tbody>
          <tfoot class="bg-slate-50 font-bold border-t-2 border-slate-200 text-slate-800">
            <tr>
              <td colspan="3" class="py-3 px-3 text-right text-xs uppercase tracking-wider text-slate-600">Total Count:</td>
              <td class="py-3 px-3 text-center text-cyan-900 bg-cyan-100/50 text-sm mono font-extrabold">${td}</td>
              <td class="py-3 px-3 text-center text-sky-900 bg-sky-100/50 text-sm mono font-extrabold">${tr}</td>
              <td class="py-3 px-3 text-center text-[11px] text-cyan-800">${pendingStr} Balance</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- Financial Calculation / Amount Due Section -->
      <div class="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">

        <!-- Payment &amp; Bank / UPI Info -->
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
            <span class="font-semibold text-slate-800 mono">${td} Jars</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Rate per Jar:</span>
            <span class="font-semibold text-slate-800 mono">\u20B9${Number(c.price_per_jar).toFixed(2)}</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Empty Jar Security Deposit:</span>
            ${securityDisplay}
          </div>
          <div class="flex justify-between text-xs text-slate-600 pt-1 border-t border-cyan-200/50">
            <span class="">Current Bill Amount:</span>
            <span class="font-semibold text-slate-800 mono">\u20B9${currentBill.toFixed(2)}</span>
          </div>
          <div class="flex justify-between text-xs text-slate-600">
            <span class="">Previous Dues / Balance:</span>
            <span class="font-semibold text-slate-800 mono">\u20B9${Number(c.previous_dues).toFixed(2)}</span>
          </div>
          <div class="border-t border-cyan-200/80 pt-2 flex justify-between items-baseline">
            <span class="text-xs font-bold text-slate-900 uppercase tracking-wide">Total Net Payable:</span>
            <span class="text-lg font-black text-cyan-900 mono">\u20B9${totalPayable.toFixed(2)}</span>
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
      <span class="">Thank you for choosing <strong>OOS AQUA</strong> \u2013 Pure Natural Mineral Water.</span>
      <span class="text-slate-500">Helpline: +91 9608107897</span>
    </div>

  </div>

  ${page2}

</body>
</html>`;

    return html(doc);
  } catch (err) {
    console.error('[invoice] failed', err);
    return error(500, 'Failed to generate invoice');
  }
};

function buildPaymentPage(totalPayable, billNumber, monthName, year) {
  return `
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
        <p class="text-4xl font-black text-cyan-900 mono">\u20B9${totalPayable.toFixed(2)}</p>
        <p class="text-xs text-slate-500 mt-1">Bill: ${billNumber} | ${monthName} ${year}</p>
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
      <span>Thank you for choosing <strong>OOS AQUA</strong> \u2013 Pure Natural Mineral Water. | Helpline: +91 9608107897</span>
    </div>

  </div>`;
}

export const config = { path: '/api/billing/invoice', method: ['GET'] };