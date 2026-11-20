#!/usr/bin/env node
// Orchestration files for people: read one, review a change, compare the repo with App Hub.
//
//   node tools/orch_format.js pretty <file>            indented JSON on stdout (for reading or a review diff)
//   node tools/orch_format.js compact <file>           rewrite the file on one line, as App Hub writes it (small git diffs)
//   node tools/orch_format.js outline <file>           the steps, nested, with their type: a quick map of the flow
//   node tools/orch_format.js diff <a> <b>             steps added, removed or changed between two files or two folders
//
// Comparing with App Hub: wdcli app download <ref> --latest-version -d /tmp/hub, then
//   node tools/orch_format.js diff app/orchestration /tmp/hub/orchestration
// A step that differs was changed in Orchestration Builder (or in the repo) and not copied across: the next upload
// from the repo replaces App Hub's copy. Node 16+, no packages, reads only the files given (compact rewrites its one).
const fs = require('fs');
const path = require('path');

const [cmd, a, b] = process.argv.slice(2);
const usage = () => { console.error('usage: node tools/orch_format.js pretty|compact|outline <file> | diff <a> <b>'); process.exit(2); };
if (!cmd || !a) usage();
const load = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
const val = (x) => (x && typeof x === 'object' && '_value' in x ? x._value : x);
const typeName = (t) => (Array.isArray(t) ? t.map(typeName).join('/') : String(t));

// A step = an object {_type, _value:{name:{_type:'Identifier', _value}}}. Its signature replaces nested steps by their
// names, so a change shows on the step that holds it, not on every group around it.
function steps(root) {
  const out = new Map();
  const sig = (n) => {
    if (Array.isArray(n)) return n.map(sig);
    if (!n || typeof n !== 'object') return n;
    const nm = isStep(n) ? stepName(n) : null;
    if (nm && n !== cur) return { step: nm };
    const o = {};
    for (const k of Object.keys(n).sort()) o[k] = sig(n[k]);
    return o;
  };
  let cur = null;
  (function walk(n, depth) {
    if (Array.isArray(n)) return n.forEach((x) => walk(x, depth));
    if (!n || typeof n !== 'object') return;
    let d = depth;
    if (isStep(n)) {
      cur = n;
      const name = stepName(n);
      out.set(name, { type: typeName(n._type), depth, sig: JSON.stringify(sig(n)) });
      d = depth + 1;
    }
    Object.values(n).forEach((x) => walk(x, d));
  })(root, 0);
  return out;
}
function isStep(n) {
  const v = n && n._value;
  return v && typeof v === 'object' && !Array.isArray(v) && v.name && v.name._type === 'Identifier' && n._type !== 'Flow';
}
function stepName(n) { return String(n._value.name._value); }

function filesOf(p) {
  if (fs.statSync(p).isDirectory()) {
    return Object.fromEntries(fs.readdirSync(p).filter((f) => /\.(sub)?orchestration$/.test(f)).map((f) => [f, path.join(p, f)]));
  }
  return { [path.basename(p)]: p };
}

if (cmd === 'pretty') process.stdout.write(JSON.stringify(load(a), null, 2) + '\n');
else if (cmd === 'compact') { fs.writeFileSync(a, JSON.stringify(load(a))); console.error('compacted', a); }
else if (cmd === 'outline') {
  const d = load(a);
  console.log(`${val(val(d).name)} (${val(val(d).type)})`);
  for (const [name, s] of steps(d)) console.log(`${'  '.repeat(s.depth + 1)}${name}  [${s.type}]`);
} else if (cmd === 'diff') {
  if (!b) usage();
  const fa = filesOf(a), fb = filesOf(b);
  const single = Object.keys(fa).length === 1 && Object.keys(fb).length === 1;
  const pairs = single ? [[Object.keys(fa)[0], Object.values(fa)[0], Object.values(fb)[0]]]
    : [...new Set([...Object.keys(fa), ...Object.keys(fb)])].sort().map((k) => [k, fa[k], fb[k]]);
  let differences = 0;
  for (const [name, pa, pb] of pairs) {
    if (!pa || !pb) { console.log(`${name}: only in ${pa ? a : b}`); differences++; continue; }
    const sa = steps(load(pa)), sb = steps(load(pb));
    const lines = [];
    for (const [k, s] of sa) if (!sb.has(k)) lines.push(`  - ${k} [${s.type}] only in ${a}`);
    for (const [k, s] of sb) if (!sa.has(k)) lines.push(`  + ${k} [${s.type}] only in ${b}`);
    for (const [k, s] of sa) if (sb.has(k) && sb.get(k).sig !== s.sig) lines.push(`  ~ ${k} [${s.type}] differs`);
    const flowA = JSON.stringify(load(pa)), flowB = JSON.stringify(load(pb));
    if (!lines.length && flowA !== flowB) lines.push('  ~ flow settings differ (not a step: start, end, credentials, notes)');
    if (lines.length) { console.log(`${name}:`); lines.forEach((l) => console.log(l)); differences++; }
  }
  console.log(differences ? `${differences} orchestration${differences > 1 ? 's differ' : ' differs'}.` : 'Same steps and settings.');
  process.exit(differences ? 1 : 0);
} else usage();
