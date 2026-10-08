const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function client(fetch) {
  const values = new Map(); const events = [];
  const context = {
    exports: {}, fetch, Event, JSON, TextDecoder,
    sessionStorage: { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v), removeItem: k => values.delete(k) },
    window: { dispatchEvent: e => events.push(e.type) },
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/api/client.ts'), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  vm.runInNewContext(output, context);
  return { ...context.exports, values, events };
}

test('verified login attaches credentials to the patient profile request', async () => {
  const calls = [];
  const c = client(async (url, init) => {
    calls.push([url, init]);
    return Response.json(url.endsWith('/auth/login') ? { access_token: 'verified-token' } : { patient_id: 'verified-subject' });
  });
  await c.authApi.login('nathan', 'issued-password');
  assert.equal((await c.patientApi.me()).patient_id, 'verified-subject');
  assert.equal(calls[1][1].headers.Authorization, 'Bearer verified-token');
});

test('chat streaming carries the same credentials as normal requests', async () => {
  let headers;
  const c = client(async (url, init) => {
    if (url.endsWith('/auth/login')) return Response.json({ access_token: 'verified-token' });
    headers = init.headers;
    return new Response('data: {"type":"final","answer":"Access restricted","route":"privacy"}\n\n');
  });
  await c.authApi.login('nathan', 'issued-password');
  const response = await c.chatApi.stream({ user_id: 'verified-subject', session_id: 'session', message: 'Claire appointments' }, () => {});
  assert.equal(headers.Authorization, 'Bearer verified-token');
  assert.equal(response.route, 'privacy');
});

test('expired credentials clear the session and notify the sign-in screen', async () => {
  const c = client(async url => url.endsWith('/auth/login') ? Response.json({ access_token: 'old-token' }) : Response.json({ detail: 'Authentication required' }, { status: 401 }));
  await c.authApi.login('nathan', 'issued-password');
  await assert.rejects(c.patientApi.me(), error => error.status === 401);
  assert.equal(c.authApi.hasToken(), false);
  assert.ok(c.events.includes('health-auth-expired'));
});

test('staff diagnostics refusal does not remove the patient session or block public health', async () => {
  const c = client(async url => {
    if (url.endsWith('/auth/login')) return Response.json({ access_token: 'verified-token' });
    if (url.endsWith('/config')) return Response.json({ detail: 'Staff role required' }, { status: 403 });
    return Response.json({ status: 'ok' });
  });
  await c.authApi.login('nathan', 'issued-password');
  await assert.rejects(c.systemApi.config(), error => error.status === 403);
  assert.equal(c.authApi.hasToken(), true);
  assert.equal((await c.systemApi.health()).status, 'ok');
});
