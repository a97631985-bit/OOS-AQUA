import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error } from './_lib/http.mjs';

export default async (req) => {
  await ensureSchema();

  const url = new URL(req.url);
  const month = url.searchParams.get('month');
  const year = url.searchParams.get('year');
  if (!month || !year) return error(400, 'Missing month or year');

  const likeDate = `${year}-${String(month).padStart(2, '0')}-%`;

  try {
    // Single query for ALL customers (replaces the old per-customer loop = N+1,
    // which was a major source of lag as customers grew).
    const rows = await query(
      `SELECT c.id, c.name, c.phone, c.address, c.price_per_jar,
              c.jar_security_deposit, c.jars_holding, c.previous_dues,
              COALESCE(SUM(e.jars_delivered) FILTER (WHERE e.is_deleted = 0), 0) AS td,
              COALESCE(SUM(e.jars_returned) FILTER (WHERE e.is_deleted = 0), 0) AS tr
       FROM customers c
       LEFT JOIN entries e ON e.customer_id = c.id AND e.date LIKE $1
       WHERE c.is_deleted = 0
       GROUP BY c.id
       ORDER BY c.name`,
      [likeDate]
    );

    const invoices = rows.map((r) => {
      const td = Number(r.td);
      const currentBill = td * r.price_per_jar;
      const totalPayable = currentBill + r.previous_dues;
      return {
        customer: {
          id: r.id,
          name: r.name,
          phone: r.phone,
          address: r.address,
          price_per_jar: r.price_per_jar,
          jar_security_deposit: r.jar_security_deposit,
          jars_holding: r.jars_holding,
          previous_dues: r.previous_dues,
        },
        jars_delivered: td,
        jars_returned: Number(r.tr),
        current_bill: currentBill,
        total_payable: totalPayable,
      };
    });

    let totalRevenue = 0;
    let pendingDues = 0;
    for (const inv of invoices) {
      totalRevenue += inv.current_bill;
      pendingDues += inv.total_payable;
    }

    return json({
      summary: { total_revenue: totalRevenue, pending_dues: pendingDues },
      invoices,
    });
  } catch (err) {
    console.error('[billing] failed', err);
    return error(500, 'Failed to load billing');
  }
};

export const config = { path: '/api/billing', method: ['GET'] };