import { listBackups } from './_lib/backup.mjs';
import { json, error } from './_lib/http.mjs';

export default async () => {
  try {
    const rows = await listBackups(100);
    const backups = rows.map((r) => ({
      id: r.id,
      reason: r.reason,
      created: r.created_at,
      size_kb: Math.max(1, Math.round(Number(r.size_bytes) / 1024)),
    }));
    return json(backups);
  } catch (err) {
    console.error('[backups] list failed', err);
    return error(500, 'Failed to list backups');
  }
};

export const config = { path: '/api/backups', method: ['GET'] };