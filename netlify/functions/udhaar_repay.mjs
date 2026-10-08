import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

export default async (req) => {
  if (req.method !== 'POST') return error(405, 'Method not allowed');
  await ensureSchema();

  const data = await readJson(req);
  const id = Number(data.udhaar_id);
  const amount = Number(data.amount);
  if (!id) return error(400, 'udhaar_id is required');
  if (!amount || amount <= 0) return error(400, 'Enter a valid repayment amount');

  try {
    // Money matters: full snapshot before recording repayment.
    await createBackup('before_udhaar_repay');

    const rows = await query(
      'SELECT * FROM udhaar WHERE id = $1 AND is_deleted = 0',
      [id]
    );
    if (!rows.length) return error(404, 'Udhaar record not found');
    const loan = rows[0];

    const repaid = await query(
      'SELECT COALESCE(SUM(amount), 0) AS repaid FROM udhaar_payments WHERE udhaar_id = $1 AND is_deleted = 0',
      [id]
    );
    const newRepaid = Number(repaid[0].repaid) + amount;
    const remaining = Math.max(0, Number(loan.amount_given) - newRepaid);

    await query(
      `INSERT INTO udhaar_payments (udhaar_id, amount, note) VALUES ($1, $2, $3)`,
      [id, amount, (data.note || '').trim()]
    );

    return json({
      success: true,
      udhaar_id: id,
      repaid: newRepaid,
      remaining,
      message: `Repayment of Rs.${amount.toFixed(0)} recorded. Remaining udhaar: Rs.${remaining.toFixed(0)}`,
    });
  } catch (err) {
    console.error('[udhaar/repay] failed', err);
    return error(500, 'Failed to save repayment');
  }
};

export const config = { path: '/api/udhaar/repay', method: ['POST'] };