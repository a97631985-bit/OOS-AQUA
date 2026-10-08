import { query, withTransaction } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { json, error, readJson } from './_lib/http.mjs';
import { ensureRecentBackup, createBackup } from './_lib/backup.mjs';

const LOANS_SQL = `
  SELECT u.id, u.person_name, u.phone, u.amount_given, u.note, u.is_deleted, u.created_at,
         COALESCE((SELECT SUM(p.amount) FROM udhaar_payments p WHERE p.udhaar_id = u.id AND p.is_deleted = 0), 0) AS repaid
  FROM udhaar u
  WHERE u.is_deleted = 0
  ORDER BY u.id DESC
`;

export default async (req) => {
  await ensureSchema();

  if (req.method === 'GET') {
    try {
      const loans = await query(LOANS_SQL);
      const payments = await query(
        `SELECT p.*, u.person_name
         FROM udhaar_payments p
         JOIN udhaar u ON u.id = p.udhaar_id
         WHERE p.is_deleted = 0
         ORDER BY p.id DESC`
      );

      let totalGiven = 0;
      let totalRepaid = 0;
      loans.forEach((l) => {
        totalGiven += Number(l.amount_given);
        totalRepaid += Number(l.repaid);
      });

      return json({
        loans,
        payments,
        summary: {
          given_count: loans.length,
          total_given: totalGiven,
          total_repaid: totalRepaid,
          total_remaining: Math.max(0, totalGiven - totalRepaid),
        },
      });
    } catch (err) {
      console.error('[udhaar] GET failed', err);
      return error(500, 'Failed to load udhaar');
    }
  }

  if (req.method === 'POST') {
    const data = await readJson(req);
    const name = (data.person_name || '').trim();
    const amount = Number(data.amount_given);
    if (!name) return error(400, 'Person name is required');
    if (!amount || amount <= 0) return error(400, 'Enter a valid amount given');

    try {
      await ensureRecentBackup('auto');
      const newId = await withTransaction(async (client) => {
        const res = await client.query(
          `INSERT INTO udhaar (person_name, phone, amount_given, note)
           VALUES ($1, $2, $3, $4)
           RETURNING id`,
          [name, (data.phone || '').trim(), amount, (data.note || '').trim()]
        );
        return res.rows[0].id;
      });
      return json({ success: true, id: newId });
    } catch (err) {
      console.error('[udhaar] POST failed', err);
      return error(500, 'Failed to save udhaar record');
    }
  }

  if (req.method === 'DELETE') {
    const url = new URL(req.url);
    const id = Number(url.searchParams.get('id'));
    if (!id) return error(400, 'id is required');
    try {
      // Money matters: full snapshot before hiding anything.
      await createBackup('before_udhaar_delete');
      await query('UPDATE udhaar SET is_deleted = 1 WHERE id = $1', [id]);
      return json({ success: true, message: 'Udhaar record hidden. Data preserved in backups.' });
    } catch (err) {
      console.error('[udhaar] DELETE failed', err);
      return error(500, 'Failed to delete udhaar record');
    }
  }

  return error(405, 'Method not allowed');
};

export const config = { path: '/api/udhaar', method: ['GET', 'POST', 'DELETE'] };