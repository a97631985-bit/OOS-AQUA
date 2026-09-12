import { pool } from './db.mjs';
import { ensureSchema } from './schema.mjs';

const SNAPSHOT_SQL = `
  INSERT INTO backups (reason, snapshot)
  SELECT $1, json_build_object(
    'export_date', now(),
    'app_name', 'OOS AQUA Water Management',
    'customers', (SELECT COALESCE(json_agg(row_to_json(c) ORDER BY c.id), '[]'::json) FROM customers c),
    'entries', (SELECT COALESCE(json_agg(row_to_json(e) ORDER BY e.id), '[]'::json) FROM entries e)
  )
`;

/**
 * Always create a full snapshot (used before every destructive operation and
 * for manual backups). Returns the new backup row id.
 */
export async function createBackup(reason = 'manual') {
  await ensureSchema();
  const res = await pool.query(`${SNAPSHOT_SQL} RETURNING id, created_at`, [reason]);
  await pruneBackups(60);
  return res.rows[0];
}

/**
 * Cheap "guard" backup: creates a snapshot only when the most recent one is
 * older than `hours` hours. This gives automatic protection without needing a
 * cron scheduler, so data is safe even on free Netlify plans.
 */
export async function ensureRecentBackup(reason = 'auto', hours = 6) {
  await ensureSchema();
  await pool.query(
    `${SNAPSHOT_SQL}
     WHERE NOT EXISTS (
       SELECT 1 FROM backups
       WHERE created_at > now() - make_interval(hours => $2)
     )`,
    [reason, hours]
  );
}

/**
 * Keep only the most recent `keep` snapshots to control storage usage.
 */
export async function pruneBackups(keep = 60) {
  await pool.query(
    `DELETE FROM backups
     WHERE id NOT IN (SELECT id FROM backups ORDER BY id DESC LIMIT $1)`,
    [keep]
  );
}

export async function listBackups(limit = 100) {
  await ensureSchema();
  const res = await pool.query(
    `SELECT id, reason, created_at, pg_column_size(snapshot) AS size_bytes
     FROM backups
     ORDER BY id DESC
     LIMIT $1`,
    [limit]
  );
  return res.rows;
}