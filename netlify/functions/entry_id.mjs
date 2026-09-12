import { query, withTransaction } from './_lib/db.mjs';
import { nullableId } from './_lib/params.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

export default async (_req, context) => {
  await ensureSchema();
  const id = nullableId(context);

  if (!id) return error(400, 'Invalid entry id');

  try {
    // Data safety: snapshot BEFORE changing anything.
    await createBackup('before_entry_delete');

    await withTransaction(async (client) => {
      const res = await client.query(
        `SELECT customer_id, jars_delivered, jars_returned
         FROM entries WHERE id = $1 AND is_deleted = 0`,
        [id]
      );
      const entry = res.rows[0];
      if (!entry) throw Object.assign(new Error('Entry not found'), { status: 404 });

      const netJars = entry.jars_delivered - entry.jars_returned;
      await client.query(
        'UPDATE customers SET jars_holding = jars_holding - $1 WHERE id = $2',
        [netJars, entry.customer_id]
      );
      await client.query(
        'UPDATE entries SET is_deleted = 1 WHERE id = $1',
        [id]
      );
    });

    return json({ success: true });
  } catch (err) {
    if (err.status === 404) return error(404, 'Entry not found');
    console.error('[entry] DELETE failed', err);
    return error(500, 'Failed to delete entry');
  }
};

export const config = { path: '/api/entries/:id', method: ['DELETE'] };