import { createBackup } from './_lib/backup.mjs';
import { json, error } from './_lib/http.mjs';

export default async () => {
  try {
    const row = await createBackup('manual');
    return json({
      success: true,
      backup_file: `snapshot_${row.id}`,
      message: 'Backup snapshot created successfully!',
      created_at: row.created_at,
    });
  } catch (err) {
    console.error('[backup] manual failed', err);
    return error(500, 'Failed to create backup');
  }
};

export const config = { path: '/api/backup', method: ['POST'] };