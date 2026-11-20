#!/usr/bin/env python3
"""Dynamic Forms lab: one fill page whose fixed pool of question slots is switched on, labelled and checked by
question records (a design sent 2026-11-17). It tests the design's open questions live:
  1. the refresh pattern (rules, required, calculated values) on a few questions;
  2. whether a page function can loop over slots by reference (refreshLoop) or must spell each slot out (refreshFlat);
  3. how many slots fit under the 100 KB page limit (DynFormBigLoop / DynFormBigFlat, sized here to just under it);
  4. whether delivered Workday reporting can read the answers (DynResponse.subject -> WORKER, enableReportingFromTarget).
Test data uses form codes TEST:DYN:SMALL and TEST:DYN:BIG. Run after build_lab.py, before build_ui.py.
"""
import datetime, json, os, glob

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PRES = os.path.join(ROOT, 'app', 'presentation')
MODEL = os.path.join(ROOT, 'app', 'model')
DOM = ["UseDynamicForms"]
REF = json.load(open(os.path.join(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')), 'app', 'appManifest.json'), encoding='utf-8'))['referenceId']
FAIL = [{"code": 400}, {"code": 403}]
LIMIT = 100 * 1024
WARN = 85 * 1024   # App Hub warns from 85 KB (build log 2026-11-19); generated pages stay under it
SMALL_SLOTS = 10
# question slots on the real fill pages (DynFormLookup, DynMyFill); the copy page's warning uses the same number.
# Raised from 12 (2026-11-19) after the slot widgets moved to short page functions (F, L, S, R): page size, not a
# platform limit, set the old number.
LOOKUP_SLOTS = 28   # 30 put DynMyFill at 85.1 KB, over App Hub's 85 KB warning (2026-11-19)
TYPES = ["text", "number", "date", "choice", "yesno"]   # widget order in a slot; df.wi() returns 1..5


def write(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=None if compact else 2, ensure_ascii=False,
                           separators=(',', ':') if compact else None) + '\n')


def field(i, name, label, ftype, **kw):
    f = {"id": i, "name": name, "label": label, "type": ftype}
    f.update(kw)
    return f


def bo(i, name, label, coll, collLabel, fields):
    return {"id": i, "name": name, "label": label, "defaultSecurityDomains": DOM,
            "defaultCollection": {"name": coll, "label": collLabel}, "fields": fields}


# ---- model: four business objects (the design has six; versions and assignments are left out of the test) ----
write(os.path.join(MODEL, 'DynForm.businessobject'), bo(3, "DynForm", "Dyn Form", "dynForms", "All Dyn Forms", [
    field(1, "code", "Code", "TEXT", useForDisplay=True, enableIndex=True),
    field(2, "formName", "Form Name", "TEXT"),
    field(3, "version", "Version", "INTEGER"),
    field(4, "status", "Status", "TEXT"),
    field(5, "description", "Description", "TEXT"),
    field(6, "targetObject", "Target Object", "TEXT"),
    field(7, "dataSources", "Data Sources", "TEXT"),
    field(8, "requestFramework", "Request Framework", "BOOLEAN"),
    field(9, "requestType", "Request Type", "TEXT"),
    field(10, "businessProcess", "Business Process", "TEXT"),
    # copies and versions (2026-11-18): copiedFrom = the code this form was copied from; family = the code of version 1,
    # shared by every version (CODE, CODE@2, CODE@3 ...), so FormAssign can find the published one
    field(11, "copiedFrom", "Copied From", "TEXT"),
    field(12, "family", "Form Family", "TEXT", enableIndex=True),
    # gate policy (2026-11-19): what FormGate does when this form wasn't filled (noFormPolicy) or its check failed
    # (failPolicy): cancel | sendback | pass; empty = the orchestration's default. A BP Service step can't pass launch
    # parameters, so the policy lives on the form.
    field(13, "noFormPolicy", "Gate Policy When Not Filled", "TEXT"),
    field(14, "failPolicy", "Gate Policy When Check Fails", "TEXT"),
    # several forms on one process (2026-11-19): up to two more form families, comma separated, that FormAssign assigns
    # with this one; FormGate requires each of them to be filled too
    field(15, "alsoAssign", "Also Assign Forms", "TEXT")]))
write(os.path.join(MODEL, 'DynQuestion.businessobject'), bo(4, "DynQuestion", "Dyn Question", "dynQuestions", "All Dyn Questions", [
    field(1, "formCode", "Form Code", "TEXT", enableIndex=True),
    field(2, "qKey", "Question Key", "TEXT", useForDisplay=True),
    field(3, "sortOrder", "Sort Order", "INTEGER"),
    field(4, "qType", "Question Type", "TEXT"),
    field(5, "qLabel", "Question Label", "TEXT"),
    field(6, "help", "Help", "TEXT"),
    field(7, "required", "Required", "BOOLEAN"),
    field(8, "qOptions", "Options", "TEXT"),
    field(9, "showKey", "Show When Key", "TEXT"),
    field(10, "showOp", "Show When Operator", "TEXT"),
    field(11, "showValue", "Show When Value", "TEXT"),
    field(12, "calc", "Calculation", "TEXT"),
    field(13, "lookup", "Lookup Source", "TEXT"),
    field(14, "prefill", "Prefill From", "TEXT"),
    field(15, "regex", "Regular Expression", "TEXT"),
    field(16, "regexMessage", "Regular Expression Message", "TEXT"),
    field(17, "dataSource", "Data Source", "TEXT"),
    field(18, "sourceField", "Source Field", "TEXT"),
    field(19, "targetField", "Target Field", "TEXT"),
    field(20, "params", "Parameters", "TEXT"),
    # labels: per-language text as JSON {"fr-CA": "...", ...}; confidential: the answer goes to DynAnswer.secretText,
    # which only the DynConfidential domain can read
    field(21, "labels", "Labels by Language", "TEXT"),
    field(22, "confidential", "Confidential", "BOOLEAN")]))
write(os.path.join(MODEL, 'DynResponse.businessobject'), bo(5, "DynResponse", "Dyn Response", "dynResponses", "All Dyn Responses", [
    field(1, "responseKey", "Response Key", "TEXT", useForDisplay=True, enableIndex=True),
    field(2, "formCode", "Form Code", "TEXT"),
    field(3, "status", "Status", "TEXT"),
    field(4, "subject", "Subject", "SINGLE_INSTANCE", target="WORKER", enableReportingFromTarget=True),
    field(5, "parentKey", "Parent Response Key", "TEXT", enableIndex=True),
    field(6, "nextForm", "Next Form", "TEXT"),
    field(7, "bpEvent", "Business Process Event", "TEXT", enableIndex=True),
    field(8, "bpTarget", "Business Process Target", "TEXT"),
    # reporting (2026-11-19): the form family and version a response was filled on, and the filler's organization
    field(9, "family", "Form Family", "TEXT"),
    field(10, "formVersion", "Form Version", "INTEGER"),
    field(11, "orgName", "Organization", "TEXT"),
    # 2026-11-19: on a business process assignment, the extra form families FormAssign was told to assign with it
    # ("-" = none), so FormReconcile and FormGate check what was expected when the request started, not the form's
    # current alsoAssign (changing a published form must not apply to requests already running)
    field(12, "alsoExpected", "Also Expected Forms", "TEXT"),
    # 2026-11-19: the Person WID of the assignment's target, so a new hire before the start date (for whom
    # common/v1/workers/me fails) finds their assignments through person/v4/people/me
    field(13, "bpPerson", "Business Process Person", "TEXT")]))
write(os.path.join(MODEL, 'DynAnswer.businessobject'), bo(6, "DynAnswer", "Dyn Answer", "dynAnswers", "All Dyn Answers", [
    field(1, "responseKey", "Response Key", "TEXT", enableIndex=True),
    field(2, "formCode", "Form Code", "TEXT"),
    field(3, "qKey", "Question Key", "TEXT", useForDisplay=True),
    field(4, "rowNumber", "Row Number", "INTEGER"),
    field(5, "textValue", "Text Value", "TEXT"),
    field(6, "numberValue", "Number Value", "DECIMAL", decimals=2),
    field(7, "dateValue", "Date Value", "DATE", precision="DAY"),
    field(8, "refId", "Picked Record ID", "TEXT"),
    field(9, "refDescriptor", "Picked Record Name", "TEXT"),
    field(10, "organization", "Organization", "SINGLE_INSTANCE", target="SUPERVISORY_ORGANIZATION"),
    field(11, "position", "Position", "SINGLE_INSTANCE", target="POSITION"),
    field(12, "worker", "Worker", "SINGLE_INSTANCE", target="WORKER", enableReportingFromTarget=True),
    field(13, "secretText", "Confidential Value", "TEXT", securityDomains=["DynConfidential"])]))
write(os.path.join(MODEL, 'DynConfidential.securitydomain'), {"id": 2, "name": "DynConfidential", "label": "Dyn Confidential Answers",
                                                              "enabledForPageSecurity": False, "enabledForOrchestrationSecurity": False})

# ---- the interpreter: pure functions over the question records (helpers before their callers) ----
SCRIPT = r'''
var sorted = function(d) {
  list:sort(d ?? [], 'sortOrder', true);
};

var copyQ = function(x, ord) {
  var m = {:};
  m.addAll(x);
  m.put('sortOrder', ord);
  m;
};

var childQ = function(y, parent, ord) {
  var m = copyQ(y, ord);
  m.put('pKey', parent.showKey ?? '');
  m.put('pOp', parent.showOp ?? 'eq');
  m.put('pValue', parent.showValue ?? '');
  m;
};

var subCode = function(d, n) {
  var subs = sorted(d).filter(x => { (x.qType ?? '') == 'subform' || (x.qType ?? '') == 'repeat' });
  subs.size() >= n ? ('' + (subs.get(n - 1).qOptions ?? '')).trim() : '';
};

// a repeating group (qType repeat, 2026-11-19): qOptions = the sub-form whose questions repeat, params =
// "count=<key of a number question>;max=<n>". Copy k of each question gets key <key>_<k>, label "<label> (k)", rules
// between the group's own questions renamed to copy k, and shows only while the count question's answer is k or more.
// baseKey and rowNumber carry the original key and k, so answers are saved as qKey + rowNumber.
var par = function(x, name) {
  var raw = ';' + ('' + (x.params ?? '')).replace(' ', '') + ';';
  raw.contains(';' + name + '=') ? raw.substringAfter(';' + name + '=').substringBefore(';') : '';
};

var repQ = function(y, parent, k, keys, ord) {
  var m = copyQ(y, ord);
  var key = y.qKey ?? '';
  m.put('qKey', key + '_' + k);
  m.put('baseKey', key);
  m.put('rowNumber', k);
  m.put('qLabel', (y.qLabel ?? key) + ' (' + k + ')');
  var sk = y.showKey ?? '';
  if (!empty(sk) && keys.contains(sk)) { m.put('showKey', sk + '_' + k); }
  m.put('pKey', par(parent, 'count'));
  m.put('pOp', 'ge');
  m.put('pValue', '' + k);
  m;
};

// a repeating group's count above its max: the extra copies can't be shown, so say so on the count box (2026-11-19:
// 9 showed 4 copies with no message). Returns 'na' (not a count), 'ok', or the message.
var overMax = function(d, key, val) {
  var top = 0;
  for (var x : (d ?? [])) { if ((x.pKey ?? '') == key && !empty(key) && (x.rowNumber ?? 0) > top) { top = x.rowNumber; } }
  top == 0 ? 'na' : ((!empty(val) && ('' + val).isNumber() && ('' + val).toDecimal() > top) ? ('At most ' + top + ' here; only ' + top + ' can be entered.') : 'ok');
};
var expand = function(d, s1, s2, s3) {
  var kids = [s1 ?? [], s2 ?? [], s3 ?? []];
  var out = [];
  var n = 0;
  var ord = 0;
  for (var x : sorted(d)) {
    var ty = x.qType ?? '';
    if (ty == 'repeat') {
      n = n + 1;
      if (n <= 3) {
        var rk = sorted(kids.get(n - 1)).filter(y => { (y.qType ?? '') != 'subform' && (y.qType ?? '') != 'nextform' && (y.qType ?? '') != 'repeat' });
        var rkeys = rk.map(y => { y.qKey ?? '' });
        var mx = par(x, 'max');
        var top = empty(mx) ? 3 : ('' + mx).toInt();
        for (var kk : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) {
          if (kk <= top) { for (var y2 : rk) { ord = ord + 1; out.add(repQ(y2, x, kk, rkeys, ord)); } }
        }
      }
    }
    if (ty == 'subform') {
      n = n + 1;
      if (n <= 3) {
        for (var y : sorted(kids.get(n - 1))) {
          var yt = y.qType ?? '';
          if (yt != 'subform' && yt != 'nextform') { ord = ord + 1; out.add(childQ(y, x, ord)); }
        }
      }
    } else {
      if (ty != 'nextform' && ty != 'repeat') { ord = ord + 1; out.add(copyQ(x, ord)); }
    }
  }
  out;
};

var q = function(d, i) {
  var s = sorted(d);
  s.size() >= i ? s.get(i - 1) : {:};
};

var k = function(d, i) {
  q(d, i).qKey ?? '';
};

var t = function(d, i) {
  q(d, i).qType ?? '';
};

var l = function(d, i) {
  q(d, i).qLabel ?? '';
};

// the label in the user's language: labels holds compact JSON {"fr-CA":"..."}; lang comes from the page (a text whose
// translated label is the language code), falling back to qLabel
var ll = function(d, i, lang) {
  var raw = '' + (q(d, i).labels ?? '');
  var tag = '"' + (lang ?? '') + '":"';
  (empty(lang) || raw.indexOf(tag) < 0) ? l(d, i) : raw.substringAfter(tag).substringBefore('"');
};

var sec = function(d, i) {
  q(d, i).confidential == true;
};

var h = function(d, i) {
  q(d, i).help ?? '';
};

var wi = function(d, i) {
  var ty = t(d, i);
  ty == 'text' ? 1 : (ty == 'number' ? 2 : (ty == 'date' ? 3 : (ty == 'choice' ? 4 : (ty == 'yesno' ? 5 : 0))));
};

var req = function(d, i) {
  q(d, i).required ?? false;
};

var c = function(d, i) {
  !empty(q(d, i).calc);
};

var str = function(v) {
  empty(v) ? '' : '' + v;
};

var num = function(v) {
  empty(v) ? 0 : ('' + v).toDecimal();
};

var cond = function(key, op, val, ans) {
  var cur = str(ans.get(key));
  empty(key) ? true : (op == 'filled' ? !empty(cur) : (op == 'ne' ? cur != (val ?? '') : (op == 'ge' ? (!empty(cur) && num(cur) >= num(val)) : cur == (val ?? ''))));
};

var show = function(d, i, ans) {
  var x = q(d, i);
  cond(x.showKey ?? '', x.showOp ?? 'eq', x.showValue ?? '', ans) && cond(x.pKey ?? '', x.pOp ?? 'eq', x.pValue ?? '', ans);
};

var nextForm = function(d, ans) {
  var hits = sorted(d).filter(x => { (x.qType ?? '') == 'nextform' && cond(x.showKey ?? '', x.showOp ?? 'eq', x.showValue ?? '', ans) });
  hits.size() > 0 ? ('' + (hits.get(0).qOptions ?? '')).trim() : '';
};

var v = function(d, i) {
  !empty(k(d, i)) && show(d, i, {:});
};

var r = function(d, i, ty) {
  t(d, i) == ty && req(d, i) && v(d, i);
};

var o = function(d, i) {
  var raw = q(d, i).qOptions ?? '';
  empty(raw) ? [] : raw.split('|').map(p => { { 'id': p.substringBefore('='), 'descriptor': p.substringAfter('=') } });
};

var pick = function(d, i, vals) {
  var n = wi(d, i);
  var raw = n > 0 ? vals.get(n - 1) : null;
  n == 3 ? (empty(raw) ? null : raw.format('yyyy-MM-dd')) : (n == 4 ? (empty(raw) ? null : raw.get(0)) : (n == 5 ? (raw == true ? 'true' : 'false') : raw));
};

var shownKey = function(d, key, ans) {
  var i = sorted(d).map(x => { x.qKey ?? '' }).indexOf(key);
  i >= 0 && show(d, i + 1, ans);
};

var calcVal = function(d, i, ans) {
  var spec = q(d, i).calc ?? '';
  var keys = spec.substringAfter('sum:').split(',');
  keys.map(x => { shownKey(d, x.trim(), ans) ? num(ans.get(x.trim())) : 0 }).reduce((a, b) => { a + b });
};

var answers = function(d, ans, responseKey, formCode) {
  var out = [];
  var i = 0;
  for (var x : sorted(d)) {
    i = i + 1;
    var key = x.qKey ?? '';
    var val = ans.get(key);
    if (!empty(key) && !empty(val) && show(d, i, ans)) {
      var m = {:};
      m.put('responseKey', responseKey);
      m.put('formCode', formCode);
      m.put('qKey', key);
      m.put('rowNumber', 1);
      if (x.confidential == true) { m.put('secretText', '' + val); }
      if (x.confidential != true && x.qType == 'number') { m.put('numberValue', val); }
      if (x.confidential != true && x.qType == 'date') { m.put('dateValue', val); }
      if (x.confidential != true && x.qType != 'number' && x.qType != 'date') { m.put('textValue', '' + val); }
      out.add(m);
    }
  }
  out;
};

var qmap = function(code, n, key, ty, label, required, opts, showKey, showOp, showValue, calc, help) {
  var m = {:};
  m.put('formCode', code);
  m.put('sortOrder', n);
  m.put('qKey', key);
  m.put('qType', ty);
  m.put('qLabel', label);
  m.put('required', required);
  if (!empty(opts)) { m.put('qOptions', opts); }
  if (!empty(showKey)) { m.put('showKey', showKey); m.put('showOp', showOp); m.put('showValue', showValue); }
  if (!empty(calc)) { m.put('calc', calc); }
  if (!empty(help)) { m.put('help', help); }
  m;
};

var sample = function(which, count) {
  var code = which == 'big' ? 'TEST:DYN:BIG' : 'TEST:DYN:SMALL';
  var out = [];
  if (which != 'big') {
    out.add(qmap(code, 1, 'hasPosition', 'choice', 'Do you manage a position?', true, 'yes=Yes|no=No', '', '', '', '', ''));
    out.add(qmap(code, 2, 'positionCount', 'number', 'How many positions?', true, '', 'hasPosition', 'eq', 'yes', '', ''));
    out.add(qmap(code, 3, 'budget', 'number', 'Extra budget', false, '', '', '', '', '', ''));
    out.add(qmap(code, 4, 'total', 'number', 'Total (positions + budget)', false, '', '', '', '', 'sum:positionCount,budget', ''));
    out.add(qmap(code, 5, 'startDate', 'date', 'Start date', false, '', '', '', '', '', 'Pick the first day.'));
    out.add(qmap(code, 6, 'notes', 'text', 'Notes about the start', false, '', 'startDate', 'filled', '', '', 'Shown once a start date is picked.'));
    out.add(qmap(code, 7, 'confirm', 'yesno', 'I confirm this is test data', false, '', '', '', '', '', ''));
  }
  out;
};

var lk = function(d, i) {
  q(d, i).lookup ?? '';
};

var uses = function(d, key) {
  (d ?? []).map(x => { x.lookup ?? '' }).contains(key);
};

var wk = function(d, i) {
  var ty = t(d, i);
  var key = lk(d, i);
  ty == 'lookup' ? ((key == 'workers' || key == 'positions' || key == 'orgs' || key == 'domains') ? 'browse' : 'lookup') : ty;
};

// one call per widget attribute (2026-11-19, page size): shown as this kind / required as this kind
var sw = function(d, i, kind) {
  wk(d, i) == kind;
};

var rq = function(d, i, kind) {
  wk(d, i) == kind && req(d, i) && v(d, i);
};

var rxErr = function(d, i, v) {
  var rx = q(d, i).regex ?? '';
  var msg = q(d, i).regexMessage ?? '';
  (empty(rx) || empty(v)) ? '' : (validate:match(rx, '' + v) ? '' : (empty(msg) ? 'Not in the expected format.' : msg));
};

var pre = function(d, i, w) {
  var key = q(d, i).prefill ?? '';
  var loc = empty(w) ? {:} : (w.location ?? {:});
  empty(w) ? '' : (key == 'name' ? (w.descriptor ?? '') : (key == 'title' ? (w.businessTitle ?? '') : (key == 'location' ? (loc.descriptor ?? '') : (key == 'email' ? (w.primaryWorkEmail ?? '') : ''))));
};

var preSel = function(d, i, w) {
  var key = q(d, i).prefill ?? '';
  var org = empty(w) ? {:} : (w.primarySupervisoryOrganization ?? {:});
  key == 'org' && !empty(org.id) ? [{ 'id': org.id, 'descriptor': org.descriptor ?? '' }] : [];
};

var posName = function(x) {
  (x.positionID ?? '') + ' ' + (x.positionTitle ?? '') + (empty(x.worker) ? ' (Unfilled)' : ' - ' + (x.worker.descriptor ?? ''));
};

var ref2 = function(id, desc) {
  var m = {:};
  m.put('id', id);
  m.put('descriptor', desc);
  m;
};

var pItem = function(x) {
  var m = {:};
  m.put('id', x.workdayID);
  m.put('descriptor', posName(x));
  m;
};

var pKey = function(x, by) {
  var o = by == 'byOrg' ? x.supervisoryOrganization : (by == 'byManager' ? x.manager : x.location);
  empty(o) ? '(none)' : ('' + (o.descriptor ?? '(none)'));
};

var pGroups = function(rows, by) {
  var keys = rows.map(x => { pKey(x, by) }).sort();
  var out = [];
  var last = '';
  for (var g : keys) {
    if (g != last) {
      var m = {:};
      m.put('id', 'g:' + g);
      m.put('descriptor', g + '  (' + (keys.lastIndexOf(g) - keys.indexOf(g) + 1) + ')');
      out.add(m);
      last = g;
    }
  }
  out;
};

var pRoot = function(rows) {
  var n = rows.filter(x => { empty(x.worker) }).size();
  var out = [];
  out.add(ref2('byOrg', 'By organization'));
  out.add(ref2('byManager', 'By manager'));
  out.add(ref2('byLocation', 'By location'));
  out.add(ref2('unfilled', 'Unfilled positions  (' + n + ')'));
  out;
};

var pLevel = function(rows, sel) {
  var by = empty(sel) ? '' : sel[0];
  var two = empty(sel) ? false : sel.size() > 1;
  var g = two ? sel[1] : '';
  by == 'unfilled' ? [rows.filter(x => { empty(x.worker) }).map(x => { pItem(x) }), false] :
    (two ? [rows.filter(x => { ('g:' + pKey(x, by)) == g }).map(x => { pItem(x) }), false] : [pGroups(rows, by), true]);
};

var pFind = function(rows, q) {
  var s = ('' + (q ?? '')).lowerCase().trim();
  empty(s) ? [] : rows.filter(x => { posName(x).lowerCase().contains(s) || pKey(x, 'byOrg').lowerCase().contains(s) || pKey(x, 'byManager').lowerCase().contains(s) }).map(x => { pItem(x) });
};

var opts = function(d, i, orgs, positions, domains) {
  var key = lk(d, i);
  key == 'orgs' ? (orgs ?? []).map(x => { { 'id': x.workdayID, 'descriptor': x.name ?? '' } }) :
  (key == 'positions' ? (positions ?? []).map(x => { { 'id': x.workdayID, 'descriptor': posName(x) } }) :
  (key == 'domains' ? (domains ?? []).map(x => { { 'id': x.workdayID, 'descriptor': x.domainName ?? '' } }) : []));
};

var clean = function(s) {
  ('' + (s ?? '')).replace('\'', '').replace('%5C'.urlDecode(), '').trim();
};

var wmap = function(res) {
  (res ?? []).filter(x => { !empty(x.worker) }).map(x => { { 'id': x.worker.id, 'descriptor': x.worker.descriptor ?? '' } });
};

var ref = function(id) {
  var m = {:};
  m.put('id', id);
  m;
};

var pick2 = function(d, i, vals) {
  var kind = wk(d, i);
  kind == 'text' ? vals[0] : (kind == 'number' ? vals[1] : (kind == 'date' ? (empty(vals[2]) ? null : vals[2].format('yyyy-MM-dd')) :
    (kind == 'choice' ? (empty(vals[3]) ? null : vals[3][0]) : (kind == 'yesno' ? (vals[4] == true ? 'true' : 'false') :
      (kind == 'lookup' ? (empty(vals[5]) ? null : vals[5][0]) : (kind == 'search' ? (empty(vals[6]) ? null : vals[6][0]) : (kind == 'browse' ? (empty(vals[7]) ? null : vals[7][0]) : null)))))));
};

var wi2 = function(d, i) {
  var kind = wk(d, i);
  kind == 'number' ? 2 : (kind == 'date' ? 3 : (kind == 'choice' ? 4 : (kind == 'yesno' ? 5 : (kind == 'lookup' ? 6 : (kind == 'search' ? 7 : (kind == 'browse' ? 8 : 1))))));
};

var lanswers = function(d, rows, responseKey, formCode, ans) {
  var out = [];
  var i = 0;
  for (var row : rows) {
    i = i + 1;
    var key = k(d, i);
    var kind = show(d, i, ans) ? wk(d, i) : 'hidden';
    var m = {:};
    m.put('responseKey', responseKey);
    m.put('formCode', q(d, i).formCode ?? formCode);
    m.put('qKey', q(d, i).baseKey ?? key);
    m.put('rowNumber', q(d, i).rowNumber ?? 1);
    // a confidential answer of any type goes only to secretText (the DynConfidential field), never to the open
    // value fields that the gate, comments and reports read (2026-11-19: numbers, dates and yes/no used to bypass it)
    var hide = sec(d, i);
    if (kind == 'text' && !empty(row[0])) { m.put(hide ? 'secretText' : 'textValue', '' + row[0]); out.add(m); }
    if (kind == 'number' && !empty(row[5])) { if (hide) { m.put('secretText', '' + row[5]); } else { m.put('numberValue', row[5]); } out.add(m); }
    if (kind == 'date' && !empty(row[6])) { m.put(hide ? 'secretText' : 'dateValue', row[6].format('yyyy-MM-dd')); out.add(m); }
    if (kind == 'choice' && !empty(row[7])) { m.put(hide ? 'secretText' : 'textValue', row[7][0]); out.add(m); }
    if (kind == 'yesno' && !empty(key)) { m.put(hide ? 'secretText' : 'textValue', row[8] == true ? 'true' : 'false'); out.add(m); }
    var ids = hide ? [] : (kind == 'lookup' ? row[1] : (kind == 'search' ? row[3] : (kind == 'browse' ? row[9] : [])));
    var hents = kind == 'lookup' ? row[2] : (kind == 'search' ? row[4] : (kind == 'browse' ? row[10] : []));
    if (hide && !empty(hents)) { m.put('secretText', hents[0].descriptor ?? ''); out.add(m); }
    var ents = kind == 'lookup' ? row[2] : (kind == 'search' ? row[4] : (kind == 'browse' ? row[10] : []));
    if (!empty(ids)) {
      var id = ids[0];
      var desc = empty(ents) ? '' : (ents[0].descriptor ?? '');
      m.put('refId', id);
      m.put('refDescriptor', desc);
      m.put('textValue', desc);
      var src = lk(d, i);
      if (src == 'orgs') { m.put('organization', ref(id)); }
      if (src == 'positions') { m.put('position', ref(id)); }
      if (src == 'workers') { m.put('worker', ref(id)); }
      out.add(m);
    }
  }
  out;
};

// ---- copying forms (2026-11-18): keys stay unique in the target, rules and sums follow renamed keys ----
var newKey = function(key, taken) {
  var out = key;
  if (taken.contains(key)) {
    out = '';
    for (var n : [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]) { if (empty(out) && !taken.contains(key + '_' + n)) { out = key + '_' + n; } }
  }
  out;
};

var fRow = function(forms, code) {
  var i = (forms ?? []).map(f => { f.code ?? '' }).indexOf(code);
  i < 0 ? {:} : forms.get(i);
};

var family = function(forms, code) {
  var f = fRow(forms, code);
  empty(f.family) ? code : f.family;
};

var cpCode = function(mode, src, tgt, typed, forms) {
  var fam = family(forms, src);
  var vs = (forms ?? []).filter(f => { (empty(f.family) ? (f.code ?? '') : f.family) == fam }).map(f => { f.version ?? 1 });
  var top = vs.size() == 0 ? 1 : vs.reduce((a, b) => { a > b ? a : b });
  mode == 'add' ? (tgt ?? '') : (mode == 'version' ? fam + '@' + ('' + (top + 1)).substringBefore('.') : (mode == 'publish' ? src : ('' + (typed ?? '')).trim()));
};

var cpVersion = function(mode, src, forms) {
  var fam = family(forms, src);
  var vs = (forms ?? []).filter(f => { (empty(f.family) ? (f.code ?? '') : f.family) == fam }).map(f => { f.version ?? 1 });
  mode == 'version' ? (vs.size() == 0 ? 2 : vs.reduce((a, b) => { a > b ? a : b }) + 1) : 1;
};

var cpPlan = function(src, picked, tgt, code, mode, sizes) {
  var taken = [];
  if (mode == 'add') { for (var t0 : (tgt ?? [])) { taken.add(t0.qKey ?? ''); } }
  var rows = sorted(src).filter(x => { mode != 'add' || empty(picked) || picked.contains(x.qKey ?? '') });
  var ren = {:};
  var notes = [];
  for (var x : rows) {
    var key = x.qKey ?? '';
    var nk = newKey(key, taken);
    taken.add(nk);
    ren.put(key, nk);
    if (nk != key) { notes.add('Renamed ' + key + ' to ' + nk + ' (the form already has ' + key + ').'); }
  }
  var base = mode == 'add' ? (tgt ?? []).size() : 0;
  var out = [];
  var i = 0;
  for (var x : rows) {
    i = i + 1;
    var m = {:};
    for (var f : ['qType', 'qLabel', 'help', 'required', 'qOptions', 'showOp', 'showValue', 'lookup', 'prefill', 'regex', 'regexMessage', 'dataSource', 'sourceField', 'targetField', 'params', 'labels', 'confidential']) { var val = x.get(f); if (val != null) { m.put(f, val); } }
    m.put('formCode', code);
    m.put('sortOrder', base + i);
    m.put('qKey', ren.get(x.qKey ?? ''));
    var sk = x.showKey ?? '';
    if (!empty(sk)) {
      m.put('showKey', ren.containsKey(sk) ? ren.get(sk) : sk);
      if (ren.containsKey(sk) && ren.get(sk) != sk) { notes.add('Rule on ' + ren.get(x.qKey ?? '') + ' now reads ' + ren.get(sk) + '.'); }
      if (!ren.containsKey(sk)) { notes.add('Rule on ' + ren.get(x.qKey ?? '') + ' reads ' + sk + ', which was not copied.'); }
    }
    var cl = x.calc ?? '';
    if (!empty(cl)) {
      var parts = cl.substringAfter('sum:').split(',').map(p => { ren.containsKey(p.trim()) ? ren.get(p.trim()) : p.trim() });
      m.put('calc', 'sum:' + parts.join(','));
      if (('sum:' + parts.join(',')) != cl) { notes.add('Sum on ' + ren.get(x.qKey ?? '') + ' now reads ' + parts.join(', ') + '.'); }
      for (var pk : cl.substringAfter('sum:').split(',')) { if (!ren.containsKey(pk.trim()) && !taken.contains(pk.trim())) { notes.add('Sum on ' + ren.get(x.qKey ?? '') + ' reads ' + pk.trim() + ', which is not in the form.'); } }
    }
    var pc = par(x, 'count');
    if (!empty(pc)) {
      var npc = ren.containsKey(pc) ? ren.get(pc) : pc;
      m.put('params', 'count=' + npc + (empty(par(x, 'max')) ? '' : ';max=' + par(x, 'max')));
      if (npc != pc) { notes.add('Repeating group ' + ren.get(x.qKey ?? '') + ' now counts ' + npc + '.'); }
      if (!ren.containsKey(pc) && !taken.contains(pc)) { notes.add('Repeating group ' + ren.get(x.qKey ?? '') + ' counts ' + pc + ', which is not in the form.'); }
    }
    var lk0 = x.lookup ?? '';
    if (!empty(lk0) && !['orgs', 'positions', 'domains', 'workers'].contains(lk0)) { notes.add('Lookup ' + lk0 + ' on ' + ren.get(x.qKey ?? '') + ' is not an approved source here.'); }
    var qt0 = x.qType ?? '';
    if (!['text', 'number', 'date', 'choice', 'yesno', 'lookup', 'subform', 'nextform', 'repeat'].contains(qt0)) { notes.add('Question ' + ren.get(x.qKey ?? '') + ' has type ' + qt0 + ', which the fill page does not show (use text, number, date, choice, yesno, lookup, subform, repeat or nextform).'); }
    out.add(m);
  }
  // the fill page has a fixed pool of question slots and takes up to 3 sub-forms (acceptance copy test, 2026-11-19)
  var allQ = [];
  if (mode == 'add') { allQ.addAll(tgt ?? []); }
  allQ.addAll(out);
  var subN = allQ.filter(x => { (x.qType ?? '') == 'subform' || (x.qType ?? '') == 'repeat' }).size();
  var plainN = allQ.filter(x => { (x.qType ?? '') != 'subform' && (x.qType ?? '') != 'nextform' && (x.qType ?? '') != 'repeat' }).size();
  // slots the fill page needs: plain questions, each sub-form's questions, and max copies of each repeating group's
  // questions (sizes = question count per sub-form code, looked up by the page; unknown counts as 1)
  var slotN = plainN;
  for (var y : allQ) {
    var yt = y.qType ?? '';
    var ysz = (sizes ?? {:}).containsKey(y.qOptions ?? '') ? sizes.get(y.qOptions ?? '') : 1;
    if (yt == 'subform') { slotN = slotN + ysz; }
    if (yt == 'repeat') { var mx = par(y, 'max'); slotN = slotN + ysz * (empty(mx) ? 1 : mx.toInt()); }
  }
  if (slotN > {SLOTS}) { notes.add('Warning: the form needs ' + slotN + ' question slots (sub-form questions and every repeating copy count), but the fill page shows {SLOTS}; the rest will not appear. Lower a repeating group\'s max or split the form.'); }
  if (slotN <= {SLOTS} && subN > 0) { notes.add('The fill page will use ' + slotN + ' of its {SLOTS} question slots, counting sub-form questions and every repeating copy.'); }
  if (subN > 3) { notes.add('Warning: the form will have ' + subN + ' sub-forms or repeating groups; the fill page shows the first 3.'); }
  var res = {:};
  res.put('rows', out);
  res.put('summary', (empty(code) ? 'Pick the form and the new code. ' : '') + out.size() + ' questions to ' + code + '. ' + (notes.size() == 0 ? 'No keys or rules changed.' : notes.join(' ')));
  res;
};

var cpExport = function(forms, src, qs) {
  var f = fRow(forms, src);
  var m = {:};
  m.put('code', src);
  m.put('formName', f.formName ?? '');
  m.put('version', f.version ?? 1);
  m.put('questions', cpPlan(qs, [], [], src, 'copy', {:}).rows);
  json:stringify(m);
};

var cpImport = function(text) {
  var m = empty(text) ? {:} : json:parse(text);
  var res = {:};
  res.put('code', m.code ?? '');
  res.put('formName', m.formName ?? '');
  res.put('questions', m.questions ?? []);
  res;
};

// open assignments and next forms nobody has filled yet. Was a filter inside a filter (every row against every row),
// which failed the Results page once there were ~450 responses (2026-11-19); the parent keys are joined once and
// each row looks itself up in that text.
// answer rows with their response's and question's WIDs looked up once per row (cells looked them up three times
// each, mapping every response and question every time: most of the Results page's 8 s, 2026-11-19)
var tag = function(rows, resps, qs) {
  var rk = (resps ?? []).map(x => { '' + (x.responseKey ?? '') });
  var qk = (qs ?? []).map(x => { (x.formCode ?? '') + '|' + (x.qKey ?? '') });
  (rows ?? []).map(r => {
    var i = rk.indexOf('' + (r.responseKey ?? ''));
    var j = qk.indexOf((r.formCode ?? '') + '|' + (r.qKey ?? ''));
    var m = { 'responseKey': r.responseKey, 'formCode': r.formCode, 'qKey': r.qKey, 'textValue': r.textValue, 'secretText': r.secretText,
       'numberValue': r.numberValue, 'dateValue': r.dateValue, 'refDescriptor': r.refDescriptor, 'organization': r.organization,
       'position': r.position, 'worker': r.worker,
       'rw': i < 0 ? '' : ('' + (resps.get(i).workdayID ?? '')), 'qw': j < 0 ? '' : ('' + (qs.get(j).workdayID ?? '')) };
    m;
  });
};
var cap = function(rows, n) {
  (rows ?? []).size() > n ? rows.subList(0, n) : (rows ?? []);
};
var pending = function(rows) {
  var parents = '|' + (rows ?? []).map(c => { '' + (c.parentKey ?? '') }).join('|') + '|';
  (rows ?? []).filter(r => { !empty(r.nextForm) && !('' + (r.status ?? '')).startsWith('Closed') && !parents.contains('|' + (r.responseKey ?? '') + '|') });
};

var widOf = function(rows, field, value) {
  var keys = (rows ?? []).map(x => { '' + (x[field] ?? '') });
  var i = keys.indexOf('' + (value ?? ''));
  (empty(value) || i < 0) ? '' : ('' + (rows.get(i).workdayID ?? (rows.get(i).id ?? '')));
};

// Form column: the form record, or for BP/GATE/ROUTE records (no form of that code) the business process event.
var formWid = function(forms, r) {
  var w = widOf(forms, 'code', r.formCode);
  !empty(w) ? w : ('' + (r.bpEvent ?? ''));
};

// Status column: the business process event when the record came from one, otherwise the response record itself.
var statusWid = function(r) {
  !empty(r.bpEvent) ? ('' + r.bpEvent) : ('' + (r.workdayID ?? ''));
};

// Subject column: the response's subject, or for an assignment (BP record) the process target it stored as text;
// its name is the end of the status ("Assigned: Absence Request: Logan McNeil").
var subjWid = function(r) {
  !empty(r.subject) ? ('' + (r.subject.id ?? '')) : ('' + (r.bpTarget ?? ''));
};
var subjName = function(r) {
  !empty(r.subject) ? ('' + (r.subject.descriptor ?? '')) : (empty(r.bpTarget) ? '' : ('' + (r.status ?? '')).substringAfterLast(': '));
};

// Question column of the answers grid: the question record (same form code and question key).
var qWid = function(qs, a) {
  var keys = (qs ?? []).map(x => { (x.formCode ?? '') + '|' + (x.qKey ?? '') });
  var i = keys.indexOf((a.formCode ?? '') + '|' + (a.qKey ?? ''));
  i < 0 ? '' : ('' + (qs.get(i).workdayID ?? ''));
};

var resQ = function(form, kind) {
  var f = ('' + (form ?? '')).replace('\'', '').replace('\\', '');
  var cols = kind == 'answers' ? 'responseKey, formCode, qKey, textValue, secretText, numberValue, dateValue, refDescriptor, organization, position, worker' : 'workdayID, responseKey, formCode, status, subject, parentKey, nextForm, bpEvent, bpTarget';
  var src = kind == 'answers' ? '{REF}_dynAnswers' : '{REF}_dynResponses';
  // responses: all of them, so a follow-up filled from another form still marks its parent done; answers: only the
  // form's own when a form is picked (a page reading every answer took 17-19 s once there were ~450 responses).
  'SELECT ' + cols + ' FROM ' + src + ' ORDER BY responseKey DESC';
};
// answers of the responses on show, by response key: a form's sub-form and repeat answers carry the sub-form's code,
// so filtering answers by formCode dropped them (2026-11-19). More than 50 keys: no filter (100 keys made the query
// too long and failed the page), up to 10,000 answers.
var ansQ = function(keys) {
  var ks = (keys ?? []).map(k => { '"' + ('' + (k ?? '')).replace('"', '').replace('\\', '') + '"' });
  var w = ks.size() == 0 ? ' WHERE responseKey = "-"' : (ks.size() <= 50 ? (' WHERE responseKey in (' + ks.join(', ') + ')') : '');
  'SELECT responseKey, formCode, qKey, textValue, secretText, numberValue, dateValue, refDescriptor, organization, position, worker FROM {REF}_dynAnswers' + w + ' ORDER BY responseKey DESC';
};

{
  "q": q, "k": k, "t": t, "l": l, "ll": ll, "sec": sec, "h": h, "wi": wi, "req": req, "c": c, "str": str, "show": show, "v": v, "r": r, "o": o,
  "pick": pick, "num": num, "shownKey": shownKey, "calcVal": calcVal, "answers": answers, "qmap": qmap, "sample": sample,
  "lk": lk, "uses": uses, "wk": wk, "rxErr": rxErr, "pick2": pick2, "wi2": wi2, "pre": pre, "preSel": preSel, "posName": posName, "ref2": ref2, "pItem": pItem, "pKey": pKey, "pGroups": pGroups, "pRoot": pRoot, "pLevel": pLevel, "pFind": pFind, "opts": opts, "clean": clean, "wmap": wmap, "ref": ref, "lanswers": lanswers, "resQ": resQ, "ansQ": ansQ, "widOf": widOf, "formWid": formWid, "statusWid": statusWid, "subjWid": subjWid, "subjName": subjName, "qWid": qWid, "pending": pending, "cap": cap, "tag": tag, "copyQ": copyQ, "newKey": newKey, "fRow": fRow, "family": family, "cpCode": cpCode, "cpVersion": cpVersion, "cpPlan": cpPlan, "cpExport": cpExport, "cpImport": cpImport, "childQ": childQ, "par": par, "repQ": repQ, "sw": sw, "rq": rq, "subCode": subCode, "overMax": overMax, "expand": expand, "ex": expand, "cond": cond, "nextForm": nextForm
}
'''
with open(os.path.join(PRES, 'scripts', 'df.script'), 'w', encoding='utf-8') as f:
    f.write(SCRIPT.lstrip().replace('{SLOTS}', str(LOOKUP_SLOTS)).replace('{REF}', json.load(open(os.path.join(ROOT, 'app', 'appManifest.json'), encoding='utf-8'))['referenceId']))

# ---- page parts ----
QS = {"name": "qs", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
      "url": "<% 'dynQuestions?limit=100&formCode=' + (queryParams.form ?? 'TEST:DYN:SMALL').urlEncode() %>"}
ME = {"name": "me", "baseUrlType": "workday-api", "url": "common/v1/workers/me", "authType": "sso", "failOnStatusCodes": FAIL}


def X(expr):
    return "<% " + expr + " %>"


D = "df.ex(qs.data??[],s1.data??[],s2.data??[],s3.data??[])"
SUBS = [{"name": "s%d" % n, "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
         "url": "<% 'dynQuestions?limit=100&formCode=' + df.subCode(qs.data ?? [], " + str(n) + ").urlEncode() %>",
         "exclude": "<% empty(df.subCode(qs.data ?? [], " + str(n) + ")) %>"} for n in (1, 2, 3)]


def slot(i, guides):
    a = "qs.data,%d" % i
    oc = X("refresh()")
    def w(ty, wtype, wid, extra=None):
        x = {"type": wtype, "id": wid, "label": X("df.l(%s)" % a), "visible": X("df.t(%s)=='%s'" % (a, ty)),
             "required": X("df.r(%s,'%s')" % (a, ty)), "onChange": oc}
        if extra:
            x.update(extra)
        return x
    kids = [w("text", "text", "q%dText" % i,
              {"guide": {"type": "guide", "id": "q%dGuide" % i, "title": X("df.l(%s)" % a), "text": X("df.h(%s)" % a)}} if guides else None),
            w("number", "number", "q%dNumber" % i, {"enabled": X("!df.c(%s)" % a)}),
            w("date", "date", "q%dDate" % i),
            w("choice", "instanceList", "q%dInstanceList" % i, {"values": X("df.o(%s)" % a)}),
            w("yesno", "checkBox", "q%dCheckBox" % i)]
    return {"type": "fieldSet", "id": "q%dFieldSet" % i, "visible": X("df.v(%s)" % a), "children": kids}


def wlist(i):
    return "[q%dFieldSet, q%dText, q%dNumber, q%dDate, q%dInstanceList, q%dCheckBox]" % ((i,) * 6)


def vals(i):
    return "[q%dText.getValue(), q%dNumber.getValue(), q%dDate.getValue(), q%dInstanceList.getValue(), q%dCheckBox.getValue()]" % ((i,) * 5)


def loop_fn(n):
    return ("  var slots = function() {\n    [" + ", ".join(wlist(i) for i in range(1, n + 1)) + "];\n  };\n"
            "  var refreshLoop = function() {\n"
            "    var d = qs.data ?? [];\n    var all = slots();\n    var ans = {:};\n    var i = 0;\n"
            "    for (var s : all) {\n      i = i + 1;\n      var key = df.k(d, i);\n"
            "      if (!empty(key)) { ans.put(key, df.pick(d, i, [s[1].getValue(), s[2].getValue(), s[3].getValue(), s[4].getValue(), s[5].getValue()])); }\n    }\n"
            "    var j = 0;\n"
            "    for (var s2 : all) {\n      j = j + 1;\n"
            "      if (!empty(df.k(d, j))) {\n        var vis = df.show(d, j, ans);\n        s2[0].setVisible(vis);\n"
            "        var w = s2[df.wi(d, j)];\n        w.setRequired(vis && df.req(d, j));\n"
            "        if (df.c(d, j)) { var nv = df.calcVal(d, j, ans); if (w.getValue() != nv) { w.setValue(nv); } }\n      }\n    }\n    ans;\n  };\n")


def flat_fn(n):
    s = "  var refreshFlat = function() {\n    var d = qs.data ?? [];\n    var ans = {:};\n"
    for i in range(1, n + 1):
        s += "    if (!empty(df.k(d,%d))) { ans.put(df.k(d,%d), df.pick(d,%d,%s)); }\n" % (i, i, i, vals(i))
    for i in range(1, n + 1):
        s += ("    if (!empty(df.k(d,{i}))) {{ var v{i} = df.show(d,{i},ans); var w{i} = df.wi(d,{i}); var r{i} = v{i} && df.req(d,{i}); "
              "q{i}FieldSet.setVisible(v{i}); q{i}Text.setRequired(r{i} && w{i}==1); q{i}Number.setRequired(r{i} && w{i}==2); "
              "q{i}Date.setRequired(r{i} && w{i}==3); q{i}InstanceList.setRequired(r{i} && w{i}==4); "
              "if (df.c(d,{i})) {{ var n{i} = df.calcVal(d,{i},ans); if (q{i}Number.getValue() != n{i}) {{ q{i}Number.setValue(n{i}); }} }} }}\n").format(i=i)
    return s + "    ans;\n  };\n"


def fill_page(pid, title, n, modes, guides=True):
    script = "<%\n"
    if "loop" in modes:
        script += loop_fn(n)
    if "flat" in modes:
        script += flat_fn(n)
    if len(modes) == 2:
        script += ("  var refresh = function() {\n    var t0 = date:now().format('mmssSSS').toInt();\n"
                   "    var res = queryParams.mode == 'flat' ? refreshFlat() : refreshLoop();\n"
                   "    timingReadOnlyText.setValue('Last refresh (' + (queryParams.mode ?? 'loop') + '): ' + (date:now().format('mmssSSS').toInt() - t0) + ' ms, ' + res.size() + ' answers');\n"
                   "    res;\n  };\n")
    else:
        script += "  var refresh = function() {\n    refresh%s();\n  };\n" % ("Loop" if modes[0] == "loop" else "Flat")
    script += "%>"
    diag = {"type": "fieldSet", "id": "diagFieldSet", "title": "Test details", "children": [
        {"type": "text", "id": "formCodeText", "label": "Form code", "enabled": False, "value": "<% queryParams.form ?? 'TEST:DYN:SMALL' %>"},
        {"type": "text", "id": "responseKeyText", "label": "Response key", "enabled": False,
         "value": "<% 'TEST:DYN:R' + date:now().format('yyyyMMddHHmmssSSS') %>"},
        {"type": "text", "id": "loadedText", "label": "Loaded", "enabled": False,
         "value": X("'' + (qs.data ?? []).size() + ' questions, form codes: ' + (qs.data ?? []).map(x => { x.formCode ?? '' }).distinct().join(', ') + ', slots: " + str(n) + "'")}]}
    if len(modes) == 2:
        diag["children"].append({"type": "readOnlyText", "id": "timingReadOnlyText", "label": "Refresh", "value": "<% 'Not run yet' %>"})
    p = {"id": pid, "securityDomains": DOM, "include": ["df.script"], "endPoints": [QS, ME], "script": script,
         "outboundData": {"outboundEndPoints": [
             {"name": "postResponse", "baseUrlType": "app", "url": "dynResponses", "httpMethod": "POST", "authType": "sso",
              "failOnStatusCodes": FAIL,
              "onSend": "<% self.data = {:}; self.data.responseKey = responseKeyText.getValue(); self.data.formCode = formCodeText.getValue(); "
                        "self.data.status = 'Submitted'; var subj = {:}; subj.id = me.id; self.data.subject = subj; self.data; %>"},
             {"name": "postAnswers", "baseUrlType": "app", "url": "dynAnswers?bulk=true", "httpMethod": "POST", "authType": "sso",
              "failOnStatusCodes": FAIL,
              "onSend": "<% self.data = {:}; self.data.data = df.answers(qs.data ?? [], refresh(), responseKeyText.getValue(), formCodeText.getValue()); self.data; %>"}]},
         "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": title},
                          "cancelOverride": {"taskId": "DynFormResults"},
                          "body": {"type": "section", "id": "bodySection", "children": [diag] + [slot(i, guides) for i in range(1, n + 1)]}}}
    write(os.path.join(PRES, pid + '.pmd'), p, compact=pid != "DynFormFill")
    return os.path.getsize(os.path.join(PRES, pid + '.pmd'))


