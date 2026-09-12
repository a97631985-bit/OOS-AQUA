import { withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

export default async (req) => {
  if (req.method !== 'POST') return error(405, 'Method not allowed');
  await ensureSchema();

  const data = await readJson(req);
  if (!data || !Array.isArray(data.customers) || !Array.isArray(data.entries)) {
    return error(400, 'Expected { customers: [...], entries: [...] }');
  }

  try {
    // Data safety: snapshot BEFORE any import changes the live data.
    await createBackup('before_import');

    let importedCustomers = 0;
    let importedEntries = 0;

    await withTransaction(async (client) => {
      for (const cust of data.customers) {
        const id = Number(cust.id);
        if (!Number.isInteger(id)) continue;
        const existing = await client.query('SELECT id FROM customers WHERE id = $1', [id]);
        if (existing.rowCount > 0) continue;
        await client.query(
          `INSERT INTO customers
             (id, name, phone, address, price_per_jar, jar_security_deposit, jars_holding, previous_dues, is_deleted)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
          [
            id,
            String(cust.name || ''),
            String(cust.phone || ''),
            String(cust.address || ''),
            Number(cust.price_per_jar ?? 35),
            Number(cust.jar_security_deposit ?? 0),
            Number(cust.jars_holding ?? 0),
            Number(cust.previous_dues ?? 0),
            Number(cust.is_deleted ?? 0),
          ]
        );
        importedCustomers += 1;
      }

      for (const entry of data.entries) {
        const id = Number(entry.id);
        if (!Number.isInteger(id)) continue;
        const existing = await client.query('SELECT id FROM entries WHERE id = $1', [id]);
        if (existing.rowCount > 0) continue;
        await client.query(
          `INSERT INTO entries (id, customer_id, date, jars_delivered, jars_returned, is_deleted)
           VALUES ($1, $2, $3, $4, $5, $6)`,
          [
            id,
            Number(entry.customer_id ?? 0),
            String(entry.date || ''),
            Number(entry.jars_delivered ?? 0),
            Number(entry.jars_returned ?? 0),
            Number(entry.is_deleted ?? 0),
          ]
        );
        importedEntries += 1;
      }
    });

    return json({
      success: true,
      message: `Imported ${importedCustomers} customers and ${importedEntries} entries.`,
      imported_customers: importedCustomers,
      imported_entries: importedEntries,
    });
  } catch (err) {
    console.error('[import] failed', err);
    return error(500, 'Failed to import data');
  }
};

export const config = { path: '/api/import', method: ['POST'] };