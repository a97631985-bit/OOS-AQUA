import { query, withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

export default async (req) => {
  await ensureSchema();
  if (req.method !== 'POST') return error(405, 'Method not allowed');

  const data = await readJson(req);
  const customerId = Number(data.customer_id);
  const paymentType = data.type; // 'full' | 'partial'
  const amount = Number(data.amount ?? 0);
  const month = data.month;
  const year = data.year;

  if (!customerId) return error(400, 'Customer ID required');
  if (!month || !year) return error(400, 'Month and year required');

  try {
    // Money matters: snapshot BEFORE any change.
    await createBackup('before_payment');

    const likeDate = `${year}-${String(month).padStart(2, '0')}-%`;

    const c = await query('SELECT * FROM customers WHERE id = $1', [customerId]);
    if (!c.length) return error(404, 'Customer not found');

    const customer = c[0];
    const stats = await query(
      `SELECT COALESCE(SUM(jars_delivered), 0) AS td
       FROM entries WHERE customer_id = $1 AND date LIKE $2 AND is_deleted = 0`,
      [customerId, likeDate]
    );
    const td = Number(stats[0].td);
    const currentBill = td * customer.price_per_jar;
    const totalPayable = currentBill + customer.previous_dues;

    let paidAmount;
    let newDues;
    if (paymentType === 'full') {
      // FULL = clear the ENTIRE payable: this month's bill + all previous dues.
      paidAmount = totalPayable;
      newDues = 0;
    } else {
      if (!amount || amount <= 0) return error(400, 'Enter a valid payment amount');
      paidAmount = amount;
      // PARTIAL = only pay this much; the rest carries over to next month's dues.
      newDues = Math.max(0, totalPayable - paidAmount);
    }

    // Update dues AND save a permanent payment record (receipt) atomically.
    const payment = await withTransaction(async (client) => {
      await client.query(
        'UPDATE customers SET previous_dues = $1 WHERE id = $2',
        [newDues, customerId]
      );
      const ins = await client.query(
        `INSERT INTO payments
           (customer_id, amount, payment_type, current_bill, previous_dues, total_payable, remaining_dues, bill_month, bill_year)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         RETURNING id`,
        [customerId, paidAmount, paymentType === 'full' ? 'full' : 'partial',
         currentBill, customer.previous_dues, totalPayable, newDues,
         Number(month), Number(year)]
      );
      return ins.rows[0];
    });

    const receiptNo = `OA-R-${String(payment.id).padStart(5, '0')}`;
    const done = newDues === 0 ? 'fully cleared.' : `next month previous dues will be Rs.${newDues.toFixed(0)}.`;

    return json({
      success: true,
      payment_id: payment.id,
      receipt_no: receiptNo,
      receipt_url: `/api/payment/receipt?id=${payment.id}`,
      current_bill: currentBill,
      previous_dues: customer.previous_dues,
      total_payable: totalPayable,
      paid_amount: paidAmount,
      remaining_dues: newDues,
      message: `Payment of Rs.${paidAmount.toFixed(0)} recorded against total Rs.${totalPayable.toFixed(0)} (bill Rs.${currentBill.toFixed(0)} + previous dues Rs.${customer.previous_dues.toFixed(0)}). Dues ${done}`,
    });
  } catch (err) {
    console.error('[payment] failed', err);
    return error(500, 'Failed to record payment');
  }
};

export const config = { path: '/api/payment', method: ['POST'] };