# Small page: both refresh styles, switched by ?mode=loop|flat.
fill_page("DynFormFill", "Dynamic form", SMALL_SLOTS, ["loop", "flat"])


def biggest(pid, title, modes):
    lo, hi = 1, 200
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fill_page(pid, title, mid, modes, guides=False) <= WARN - 2048:   # under App Hub's 85 KB warning, 2 KB left for the labels pass
            lo = mid
        else:
            hi = mid - 1
    size = fill_page(pid, title, lo, modes, guides=False)
    return lo, size


big = {}
big["loop"] = biggest("DynFormBigLoop", "Dynamic form, most slots (loop)", ["loop"])
# The spelled-out page is measured but not deployed: with it, App Hub timed out compiling the app (2026-11-17).
big["flat"] = biggest("DynFormBigFlat", "Dynamic form, most slots (spelled out)", ["flat"])
os.remove(os.path.join(PRES, 'DynFormBigFlat.pmd'))

def big_list(n):
    out = []
    for i in range(1, n + 1):
        ty = TYPES[(i - 1) % 5]
        m = "'formCode': 'TEST:DYN:BIG', 'sortOrder': %d, 'qKey': 'q%d', 'qType': '%s', 'qLabel': 'Question %d (%s)', 'required': false" % (i, i, ty, i, ty)
        if ty == 'choice':
            m += ", 'qOptions': 'a=Option A|b=Option B'"
        if i > 1 and i % 5 == 0:
            m += ", 'showKey': 'q%d', 'showOp': 'filled', 'showValue': ''" % (i - 1)
        out.append("{" + m + "}")
    return "[" + ", ".join(out) + "]"



