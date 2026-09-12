/**
 * Parse the :id path parameter from a Netlify function context.
 * Returns an integer, or null when missing/invalid.
 */
export function nullableId(context) {
  const raw = context?.params?.id;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : null;
}