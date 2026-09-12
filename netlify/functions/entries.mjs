import { query, withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { ensureRecentBackup } from './_lib/backup.mjs';

export default async (req) => {
  await ensureSchema();

  if (req.method === 'GET') {
    const url = new URL(req.url);
    const dateFilter = url.searchParams.get('date');
    const customerId = url.searchParams.get('customer_id');
    const month = url.searchParams.get('month');
    const year = url.searchParams.get('year');

    let sql = `SELECT e.*, c.name FROM entries e
               JOIN customers c ON e.customer_id = c.id
               WHERE e.is_deleted = 0`;
    const params = [];

    if (dateFilter) {
      params.push(dateFilter);
      sql += ` AND e.date = $${params.length}`;
    }
    if (customerId) {
      params.push(Number(customerId));
      sql += ` AND e.customer_id = $${params.length}`;
    }
    if (month && year) {
      params.push(`${year}-${month.padStart(2, '0')}-%`);
      sql += ` AND e.date LIKE $${params.length}`;
    }
    sql += ' ORDER BY e.id DESC';

    try {
      const rows = await query(sql, params);
      return json(rows);
    } catch (err) {
      console.error('[entries] GET failed', err);
      return error(500, 'Failed to load entries');
    }
  }

  if (req.method === 'POST') {
    const data = await readJson(req);

    const customerId = Number(data.customer_id);
    const date = data.date;
    const delivered = Number(data.jars_delivered ?? 0);
    const returned = Number(data.jars_returned ?? 0);

    if (!customerId || !date) return error(400, 'Customer and date are required');
    if (delivered === 0 && returned === 0) return error(400, 'No jars quantities provided');

    const netJars = delivered - returned;

    try {
      await ensureRecentBackup('auto');
      const newId = await withTransaction(async (client) => {
        const ins = await client.query(
          `INSERT INTO entries (customer_id, date, jars_delivered, jars_returned)
           VALUES ($1, $2, $3, $4) RETURNING id`,
          [customerId, date, delivered, returned]
        );
        await client.query(
          'UPDATE customers SET jars_holding = jars_holding + $1 WHERE id = $2',
          [netJars, customerId]
        );
        return ins.rows[0].id;
      });
      return json({ success: true, id: newId });
    } catch (err) {
      console.error('[entries] POST failed', err);
      return error(500, 'Failed to save entry');
    }
  }

  return error(405, 'Method not allowed');
};

export const config = { path: '/api/entries', method: ['GET', 'POST'] };