# ---- Lookup page: questions whose choices come from other sources (approved lookups, search as you type, prefill) ----


def wql(name, query, limit, src):
    return {"name": name, "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
            "url": X("'data?limit=" + str(limit) + "&query=' + string:pathEncode('" + query + "')"),
            "exclude": X("!df.uses(" + D + ", '%s')" % src)}


LOOKUP_EPS = [QS, ME] + SUBS + [
              wql("orgs", "SELECT workdayID, name, supervisoryManager, superiorOrganization, primaryLocation FROM supervisoryOrganizations ORDER BY name", 1000, "orgs"),
              wql("positions", "SELECT workdayID, positionID, positionTitle, worker, supervisoryOrganization, manager, location FROM allPositions ORDER BY positionID", 1000, "positions"),
              wql("domains", "SELECT workdayID, domainName, functionalAreas FROM allDomains", 10000, "domains"),
              wql("workers", "SELECT worker, supervisoryOrganization, workersManager, location FROM workersForHCMReporting(dataSourceFilter=allActiveWorkers)", 10000, "workers"),
              {"name": "wsearch", "baseUrlType": "workday-wql", "authType": "sso", "deferred": True,
               "url": "<% 'data?limit=50&query=' + string:pathEncode('SELECT worker FROM workersForHCMReporting(dataSourceFilter=allActiveWorkers) WHERE fullName contains \\'' + q + '\\'') %>"}]


