import { createBackup } from './_lib/backup.mjs';

export const config = { schedule: '@daily' };

export default async () => {
  try {
    await createBackup('scheduled_daily');
    return new Response('OK: daily snapshot created', { status: 200 });
  } catch (err) {
    console.error('[backup] scheduled failed', err);
    return new Response(`ERROR: ${err.message}`, { status: 500 });
  }
};