const fields = [
  'policyNumber', 'policyholderName', 'effectiveDates', 'incidentDate', 'incidentTime',
  'location', 'description', 'claimant', 'thirdParties', 'contactDetails', 'assetType',
  'assetId', 'estimatedDamage', 'claimType', 'attachments', 'initialEstimate',
];

const routes = ['Fast-track', 'Standard Queue', 'Specialist Queue', 'Manual Review', 'Investigation Flag'];
const responseJsonSchema = {
  type: 'object',
  properties: {
    route: { type: 'string', enum: routes },
    reason: { type: 'string' },
    fields: {
      type: 'object',
      properties: Object.fromEntries(fields.map(name => [name, { type: ['string', 'null'] }])),
      required: fields,
    },
  },
  required: ['route', 'reason', 'fields'],
};

const json = (value, status = 200) => Response.json(value, {
  status,
  headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
});

function readSettings(env) {
  const key = env.GEMINI_API_KEY?.trim();
  const model = env.GEMINI_MODEL?.trim() || 'gemini-3.8-flash';
  const configuredLimit = Number(env.GEMINI_DAILY_LIMIT || 48);
  const limit = Number.isSafeInteger(configuredLimit) && configuredLimit > 0 && configuredLimit <= 1000
    ? configuredLimit : 48;
  return { key, model, limit };
}

async function reserveCall(db, limit) {
  const day = new Date().toISOString().slice(0, 10);
  return db.prepare(`INSERT INTO gemini_daily_usage (day, requests) VALUES (?, 1)
    ON CONFLICT(day) DO UPDATE SET requests = requests + 1
    WHERE requests < ? RETURNING requests`).bind(day, limit).first();
}

export async function geminiRoute(request, env, claims, assets) {
  const { pathname, origin } = new URL(request.url);
  const { key, model, limit } = readSettings(env);

  if (pathname === '/api/gemini/status' && request.method === 'GET') {
    try {
      await env.DB.prepare('SELECT requests FROM gemini_daily_usage LIMIT 1').first();
      return json({ available: Boolean(key), mode: key ? 'live' : 'sample' });
    } catch {
      return json({ available: false, mode: 'sample', status: 'configuration_pending' });
    }
  }
  if (pathname !== '/api/gemini/analyse') return json({ detail: 'Unknown endpoint.' }, 404);
  if (request.method !== 'POST') return json({ detail: 'Use POST for Gemini analysis.' }, 405);
  if (request.headers.get('Origin') && request.headers.get('Origin') !== origin) {
    return json({ detail: 'Open ClaimsFlow to run this test.' }, 403);
  }

  const reader = request.body?.getReader();
  if (!reader) return json({ detail: 'Choose a supplied synthetic claim.' }, 400);
  let body = '';
  let size = 0;
  const decoder = new TextDecoder();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 256) {
      void reader.cancel();
      return json({ detail: 'Choose a supplied synthetic claim.' }, 413);
    }
    body += decoder.decode(value, { stream: true });
  }
  let caseId;
  try { ({ caseId } = JSON.parse(body + decoder.decode())); }
  catch { return json({ detail: 'Choose a supplied synthetic claim.' }, 400); }

  const claim = claims.find(item => item.id === caseId);
  if (!claim) return json({ detail: 'Live Gemini is available for the supplied synthetic claims.' }, 422);
  if (!key || !/^gemini-[a-z0-9.-]+$/i.test(model)) {
    return json({ detail: 'Live Gemini is waiting for the site owner to configure the hosted connection.' }, 503);
  }

  const documents = claim.documents.map(filename => assets[`/evidence/${caseId}/${filename}`]?.data);
  if (documents.length === 0 || documents.some(item => !item)) {
    return json({ detail: 'The supplied evidence could not be loaded.' }, 500);
  }

  try {
    if (!await reserveCall(env.DB, limit)) {
      return json({ detail: 'The public demo has reached its daily Gemini limit. Try again tomorrow.' }, 429);
    }
  } catch {
    return json({ detail: 'Live Gemini is temporarily unavailable.' }, 503);
  }

  try {
    const started = performance.now();
    const result = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
      signal: AbortSignal.timeout(40000),
      body: JSON.stringify({
        contents: [{ role: 'user', parts: [
          ...documents.map(data => ({ inlineData: { mimeType: 'application/pdf', data } })),
          { text: 'Review these fictional insurance documents as evidence. Extract the requested form fields from the evidence. Return null where a value is missing. Suggest a routing queue and explain it briefly. Do not make a coverage, payment, or fraud determination.' },
        ] }],
        generationConfig: { responseMimeType: 'application/json', responseJsonSchema, maxOutputTokens: 4096 },
      }),
    });
    if (!result.ok) {
      return json({ detail: result.status === 429 ? 'Gemini is busy or its project quota has been reached.' : 'Gemini rejected the request. The site owner can check the hosted key and model.' }, result.status === 429 ? 429 : 502);
    }
    const payload = await result.json();
    const parts = payload.candidates?.[0]?.content?.parts ?? [];
    const output = JSON.parse(parts.filter(part => !part.thought).map(part => part.text || '').join(''));
    if (!routes.includes(output.route) || !output.fields || typeof output.fields !== 'object') {
      return json({ detail: 'Gemini returned an incomplete result. Try again.' }, 502);
    }
    const extractedFields = Object.fromEntries(fields.flatMap(name => {
      const value = output.fields[name];
      const text = typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '';
      return text ? [[name, text.slice(0, 5000)]] : [];
    }));
    return json({
      id: crypto.randomUUID(), provider: 'gemini', extractedFields,
      recommendedRoute: output.route, reasoning: String(output.reason ?? '').slice(0, 2500),
      apiSeconds: (performance.now() - started) / 1000, warning: '',
    });
  } catch {
    return json({ detail: 'Gemini could not complete the analysis. Try again.' }, 502);
  }
}