def lslot(i):
    """One question slot. Every attribute calls a short page function (F = the expanded questions, L/S/R = label,
    shown, required): the old form repeated df.ex(qs.data??[],s1...) about 35 times per slot (5.3 KB a slot)."""
    a = "F(),%d" % i
    shown = lambda kind: X("S(%d,'%s')" % (i, kind))
    req = lambda kind: X("R(%d,'%s')" % (i, kind))
    lab = X("L(%d)" % i)
    oc = X("refresh()")
    raw = "orgs.data ?? [], positions.data ?? [], domains.data ?? [], workers.data ?? []"
    return {"type": "fieldSet", "id": "q%dFieldSet" % i, "visible": X("df.v(%s)" % a), "children": [
        {"type": "text", "id": "q%dText" % i, "label": lab, "visible": shown("text"), "required": req("text"),
         "value": X("df.pre(%s, me)" % a),
         "onChange": X("refresh(); rx(%d, self)" % i)},
        {"type": "number", "id": "q%dNumber" % i, "label": lab, "visible": shown("number"), "required": req("number"),
         "enabled": X("!df.c(%s)" % a), "onChange": oc},
        {"type": "date", "id": "q%dDate" % i, "label": lab, "visible": shown("date"), "required": req("date"), "onChange": oc},
        {"type": "instanceList", "id": "q%dChoiceInstanceList" % i, "label": lab, "visible": shown("choice"), "required": req("choice"),
         "values": X("df.o(%s)" % a), "onChange": oc},
        {"type": "checkBox", "id": "q%dCheckBox" % i, "label": lab, "visible": shown("yesno"), "onChange": oc},
        {"type": "instanceList", "id": "q%dLookupInstanceList" % i, "label": lab, "visible": shown("lookup"),
         "required": req("lookup"), "values": X("df.opts(%s, orgs.data ?? [], positions.data ?? [], domains.data ?? [])" % a),
         "selectedValuesAndDescriptors": X("df.preSel(%s, me)" % a), "onChange": oc},
        {"type": "instanceList", "id": "q%dSearchInstanceList" % i, "label": lab, "visible": shown("search"),
         "required": req("search"), "values": "<% [] %>", "onChange": oc,
         "onSearch": X("empty(event.query) ? [] : df.wmap(wsearch.invoke({'q': df.clean(event.query)}).data)")},
        {"type": "instanceList", "id": "q%dBrowseInstanceList" % i, "label": lab, "visible": shown("browse"),
         "required": req("browse"), "values": X("browse.rootFor(df.lk(%s), positions.data ?? [])" % a), "onChange": oc,
         "selectedValuesAndDescriptors": X("df.preSel(%s, me)" % a),
         "dynamicMonikerLevels": X("browse.levelFor(df.lk(%s), %s, self.promptSelections)" % (a, raw)),
         "onSearch": X("browse.findFor(df.lk(%s), %s, event.query)" % (a, raw))}]}


