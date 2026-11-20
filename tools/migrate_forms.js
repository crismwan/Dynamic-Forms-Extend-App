#!/usr/bin/env node
// One-off: copy the form definitions (dynForms + dynQuestions) from the Extend Toolkit app to this app.
// Responses and answers are test data and stay behind. A form code that already exists here is skipped, so the
// script can be rerun.
//   WD_TOKEN=<tenant token> FROM=developertoolkitappv1_kwswrv DRY=1 node tools/migrate_forms.js
const https = require('https');
const fs = require('fs'); const path = require('path');
const API = 'https://api.workday.com';
const TO = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'app', 'appManifest.json'), 'utf8')).referenceId;
const FROM = process.env.FROM || 'developertoolkitappv1_kwswrv';
const TOKEN = (process.env.WD_TOKEN || '').replace(/["\s]/g, '');
const DRY = process.env.DRY === '1';
const fieldsOf = (bo) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'app', 'model', `${bo}.businessobject`), 'utf8')).fields.map((f) => f.name);
const FORM_FIELDS = fieldsOf('DynForm');
const Q_FIELDS = fieldsOf('DynQuestion');

function req(method, url, body) {
  return new Promise((resolve) => {
    const u = new URL(url); const data = body ? JSON.stringify(body) : null;
    const r = https.request({ hostname: u.hostname, path: u.pathname + u.search, method, timeout: 90000,
      headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/json', ...(data ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } : {}) } },
    (res) => { let raw = ''; res.on('data', (d) => { raw += d; }); res.on('end', () => { let j = raw; try { j = JSON.parse(raw); } catch (_) {} resolve({ status: res.statusCode, body: j }); }); });
    r.on('error', (e) => resolve({ status: 0, body: String(e) })); r.on('timeout', () => r.destroy(new Error('timeout')));
    if (data) r.write(data); r.end();
  });
}
async function all(app, coll) {
  const rows = [];
  for (let off = 0; off < 20000; off += 100) {
    const pg = await req('GET', `${API}/apps/${app}/v1/${coll}?limit=100&offset=${off}`);
    if (pg.status !== 200) throw new Error(`GET ${app}/${coll}: ${pg.status} ${JSON.stringify(pg.body).slice(0, 300)}`);
    const d = pg.body.data || []; rows.push(...d); if (d.length < 100) break;
  }
  return rows;
}
const pick = (row, fields) => { const o = {}; for (const f of fields) if (row[f] !== undefined && row[f] !== null) o[f] = row[f]; return o; };
const key = (f) => `${f.code}|${f.version}`;

(async () => {
  if (!TOKEN) { console.log('WD_TOKEN missing'); process.exit(1); }
  const srcForms = await all(FROM, 'dynForms'); const srcQs = await all(FROM, 'dynQuestions');
  const dstForms = await all(TO, 'dynForms'); const dstQs = await all(TO, 'dynQuestions');
  console.log(`source: ${srcForms.length} forms, ${srcQs.length} questions; target before: ${dstForms.length} forms, ${dstQs.length} questions`);
  const have = new Set(dstForms.map(key)); const haveQ = new Set(dstQs.map((q) => q.formCode));
  const forms = srcForms.filter((f) => !have.has(key(f))).map((f) => pick(f, FORM_FIELDS));
  const qs = srcQs.filter((q) => !haveQ.has(q.formCode)).map((q) => pick(q, Q_FIELDS));
  console.log(`to copy: ${forms.length} forms, ${qs.length} questions${DRY ? ' (dry run)' : ''}`);
  if (DRY) { console.log(forms.map(key).join('\n')); return; }
  let bad = 0;
  for (const [coll, list] of [['dynForms', forms], ['dynQuestions', qs]]) {
    for (let i = 0; i < list.length; i += 100) {
      const r = await req('POST', `${API}/apps/${TO}/v1/${coll}?bulk=true`, { data: list.slice(i, i + 100) });
      const errs = ((r.body && r.body.data) || []).filter((x) => x.status && String(x.status) !== '201' && String(x.status) !== '200');
      if (r.status >= 300 || errs.length) { bad++; console.log(`POST ${coll} ${i}: ${r.status} ${JSON.stringify(errs.length ? errs.slice(0, 3) : r.body).slice(0, 600)}`); }
    }
  }
  const after = await all(TO, 'dynForms'); const afterQ = await all(TO, 'dynQuestions');
  console.log(`target after: ${after.length} forms, ${afterQ.length} questions; ${bad ? 'FAILED batches: ' + bad : 'all batches ok'}`);
  const want = new Set(srcForms.map(key)); const got = new Set(after.map(key));
  const missing = [...want].filter((k) => !got.has(k));
  console.log(missing.length ? `MISSING: ${missing.join(', ')}` : 'every source form is present in the target');
  if (bad || missing.length) process.exit(1);
})();
