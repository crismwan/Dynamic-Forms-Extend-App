#!/usr/bin/env node
// Acceptance item 9 (bulk volume): start N one-hour Request Time Off events for one worker through the absence REST API,
// count the Dynamic Forms assignments FormAssign creates for them, then (unless KEEP=1) cancel the events and close
// their assignments.
//   WD_TOKEN=<tenant token> WORKER="Beth Liu" N=50 node tools/bulk_events.js
// Writes only test data: time off on weekdays in 2027, comments marked TEST:DYN:BULK.
const https = require('https');
const API = 'https://api.workday.com';
const REF = JSON.parse(require('fs').readFileSync(require('path').join(__dirname, '..', 'app', 'appManifest.json'), 'utf8')).referenceId;
const APP = `${API}/apps/${REF}/v1`;
const TOKEN = (process.env.WD_TOKEN || '').replace(/["\s]/g, '');
const N = Number(process.env.N || 50);
const WORKER = process.env.WORKER || 'Beth Liu';
const KEEP = process.env.KEEP === '1';
const SUBMIT = 'd9e4223e446c11de98360015c5e6daf6';
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
const short = (x, n = 400) => (typeof x === 'string' ? x : JSON.stringify(x)).slice(0, n);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function weekdays(count) {
  const out = []; const d = new Date(Date.UTC(2027, 0, 4));
  while (out.length < count) { const w = d.getUTCDay(); if (w > 0 && w < 6) out.push(d.toISOString().slice(0, 10)); d.setUTCDate(d.getUTCDate() + 1); }
  return out;
}
async function allAssignments() {
  const rows = [];
  for (let off = 0; off < 5000; off += 100) {
    const pg = await req('GET', `${APP}/dynResponses?limit=100&offset=${off}&formCode=BP`);
    const d = (pg.body && pg.body.data) || []; rows.push(...d); if (d.length < 100) break;
  }
  return rows;
}
(async () => {
  const me = await req('GET', `${API}/common/v1/workers/me`);
  console.log(`AUTH ${me.status} ${me.status === 200 ? me.body.descriptor : short(me.body, 200)}`);
  if (me.status !== 200) process.exit(1);
  const ws = await req('GET', `${API}/common/v1/workers?search=${encodeURIComponent(WORKER)}&limit=5`);
  const w = ((ws.body && ws.body.data) || []).find((x) => x.descriptor === WORKER) || ((ws.body && ws.body.data) || [])[0];
  if (!w) { console.log(`NO WORKER ${ws.status} ${short(ws.body)}`); process.exit(1); }
  console.log(`WORKER ${w.descriptor} ${w.id}`);
  const types = await req('GET', `${API}/absenceManagement/v1/workers/${w.id}/eligibleAbsenceTypes?limit=100`);
  const list = (types.body && types.body.data) || [];
  console.log(`TYPES ${types.status} ${list.map((t) => t.descriptor).join(' | ').slice(0, 600)}`);
  const vac = list.find((t) => /Vacation/i.test(t.descriptor)) || list[0];
  if (!vac) { console.log(`NO TYPE ${short(types.body)}`); process.exit(1); }
  console.log(`TYPE ${vac.descriptor} ${vac.id}`);
  const before = new Set((await allAssignments()).map((r) => r.id));
  console.log(`ASSIGNMENTS BEFORE ${before.size}`);
  const days = weekdays(N); const events = []; const t0 = Date.now();
  for (let i = 0; i < days.length; i++) {
    const body = { days: [{ date: `${days[i]}T08:00:00.000Z`, dailyQuantity: 1, comment: `TEST:DYN:BULK ${i + 1}`, timeOffType: { id: vac.id } }],
      businessProcessParameters: { action: { id: SUBMIT }, comment: `TEST:DYN:BULK ${i + 1}` } };
    const r = await req('POST', `${API}/absenceManagement/v1/workers/${w.id}/requestTimeOff`, body);
    const bp = r.body && r.body.businessProcessParameters;
    const ev = bp && (bp.overallBusinessProcess || {}).id;
    if (i < 2 || r.status >= 300) console.log(`START ${i + 1} ${days[i]} ${r.status} ${short(r.body, 600)}`);
    if (r.status >= 300) { if (i === 0) process.exit(1); continue; }
    events.push({ day: days[i], ev });
  }
  console.log(`STARTED ${events.length}/${N} in ${Math.round((Date.now() - t0) / 1000)} s`);
  // FormAssign runs on each event's first Service step; give it time
  let created = [];
  for (let wait = 0; wait < 12; wait++) {
    await sleep(20000);
    created = (await allAssignments()).filter((r) => !before.has(r.id));
    console.log(`AFTER ${(wait + 1) * 20} s: ${created.length} new assignments`);
    if (created.length >= events.length) break;
  }
  const evIds = new Set(created.map((r) => r.bpEvent));
  console.log(`DISTINCT EVENTS WITH AN ASSIGNMENT ${evIds.size}; pinned forms: ${[...new Set(created.map((r) => r.nextForm))].join(', ')}`);
  const dup = created.length - evIds.size;
  console.log(`DUPLICATE ASSIGNMENTS (extra forms count here too) ${dup}`);
  console.log(`RESULT ${created.length >= events.length ? 'PASS' : 'FAIL'}: ${events.length} events, ${evIds.size} with assignments`);
  if (KEEP) return;
  // clean up: cancel each started event and close its assignments
  let cancelled = 0; let closed = 0;
  const actionEvents = [...evIds];
  for (const id of actionEvents) {
    const c = await req('POST', `${API}/businessProcess/v1/events/${id}/cancel`, { comment: 'TEST:DYN:BULK cleanup' });
    if (c.status < 300) cancelled++; else console.log(`CANCEL ${id} ${c.status} ${short(c.body, 200)}`);
  }
  for (const e of events.filter((x) => x.ev && !evIds.has(x.ev))) {
    const c = await req('POST', `${API}/businessProcess/v1/events/${e.ev}/cancel`, { comment: 'TEST:DYN:BULK cleanup' });
    if (c.status < 300) cancelled++; else console.log(`CANCEL overall ${e.ev} ${c.status} ${short(c.body, 200)}`);
  }
  for (const r of created) {
    const p = await req('PATCH', `${APP}/dynResponses/${r.id}`, { status: 'Closed: TEST:DYN:BULK cleanup' });
    if (p.status < 300) closed++;
  }
  console.log(`CLEANUP cancelled ${cancelled}, closed ${closed} assignments`);
})();