def lrow(i):
    return ("[q{i}Text.getValue(), q{i}LookupInstanceList.getValue(), q{i}LookupInstanceList.selectedEntries, "
            "q{i}SearchInstanceList.getValue(), q{i}SearchInstanceList.selectedEntries, q{i}Number.getValue(), q{i}Date.getValue(), "
            "q{i}ChoiceInstanceList.getValue(), q{i}CheckBox.getValue(), q{i}BrowseInstanceList.getValue(), q{i}BrowseInstanceList.selectedEntries]").format(i=i)


def lslots(n):
    return ", ".join("[q{i}FieldSet, q{i}Text, q{i}Number, q{i}Date, q{i}ChoiceInstanceList, q{i}CheckBox, q{i}LookupInstanceList, q{i}SearchInstanceList, q{i}BrowseInstanceList]".format(i=i) for i in range(1, n + 1))


# The expanded question list is built once per load into a hidden widget (dxHidden, as JSON) and the slot functions
# parse that, rather than expanding the questions in every slot attribute: F() expanded them ~1,000 times per load,
# 12.5 s for a form with a repeating group at 30 slots (2026-11-19). A top-level page-script variable didn't help:
# Workday runs the page script's top level again for every function call.
LOOKUP_SCRIPT = ("<%\n  var F = function() {\n    json:parse(dxHidden.getValue());\n  };\n"
                 "  var L = function(i) {\n    df.ll(F(), i, langCodeText.getLabel());\n  };\n"
                 "  var S = function(i, kind) {\n    df.sw(F(), i, kind);\n  };\n"
                 "  var R = function(i, kind) {\n    df.rq(F(), i, kind);\n  };\n"
                 "  var rx = function(i, w) {\n    var e = df.rxErr(F(), i, w.getValue());\n    if (empty(e)) { w.clearError(); } else { w.setError(e); }\n  };\n"
                 "  var slots = function() {\n    [" + lslots(LOOKUP_SLOTS) + "];\n  };\n"
                 "  var refresh = function() {\n    var d = F();\n    var all = slots();\n    var ans = {:};\n    var i = 0;\n"
                 "    for (var s : all) {\n      i = i + 1;\n      var key = df.k(d, i);\n"
                 "      if (!empty(key)) { ans.put(key, df.pick2(d, i, [s[1].getValue(), s[2].getValue(), s[3].getValue(), s[4].getValue(), s[5].getValue(), s[6].getValue(), s[7].getValue(), s[8].getValue()])); }\n    }\n"
                 "    var j = 0;\n"
                 "    for (var s2 : all) {\n      j = j + 1;\n"
                 "      if (!empty(df.k(d, j))) {\n        var vis = df.show(d, j, ans);\n        s2[0].setVisible(vis);\n"
                 "        var w = s2[df.wi2(d, j)];\n        w.setRequired(vis && df.req(d, j) && df.wk(d, j) != 'yesno');\n"
                 "        var om = df.overMax(d, df.k(d, j), w.getValue());\n        if (om == 'ok') { w.clearError(); } else { if (om != 'na') { w.setError(om); } }\n"
                 "        if (df.c(d, j)) { var nv = df.calcVal(d, j, ans); if (s2[2].getValue() != nv) { s2[2].setValue(nv); } }\n      }\n    }\n    ans;\n  };\n%>")

lookup_page = {"id": "DynFormLookup", "securityDomains": DOM, "include": ["df.script", "browse.script"], "endPoints": LOOKUP_EPS, "script": LOOKUP_SCRIPT,
    "outboundData": {"outboundEndPoints": [
        {"name": "postResponse", "baseUrlType": "app", "url": "dynResponses", "httpMethod": "POST", "authType": "sso",
         "failOnStatusCodes": FAIL,
         "onSend": "<% self.data = {:}; self.data.responseKey = responseKeyText.getValue(); self.data.formCode = formCodeText.getValue(); "
                   "self.data.status = 'Submitted'; var subj = {:}; subj.id = me.id; self.data.subject = subj; "
                   "self.data.parentKey = queryParams.parent ?? ''; self.data.nextForm = df.nextForm(qs.data ?? [], refresh()); "
                   "var fc = '' + formCodeText.getValue(); self.data.family = fc.contains('@') ? fc.substringBefore('@') : fc; "
                   "self.data.formVersion = fc.contains('@') ? fc.substringAfter('@').toInt() : 1; "
                   "self.data.orgName = empty(me.primarySupervisoryOrganization) ? '' : ('' + (me.primarySupervisoryOrganization.descriptor ?? '')); self.data; %>"},
        {"name": "postAnswers", "baseUrlType": "app", "url": "dynAnswers?bulk=true", "httpMethod": "POST", "authType": "sso",
         "failOnStatusCodes": FAIL,
         "onSend": "<% self.data = {:}; self.data.data = df.lanswers(" + D + ", [" + ", ".join(lrow(i) for i in range(1, LOOKUP_SLOTS + 1)) +
                   "], responseKeyText.getValue(), formCodeText.getValue(), refresh()); self.data; %>"}]},
    "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Fill a form"},
                     "cancelOverride": {"taskId": "FormStudio"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "diagFieldSet", "title": "Form", "collapsible": True, "initializeCollapsed": True, "children": [
                             {"type": "hidden", "id": "dxHidden", "value": "<% json:stringify(" + D + ") %>"},
                             {"type": "text", "id": "formCodeText", "label": "Form code", "enabled": False, "value": "<% queryParams.form ?? 'TEST:DYN:LOOKUP2' %>"},
                             # the translated label of this text is the user's language code (en-US.properties: en-US, fr-CA: fr-CA)
                             {"type": "text", "id": "langCodeText", "label": "en-US", "enabled": False, "value": "<% 'Language used for question labels' %>"},
                             {"type": "text", "id": "responseKeyText", "label": "Response key", "enabled": False,
                              "value": "<% 'TEST:DYN:R' + date:now().format('yyyyMMddHHmmssSSS') %>"},
                             {"type": "text", "id": "loadedText", "label": "Loaded", "enabled": False,
                              "value": "<% '' + (" + D + ").size() + ' questions (' + (qs.data ?? []).size() + ' in this form' + (empty(queryParams.parent) ? '' : ', follows ' + queryParams.parent) + '); lists loaded: orgs ' + (orgs.data ?? []).size() + ', positions ' + "
                                       "(positions.data ?? []).size() + ', domains ' + (domains.data ?? []).size() + ', workers ' + (workers.data ?? []).size() %>"}]}]
                         + [lslot(i) for i in range(1, LOOKUP_SLOTS + 1)]}}}
write(os.path.join(PRES, 'DynFormLookup.pmd'), lookup_page, compact=True)

# ---- Employee pages (acceptance item 10, 2026-11-19): least privilege for the people who fill forms ----
# Domain DynFill opens only these two pages. Every read and write of app data here goes through the ISU sign-in
# (SMD authType isuAuth, the app's integration system user), so an employee needs no access to any business object:
# the page shows them only their own open assignments and writes their answers; they can't read anyone's responses.
# Confidential answers stay behind DynConfidential (HR only). Lookups to Workday data (WQL) still run as the employee.
FILL_DOM = ["DynFill"]
write(os.path.join(MODEL, 'DynFill.securitydomain'), {"id": 3, "name": "DynFill", "label": "Dyn Forms Fill",
                                                      "enabledForPageSecurity": True, "enabledForOrchestrationSecurity": False})
write(os.path.join(MODEL, 'MyForms.task'), {"id": 12, "name": "MyForms", "label": "My Forms to Fill", "securityDomains": FILL_DOM,
                                            "routePath": "/dynMyForms"})


def isu(ep):
    e = dict(ep)
    if e.get("baseUrlType") == "app":
        e["authType"] = "isuAuth"
    return e


# Employee pages identify the signed-in person with person/v4/people/me, which works before a new hire's start date
# (common/v1/workers/me fails then, 2026-11-19), plus their worker row from WQL allWorkers by person when they can
# see it (employees; empty for a pre-employee). ME() gives the old `me` shape; with no worker row the form's own
# assignment (queryParams.parent, read through the ISU) supplies the worker the form is for.
PME = {"name": "pme", "baseUrlType": "workday-api", "url": "person/v4/people/me", "authType": "sso", "failOnStatusCodes": FAIL}
MEW = {"name": "mew", "baseUrlType": "workday-wql", "authType": "sso",
       "url": "<% 'data?limit=5&query=' + string:pathEncode('SELECT worker, businessTitle, location, supervisoryOrganization FROM allWorkers WHERE person in (' + (empty(pme.id) ? 'x' : pme.id) + ')') %>"}
ASG1 = {"name": "asgOne", "baseUrlType": "app", "authType": "isuAuth",
        "url": "<% 'dynResponses?limit=1&responseKey=' + (queryParams.parent ?? '').urlEncode() %>", "exclude": "<% empty(queryParams.parent) %>"}
ME_FN = ("  var ME = function() {\n    var r = (mew.data ?? []).size() > 0 ? mew.data[0] : {:};\n"
         "    var a = (asgOne.data ?? []).size() > 0 ? asgOne.data[0] : {:};\n    var m = {:};\n"
         "    m.put('id', !empty(a.bpTarget) ? a.bpTarget : (empty(r.worker) ? '' : r.worker.id));\n"
         "    m.put('descriptor', empty(r.worker) ? '' : (r.worker.descriptor ?? ''));\n    m.put('businessTitle', r.businessTitle ?? '');\n"
         "    m.put('location', r.location ?? {:});\n    m.put('primarySupervisoryOrganization', r.supervisoryOrganization ?? {:});\n"
         "    m.put('primaryWorkEmail', '');\n    m;\n  };\n")

my_fill = json.loads(json.dumps(lookup_page))
my_fill["id"] = "DynMyFill"
my_fill["securityDomains"] = FILL_DOM
my_fill["endPoints"] = [isu(e) for e in my_fill["endPoints"] if e["name"] != "me"] + [PME, MEW, ASG1]
my_fill["script"] = my_fill["script"].replace("<%\n", "<%\n" + ME_FN, 1)
_mf = json.dumps(my_fill)
_mf = _mf.replace("var subj = {:}; subj.id = me.id; self.data.subject = subj; ",
                  "if (!empty(ME().id)) { var subj = {:}; subj.id = ME().id; self.data.subject = subj; } ")
_mf = _mf.replace("empty(me.primarySupervisoryOrganization) ? '' : ('' + (me.primarySupervisoryOrganization.descriptor ?? ''))",
                  "('' + (ME().primarySupervisoryOrganization.descriptor ?? ''))")
_mf = _mf.replace(", me)", ", ME())")
assert " me." not in _mf and "(me." not in _mf and ", me)" not in _mf, "a me reference is left on DynMyFill"
my_fill = json.loads(_mf)
for e in my_fill["outboundData"]["outboundEndPoints"]:
    e["authType"] = "isuAuth"
my_fill["presentation"]["title"]["label"] = "Fill your form"
my_fill["presentation"]["cancelOverride"] = {"taskId": "DynMyForms"}
write(os.path.join(PRES, 'DynMyFill.pmd'), my_fill, compact=True)

# the newest 200 BP assignments (collections come back oldest first: count, then the last pages), mine and still open
MY_COUNT = {"name": "asgCount", "baseUrlType": "app", "authType": "isuAuth", "failOnStatusCodes": FAIL, "url": "dynResponses?limit=1"}
MY_PAGES = [{"name": "asgPage%d" % n, "baseUrlType": "app", "authType": "isuAuth",
             "url": "<% let t = asgCount.total ?? 0; let st = t - " + str(100 * (n + 1)) + "; '/dynResponses?limit=100&offset=' + (st < 0 ? 0 : st) %>",
             "exclude": "<% (asgCount.total ?? 0) - " + str(100 * n) + " <= 0 %>"} for n in (0, 1)]
# mine, still open, and not filled yet (a filled form is a response whose parentKey is the assignment's key)
MY_SCRIPT = ("<%\n  var rows = function() {\n"
             "    var all = list:flatten([asgPage0.data ?? [], asgPage1.data ?? []]);\n"
             "    var done = '|' + all.map(c => { '' + (c.parentKey ?? '') }).join('|') + '|';\n"
             "    var mine = (mew.data ?? []).map(w => { empty(w.worker) ? '' : w.worker.id });\n"
             "    all.filter(r => { (r.formCode ?? '') == 'BP' && !done.contains('|' + (r.responseKey ?? '') + '|') "
             "&& ((!empty(r.bpPerson) && r.bpPerson == pme.id) || (!empty(r.bpTarget) && mine.contains(r.bpTarget))) "
             "&& ('' + (r.status ?? '')).startsWith('Assigned') });\n  };\n%>")
MY_ROWS = "<% rows() %>"
my_forms = {"id": "DynMyForms", "securityDomains": FILL_DOM, "endPoints": [PME, MEW, MY_COUNT] + MY_PAGES, "script": MY_SCRIPT,
    "presentation": {"title": {"type": "title", "id": "pageTitle", "label": "My forms to fill"},
        "body": {"type": "section", "id": "bodySection", "children": [
            {"type": "fieldSet", "id": "aboutFieldSet", "title": "About", "children": [
                {"type": "richText", "id": "aboutRichText", "value": "<span style=\"color:#374151;font-size:13px\">Forms your requests are waiting on. Click Fill, answer the questions and click OK. Your answers go to HR; only HR can see answers marked confidential.</span>"}]},
            {"type": "grid", "id": "myFormsGrid", "label": "Forms to fill", "rows": MY_ROWS, "rowVariableName": "mr",
             "render": "<% rows().size() > 0 %>",
             "columns": [
                 {"type": "column", "columnId": "forColumn", "label": "For", "cellTemplate": {"type": "text", "id": "forText", "value": "<% ('' + (mr.status ?? '')).substringAfter('Assigned: ') %>"}},
                 {"type": "column", "columnId": "formColumn", "label": "Form", "cellTemplate": {"type": "text", "id": "formText", "value": "<% mr.nextForm ?? '' %>"}},
                 {"type": "column", "columnId": "fillColumn", "label": "Fill", "cellTemplate": {"type": "button", "id": "fillButton", "label": "Fill", "action": "PRIMARY",
                  "taskReference": {"taskId": "DynMyFill", "parameterBindings": {"form": "<% mr.nextForm ?? '' %>", "parent": "<% mr.responseKey ?? '' %>"}}}}]},
            {"type": "fieldSet", "id": "noneFieldSet", "title": "Nothing waiting", "render": "<% rows().size() == 0 %>", "children": [
                {"type": "text", "id": "noneText", "label": "Status", "enabled": False, "value": "<% 'No forms are waiting for you.' %>"}]}]}}}
