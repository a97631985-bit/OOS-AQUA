import pg from 'pg';

const { Pool } = pg;

const DATABASE_URL = process.env.DATABASE_URL;

if (!DATABASE_URL) {
  console.error('[oos-aqua] DATABASE_URL environment variable is not set. ' +
    'Functions will fail. Set it in Netlify: Site settings > Environment variables.');
}

export const pool = new Pool({
  connectionString: DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  max: 5,
  min: 0,
  idleTimeoutMillis: 15000,
  connectionTimeoutMillis: 10000,
});

pool.on('error', (err) => {
  console.error('[oos-aqua] Unexpected error on idle Postgres client', err);
});

export async function query(text, params) {
  const res = await pool.query(text, params);
  return res.rows;
}

/**
 * Run several statements inside a single transaction.
 * fn(client) must not release the client; this helper manages it.
 */
export async function withTransaction(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    try {
      await client.query('ROLLBACK');
    } catch (_) { /* connection may be dead */ }
    throw err;
  } finally {
    client.release();
  }
}