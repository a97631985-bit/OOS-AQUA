import { query, withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

/**
 * Recovery helper: un-hides records that were soft-deleted (is_deleted=1).
 * - No filter  -> restore EVERYTHING that is soft-deleted.
 * - { customers: [ids], entries: [ids] } -> restore only those ids.
 * Always snapshots the current state BEFORE restoring, so nothing can be lost.
 */
export default async (req) => {
  if (req.method !== 'POST') return error(405, 'Method not allowed');
  await ensureSchema();

  const data = await readJson(req);
  const custIds = Array.isArray(data?.customers) ? data.customers.map(Number) : null;
  const entryIds = Array.isArray(data?.entries) ? data.entries.map(Number) : null;

  try {
    await createBackup('before_restore');

    let restoredCustomers = 0;
    let restoredEntries = 0;

    await withTransaction(async (client) => {
      if (custIds && custIds.length) {
        const r = await client.query(
          `UPDATE customers SET is_deleted = 0 WHERE is_deleted = 1 AND id = ANY($1)`,
          [custIds]
        );
        restoredCustomers = r.rowCount;
      } else {
        const r = await client.query(
          'UPDATE customers SET is_deleted = 0 WHERE is_deleted = 1'
        );
        restoredCustomers = r.rowCount;
      }

      if (entryIds && entryIds.length) {
        const r = await client.query(
          `UPDATE entries SET is_deleted = 0 WHERE is_deleted = 1 AND id = ANY($1)`,
          [entryIds]
        );
        restoredEntries = r.rowCount;
      } else {
        const r = await client.query(
          'UPDATE entries SET is_deleted = 0 WHERE is_deleted = 1'
        );
        restoredEntries = r.rowCount;
      }
    });

    return json({
      success: true,
      message: `Restored ${restoredCustomers} customers and ${restoredEntries} entries.`,
      restored_customers: restoredCustomers,
      restored_entries: restoredEntries,
    });
  } catch (err) {
    console.error('[restore] failed', err);
    return error(500, 'Failed to restore records');
  }
};

export const config = { path: '/api/restore', method: ['POST'] };