write(os.path.join(PRES, 'DynMyForms.pmd'), my_forms)


def qlit(code, n, key, ty, label, required, lookup='', prefill='', extra=None):
    m = "'formCode': '%s', 'sortOrder': %d, 'qKey': '%s', 'qType': '%s', 'qLabel': '%s', 'required': %s" % (
        code, n, key, ty, label, 'true' if required else 'false')
    for ek, ev in (extra or {}).items():
        m += (", '%s': %s" % (ek, 'true' if ev else 'false')) if isinstance(ev, bool) else (", '%s': '%s'" % (ek, ev))
    if lookup:
        m += ", 'lookup': '%s'" % lookup
    if prefill:
        m += ", 'prefill': '%s'" % prefill
    return "{" + m + "}"


LOOKUP_FORMS = {
    "lookup": ("TEST:DYN:LOOKUP2", "Test lookup form", [
        ("name", "text", "Your name (from Workday)", False, "", "name"),
        ("title", "text", "Your business title (from Workday)", False, "", "title"),
        ("location", "text", "Your location (from Workday)", False, "", "location"),
        ("org", "lookup", "Supervisory organization (your own preselected)", True, "orgs", "org"),
        ("position", "lookup", "Position", False, "positions", ""),
        ("delegate", "lookup", "Delegate (type a name to search)", False, "workers", ""),
        ("email", "text", "Work email (from Workday)", False, "", "email"),
        ("comment", "text", "Comment", False, "", "")]),
    "biglist": ("TEST:DYN:BIGLIST", "Test big lookup list", [
        ("domain", "lookup", "Security domain (all 4,000+)", False, "domains", ""),
        ("comment", "text", "Comment", False, "", "")]),
    "huge": ("TEST:DYN:HUGE", "Test 150-question form", [("h%d" % i, "text", "Huge question %d" % i, False, "", "") for i in range(1, 151)]),
    "req": ("TEST:DYN:REQ", "Test request with sub-forms", [
        ("requester", "text", "Requester (from Workday)", False, "", "name"),
        ("requestType", "choice", "Request type", True, "", "", {"qOptions": "hw=Hardware|sw=Software|access=Access"}),
        ("hwForm", "subform", "Hardware details", False, "", "", {"qOptions": "TEST:DYN:HW", "showKey": "requestType", "showOp": "eq", "showValue": "hw"}),
        ("swForm", "subform", "Software details", False, "", "", {"qOptions": "TEST:DYN:SW", "showKey": "requestType", "showOp": "eq", "showValue": "sw"}),
        ("accessNext", "nextform", "Access request", False, "", "", {"qOptions": "TEST:DYN:ACCESS", "showKey": "requestType", "showOp": "eq", "showValue": "access"}),
        ("comment", "text", "Comment", False, "", "")]),
    "hw": ("TEST:DYN:HW", "Test hardware sub-form", [
        ("device", "choice", "Device", True, "", "", {"qOptions": "laptop=Laptop|monitor=Monitor|phone=Phone"}),
        ("quantity", "number", "Quantity", True, "", ""),
        ("specs", "text", "Laptop specs (shown for laptops)", False, "", "", {"showKey": "device", "showOp": "eq", "showValue": "laptop"}),
        ("neededBy", "date", "Needed by", False, "", "")]),
    "sw": ("TEST:DYN:SW", "Test software sub-form", [
        ("software", "text", "Software name", True, "", ""),
        ("licenses", "number", "Licenses", True, "", "")]),
    "access": ("TEST:DYN:ACCESS", "Test access follow-up form", [
        ("system", "text", "System", True, "", ""),
        ("reason", "text", "Reason", True, "", ""),
        ("approver", "lookup", "Approver", False, "workers", "")]),
    "addr": ("TEST:DYN:ADDR", "Test address change follow-up", [
        ("parking", "yesno", "Do you need a parking permit at the new address?", False, "", ""),
        ("commute", "number", "Commute distance (km)", False, "", ""),
        ("addrNotes", "text", "Anything else HR should know about the move?", False, "", "")]),
    # acceptance tests (2026-11-18): gate and route answers, a French label, a confidential answer; seeded Published
    "acc": ("TEST:DYN:ACC", "Test acceptance form", [
        ("parking", "yesno", "Do you need a parking permit?", False, "", ""),
        ("commute", "number", "Commute distance (km)", False, "", "", {"labels": '{"fr-CA":"Distance domicile-travail (km)"}'}),
        ("salary", "text", "Expected salary (confidential)", False, "", "", {"confidential": True}),
        ("accNotes", "text", "Anything else HR should know?", False, "", "")]),
    # repeating group (2026-11-19): DEP's questions repeat once per dependant, up to 4 times
    "rep": ("TEST:DYN:REP", "Test form with a repeating group", [
        ("depCount", "choice", "How many dependants?", True, "", "", {"qOptions": "0=0|1=1|2=2|3=3|4=4"}),
        ("deps", "repeat", "Dependants", False, "", "", {"qOptions": "TEST:DYN:DEP", "params": "count=depCount;max=4"}),
        ("repNotes", "text", "Anything else?", False, "", "")]),
    "dep": ("TEST:DYN:DEP", "Test dependant (repeated)", [
        ("depName", "text", "Dependant name", True, "", ""),
        ("depBirth", "date", "Date of birth", False, "", ""),
        ("depStudent", "yesno", "Full-time student", False, "", ""),
        ("depSchool", "text", "School", False, "", "", {"showKey": "depStudent", "showOp": "eq", "showValue": "true"})]),
    "plain": ("TEST:DYN:PLAIN", "Test plain form", [
        ("comment", "text", "Comment", False, "", ""),
        ("other", "text", "Other", False, "", "")])}


def lookup_list(which):
    code, _, qs_ = LOOKUP_FORMS[which]
    return "[" + ", ".join(qlit(code, n + 1, *q) for n, q in enumerate(qs_)) + "]"


# Seed page: writes the two test forms and their questions (no chaining: questions link by form code).
seed = {"id": "DynFormSeed", "securityDomains": DOM, "include": ["df.script"],
        "outboundData": {"outboundEndPoints": [
            {"name": "postForm", "baseUrlType": "app", "url": "dynForms", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
             "onSend": "<% self.data = {:}; var w = sampleInstanceList.value[0]; "
                       "self.data.code = (w == 'addr' ? 'TEST:DYN:ADDR' : (w == 'req' ? 'TEST:DYN:REQ' : (w == 'hw' ? 'TEST:DYN:HW' : (w == 'sw' ? 'TEST:DYN:SW' : (w == 'access' ? 'TEST:DYN:ACCESS' : (w == 'big' ? 'TEST:DYN:BIG' : (w == 'lookup' ? 'TEST:DYN:LOOKUP2' : (w == 'biglist' ? 'TEST:DYN:BIGLIST' : (w == 'plain' ? 'TEST:DYN:PLAIN' : (w == 'huge' ? 'TEST:DYN:HUGE' : (w == 'acc' ? 'TEST:DYN:ACC' : (w == 'rep' ? 'TEST:DYN:REP' : (w == 'dep' ? 'TEST:DYN:DEP' : 'TEST:DYN:SMALL'))))))))))))); "
                       "self.data.formName = 'Test form ' + w; self.data.description = w == 'req' ? 'Shows Hardware or Software details inline and offers the Access form next.' : ''; self.data.version = 1; self.data.status = w == 'acc' ? 'Published' : 'Approved'; self.data.family = self.data.code; self.data; %>"},
            {"name": "postQuestions", "baseUrlType": "app", "url": "dynQuestions?bulk=true", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
             "onSend": "<% self.data = {:}; var w = sampleInstanceList.value[0]; self.data.data = w == 'addr' ? " + lookup_list('addr') + " : (w == 'req' ? " + lookup_list('req') + " : (w == 'hw' ? " + lookup_list('hw') + " : (w == 'sw' ? " + lookup_list('sw') + " : (w == 'access' ? " + lookup_list('access') + " : (w == 'big' ? " + big_list(max(big["loop"][0], big["flat"][0])) +
                       " : (w == 'lookup' ? " + lookup_list('lookup') + " : (w == 'biglist' ? " + lookup_list('biglist') + " : (w == 'plain' ? " + lookup_list('plain') + " : (w == 'huge' ? " + lookup_list('huge') +
                       " : (w == 'acc' ? " + lookup_list('acc') + " : (w == 'rep' ? " + lookup_list('rep') + " : (w == 'dep' ? " + lookup_list('dep') + " : df.sample('small', 0))))))))))))); self.data; %>"}]},
        "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Seed test forms"},
                         "cancelOverride": {"taskId": "DynFormResults"},
                         "body": {"type": "section", "id": "bodySection", "children": [
                             {"type": "fieldSet", "id": "seedFieldSet", "title": "Seed", "children": [
                                 {"type": "instanceList", "id": "sampleInstanceList", "label": "Form", "required": True,
                                  "instanceList": [{"id": "small", "descriptor": "TEST:DYN:SMALL (7 questions with rules)"},
                                                   {"id": "big", "descriptor": "TEST:DYN:BIG (generated questions)"},
                                                   {"id": "lookup", "descriptor": "TEST:DYN:LOOKUP2 (lookups, search, prefill)"},
                                                   {"id": "biglist", "descriptor": "TEST:DYN:BIGLIST (4,000+ option list)"},
                                                   {"id": "plain", "descriptor": "TEST:DYN:PLAIN (two text questions)"},
                                                   {"id": "req", "descriptor": "TEST:DYN:REQ (request with sub-forms and a next form)"},
                                                   {"id": "addr", "descriptor": "TEST:DYN:ADDR (address change follow-up, assigned by a business process)"},
                                                   {"id": "hw", "descriptor": "TEST:DYN:HW (hardware sub-form)"},
                                                   {"id": "sw", "descriptor": "TEST:DYN:SW (software sub-form)"},
                                                   {"id": "access", "descriptor": "TEST:DYN:ACCESS (access follow-up form)"},
                                                   {"id": "huge", "descriptor": "TEST:DYN:HUGE (150 questions in one bulk call)"},
                                                   {"id": "acc", "descriptor": "TEST:DYN:ACC (acceptance tests: gate, route, French label, confidential answer; Published)"},
                                                   {"id": "rep", "descriptor": "TEST:DYN:REP (repeating group: up to 4 dependants)"},
                                                   {"id": "dep", "descriptor": "TEST:DYN:DEP (the repeated dependant questions; seed it too)"}]}
                                 ]}]}}}
write(os.path.join(PRES, 'DynFormSeed.pmd'), seed)

col = lambda cid, label, value: {"type": "column", "columnId": cid, "label": label,
                                 "cellTemplate": {"type": "text", "id": cid.replace('Column', 'Text'), "enabled": False, "value": value}}
def lcol(cid, label, id_expr, desc_expr):
    """A column whose cell links a record (Workday object or app record): the link opens it and its related-actions
    menu lists its tasks. Plain text when there is no WID."""
    base = cid.replace("Column", "")
    return {"type": "column", "columnId": cid, "label": label, "cellTemplate": {"type": "fieldSet", "id": base + "FieldSet", "children": [
        {"type": "instanceList", "id": base + "InstanceList", "visible": "<% !empty(" + id_expr + ") %>",
         "values": "<% empty(" + id_expr + ") ? [] : [{'id': " + id_expr + ", 'descriptor': " + desc_expr + "}] %>",
         "widKey": "id", "view": True, "relatedTask": True},
        {"type": "text", "id": base + "Text", "enabled": False, "visible": "<% empty(" + id_expr + ") %>", "value": "<% " + desc_expr + " %>"}]}}


# with nothing picked, the newest 50 responses only (their answers are read by key; see df.ansQ) (all ~600 with their per-row lookups took 18 s, 2026-11-19)
RESP_ROWS = ("df.cap((responses.data ?? []).filter(r => { (empty(queryParams.form) || r.formCode == queryParams.form) && "
             "(empty(queryParams.key) || r.responseKey == queryParams.key || r.parentKey == queryParams.key) && "
             "(empty(queryParams.taskObjectId) || r.workdayID == queryParams.taskObjectId) }), "
             "(empty(queryParams.form) && empty(queryParams.key) && empty(queryParams.taskObjectId)) ? 50 : 10000)")
