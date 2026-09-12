const CORS_HEADERS = { 'Access-Control-Allow-Origin': '*' };

export function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...CORS_HEADERS, ...extra },
  });
}

export function html(body, status = 200, extra = {}) {
  return new Response(body, {
    status,
    headers: { 'Content-Type': 'text/html; charset=utf-8', ...CORS_HEADERS, ...extra },
  });
}

export function error(status, message) {
  return json({ success: false, message }, status);
}

export async function readJson(req) {
  const text = await req.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}