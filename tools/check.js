#!/usr/bin/env node
// Static checks for the WQL Workbench app (no tenant access). Exit 1 on any failure.
// Each check encodes a Workday Extend pitfall that has broken a build or a page before (see CLAUDE.md).
//   node tools/check.js            all checks
//   node tools/check.js --deploy   also require a real app (not the placeholder) before an upload
const fs = require('fs');
const path = require('path');

const APP = process.env.CHECK_APP ? path.resolve(process.env.CHECK_APP) : path.join(__dirname, '..', 'app');
const fails = [];
const fail = (f, msg) => fails.push(`${path.relative(APP, f)}: ${msg}`);
const files = [];
(function walk(d) { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); e.isDirectory() ? walk(p) : files.push(p); } })(APP);

// Script text with string literals blanked, so brackets inside quotes don't count.
const blank = (s) => s.replace(/'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"/g, (m) => m[0] + ' '.repeat(Math.max(0, m.length - 2)) + m[0]);
const balanced = (s0) => { const s = s0.replace(/\/\*[\s\S]*?\*\//g, ' '); const st = []; const pair = { ')': '(', ']': '[', '}': '{' }; for (const c of blank(s)) { if ('([{'.includes(c)) st.push(c); else if (')]}'.includes(c)) { if (st.pop() !== pair[c]) return false; } } return st.length === 0; };
const OPWORDS = ['le', 'lt', 'ge', 'gt', 'eq', 'ne', 'and', 'or', 'not', 'div', 'mod', 'size', 'empty', 'new'];

const orchestrations = {};   // file -> parsed orchestration
const scripts = [];   // [file, script text]
const json = {};
const props = {};  // presentationLabels/*.properties text
for (const f of files) {
  const t = fs.readFileSync(f, 'utf8');
  if (t.charCodeAt(0) === 0xfeff) fail(f, 'starts with a byte-order mark (App Builder rejects it)');
  if (/claude/i.test(t)) fail(f, 'contains the word "claude" (not allowed in anything entered in a tenant)');
  if (fs.statSync(f).size > 100 * 1024 && /\.(pmd|amd|smd|pod|script)$/.test(f)) fail(f, 'over the 100 KB file limit');
  if (f.endsWith('.script')) { scripts.push([f, t.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, '')]); continue; }
  if (/\.(png|jpg|svg)$/.test(f)) continue;
  if (f.endsWith('.properties')) { props[f] = t; continue; }
  try { json[f] = JSON.parse(t); } catch (e) { fail(f, 'not valid JSON: ' + e.message); continue; }
  // Orchestration files are typed trees ({_type, _value}); the underscore rule is for PMD-style files only.
  if (/\.(orchestration|suborchestration)$/.test(f)) { orchestrations[f] = json[f]; delete json[f]; continue; }
  (function visit(n) {
    if (typeof n === 'string') { for (const m of n.matchAll(/<%([\s\S]*?)%>/g)) scripts.push([f, m[1]]); return; }
    if (Array.isArray(n)) return n.forEach(visit);
    if (n && typeof n === 'object') {
      for (const k of Object.keys(n)) if (k.startsWith('_') && k !== '_comments') fail(f, `attribute ${k} (App Builder metadata, not a valid PMD attribute)`);
      Object.values(n).forEach(visit);
    }
  })(json[f]);
}

for (const [f, s] of scripts) {
  if (!balanced(s)) fail(f, 'unbalanced brackets in a script: ' + s.slice(0, 80).replace(/\s+/g, ' '));
  for (const m of s.matchAll(/\b(?:let|var)\s+([A-Za-z_]\w*)/g)) if (OPWORDS.includes(m[1])) fail(f, `variable named "${m[1]}" (an operator word; the build fails)`);
}

// dataVariableName / rowVariableName / "as" names an operator word: "gt" failed the App Hub build (live 2026-11-14)
for (const [f, j] of Object.entries(json)) (function walk(n) {
  if (Array.isArray(n)) return n.forEach(walk);
  if (n && typeof n === 'object') {
    for (const k of ['dataVariableName', 'rowVariableName', 'itemVariableName', 'indexVariableName', 'as'])
      if (typeof n[k] === 'string' && OPWORDS.includes(n[k])) fail(f, `${k} "${n[k]}" is an operator word (the build fails)`);
    Object.values(n).forEach(walk);
  }
})(j);

// Translations (developer.workday.com "Translate Widgets ..."): every presentationLabels key a page binds must exist in
// every language file, each file under 100 KB, and every language file's code listed in the SMD's languages.
{
  const keysOf = t => new Set(t.split('\n').filter(l => l && !l.startsWith('#') && l.includes('=')).map(l => l.slice(0, l.indexOf('='))));
  const langs = Object.entries(props).filter(([f]) => f.includes('presentationLabels'));
  const bound = new Set();
  for (const [, s] of scripts) for (const m of s.matchAll(/presentationLabels\.([A-Za-z0-9_]+)/g)) bound.add(m[1]);
  if (bound.size && !langs.length) fail('presentation/presentationLabels', 'pages bind presentationLabels but there is no language file');
  const smd = Object.entries(json).find(([f]) => f.endsWith('.smd'));
  const codes = new Set(((smd && smd[1].languages) || []).map(l => l.code));
  for (const [f, t] of langs) {
    const keys = keysOf(t);
    for (const k of bound) if (!keys.has(k)) fail(f, `no text for the key ${k}`);
    if (Buffer.byteLength(t) > 100 * 1024) fail(f, 'over the 100 KB limit for a language file');
    const code = f.split('/').pop().replace('.properties', '');
    if (!codes.has(code)) fail(f, `language ${code} is not in the SMD's languages`);
  }
}

// Workday reads <% %> as script even inside a string in a .script file (Known Errors page, live 2026-11-14)
for (const [f, s] of scripts.filter(([f]) => f.endsWith('.script'))) {
  if (/<%|%>/.test(s)) fail(f, 'contains <% or %>: Workday parses it as script even inside a string (tokenization error)');
}

// Built-in PMD variable names can't appear in a .script, even as a map key (App Hub build 2026-11-14: m.tenant)
for (const [f, s] of scripts.filter(([f]) => f.endsWith('.script'))) {
  const code = s.replace(/'(?:[^'\\]|\\.)*'/g, "''");
  const hit = code.match(/(?:\.|\b(?:var|let)\s+)(tenant|environment|pageVariables|queryParams|site)\b/);
  if (hit) fail(f, `uses the reserved PMD word '${hit[1]}' as a name (App Hub build error)`);
}

// A line break inside a quoted string in a .script fails the App Hub build ("PMD Scripting syntax error", 2026-11-14)
for (const [f, s] of scripts.filter(([f]) => f.endsWith('.script'))) {
  s.split('\n').forEach((line, i) => {
    const q = line.replace(/\\./g, '').replace(/"[^"]*"/g, '');
    if ((q.match(/'/g) || []).length % 2 === 1) fail(f, `line ${i + 1}: a quoted string doesn't end on its line`);
  });
}

// A page may call only functions a .script exports. A call to an unexported one fails at run time as
// "Unknown Function call: <outer page function>()", naming the caller, not the missing function (live 2026-11-14).
{
  const exportsOf = {};
  for (const [f, s] of scripts.filter(([f]) => f.endsWith('.script'))) {
    const tail = s.slice(s.lastIndexOf('{\n'));
    exportsOf[path.basename(f, '.script')] = new Set([...tail.matchAll(/"(\w+)"\s*:/g)].map((m) => m[1]));
  }
  for (const [f, s] of scripts.filter(([f]) => !f.endsWith('.script'))) {
    for (const m of s.matchAll(/\b(\w+)\.(\w+)\s*\(/g)) {
      if (exportsOf[m[1]] && !exportsOf[m[1]].has(m[2])) fail(f, `calls ${m[1]}.${m[2]}(), which ${m[1]}.script doesn't export`);
    }
  }
}

// App Hub build warnings (2026-11-15): Excel export is for view pages only, and every child of a horizontal section
// must itself be a container (section or fieldSet).
// Every orchestration a page launches exists, and every orchestration names a security domain of this app.
{
  const names = new Set(Object.values(orchestrations).map((o) => o._value.name._value));
  for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd')))
    for (const m of JSON.stringify(json[f]).matchAll(/\/([A-Za-z0-9_]+)\/launch/g)) if (!names.has(m[1])) fail(f, `launches orchestration ${m[1]}, which is not in orchestration/`);
  // App Hub build 2026-11-20: 'type' (and other reserved words) can't name a step or a value, and data.x.type fails
  for (const [f, o] of Object.entries(orchestrations)) {
    const t = JSON.stringify(o);
    for (const m of t.matchAll(/"name":\{"_type":"Identifier","_value":"(type|data|context|item|start|end)"\}/g)) fail(f, `names a step or value '${m[1]}', a reserved orchestration word (App Hub build error)`);
    if (/data\.[A-Za-z0-9_]+\.type\b/.test(t)) fail(f, "reads data.<step>.type: 'type' is reserved in the data shorthand (App Hub build error)");
  }
  for (const [f, o] of Object.entries(orchestrations)) {
    const sd = o._value.securityDomains && o._value.securityDomains._value;
    const t = o._value.type._value;
    if ((t === '.maya.FlowSync' || t === '.maya.FlowAsync') && !(sd && sd._value && sd._value.length === 1)) fail(f, 'a launchable orchestration needs exactly one security domain');
    // App Hub build 2026-11-18: "Negative array accessors not supported" (e.g. $.data[-1:]); read the last row by count + offset
    if (/\$[^"]*\[-\d/.test(JSON.stringify(o))) fail(f, 'a JSONPath uses a negative index, which App Hub refuses; count first and read by offset');
  }
}
for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd'))) {
  const page = json[f];
  const edit = String((page.presentation || {}).pageType || page.pageType || '').toUpperCase() === 'EDIT';
  const walk = (n) => {
    if (Array.isArray(n)) { n.forEach(walk); return; }
    if (!n || typeof n !== 'object') return;
    if (edit && n.type === 'grid' && n.excelExportEnabled) fail(f, `grid ${n.id} has excelExportEnabled on an EDIT page (Workday: view pages only)`);
    if (n.horizontal === true && Array.isArray(n.children)) {
      for (const c of n.children) if (c && !['section', 'fieldSet'].includes(c.type)) fail(f, `horizontal section ${n.id} has a ${c.type} child (${c.id}); wrap it in its own section`);
    }
    Object.values(n).forEach(walk);
  };
  walk(page);
}

// .script helpers must be defined before their first use
for (const [f, s] of scripts.filter(([f]) => f.endsWith('.script'))) {
  const defs = [...s.matchAll(/var\s+(\w+)\s*=\s*function/g)].map((m) => [m[1], m.index]);
  for (const [name, at] of defs) {
    const firstUse = s.search(new RegExp(`(?<![\\w.])${name}\\(`));
    if (firstUse >= 0 && firstUse < at) fail(f, `helper ${name}() is used before it is defined`);
  }
}

// Page-script functions too: one called inside the page script before it is defined failed the App Hub build
// ("calls an undefined function: showResults", reported on every script of the page, 2026-11-16)
for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd'))) {
  const s = json[f].script || '';
  const defs = [...s.matchAll(/var\s+(\w+)\s*=\s*function/g)].map((m) => [m[1], m.index]);
  for (const [name, at] of defs) {
    const firstUse = s.search(new RegExp(`(?<![\\w.])${name}\\(`));
    if (firstUse >= 0 && firstUse < at) fail(f, `page function ${name}() is used in the page script before it is defined`);
  }
}

// Model labels (tasks, domains, business objects...): App Hub error E103 allows letters, digits, space, hyphen, colon only
for (const f of Object.keys(json).filter((f) => f.includes(`${path.sep}model${path.sep}`))) {
  const l = json[f].label;
  if (typeof l === 'string' && !/^[A-Z0-9][A-Za-z0-9 :-]*$/.test(l)) fail(f, `label "${l}" (App Hub E103: start with a capital or digit; letters, digits, spaces, hyphens and colons only)`);
}

// Pages: uppercase pageType, ids camelCase, every taskId known, endpoints referenced exist
const amdFile = Object.keys(json).find((f) => f.endsWith('.amd'));
const amd = amdFile && json[amdFile];
const smdFile = Object.keys(json).find((f) => f.endsWith('.smd'));
const man = json[path.join(APP, 'appManifest.json')];
if (!amd || !smdFile || !man) fail(APP, 'missing appManifest.json, AMD or SMD');
else {
  const ref = man.referenceId;
  for (const [f, k] of [[amdFile, 'applicationId'], [smdFile, 'applicationId'], [smdFile, 'id'], [smdFile, 'siteId']]) if (json[f][k] !== ref) fail(f, `${k} is ${json[f][k]}, manifest referenceId is ${ref}`);
  if (path.basename(amdFile) !== `${ref}.amd`) fail(amdFile, `should be named ${ref}.amd`);
  const pages = new Set(Object.keys(json).filter((f) => f.endsWith('.pmd')).map((f) => json[f].id));
  for (const t of amd.tasks || []) if (!pages.has(t.page.id)) fail(amdFile, `task ${t.id} points at missing page ${t.page.id}`);
  const taskIds = new Set((amd.tasks || []).map((t) => t.id));
  for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd'))) for (const m of JSON.stringify(json[f]).matchAll(/"taskId":"([^"]+)"/g)) if (!taskIds.has(m[1])) fail(f, `taskReference to unknown task ${m[1]}`);
  const providers = new Set((amd.dataProviders || []).map((p) => p.key));
  for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd'))) for (const e of json[f].endPoints || []) if (!providers.has(e.baseUrlType)) fail(f, `endpoint ${e.name} uses unknown data provider ${e.baseUrlType}`);
  const domains = new Set(Object.keys(json).filter((f) => f.endsWith('.securitydomain')).map((f) => json[f].name));
  for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd') || f.endsWith('.task'))) for (const d of json[f].securityDomains || []) if (!domains.has(d)) fail(f, `unknown security domain ${d}`);
  if (process.argv.includes('--deploy') && (/PLACEHOLDER/.test(ref) || !/^[0-9a-f]{32}$/.test(man.id || ''))) fail(path.join(APP, 'appManifest.json'), 'still the placeholder app: run tools/set_app.py <referenceId> <appId> first');
}
for (const f of Object.keys(json).filter((f) => f.endsWith('.pmd'))) {
  const d = json[f];
  const pt = d.presentation && d.presentation.pageType;
  if (pt && pt !== pt.toUpperCase()) fail(f, `pageType "${pt}" must be uppercase`);
  if (!/^[A-Z]/.test(d.id)) fail(f, `page id ${d.id} should be PascalCase`);
  const eps = new Set((d.endPoints || []).map((e) => e.name));
  const body = JSON.stringify(d);
  for (const m of body.matchAll(/\b(\w+)\.invoke\(/g)) if (!eps.has(m[1])) fail(f, `invokes unknown endpoint ${m[1]}`);
  for (const m of body.matchAll(/endpoints\.(\w+)/g)) if (!eps.has(m[1])) fail(f, `searchEndPoint names unknown endpoint ${m[1]}`);
  const ids = [];
  (function visit(n) { if (Array.isArray(n)) return n.forEach(visit); if (n && typeof n === 'object') { if (typeof n.id === 'string' && n !== d) ids.push(n.id); Object.values(n).forEach(visit); } })(d.presentation);
  const seen = new Set();
  for (const id of ids) { if (seen.has(id)) fail(f, `duplicate widget id ${id}`); seen.add(id); if (!/^[a-z][A-Za-z0-9]*$/.test(id)) fail(f, `widget id ${id} should be camelCase`); }
  // Deferred endpoints read before they're fetched need a ?? guard
  for (const e of d.endPoints || []) if (e.deferred) for (const m of body.matchAll(new RegExp(`${e.name}\\.data(?!\\s*\\?\\?)`, 'g'))) { const ctx = body.slice(Math.max(0, m.index - 40), m.index); if (!/invoke/.test(ctx) && !/\)\.data$/.test(body.slice(m.index - 2, m.index + 5))) fail(f, `deferred endpoint ${e.name}.data read without ?? []`); }
}

// A card given a literal parameter map must pass every parameter its .card file declares: a missing one fails the
// whole page with only "A failure occurred" (Integrations KPI cards without chipLabel/kpiIcon, live 2026-11-16).
{
  const cardParams = {};
  for (const [f, d] of Object.entries(json)) if (f.endsWith('.card') && d && d.id) cardParams[d.id] = d.parameters || [];
  // App Hub build 2026-11-17: "Specify up to 10 pills per pill card. Pills found: 11."
  for (const [f, d] of Object.entries(json)) if (f.endsWith('.card') && d && d.body && d.body.type === 'pillCard' && (d.body.pills || []).length > 10) fail(f, `pill card has ${d.body.pills.length} pills (10 at most)`);
  for (const [f, d] of Object.entries(json)) {
    if (!f.endsWith('.pmd')) continue;
    (function visit(n) {
      if (Array.isArray(n)) return n.forEach(visit);
      if (!n || typeof n !== 'object') return;
      const tpl = n.type === 'card' ? n : (n.template && n.template.cardId ? n.template : null);
      if (tpl && typeof tpl.cardId === 'string' && cardParams[tpl.cardId] && typeof tpl.parameters === 'string') {
        const m = tpl.parameters.match(/^<%\s*\{([\s\S]*)\}\s*%>$/);
        if (m) {
          const keys = new Set([...m[1].matchAll(/'(\w+)'\s*:/g)].map((x) => x[1]));
          const missing = cardParams[tpl.cardId].filter((k) => !keys.has(k));
          if (missing.length) fail(f, `card ${tpl.cardId} is missing parameter(s) ${missing.join(', ')} (pass null when unused)`);
        }
      }
      Object.values(n).forEach(visit);
    })(d);
  }
}

// Dynamic sections are allowed on EDIT pages only (App Hub build error, 2026-11-16).
for (const [f, d] of Object.entries(json)) {
  if (!f.endsWith('.pmd') || !d.presentation) continue;
  if ((d.presentation.pageType || 'VIEW') !== 'EDIT' && JSON.stringify(d.presentation).includes('"dynamicSection"')) fail(f, 'dynamicSection on a page that is not EDIT (App Hub refuses it)');
}

if (fails.length) { console.log(fails.map((x) => '  FAIL  ' + x).join('\n')); console.log(`\n${fails.length} problem(s)`); process.exit(1); }
console.log(`static checks passed: ${files.length} files, ${scripts.length} scripts`);