results = {"id": "DynFormResults", "securityDomains": DOM, "include": ["df.script"], "endPoints": [
    {"name": "forms", "baseUrlType": "app", "url": "dynForms?limit=100", "authType": "sso", "failOnStatusCodes": FAIL},
    {"name": "responses", "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
     "url": "<% 'data?limit=10000&query=' + string:pathEncode(df.resQ(queryParams.form, 'responses')) %>"},
    {"name": "answers", "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
     "url": "<% 'data?limit=10000&query=' + string:pathEncode(df.ansQ(" + RESP_ROWS + ".map(x => { x.responseKey }))) %>"},
    {"name": "questions", "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
     "url": "<% 'data?limit=10000&query=' + string:pathEncode('SELECT workdayID, formCode, qKey FROM ' + '" + REF + "_dynQuestions') %>"}],
    "presentation": {"pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Dynamic form results"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "grid", "id": "nextGrid", "label": "Next forms to fill", "rowVariableName": "nr",
                          "render": "<% !empty(df.pending(responses.data ?? [])) %>", "rows": "<% df.pending(responses.data ?? []) %>",
                          "columns": [lcol("nkeyColumn", "After response", "nr.workdayID", "nr.responseKey ?? ''"), lcol("nformColumn", "Form", "df.formWid(forms.data, nr)", "nr.formCode ?? ''"),
                                      lcol("nstatusColumn", "Status", "df.statusWid(nr)", "nr.status ?? ''"),
                                      lcol("nnextColumn", "Next form", "df.widOf(forms.data, 'code', nr.nextForm)", "nr.nextForm ?? ''"),
                                      {"type": "column", "columnId": "nfillColumn", "label": "Fill", "excel": {"enabled": False},
                                       "cellTemplate": {"type": "button", "id": "fillNextButton", "label": "Fill next form", "action": "PRIMARY",
                                                        "taskReference": {"taskId": "DynFormLookup",
                                                                          "parameterBindings": {"form": "<% nr.nextForm ?? '' %>", "parent": "<% nr.responseKey ?? '' %>"}}}}]},
                         {"type": "grid", "id": "responsesGrid", "label": "Responses", "rowVariableName": "rr", "rows": "<% " + RESP_ROWS + " %>",
                          "columns": [lcol("keyColumn", "Response key", "rr.workdayID", "rr.responseKey ?? ''"), lcol("formColumn", "Form", "df.formWid(forms.data, rr)", "rr.formCode ?? ''"),
                                      lcol("statusColumn", "Status", "df.statusWid(rr)", "rr.status ?? ''"),
                                      lcol("subjectColumn", "Subject", "df.subjWid(rr)", "df.subjName(rr)"),
                                      lcol("parentColumn", "Follows", "df.widOf(responses.data, 'responseKey', rr.parentKey)", "rr.parentKey ?? ''"),
                                      lcol("nextColumn", "Next form", "df.widOf(forms.data, 'code', rr.nextForm)", "rr.nextForm ?? ''")]},
                         {"type": "grid", "id": "answersGrid", "label": "Answers", "rowVariableName": "ar", "rows": "<% let keys = " + RESP_ROWS + ".map(x => { x.responseKey }).join('|'); let kt = '|' + keys + '|'; df.tag((answers.data ?? []).filter(r => { kt.contains('|' + (r.responseKey ?? '') + '|') }), responses.data ?? [], questions.data ?? []) %>",
                          "columns": [lcol("akeyColumn", "Response key", "ar.rw", "ar.responseKey ?? ''"), lcol("qColumn", "Question", "ar.qw", "ar.qKey ?? ''"),
                                      col("textColumn", "Text", "<% ar.textValue ?? '' %>"),
                                      col("secretColumn", "Confidential", "<% ar.secretText ?? '' %>"),
                                      col("numberColumn", "Number", "<% (empty(ar.numberValue) || ('' + ar.numberValue) == '0') ? '' : '' + ar.numberValue %>"),
                                      col("dateColumn", "Date", "<% ar.dateValue ?? '' %>"),
                                      lcol("refColumn", "Picked record",
                                           "(!empty(ar.organization) ? ar.organization.id : (!empty(ar.position) ? ar.position.id : (!empty(ar.worker) ? ar.worker.id : '')))",
                                           "ar.refDescriptor ?? ''")]}]}}}
write(os.path.join(PRES, 'DynFormResults.pmd'), results)

# DynFormNext: opened from a response record's related actions ("Fill Next Form"); one button to that record's next form.
nextpage = {"id": "DynFormNext", "securityDomains": DOM, "endPoints": [
    {"name": "rec", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
     "url": "<% 'dynResponses/' + (queryParams.taskObjectId ?? '') %>"}],
    "presentation": {"pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Fill the next form"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "recFieldSet", "title": "Response", "children": [
                             {"type": "text", "id": "keyText", "label": "Response key", "enabled": False, "value": "<% rec.responseKey ?? '' %>"},
                             {"type": "text", "id": "statusText", "label": "Status", "enabled": False, "value": "<% rec.status ?? '' %>"},
                             {"type": "text", "id": "nextText", "label": "Next form", "enabled": False,
                              "value": "<% empty(rec.nextForm) ? 'This response has no next form.' : rec.nextForm %>"},
                             {"type": "button", "id": "fillNextButton", "label": "Fill next form", "action": "PRIMARY", "render": "<% !empty(rec.nextForm) %>",
                              "taskReference": {"taskId": "DynFormLookup", "parameterBindings": {"form": "<% rec.nextForm ?? '' %>", "parent": "<% rec.responseKey ?? '' %>"}}},
                             {"type": "button", "id": "allResponsesButton", "label": "All responses", "action": "LINK",
                              "taskReference": {"taskId": "DynFormResults"}}]}]}}}
write(os.path.join(PRES, 'DynFormNext.pmd'), nextpage)
for tid, name, label, route in [(9, "ViewFormResponse", "View Form Response", "/dynFormResults/{taskObjectId}"),
                                (10, "FillNextForm", "Fill Next Form", "/dynFormNext/{taskObjectId}")]:
    write(os.path.join(MODEL, name + '.task'), {"id": tid, "name": name, "label": label, "securityDomains": DOM,
                                                "businessObject": "DynResponse", "routePath": route})

# ---- DynFormCopy (2026-11-18): copy a form, start a new version, add questions from another form, publish a version,
# export or import a version as JSON. Questions go in bulk POSTs of up to 100 (two calls cover 200). Rules (showKey)
# and sums follow renamed keys; the preview lists every rename, rewritten rule and lookup that isn't approved here.
FORM_OPTS = "<% (forms.data ?? []).map(f => { { 'id': f.code ?? '', 'descriptor': (f.code ?? '') + ' · v' + ('' + (f.version ?? 1)).substringBefore('.') + ' · ' + (f.status ?? '') } }) %>"
COPY_SCRIPT = """<%
  var mode = function() { empty(modeInstanceList.getValue()) ? 'copy' : modeInstanceList.getValue()[0]; };
  var src = function() { empty(sourceInstanceList.getValue()) ? '' : sourceInstanceList.getValue()[0]; };
  var tgt = function() { empty(targetInstanceList.getValue()) ? '' : targetInstanceList.getValue()[0]; };
  var srcQs = function() { mode() == 'import' ? df.cpImport(importTextArea.getValue()).questions : (empty(src()) ? [] : (qsOf.invoke({'c': src()}).data ?? [])); };
  var code = function() { mode() == 'import' ? (empty(newCodeText.getValue()) ? df.cpImport(importTextArea.getValue()).code : ('' + newCodeText.getValue()).trim()) : df.cpCode(mode(), src(), tgt(), newCodeText.getValue(), forms.data ?? []); };
  var subSizes = function(qs) {
    var m = {:};
    for (var x : qs) { var c0 = x.qOptions ?? ''; if (((x.qType ?? '') == 'subform' || (x.qType ?? '') == 'repeat') && !empty(c0) && !m.containsKey(c0)) { m.put(c0, (qsOf.invoke({'c': c0}).data ?? []).size()); } }
    m;
  };
  var plan = function() {
    var tq = (mode() == 'add' && !empty(tgt())) ? (qsOf.invoke({'c': tgt()}).data ?? []) : [];
    var sq = srcQs();
    var both = [];
    both.addAll(sq);
    both.addAll(tq);
    df.cpPlan(sq, questionsInstanceList.getValue() ?? [], tq, code(), mode() == 'import' ? 'copy' : mode(), subSizes(both));
  };
  var pol = function(w) { empty(w.getValue()) ? 'default' : ('' + w.getValue()[0]).replace('Nf', '').replace('Fail', ''); };
  var preview = function() {
    var m = mode();
    newCodeText.setRequired(m == 'copy');
    targetInstanceList.setRequired(m == 'add');
    importTextArea.setRequired(m == 'import');
    sourceInstanceList.setRequired(m != 'import');
    var taken = (forms.data ?? []).map(f => { f.code ?? '' });
    var c = code();
    if ((m == 'copy' || m == 'import' || m == 'version') && taken.contains(c)) { newCodeText.setError('A form with the code ' + c + ' already exists.'); } else { newCodeText.clearError(); }
    previewReadOnlyText.setValue(m == 'policy' ? (empty(src()) ? 'Pick the form.' : src() + ': when not filled ' + pol(noFormInstanceList) + ', when the check fails ' + pol(failInstanceList) + ' (empty = the orchestration default, cancel).' + (empty(alsoAssignText.getValue()) ? '' : ' Also assigned with it: ' + alsoAssignText.getValue() + '.')) : m == 'publish' ? (empty(src()) ? 'Pick the version to publish.' : src() + ' becomes Published. New requests get the highest published version of its family; requests already assigned keep theirs.') : plan().summary);
  };
  var pickSource = function() {
    var qs = empty(src()) ? [] : (qsOf.invoke({'c': src()}).data ?? []);
    questionsInstanceList.setValues(qs.map(x => { { 'id': x.qKey ?? '', 'descriptor': (x.qKey ?? '') + ' · ' + (x.qLabel ?? '') } }));
    exportTextArea.setValue(empty(src()) ? '' : df.cpExport(forms.data ?? [], src(), qs));
    preview();
  };
%>"""
copy_page = {"id": "DynFormCopy", "securityDomains": DOM, "include": ["df.script"], "script": COPY_SCRIPT, "endPoints": [
    {"name": "forms", "baseUrlType": "app", "url": "dynForms?limit=100", "authType": "sso", "failOnStatusCodes": FAIL},
    {"name": "qsOf", "baseUrlType": "app", "authType": "sso", "deferred": True, "url": "<% 'dynQuestions?limit=100&formCode=' + c.urlEncode() %>"}],
    "outboundData": {"outboundEndPoints": [
        {"name": "postForm", "baseUrlType": "app", "url": "dynForms", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
         "exclude": "<% mode() == 'add' || mode() == 'publish' || mode() == 'policy' %>",
         "onSend": "<% self.data = {:}; var f = df.fRow(forms.data ?? [], src()); self.data.code = code(); "
                   "self.data.formName = mode() == 'import' ? df.cpImport(importTextArea.getValue()).formName : ((f.formName ?? src()) + (mode() == 'copy' ? ' (copy)' : '')); "
                   "self.data.version = df.cpVersion(mode(), src(), forms.data ?? []); self.data.status = 'Draft'; "
                   "self.data.copiedFrom = mode() == 'import' ? 'import' : src(); "
                   "self.data.family = mode() == 'version' ? df.family(forms.data ?? [], src()) : code(); self.data; %>"},
        {"name": "publishForm", "baseUrlType": "app", "httpMethod": "PATCH", "authType": "sso", "failOnStatusCodes": FAIL,
         "url": "<% 'dynForms/' + (df.fRow(forms.data ?? [], src()).id ?? 'none') %>", "exclude": "<% mode() != 'publish' %>",
         "onSend": "<% self.data = {:}; self.data.status = 'Published'; self.data.family = df.family(forms.data ?? [], src()); self.data; %>"},
        {"name": "policyForm", "baseUrlType": "app", "httpMethod": "PATCH", "authType": "sso", "failOnStatusCodes": FAIL,
         "url": "<% 'dynForms/' + (df.fRow(forms.data ?? [], src()).id ?? 'none') %>", "exclude": "<% mode() != 'policy' %>",
         "onSend": "<% self.data = {:}; self.data.noFormPolicy = empty(noFormInstanceList.getValue()) ? '' : ('' + noFormInstanceList.getValue()[0]).replace('Nf', '').replace('Fail', ''); self.data.failPolicy = empty(failInstanceList.getValue()) ? '' : ('' + failInstanceList.getValue()[0]).replace('Nf', '').replace('Fail', ''); self.data.alsoAssign = (alsoAssignText.getValue() ?? '').replace(' ', '').replace('\\'', '').replace('\"', ''); self.data; %>"},
        {"name": "postQuestions1", "baseUrlType": "app", "url": "dynQuestions?bulk=true", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
         "exclude": "<% mode() == 'publish' || mode() == 'policy' || plan().rows.size() == 0 %>",
         "onSend": "<% var rows = plan().rows; self.data = {:}; self.data.data = rows.size() > 100 ? rows.subList(0, 100) : rows; self.data; %>"},
        {"name": "postQuestions2", "baseUrlType": "app", "url": "dynQuestions?bulk=true", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
         "exclude": "<% mode() == 'publish' || mode() == 'policy' || plan().rows.size() <= 100 %>",
         "onSend": "<% var rows = plan().rows; self.data = {:}; self.data.data = rows.subList(100, rows.size() > 200 ? 200 : rows.size()); self.data; %>"}]},
    "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Copy, version or publish a form"},
                     "cancelOverride": {"taskId": "DynFormResults"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "copyFieldSet", "title": "What to do", "children": [
                             {"type": "instanceList", "id": "modeInstanceList", "label": "Action", "required": True, "onChange": "<% preview() %>",
                              "instanceList": [{"id": "copy", "descriptor": "Copy as a new form (version 1, Draft)"},
                                               {"id": "version", "descriptor": "New version of the same form (Draft)"},
                                               {"id": "add", "descriptor": "Add questions to another form"},
                                               {"id": "publish", "descriptor": "Publish this version"},
                                               {"id": "import", "descriptor": "Import a form from JSON (as Draft)"},
                                               {"id": "policy", "descriptor": "Set the gate policy for this form"}]},
                             {"type": "instanceList", "id": "sourceInstanceList", "label": "Form (copy from, or publish)", "values": FORM_OPTS, "onChange": "<% pickSource() %>"},
                             {"type": "text", "id": "newCodeText", "label": "New form code (copy or import)", "onChange": "<% preview() %>"},
                             {"type": "instanceList", "id": "targetInstanceList", "label": "Add to form", "values": FORM_OPTS, "onChange": "<% preview() %>"},
                             {"type": "instanceList", "id": "questionsInstanceList", "label": "Questions to add (none picked = all)", "multiSelect": True,
                              "values": "<% [] %>", "onChange": "<% preview() %>"},
                             {"type": "textArea", "id": "importTextArea", "label": "JSON to import", "onChange": "<% preview() %>"},
                             {"type": "instanceList", "id": "noFormInstanceList", "label": "Gate policy: form not filled", "instanceList": [{"id": "cancelNf", "descriptor": "Cancel the request"}, {"id": "sendbackNf", "descriptor": "Send it back to the requester"}, {"id": "passNf", "descriptor": "Let it pass"}], "onChange": "<% preview() %>"},
                             {"type": "instanceList", "id": "failInstanceList", "label": "Gate policy: check fails", "instanceList": [{"id": "cancelFail", "descriptor": "Cancel the request"}, {"id": "sendbackFail", "descriptor": "Send it back to the requester"}, {"id": "passFail", "descriptor": "Let it pass"}], "onChange": "<% preview() %>"},
                             {"type": "text", "id": "alsoAssignText", "label": "Gate policy: also assign these form families (comma separated, up to 2)", "onChange": "<% preview() %>"},
                             {"type": "readOnlyText", "id": "previewReadOnlyText", "label": "What will happen", "value": "<% 'Pick an action and a form.' %>"}]},
                         {"type": "fieldSet", "id": "exportFieldSet", "title": "Export", "collapsible": True, "initializeCollapsed": True, "children": [
                             {"type": "textArea", "id": "exportTextArea", "label": "This version as JSON (copy it into Import in another tenant)", "enabled": False, "value": "<% '' %>"}]}]}}}
