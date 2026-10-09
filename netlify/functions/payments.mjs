import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error } from './_lib/http.mjs';

export default async (req) => {
  await ensureSchema();
  if (req.method !== 'GET') return error(405, 'Method not allowed');

  const url = new URL(req.url);
  const customerId = url.searchParams.get('customer_id');

  try {
    const params = [];
    let where = 'WHERE pm.is_deleted = 0';
    if (customerId) {
      params.push(Number(customerId));
      where += ` AND pm.customer_id = $${params.length}`;
    }

    const rows = await query(
      `SELECT pm.*, c.name AS customer_name, c.phone AS customer_phone,
              'OA-R-' || LPAD(pm.id::text, 5, '0') AS receipt_no
       FROM payments pm
       JOIN customers c ON c.id = pm.customer_id
       ${where}
       ORDER BY pm.id DESC`,
      params
    );

    const totalCollected = rows.reduce((sum, r) => sum + Number(r.amount), 0);
    return json({
      payments: rows,
      count: rows.length,
      total_collected: totalCollected,
    });
  } catch (err) {
    console.error('[payments] GET failed', err);
    return error(500, 'Failed to load payment history');
  }
};

export const config = { path: '/api/payments', method: ['GET'] };