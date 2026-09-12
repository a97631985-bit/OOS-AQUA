import { query, withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { ensureRecentBackup } from './_lib/backup.mjs';

export default async (req) => {
  await ensureSchema();

  if (req.method === 'GET') {
    try {
      const rows = await query(
        'SELECT * FROM customers WHERE is_deleted = 0 ORDER BY name'
      );
      return json(rows);
    } catch (err) {
      console.error('[customers] GET failed', err);
      return error(500, 'Failed to load customers');
    }
  }

  if (req.method === 'POST') {
    const data = await readJson(req);

    const name = (data.name || '').trim();
    const phone = (data.phone || '').trim();
    if (!name || !phone) {
      return error(400, 'Name and phone are required');
    }

    try {
      await ensureRecentBackup('auto');
      const newId = await withTransaction(async (client) => {
        const res = await client.query(
          `INSERT INTO customers
             (name, phone, address, price_per_jar, jar_security_deposit, jars_holding, previous_dues)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id`,
          [
            name,
            phone,
            data.address || '',
            Number(data.price_per_jar ?? 35),
            Number(data.jar_security_deposit ?? 0),
            Number(data.jars_holding ?? 0),
            Number(data.previous_dues ?? 0),
          ]
        );
        return res.rows[0].id;
      });
      return json({ success: true, id: newId });
    } catch (err) {
      console.error('[customers] POST failed', err);
      return error(500, 'Failed to save customer');
    }
  }

  return error(405, 'Method not allowed');
};

export const config = { path: '/api/customers', method: ['GET', 'POST'] };