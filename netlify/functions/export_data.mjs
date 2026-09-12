import { query } from './_lib/db.mjs';
import { ensureSchema } from './_lib/schema.mjs';
import { error } from './_lib/http.mjs';

export default async () => {
  await ensureSchema();
  try {
    // Include soft-deleted records too, so full history is preserved.
    const customers = await query('SELECT * FROM customers ORDER BY id');
    const entries = await query('SELECT * FROM entries ORDER BY date, id');

    const exportData = {
      export_date: new Date().toISOString(),
      app_name: 'OOS AQUA Water Management',
      customers,
      entries,
    };

    const filename = `oos_aqua_backup_${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15).replace('T', '_')}.json`;

    return new Response(JSON.stringify(exportData, null, 2), {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Disposition': `attachment; filename=${filename}`,
        'Cache-Control': 'no-store',
      },
    });
  } catch (err) {
    console.error('[export] failed', err);
    return error(500, 'Failed to export data');
  }
};

export const config = { path: '/api/export', method: ['GET'] };