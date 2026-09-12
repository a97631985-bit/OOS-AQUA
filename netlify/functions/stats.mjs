import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error } from './_lib/http.mjs';

export default async (req) => {
  await ensureSchema();

  const url = new URL(req.url);
  const dateFilter = url.searchParams.get('date') || new Date().toISOString().slice(0, 10);

  let yesterday;
  try {
    const d = new Date(`${dateFilter}T00:00:00`);
    d.setDate(d.getDate() - 1);
    yesterday = d.toISOString().slice(0, 10);
  } catch {
    yesterday = dateFilter;
  }

  try {
    // Today + yesterday in one pass over the index.
    const stats = await query(
      `SELECT
         COALESCE(SUM(jars_delivered) FILTER (WHERE date = $1), 0) AS td,
         COALESCE(SUM(jars_returned) FILTER (WHERE date = $1), 0) AS tr,
         COALESCE(SUM(jars_delivered) FILTER (WHERE date = $2), 0) AS tdy
       FROM entries
       WHERE is_deleted = 0 AND date IN ($1, $2)`,
      [dateFilter, yesterday]
    );

    const cust = await query(
      `SELECT
         COUNT(*) AS ac,
         COALESCE(SUM(jars_holding), 0) AS jc,
         COALESCE(SUM(jar_security_deposit), 0) AS sp,
         COALESCE(SUM(previous_dues), 0) AS pd
       FROM customers WHERE is_deleted = 0`
    );

    const s = stats[0];
    const c = cust[0];
    const delivered = Number(s.td);
    const returned = Number(s.tr);
    const yesterdayDelivered = Number(s.tdy);

    return json({
      today_delivered: delivered,
      today_returned: returned,
      yesterday_delivered: yesterdayDelivered,
      active_accounts: Number(c.ac),
      jars_circulating: Number(c.jc),
      security_pool: Number(c.sp),
      total_dues: Number(c.pd),
    });
  } catch (err) {
    console.error('[stats] failed', err);
    return error(500, 'Failed to load statistics');
  }
};

export const config = { path: '/api/stats', method: ['GET'] };