write(os.path.join(PRES, 'DynFormCopy.pmd'), copy_page)


# ---- Bulk volume (acceptance item 9, 2026-11-19): start time-off requests from a page ----
# The CI token works for App Hub but not this tenant's REST gateway, so the requests start from the app itself:
# deferred POST endpoints to absenceManagement, 10 per click (a page request has 60 s), then the form assignments
# FormAssign creates are counted (every new Dyn Response after the starting count), and Clean up cancels the events
# and closes those assignments.
_BULK_DATES = []
_d = datetime.date(2027, 1, 4)
while len(_BULK_DATES) < 50:
    if _d.weekday() < 5:
        _BULK_DATES.append(_d.isoformat())
    _d += datetime.timedelta(days=1)
BULK_SCRIPT = ("<%\n"
    "  var days = function() { [" + ", ".join("'%s'" % d for d in _BULK_DATES) + "]; };\n"
    "  var total = function() { countAll.invoke({'lim': '1'}).total ?? 0; };\n"
    "  var names = function() { ('' + (workerText.getValue() ?? '')).split(',').map(x => { x.trim() }).filter(x => { !empty(x) }); };\n"
    "  var started = function() { ('' + (idsText.getValue() ?? '')).split(',').filter(x => { !empty(x) }).size(); };\n"
    "  var useWorker = function(n) {\n"
    "    var all = names();\n"
    "    if (n >= all.size()) { return false; }\n"
    "    var ws = workerFind.invoke({'q': all.get(n).urlEncode()}).data ?? [];\n"
    "    if (ws.size() == 0) { return false; }\n"
    "    var ts = typesFind.invoke({'w': ws.get(0).id}).data ?? [];\n"
    "    var vac = ts.filter(t => { ('' + (t.descriptor ?? '')).contains('Vacation') });\n"
    "    widText.setValue(ws.get(0).id);\n"
    "    typeText.setValue(vac.size() > 0 ? vac.get(0).id : (ts.size() > 0 ? ts.get(0).id : ''));\n"
    "    workerIdxText.setValue('' + n);\n"
    "    doneText.setValue('0');\n"
    "    true;\n"
    "  };\n"
    "  var startBatch = function() {\n"
    "    if (empty(beforeText.getValue())) { beforeText.setValue('' + total()); }\n"
    "    if (empty(widText.getValue()) && !useWorker(0)) { statusText.setValue('No worker found.'); return false; }\n"
    "    var ok = 0; var bad = ''; var ids = '' + (idsText.getValue() ?? ''); var tries = 0;\n"
    "    while (ok < 10 && started() + ok < 50 && tries < 20) {\n"
    "      tries = tries + 1;\n"
    "      var d = ('' + (doneText.getValue() ?? '0')).toInt();\n"
    "      if (d >= 50) { if (!useWorker(('' + workerIdxText.getValue()).toInt() + 1)) { break; } d = 0; }\n"
    "      dayText.setValue(days().get(d));\n"
    "      tagText.setValue('TEST:DYN:BULK ' + (started() + ok + 1));\n"
    "      var r = startOne.invoke({'w': widText.getValue()});\n"
    "      doneText.setValue(('' + (d + 1)).substringBefore('.'));\n"
    "      var ev = ((r.businessProcessParameters ?? {:}).overallBusinessProcess ?? {:}).id ?? '';\n"
    "      if (!empty(ev)) { ok = ok + 1; ids = ids + ev + ','; idsText.setValue(ids); }\n"
    "      else {\n"
    "        bad = ('' + json:stringify(r)).substring(0, 200);\n"
    "        if (bad.contains('A1015')) { if (!useWorker(('' + workerIdxText.getValue()).toInt() + 1)) { break; } }\n"
    "      }\n"
    "    }\n"
    "    statusText.setValue('Started ' + started() + ' of 50 (this click: ' + ok + '; worker ' + (names().size() > ('' + workerIdxText.getValue()).toInt() ? names().get(('' + workerIdxText.getValue()).toInt()) : 'none left') + ')' + (empty(bad) ? '' : '. Last refusal: ' + bad));\n"
    "    true;\n"
    "  };\n"
    "  var check = function() {\n"
    "    var before = ('' + (beforeText.getValue() ?? '0')).toInt();\n"
    "    var now = total();\n"
    "    checkText.setValue('New records since the start: ' + ('' + (now - before)).substringBefore('.') + ' for ' + started() + ' started events' + ((now - before) >= started() && started() > 0 ? '. Every event got an assignment (with alsoAssign set, expect 2 each).' : '.'));\n"
    "  };\n"
    "  var cleanUp = function() {\n"
    "    var all = ('' + (idsText.getValue() ?? '')).split(',').filter(x => { !empty(x) });\n"
    "    var from = ('' + (cleanedText.getValue() ?? '0')).toInt();\n"
    "    var c = 0; var k = 0;\n"
    "    for (var n = from; n < all.size() && n < from + 10; n = n + 1) {\n"
    "      var ev = all.get(n);\n"
    "      cancelOne.invoke({'ev': ev}); c = c + 1;\n"
    "      evText.setValue(ev);\n"
    "      var r = closeLaunch.invoke({'run': '1'});\n"
    "      k = k + (r.closed ?? 0);\n"
    "    }\n"
    "    cleanedText.setValue(('' + (from + c)).substringBefore('.'));\n"
    "    checkText.setValue('Clean up: ' + ('' + (from + c)).substringBefore('.') + ' of ' + all.size() + ' events cancelled; this click closed ' + ('' + k).substringBefore('.') + ' assignments.' + (from + c < all.size() ? ' Click Clean up again.' : ''));\n"
    "  };\n"
    "%>")
WAPI = "workday-api"
bulk_page = {"id": "DynFormBulk", "securityDomains": DOM, "script": BULK_SCRIPT,
    "endPoints": [
        {"name": "workerFind", "baseUrlType": WAPI, "url": "<% 'common/v1/workers?limit=5&search=' + q %>", "authType": "sso", "deferred": True},
        {"name": "typesFind", "baseUrlType": WAPI, "url": "<% 'absenceManagement/v1/workers/' + w + '/eligibleAbsenceTypes?limit=100' %>", "authType": "sso", "deferred": True},
        {"name": "startOne", "baseUrlType": WAPI, "url": "<% 'absenceManagement/v1/workers/' + w + '/requestTimeOff' %>", "httpMethod": "POST", "authType": "sso", "deferred": True,
         "onSend": "<% self.data = {:}; self.data.days = [{'date': dayText.getValue() + 'T08:00:00.000Z', 'dailyQuantity': 8, 'comment': tagText.getValue(), 'timeOffType': {'id': typeText.getValue()}}]; self.data.businessProcessParameters = {'action': {'id': 'd9e4223e446c11de98360015c5e6daf6'}, 'comment': tagText.getValue()}; self.data; %>"},
        {"name": "countAll", "baseUrlType": "app", "url": "<% 'dynResponses?limit=' + lim %>", "authType": "sso", "deferred": True},
        {"name": "cancelOne", "baseUrlType": WAPI, "url": "<% 'businessProcess/v1/events/' + ev + '/cancel' %>", "httpMethod": "POST", "authType": "sso", "deferred": True,
         "onSend": "<% self.data = {:}; self.data.comment = 'TEST:DYN:BULK cleanup'; self.data; %>"},
        {"name": "closeLaunch", "baseUrlType": "orchestrate", "url": "<% '/DynClose/launch?run=' + run %>", "httpMethod": "POST", "authType": "sso", "deferred": True,
         "onSend": "<% self.data = {:}; self.data.ev = evText.getValue(); self.data; %>"}],
    "presentation": {"pageType": "EDIT", "standardEditButtonsHidden": True,
        "title": {"type": "title", "id": "pageTitle", "label": "Bulk test: start 50 time-off requests"},
        "body": {"type": "section", "id": "bodySection", "children": [
            {"type": "fieldSet", "id": "bulkFieldSet", "title": "Run", "children": [
                {"type": "richText", "id": "bulkHelpRichText", "value": "<span style=\"color:#374151;font-size:13px\">Starts one-day time-off requests for the worker on 50 weekdays in 2027, 10 per click (each request runs the process, so FormAssign creates its form assignments). Then Check counts the new assignments and Clean up cancels the requests and closes their assignments. Test data only.</span>"},
                {"type": "text", "id": "workerText", "label": "Workers (comma separated; the next is used when one runs out of balance)", "value": "<% 'Beth Liu, Carmen Cortes, Logan McNeil, Teresa Serrano, Kevin Lim, Maria Cardoza' %>"},
                {"type": "text", "id": "workerIdxText", "label": "Worker number", "enabled": False, "value": "<% '0' %>"},
                {"type": "readOnlyText", "id": "statusText", "label": "Status", "value": "<% 'Click Start 10 until 50 have started.' %>"},
                {"type": "readOnlyText", "id": "checkText", "label": "Check", "value": "<% '' %>"},
                {"type": "text", "id": "widText", "label": "Worker ID", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "typeText", "label": "Time off type ID", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "beforeText", "label": "Records before", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "doneText", "label": "Started so far", "enabled": False, "value": "<% '0' %>"},
                {"type": "text", "id": "dayText", "label": "Current date", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "tagText", "label": "Current comment", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "evText", "label": "Current event", "enabled": False, "value": "<% '' %>"},
                {"type": "text", "id": "cleanedText", "label": "Cleaned so far", "enabled": False, "value": "<% '0' %>"},
                {"type": "textArea", "id": "idsText", "label": "Started events", "enabled": False, "value": "<% queryParams.ids ?? '' %>"}]},
            {"type": "section", "id": "bulkButtonsSection", "horizontal": True, "children": [
                {"type": "section", "id": "startSection", "children": [{"type": "pageActionButton", "id": "startButton", "label": "Start 10", "onClick": "<% startBatch() %>"}]},
                {"type": "section", "id": "checkSection", "children": [{"type": "pageActionButton", "id": "checkButton", "label": "Check", "onClick": "<% check() %>"}]},
                {"type": "section", "id": "cleanSection", "children": [{"type": "pageActionButton", "id": "cleanButton", "label": "Clean up", "onClick": "<% cleanUp() %>"}]}]}]}}}
write(os.path.join(PRES, 'DynFormBulk.pmd'), bulk_page)

# ---- AMD tasks and the flows that bring OK back to the results ----
amd_path = glob.glob(os.path.join(PRES, '*.amd'))[0]
amd = json.load(open(amd_path, encoding='utf-8'))
have = {t["id"] for t in amd["tasks"]}
amd["tasks"] = [t for t in amd["tasks"] if t["id"] not in ("DynFormBigFlat", "DynDiagMe", "DynDiagAsg")]
have = {t["id"] for t in amd["tasks"]}
for pid in ["DynFormFill", "DynFormBigLoop", "DynFormSeed", "DynFormResults", "DynFormLookup", "DynFormCopy", "DynFormBulk", "DynMyForms", "DynMyFill"]:
    if pid not in have:
        amd["tasks"].append({"id": pid, "routingPattern": "/" + pid[0].lower() + pid[1:], "page": {"id": pid}})
for tid, route, pid in [("DynFormResultsRecord", "/dynFormResults/{taskObjectId}", "DynFormResults"),
                        ("DynFormNext", "/dynFormNext/{taskObjectId}", "DynFormNext")]:
    if tid not in have:
        amd["tasks"].append({"id": tid, "routingPattern": route, "page": {"id": pid}})
flows = [f for f in amd.get("flowDefinitions", []) if not f["id"].startswith("dynForm") and not f["id"].startswith("dynMy")]
for pid in ["DynFormFill", "DynFormBigLoop", "DynFormSeed", "DynFormLookup", "DynFormCopy"]:
    fid = "dynForm" + pid[7:] + "Flow"
    flows.append({"id": fid, "flowSteps": [
        {"id": fid + "Start", "taskId": pid, "startsFlow": True,
         "transitions": [{"order": "a", "value": fid + "End", "condition": "<% true %>"}]},
        {"id": fid + "End", "taskId": "DynFormResults", "endsFlow": True}]})
flows.append({"id": "dynMyFillFlow", "flowSteps": [
    {"id": "dynMyFillFlowStart", "taskId": "DynMyFill", "startsFlow": True,
     "transitions": [{"order": "a", "value": "dynMyFillFlowEnd", "condition": "<% true %>"}]},
    {"id": "dynMyFillFlowEnd", "taskId": "DynMyForms", "endsFlow": True}]})
amd["flowDefinitions"] = flows
write(amd_path, amd)
print('dynamic forms: small page %d slots; most slots under 98 KB: loop %d (%d bytes), spelled out %d (%d bytes)'
      % (SMALL_SLOTS, big["loop"][0], big["loop"][1], big["flat"][0], big["flat"][1]))
