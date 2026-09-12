import { pool } from './db.mjs';

let schemaPromise = null;

function ensureSchemaNow() {
  return pool.query(`
    CREATE TABLE IF NOT EXISTS customers (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      phone TEXT NOT NULL,
      address TEXT DEFAULT '',
      price_per_jar REAL NOT NULL DEFAULT 35,
      jar_security_deposit REAL DEFAULT 0,
      jars_holding INTEGER DEFAULT 0,
      previous_dues REAL DEFAULT 0,
      is_deleted INTEGER DEFAULT 0
    )
  `).then(() => pool.query(`
    CREATE TABLE IF NOT EXISTS entries (
      id SERIAL PRIMARY KEY,
      customer_id INTEGER REFERENCES customers(id),
      date TEXT NOT NULL,
      jars_delivered INTEGER DEFAULT 0,
      jars_returned INTEGER DEFAULT 0,
      is_deleted INTEGER DEFAULT 0
    )
  `)).then(() => pool.query(`
    CREATE TABLE IF NOT EXISTS backups (
      id SERIAL PRIMARY KEY,
      reason TEXT NOT NULL DEFAULT 'manual',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      snapshot JSONB NOT NULL
    )
  `)).then(() => pool.query(`
    CREATE INDEX IF NOT EXISTS idx_entries_customer_date ON entries (customer_id, date)
  `)).then(() => pool.query(`
    CREATE INDEX IF NOT EXISTS idx_entries_date ON entries (date)
  `));
}

/**
 * Idempotent schema bootstrap. Runs once per warm function instance.
 */
export function ensureSchema() {
  if (!schemaPromise) {
    schemaPromise = ensureSchemaNow().catch((err) => {
      schemaPromise = null;
      throw err;
    });
  }
  return schemaPromise;
}