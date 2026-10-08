const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const ts = require('typescript');

// A deterministic hook runner lets these tests resolve a network response
// after switching accounts without introducing timing-dependent UI tests.
function runner(file, api) {
  const cells = []; let cursor = 0; let effects = [];
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!cells[i]) cells[i] = { value: typeof initial === 'function' ? initial() : initial };
      return [cells[i].value, value => { cells[i].value = typeof value === 'function' ? value(cells[i].value) : value; }];
    },
    useRef(initial) { const i = cursor++; if (!cells[i]) cells[i] = { current: initial }; return cells[i]; },
    useCallback(fn) { cursor++; return fn; },
    useEffect(fn, deps) {
      const i = cursor++; const previous = cells[i];
      if (!previous || deps.some((value,j) => !Object.is(value, previous.deps[j]))) {
        effects.push(() => { previous?.cleanup?.(); cells[i] = { deps, cleanup: fn() }; });
      }
    },
  };
  const values = new Map();
  const context = { exports: {}, require: name => name === 'react' ? react : api, AbortController, crypto: { randomUUID }, Date, console,
    localStorage: { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v) } };
  const source = fs.readFileSync(path.join(__dirname, '../src/hooks/', file), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, context);
  const hook = Object.values(context.exports)[0];
  return { render(arg) { cursor = 0; effects = []; const value = hook(arg); effects.forEach(fn => fn()); return value; } };
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('a late session list from Nathan cannot populate Claire’s sidebar', async () => {
  let finishNathan;
  const r = runner('useSessions.ts', { chatSessionsApi: {
    list: id => id === 'nathan' ? new Promise(resolve => { finishNathan = resolve; }) : Promise.resolve({ sessions: [{ session_id: 'claire-session', patient_id: 'claire' }] }),
  } });
  r.render('nathan'); r.render('claire'); await tick();
  finishNathan({ sessions: [{ session_id: 'nathan-session', patient_id: 'nathan' }] }); await tick();
  const state = r.render('claire');
  assert.equal(state.sessions.length, 1);
  assert.equal(state.sessions[0].patient_id, 'claire');
});

test('an answer arriving after sign-out does not appear in the next account', async () => {
  let finish;
  const r = runner('useChatStream.ts', { ApiError: Error, chatApi: {
    sessionTurns: () => Promise.resolve({ turns: [] }),
    stream: () => new Promise(resolve => { finish = resolve; }),
  } });
  const state = r.render({ userId: 'nathan', sessionId: 'nathan-session' });
  const request = state.send('my records');
  r.render({ userId: 'claire', sessionId: 'claire-session' });
  finish({ answer: 'private Nathan result', route: 'crm', routes: [], latency_ms: 0 });
  await request; await tick();
  assert.equal(r.render({ userId: 'claire', sessionId: 'claire-session' }).messages.length, 0);
});

test('a lost stream never automatically repeats a potentially completed booking', async () => {
  let repeats = 0;
  const r = runner('useChatStream.ts', { ApiError: Error, chatApi: {
    sessionTurns: () => Promise.resolve({ turns: [] }),
    stream: () => Promise.reject(new Error('Connection lost after submission')),
    send: () => { repeats++; return Promise.resolve({ answer: 'duplicate booking' }); },
  } });
  await r.render({ userId: 'nathan', sessionId: 'session' }).send('book an appointment');
  assert.equal(repeats, 0);
});
