import { withTransaction } from './_lib/db.mjs';
import { nullableId } from './_lib/params.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { createBackup } from './_lib/backup.mjs';

const UPDATABLE = ['name', 'phone', 'address', 'price_per_jar', 'jar_security_deposit', 'jars_holding', 'previous_dues'];

export default async (req, context) => {
  await ensureSchema();
  const id = nullableId(context);

  if (req.method === 'PUT') {
    const data = await readJson(req);

    const updates = [];
    const params = [];
    for (const key of UPDATABLE) {
      if (key in data && data[key] !== undefined && data[key] !== null && data[key] !== '') {
        const value = ['price_per_jar', 'jar_security_deposit', 'previous_dues'].includes(key)
          ? Number(data[key])
          : ['jars_holding'].includes(key)
            ? Number(data[key])
            : String(data[key]);
        updates.push(`${key} = $${updates.length + 1}`);
        params.push(value);
      }
    }

    if (updates.length === 0) {
      return error(400, 'Nothing to update');
    }

    params.push(id);
    const setClause = updates.join(', ');
    try {
      await withTransaction(async (client) => {
        const res = await client.query(
          `UPDATE customers SET ${setClause} WHERE id = $${params.length}`,
          params
        );
        if (res.rowCount === 0) throw Object.assign(new Error('Customer not found'), { status: 404 });
      });
      return json({ success: true });
    } catch (err) {
      if (err.status === 404) return error(404, 'Customer not found');
      console.error('[customer] PUT failed', err);
      return error(500, 'Failed to update customer');
    }
  }

  if (req.method === 'DELETE') {
    try {
      // Data safety: snapshot BEFORE the change, soft delete keeps the record.
      await createBackup('before_delete_customer');
      const res = await withTransaction(async (client) => {
        const r = await client.query(
          'UPDATE customers SET is_deleted = 1 WHERE id = $1 AND is_deleted = 0',
          [id]
        );
        if (r.rowCount === 0) throw Object.assign(new Error('Customer not found'), { status: 404 });
      });
      return json({
        success: true,
        message: 'Customer archived (soft-deleted). A full backup snapshot was saved.',
      });
    } catch (err) {
      if (err.status === 404) return error(404, 'Customer not found');
      console.error('[customer] DELETE failed', err);
      return error(500, 'Failed to delete customer');
    }
  }

  return error(405, 'Method not allowed');
};

export const config = { path: '/api/customers/:id', method: ['PUT', 'DELETE'] };