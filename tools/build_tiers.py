#!/usr/bin/env python3
"""Tiered ownership for Dynamic Forms (plan "Dynamic Forms: tiered ownership plan", 2026-11-20): the model and pages
for phases 1 to 5, the onboarding kit, delivered features and access recommendations. Run after build_import.py,
before build_labels.py. Idempotent.

Model (business objects 9-16): Dyn Assign (a block attached to a process type by owner org + scope), Dyn Org Map
(nightly copy of the supervisory hierarchy: path, depth, department, company, tier, workers), Dyn Department
(organizations marked as departments), Dyn Settings (slot budgets, reach threshold, validity, recommendation
thresholds), Dyn Kit Item / Dyn Kit Task (every onboarding kit part, and one row per part per new hire), Dyn Package
(delivered features switched on in this tenant), Dyn Access Snapshot (counts only: peers in an org and job profile
holding a kit access item). Domains 4-8 are the plan's: Restricted answers, Author, Govern, Integration, Fulfil.

Pages:
  FormGovern       VIEW  governance console: blocks by tier and budget, settings, the tools below
  FormAssignments  EDIT  block assignments: owner org, scope, process, gate, order; reach preview; team scope rule
  FormDepartments  EDIT  organizations marked as departments
  FormOrgMap       EDIT  rebuild the org map from Workday (path, department, tier, workers)
  FormSettings     EDIT  Forms settings
  FormPublish      EDIT  publish and approve one block version (?form=CODE): budget, reach, classes, diff
  FormReadiness    VIEW  setup and readiness per process type and definition
  FormLibrary      VIEW  question library by key
  FormOwnerDash    VIEW  owner dashboard: blocks, reach then and now, answers, reuse
  FormMyAnswers    EDIT  a worker's reusable answers: change by clearing
  FormPurge        EDIT  retention purge by classification (launches AnswerPurge)
  KitDesigner      EDIT  kit items (copy-on-edit for delivered ones)
  KitPrepare       EDIT  manager's prepare task (?event=)
  KitWelcome       VIEW  the new hire's welcome page
  KitGuide         EDIT  learning guide (tick steps off)
  KitQueue         EDIT  fulfilment queue by group
  KitPackages      EDIT  delivered features: enable, install, compare
  KitPeers         EDIT  access snapshot (counts only) and over-provisioning list
"""
import glob, json, os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
APP = os.path.join(ROOT, 'app')
PRES = os.path.join(APP, 'presentation')
MODEL = os.path.join(APP, 'model')
ORCH = os.path.join(APP, 'orchestration')
DOM = ["UseDynamicForms"]
FILL = ["DynFill"]
FAIL = [{"code": 400}, {"code": 403}]
REF = json.load(open(os.path.join(APP, 'appManifest.json'), encoding='utf-8'))["referenceId"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkcol import link_col


def write(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=None if compact else 2, ensure_ascii=False, separators=(',', ':') if compact else None) + '\n')


def field(i, name, label, ftype, **kw):
    f = {"id": i, "name": name, "label": label, "type": ftype}
    f.update(kw)
    return f


def bo(i, name, label, coll, fields, doms):
    return {"id": i, "name": name, "label": label, "defaultSecurityDomains": doms,
            "defaultCollection": {"name": coll, "label": "All " + label + "s"}, "fields": fields}


def X(e):
    return "<% " + e + " %>"


# ---------------------------------------------------------------- domains
for i, n, l in ((4, "DynRestricted", "Dyn Forms Responses Restricted"), (5, "DynAuthor", "Dyn Forms Author"),
                (6, "DynGovern", "Dyn Forms Govern"), (7, "DynIntegration", "Dyn Forms Integration"),
                (8, "DynFulfil", "Dyn Forms Onboarding Fulfil")):
    write(os.path.join(MODEL, n + '.securitydomain'), {"id": i, "name": n, "label": l, "enabledForPageSecurity": True,
                                                        "enabledForOrchestrationSecurity": n in ("DynGovern", "DynAuthor")})

# ---------------------------------------------------------------- business objects
# Each also lists Use: Dynamic Forms, so the tenant's current forms admins and the app's ISU keep working until the new
# domains get their policies (Restricted answers are the exception: their domain only).
AUTH = DOM + ["DynAuthor"]
GOV = DOM + ["DynGovern"]
write(os.path.join(MODEL, 'DynAssign.businessobject'), bo(9, "DynAssign", "Dyn Assign", "dynAssigns", [
    field(1, "ref", "Reference", "TEXT", useForDisplay=True),
    field(2, "family", "Block Family", "TEXT", enableIndex=True),
    field(3, "processType", "Process Type", "TEXT", enableIndex=True),
    field(4, "ownerOrg", "Owner Organization", "SINGLE_INSTANCE", target="SUPERVISORY_ORGANIZATION"),
    field(5, "ownerWid", "Owner Organization ID", "TEXT"),
    field(6, "scope", "Scope", "TEXT"),
    field(7, "gateOn", "Gate On", "BOOLEAN"),
    field(8, "sectionOrder", "Section Order", "INTEGER"),
    field(9, "tier", "Tier", "TEXT"),
    field(10, "active", "Active", "BOOLEAN"),
    field(11, "origin", "Origin", "TEXT"),
    field(12, "overrides", "Overrides", "TEXT"),
    field(13, "reach", "Reach", "INTEGER")], AUTH))
write(os.path.join(MODEL, 'DynOrgMap.businessobject'), bo(10, "DynOrgMap", "Dyn Org Map", "dynOrgMaps", [
    field(1, "name", "Name", "TEXT", useForDisplay=True),
    field(2, "orgWid", "Organization ID", "TEXT", enableIndex=True),
    field(3, "org", "Organization", "SINGLE_INSTANCE", target="SUPERVISORY_ORGANIZATION"),
    field(4, "parentWid", "Parent ID", "TEXT"),
    field(5, "deptWid", "Department ID", "TEXT"),
    field(6, "deptName", "Department", "TEXT"),
    field(7, "companyName", "Company", "TEXT"),
    field(8, "depth", "Depth", "INTEGER"),
    field(9, "path", "Path", "TEXT"),
    field(10, "active", "Active", "BOOLEAN"),
    field(11, "tier", "Tier", "TEXT"),
    field(12, "workerCount", "Workers", "INTEGER"),
    field(13, "refreshedOn", "Refreshed On", "DATE", precision="DAY")], GOV))
write(os.path.join(MODEL, 'DynDept.businessobject'), bo(11, "DynDept", "Dyn Department", "dynDepts", [
    field(1, "name", "Name", "TEXT", useForDisplay=True),
    field(2, "org", "Organization", "SINGLE_INSTANCE", target="SUPERVISORY_ORGANIZATION"),
    field(3, "orgWid", "Organization ID", "TEXT", enableIndex=True),
    field(4, "designatedBy", "Designated By", "TEXT"),
    field(5, "effectiveDate", "Effective Date", "DATE", precision="DAY"),
    field(6, "active", "Active", "BOOLEAN")], GOV))
write(os.path.join(MODEL, 'DynSettings.businessobject'), bo(12, "DynSettings", "Dyn Settings", "dynSettings", [
    field(1, "settingKey", "Key", "TEXT", useForDisplay=True),
    field(2, "budgetEnterprise", "Enterprise Slots", "INTEGER"),
    field(3, "budgetDepartment", "Department Slots", "INTEGER"),
    field(4, "budgetTeam", "Team Slots", "INTEGER"),
    field(5, "reachThreshold", "Reach Threshold", "INTEGER"),
    field(6, "defaultValidMonths", "Default Validity Months", "INTEGER"),
    field(7, "recommendPct", "Recommend at Percent", "INTEGER"),
    field(8, "commonPct", "Common at Percent", "INTEGER"),
    field(9, "minPeers", "Minimum Peers", "INTEGER"),
    field(10, "retainGeneral", "Keep General Answers Months", "INTEGER"),
    field(11, "retainConfidential", "Keep Confidential Answers Months", "INTEGER"),
    field(12, "retainRestricted", "Keep Restricted Answers Months", "INTEGER"),
    field(13, "welcomeDaysBefore", "Welcome Days Before Start", "INTEGER")], GOV))
write(os.path.join(MODEL, 'DynKitItem.businessobject'), bo(13, "DynKitItem", "Dyn Kit Item", "dynKitItems", [
    field(1, "code", "Code", "TEXT", useForDisplay=True, enableIndex=True),
    field(2, "itemType", "Item Type", "TEXT"),
    field(3, "ownerOrg", "Owner Organization", "SINGLE_INSTANCE", target="SUPERVISORY_ORGANIZATION"),
    field(4, "ownerWid", "Owner Organization ID", "TEXT"),
    field(5, "scope", "Scope", "TEXT"),
    field(6, "tier", "Tier", "TEXT"),
    field(7, "title", "Title", "TEXT"),
    field(8, "body", "Body", "TEXT"),
    field(9, "dueOffset", "Due Offset Days", "INTEGER"),
    field(10, "fulfillerGroup", "Fulfiller Group", "TEXT"),
    field(11, "sensitivity", "Sensitivity", "TEXT"),
    field(12, "link", "Link", "TEXT"),
    field(13, "version", "Version", "INTEGER"),
    field(14, "status", "Status", "TEXT"),
    field(15, "origin", "Origin", "TEXT"),
    field(16, "overrides", "Overrides", "TEXT"),
    field(17, "packageCode", "Package", "TEXT"),
    field(18, "processType", "Process Type", "TEXT", enableIndex=True),
    field(19, "approvedBy", "Approved By", "TEXT"),
    field(20, "active", "Active", "BOOLEAN")], AUTH))
write(os.path.join(MODEL, 'DynKitTask.businessobject'), bo(14, "DynKitTask", "Dyn Kit Task", "dynKitTasks", [
    field(1, "key", "Key", "TEXT", useForDisplay=True, enableIndex=True),
    field(2, "taskType", "Task Type", "TEXT"),
    field(3, "newHire", "New Hire", "SINGLE_INSTANCE", target="WORKER"),
    field(4, "hireWid", "New Hire ID", "TEXT", enableIndex=True),
    field(5, "hirePerson", "New Hire Person", "TEXT"),
    field(6, "itemCode", "Kit Item", "TEXT"),
    field(7, "title", "Title", "TEXT"),
    field(8, "managerNote", "Manager Note", "TEXT"),
    field(9, "status", "Status", "TEXT"),
    field(10, "requestedBy", "Requested By", "TEXT"),
    field(11, "approvedBy", "Approved By", "TEXT"),
    field(12, "doneBy", "Done By", "TEXT"),
    field(13, "dueOffset", "Due Offset Days", "INTEGER"),
    field(14, "doneOn", "Done On", "DATE", precision="DAY"),
    field(15, "reason", "Reason", "TEXT"),
    field(16, "fulfillerGroup", "Fulfiller Group", "TEXT", enableIndex=True),
    field(17, "bpEvent", "Business Process Event", "TEXT", enableIndex=True),
    field(18, "source", "Source", "TEXT"),
    field(19, "sensitivity", "Sensitivity", "TEXT"),
    field(20, "tier", "Tier", "TEXT"),
    field(21, "orgWid", "Organization ID", "TEXT"),
    field(22, "jobProfile", "Job Profile", "TEXT")], DOM + ["DynFulfil"]))
write(os.path.join(MODEL, 'DynPackage.businessobject'), bo(15, "DynPackage", "Dyn Package", "dynPackages", [
    field(1, "code", "Code", "TEXT", useForDisplay=True),
    field(2, "name", "Name", "TEXT"),
    field(3, "jurisdiction", "Jurisdiction", "TEXT"),
    field(4, "deliveredVersion", "Delivered Version", "INTEGER"),
    field(5, "enabled", "Enabled", "BOOLEAN"),
    field(6, "enabledBy", "Enabled By", "TEXT"),
    field(7, "enabledOn", "Enabled On", "DATE", precision="DAY"),
    field(8, "readiness", "Readiness", "TEXT")], GOV))
write(os.path.join(MODEL, 'DynAccessSnap.businessobject'), bo(16, "DynAccessSnap", "Dyn Access Snapshot", "dynAccessSnaps", [
    field(1, "snapKey", "Key", "TEXT", useForDisplay=True),
    field(2, "orgWid", "Organization ID", "TEXT", enableIndex=True),
    field(3, "jobProfile", "Job Profile", "TEXT"),
    field(4, "itemCode", "Kit Item", "TEXT"),
    field(5, "holding", "Peers Holding", "INTEGER"),
    field(6, "peers", "Peers", "INTEGER"),
    field(7, "peerRule", "Peer Rule", "TEXT"),
    field(8, "asOf", "As Of", "DATE", precision="DAY")], DOM + ["DynFulfil", "DynGovern"]))

# ---------------------------------------------------------------- delivered packages (generic, jurisdiction-tagged)
REVIEW = " Your HR or legal team must review this text before use."
PACKAGES = [
    {"code": "PKG:JOINER", "name": "Onboarding kit (joiner)", "jurisdiction": "CA", "version": 1, "process": "Onboarding", "items": [
        ("W-HEAD", "welcome", "Welcome to the organization", "We are glad you are joining us. Your first day starts at 9:00; your manager will meet you." + REVIEW, 0, "", "standard", ""),
        ("L-CONDUCT", "learning", "Read the code of conduct", "Read and acknowledge the code of conduct." + REVIEW, 7, "", "standard", ""),
        ("L-PRIVACY", "learning", "Complete privacy training", "Complete the privacy and information security course.", 30, "", "standard", ""),
        ("L-SAFETY", "learning", "Complete workplace safety orientation", "Workplace safety orientation for your location.", 30, "", "standard", ""),
        ("A-LAPTOP", "access", "Laptop", "A standard laptop, ready on the first day.", -3, "IT", "standard", ""),
        ("A-EMAIL", "access", "Email account", "Work email account.", -3, "IT", "standard", ""),
        ("A-VPN", "access", "VPN access", "Remote access (VPN).", -1, "IT", "standard", ""),
        ("A-WORKDAY", "access", "Workday access", "Employee self-service in Workday (requested through Workday's own role assignment).", 0, "Workday security", "standard", "")]},
    {"code": "PKG:MOVER", "name": "Internal move kit (mover)", "jurisdiction": "CA", "version": 1, "process": "ChangeJob", "items": [
        ("W-MOVE", "welcome", "Welcome to your new team", "Your new manager will share the team's first steps." + REVIEW, 0, "", "standard", ""),
        ("L-HANDOVER", "learning", "Hand over your previous work", "List open work and hand it over to your previous manager.", 7, "", "standard", "")]},
    {"code": "PKG:LEAVER", "name": "Offboarding kit (leaver)", "jurisdiction": "CA", "version": 1, "process": "Termination", "items": [
        ("L-RETURN", "learning", "Return equipment", "Return your laptop, badge and any other equipment.", 0, "", "standard", ""),
        ("A-REMOVE", "access", "Remove system access", "Remove access to every system on the last day.", 0, "IT", "standard", "")]},
]
PKG_JSON = json.dumps([{"code": p["code"], "name": p["name"], "jurisdiction": p["jurisdiction"], "version": p["version"],
                        "process": p["process"],
                        "items": [{"code": p["code"].replace("PKG:", "") + ":" + c, "itemType": t, "title": ti, "body": b, "dueOffset": d,
                                   "fulfillerGroup": g, "sensitivity": s} for c, t, ti, b, d, g, s, _ in p["items"]]}
                       for p in PACKAGES], separators=(',', ':'))

# ---------------------------------------------------------------- tier.script (pure functions, helpers first)
PROCESSES = [("TimeOff", "Request Time Off"), ("ChangeJob", "Change Job"), ("Onboarding", "Onboarding"),
             ("Termination", "Termination"), ("Leave", "Request Leave of Absence"), ("Campaign", "Extend campaign (yearly)")]
PROC_NAMES = ", ".join("'%s': '%s'" % p for p in PROCESSES)
SCRIPT = r'''
var cnt = function(sortedList, key) {
  var i = sortedList.indexOf(key);
  i < 0 ? 0 : sortedList.lastIndexOf(key) - i + 1;
};

var first = function(d) {
  (d ?? []).size() > 0 ? d[0] : {:};
};

var procName = function(code) {
  var m = { PROC_NAMES };
  m.containsKey(code ?? '') ? m.get(code) : ('' + (code ?? ''));
};

var procList = function() {
  var out = [];
  var m = { PROC_NAMES };
  for (var k : m.keys()) { out.add({ 'id': k, 'descriptor': m.get(k) }); }
  out;
};

// the org map, built from Workday's supervisory organizations, the departments marked here and the active workers:
// path "|top|...|org|", depth, department (the nearest marked organization at or above), company (the top
// organization), tier (Enterprise = no superior, Department = marked, Team = the rest), workers in the org
var orgRows = function(orgs, depts, workers) {
  var ids = (orgs ?? []).map(o => { '' + (o.workdayID ?? '') });
  var pars = (orgs ?? []).map(o => { empty(o.superiorOrganization) ? '' : ('' + (o.superiorOrganization.id ?? '')) });
  var names = (orgs ?? []).map(o => { '' + (o.name ?? '') });
  var dset = '|' + (depts ?? []).filter(d => { d.active != false }).map(d => { '' + (d.orgWid ?? '') }).join('|') + '|';
  var wk = (workers ?? []).map(w => { empty(w.supervisoryOrganization) ? '' : ('' + (w.supervisoryOrganization.id ?? '')) }).sort();
  var today = date:now().format('yyyy-MM-dd');
  var out = [];
  var n = 0;
  for (var o : orgs ?? []) {
    var self1 = ids.get(n);
    var chain = [self1];
    var cur = pars.get(n);
    for (var g : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]) {
      if (!empty(cur) && ids.indexOf(cur) >= 0 && !chain.contains(cur)) { chain.add(cur); cur = pars.get(ids.indexOf(cur)); }
    }
    var path = '|';
    var dw = '';
    for (var c : chain) {
      path = '|' + c + path;
      if (empty(dw) && dset.contains('|' + c + '|')) { dw = c; }
    }
    var top = chain.get(chain.size() - 1);
    var isTop = empty(pars.get(n)) || ids.indexOf(pars.get(n)) < 0;
    var m = {:};
    m.put('orgWid', self1);
    m.put('name', names.get(n));
    m.put('org', { 'id': self1 });
    m.put('parentWid', pars.get(n));
    m.put('depth', chain.size());
    m.put('path', path);
    m.put('deptWid', dw);
    m.put('deptName', empty(dw) ? '' : names.get(ids.indexOf(dw)));
    m.put('companyName', names.get(ids.indexOf(top)));
    m.put('tier', isTop ? 'Enterprise' : (dset.contains('|' + self1 + '|') ? 'Department' : 'Team'));
    m.put('active', o.inactive != true);
    m.put('workerCount', cnt(wk, self1));
    m.put('refreshedOn', today);
    out.add(m);
    n = n + 1;
  }
  out;
};

// rows to create and rows to update (existing org map rows keyed by orgWid), in chunks of 100 for the bulk API
var mapPart = function(rows, existing, wantNew, part) {
  var ex = (existing ?? []).map(e => { '' + (e.orgWid ?? '') });
  var sel = [];
  for (var r : rows ?? []) {
    var at = ex.indexOf(r.orgWid);
    if (wantNew && at < 0) { sel.add(r); }
    if (!wantNew && at >= 0) { var m = {:}; m.addAll(r); m.remove('org'); m.put('id', existing.get(at).id); sel.add(m); }
  }
  var lo = part * 100;
  var hi = lo + 100 > sel.size() ? sel.size() : lo + 100;
  lo < sel.size() ? sel.subList(lo, hi) : [];
};

var mapOf = function(map, wid) {
  var hit = {:};
  for (var r : map ?? []) { if (('' + (r.orgWid ?? '')) == ('' + (wid ?? ''))) { hit = r; } }
  hit;
};

var tierOf = function(map, wid) {
  mapOf(map, wid).tier ?? '';
};

var covered = function(map, owner, scope) {
  (map ?? []).filter(r => { r.active != false && (scope == 'subs' ? ('' + (r.path ?? '')).contains('|' + owner + '|') : ('' + (r.orgWid ?? '')) == owner) });
};

var reachText = function(map, owner, scope) {
  var c = covered(map, owner ?? '', scope ?? 'org');
  var w = 0;
  for (var r : c) { w = w + (r.workerCount ?? 0); }
  empty(owner) ? 'Pick an owner organization' : ('' + c.size() + ' orgs, ' + w + ' workers');
};

var reachWorkers = function(map, owner, scope) {
  var w = 0;
  for (var r : covered(map, owner, scope ?? 'org')) { w = w + (r.workerCount ?? 0); }
  w;
};

var deptCount = function(map, owner, scope) {
  covered(map, owner, scope ?? 'org').map(r => { '' + (r.deptWid ?? '') }).filter(x => { !empty(x) }).distinct().size();
};

// rule 2: a team block's scope must stay inside one department
var scopeErr = function(map, owner, scope) {
  var t = tierOf(map, owner);
  (t == 'Team' && scope == 'subs' && deptCount(map, owner, scope) > 1) ? 'A team block can only reach orgs in one department: this scope reaches ' + deptCount(map, owner, scope) + '.' : '';
};

var orgPick = function(map) {
  (map ?? []).filter(r => { r.active != false }).map(r => { { 'id': r.orgWid, 'descriptor': (r.name ?? '') + ' (' + (r.tier ?? '') + ')' } });
};

var orgSel = function(map, wid) {
  empty(wid) ? [] : [{ 'id': wid, 'descriptor': (mapOf(map, wid).name ?? wid) + ' (' + (mapOf(map, wid).tier ?? '') + ')' }];
};

var setting = function(s, f, dflt) {
  var v = first(s).get(f);
  v == null ? dflt : v;
};

var budget = function(s, tier) {
  tier == 'Enterprise' ? setting(s, 'budgetEnterprise', 12) : (tier == 'Department' ? setting(s, 'budgetDepartment', 10) : setting(s, 'budgetTeam', 8));
};

// slots a block takes on the fill page: one per question, a repeating group takes its rows (max, default 3) times
// its children; structural rows (subform, nextform) take none
var slots = function(qs) {
  var n = 0;
  for (var x : qs ?? []) {
    var t = '' + (x.qType ?? '');
    if (t != 'subform' && t != 'nextform' && t != 'repeat') { n = n + 1; }
  }
  n;
};

var clsOf = function(x) {
  var c = ('' + (x.classification ?? '')).lowerCase();
  c == 'confidential' ? 'Confidential' : (c == 'restricted' ? 'Restricted' : (x.confidential == true ? 'Confidential' : 'General'));
};

var classCount = function(qs, c) {
  (qs ?? []).filter(x => { clsOf(x) == c }).size();
};

var keysOf = function(qs) {
  '|' + (qs ?? []).map(x => { '' + (x.qKey ?? '') }).join('|') + '|';
};

var sig = function(x) {
  (x.qType ?? '') + '/' + (x.qLabel ?? '') + '/' + (x.classification ?? '') + '/' + (x.required ?? false) + '/' + (x.reusable ?? false);
};

var diff = function(oldQs, newQs) {
  var ok = keysOf(oldQs);
  var nk = keysOf(newQs);
  var added = (newQs ?? []).filter(x => { !ok.contains('|' + (x.qKey ?? '') + '|') }).map(x => { x.qKey ?? '' });
  var removed = (oldQs ?? []).filter(x => { !nk.contains('|' + (x.qKey ?? '') + '|') }).map(x => { x.qKey ?? '' });
  var changed = [];
  for (var x : newQs ?? []) {
    for (var y : oldQs ?? []) {
      if ((x.qKey ?? '') == (y.qKey ?? '') && sig(x) != sig(y)) { changed.add(x.qKey ?? ''); }
    }
  }
  (oldQs ?? []).size() == 0 ? 'First version: ' + (newQs ?? []).size() + ' questions.' :
    ('Added: ' + (added.size() == 0 ? 'none' : added.join(', ')) + '. Removed: ' + (removed.size() == 0 ? 'none' : removed.join(', ')) +
     '. Changed: ' + (changed.size() == 0 ? 'none' : changed.distinct().join(', ')) + '.');
};

var published = function(fams) {
  var hit = {:};
  for (var f : fams ?? []) { if ((f.status ?? '') == 'Published' && (empty(hit.version) || (f.version ?? 0) > hit.version)) { hit = f; } }
  hit;
};

var blockTier = function(map, form, asgs) {
  var t = empty(form.ownerOrg) ? '' : tierOf(map, form.ownerOrg.id);
  !empty(t) ? t : (first(asgs).tier ?? (form.tier ?? 'Team'));
};

var reachAll = function(map, asgs) {
  var w = 0;
  for (var a : asgs ?? []) { if (a.active != false) { w = w + reachWorkers(map, a.ownerWid, a.scope); } }
  w;
};

var publishErr = function(map, s, form, qs, asgs, gov, reason) {
  var t = blockTier(map, form, asgs);
  var b = budget(s, t);
  var n = slots(qs);
  var r = reachAll(map, asgs);
  var se = '';
  for (var a : asgs ?? []) { if (empty(se)) { se = scopeErr(map, a.ownerWid, a.scope); } }
  n > b ? 'This ' + t + ' block takes ' + n + ' slots; the ' + t + ' budget is ' + b + '. Remove questions or ask governance for more.' :
  ((t == 'Enterprise' || classCount(qs, 'Restricted') > 0) && gov != true ? 'Enterprise blocks and Restricted questions need governance approval: tick Governance approval.' :
  ((t == 'Department' && r > setting(s, 'reachThreshold', 250) && gov != true) ? 'This block reaches ' + r + ' workers, over the ' + setting(s, 'reachThreshold', 250) + ' threshold: governance must approve.' :
  (((classCount(qs, 'Confidential') + classCount(qs, 'Restricted')) > 0 && empty(reason)) ? 'Say why the protected questions are needed (privacy reason).' : se)));
};

var summary = function(map, s, form, qs, asgs) {
  var t = blockTier(map, form, asgs);
  t + ' block: ' + slots(qs) + ' of ' + budget(s, t) + ' ' + t.lowerCase() + ' slots. Reach: ' + reachAll(map, asgs) + ' workers through ' +
    (asgs ?? []).size() + ' assignment(s). Questions: ' + classCount(qs, 'General') + ' general, ' + classCount(qs, 'Confidential') +
    ' confidential, ' + classCount(qs, 'Restricted') + ' restricted; ' + (qs ?? []).filter(x => { x.reusable == true }).size() + ' reusable.';
};

// readiness: one row per definition of every process type the app supports
var readyRows = function(defs) {
  var out = [];
  var m = { PROC_NAMES };
  for (var d : defs ?? []) {
    var tn = empty(d.businessProcessType) ? '' : ('' + (d.businessProcessType.descriptor ?? ''));
    var code = '';
    for (var k : m.keys()) { if (m.get(k) == tn) { code = k; } }
    if (!empty(code)) {
      var steps = (d.businessProcessSteps ?? []).map(x => { '' + (x.descriptor ?? '') });
      var svc = steps.filter(x => { x.contains('Service') }).size();
      var appr = steps.filter(x => { x.contains('Approval') }).size();
      var todo = steps.filter(x => { x.contains('To Do') }).size();
      var level = svc >= 2 && appr > 0 && todo > 0 ? 'Gate + route' : (svc >= 2 ? 'Gate only' : (svc == 1 ? 'Form only' : 'Not supported'));
      var r = {:};
      r.put('process', tn);
      r.put('definition', empty(d.businessProcessDefinition) ? '' : ('' + (d.businessProcessDefinition.descriptor ?? '')));
      r.put('level', level);
      r.put('checks', 'Service steps ' + svc + ' (FormCompose, FormGate), approval steps ' + appr + ', To Do steps ' + todo + ' (route marker)');
      r.put('fix', level == 'Gate + route' ? 'Ready' : (svc < 2 ? 'Add Service steps for FormCompose (start) and FormGate (before completion)' : 'Add an approval step after the gate and the route marker To Do, then the routing condition'));
      out.add(r);
    }
  }
  out;
};

var mapChecks = function(map, depts, settings) {
  var out = [];
  var none = (map ?? []).filter(r => { r.active != false && empty(r.deptWid) && (r.tier ?? '') != 'Enterprise' }).size();
  out.add({ 'item': 'Org map', 'result': (map ?? []).size() > 0 ? 'Pass' : 'Fail', 'detail': '' + (map ?? []).size() + ' organizations', 'fix': (map ?? []).size() > 0 ? '' : 'Open Org map and click OK' });
  out.add({ 'item': 'Departments', 'result': (depts ?? []).size() > 0 ? 'Pass' : 'Fail', 'detail': '' + (depts ?? []).size() + ' marked', 'fix': (depts ?? []).size() > 0 ? '' : 'Mark departments, then rebuild the org map' });
  out.add({ 'item': 'Every worker resolves to one department', 'result': none == 0 ? 'Pass' : 'Fail', 'detail': '' + none + ' organizations below the top resolve to no department', 'fix': none == 0 ? '' : 'Mark the missing departments' });
  out.add({ 'item': 'Forms settings', 'result': (settings ?? []).size() > 0 ? 'Pass' : 'Fail', 'detail': (settings ?? []).size() > 0 ? 'Budgets ' + setting(settings, 'budgetEnterprise', 12) + ' / ' + setting(settings, 'budgetDepartment', 10) + ' / ' + setting(settings, 'budgetTeam', 8) : 'Defaults in use', 'fix': (settings ?? []).size() > 0 ? '' : 'Open Settings and click OK' });
  out.add({ 'item': 'Routing calculated fields (TEST DYN Comment Route HR, TEST DYN Event Route HR Comments) and rule TEST DYN Route HR', 'result': 'Check by hand', 'detail': 'Calculated fields can not ship in an app', 'fix': 'See docs/DYNAMIC-FORMS-SETUP.md' });
  out.add({ 'item': 'Integration user: View All on each process policy, Get on read domains', 'result': 'Check by hand', 'detail': 'Security can only be read by an administrator', 'fix': 'View Security Group for the ISU group' });
  out.add({ 'item': 'Disable Integration Subscriptions is off (after-completion path only)', 'result': 'Check by hand', 'detail': 'Edit Tenant Setup - Integrations', 'fix': '' });
  out;
};

var libRows = function(qs, forms) {
  var keys = (qs ?? []).filter(x => { !empty(x.libraryKey) }).map(x => { '' + x.libraryKey }).distinct().sort();
  var out = [];
  for (var k : keys) {
    var hits = (qs ?? []).filter(x => { ('' + (x.libraryKey ?? '')) == k });
    var h = first(hits);
    out.add({ 'key': k, 'label': h.qLabel ?? '', 'cls': clsOf(h), 'reusable': h.reusable == true ? 'Yes, ' + (h.validMonths ?? 12) + ' months' : 'No',
              'blocks': hits.map(x => { x.formCode ?? '' }).distinct().join(', ') });
  }
  out;
};

var dashRows = function(forms, map, asgs, ans) {
  var codes = (ans ?? []).map(a => { '' + (a.formCode ?? '') }).sort();
  var reused = (ans ?? []).filter(a => { (a.source ?? '') == 'reused' }).map(a => { '' + (a.formCode ?? '') }).sort();
  var pre = (ans ?? []).filter(a => { (a.source ?? '') == 'prefill' }).map(a => { '' + (a.formCode ?? '') }).sort();
  var out = [];
  for (var f : (forms ?? []).filter(x => { (x.status ?? '') == 'Published' && (x.kind ?? '') != 'composed' })) {
    var fam = '' + (f.family ?? f.code ?? '');
    var mine = (asgs ?? []).filter(a => { ('' + (a.family ?? '')) == fam });
    var owner = empty(f.ownerOrg) ? '' : ('' + (f.ownerOrg.id ?? ''));
    var om = mapOf(map, owner);
    var now = reachAll(map, mine);
    var then = f.reachAtApproval ?? 0;
    out.add({ 'code': f.code ?? '', 'owner': empty(owner) ? '(none)' : (om.name ?? owner), 'tier': empty(om.tier) ? (f.tier ?? '') : om.tier,
              'status': (!empty(owner) && (empty(om.orgWid) || om.active == false)) ? 'Needs review: owner org inactive or moved' : (now != then && then > 0 ? 'Needs review: reach changed' : 'Active'),
              'reach': '' + then + ' at approval, ' + now + ' now', 'answers': '' + cnt(codes, '' + (f.code ?? '')), 'reused': '' + cnt(reused, '' + (f.code ?? '')), 'prefill': '' + cnt(pre, '' + (f.code ?? '')) });
  }
  out;
};

// my reusable answers still valid
var stillValid = function(a, today) {
  var v = ('' + (a.validUntil ?? '')).replace('-', '');
  v.length() >= 8 && v.substring(0, 8).toInt() >= today;
};

var myAnswers = function(ans) {
  var today = date:now().format('yyyyMMdd').toInt();
  (ans ?? []).filter(a => { stillValid(a, today) });
};

// ---- onboarding kit ----
var kitCovers = function(map, path, item) {
  item.active != false && ((item.scope ?? 'org') == 'subs' ? ('' + (path ?? '')).contains('|' + (item.ownerWid ?? '') + '|') : (empty(path) ? (item.tier ?? '') == 'Enterprise' : ('' + (path ?? '')).endsWith('|' + (item.ownerWid ?? '') + '|')));
};

var overridden = function(items, code) {
  (items ?? []).filter(x => { ('' + (x.overrides ?? '')) == code && (x.status ?? '') == 'Published' }).size() > 0;
};

var tierRank = function(t) {
  t == 'Enterprise' ? 1 : (t == 'Department' ? 2 : 3);
};

// the access list for one hire: every published access item that covers the hire's org (a customer copy replaces the
// delivered item it overrides), with the peers' counts when the snapshot has a group of at least minPeers
var accessRows = function(items, map, orgWid, snaps, s) {
  var path = mapOf(map, orgWid).path ?? '';
  var rec = setting(s, 'recommendPct', 80);
  var com = setting(s, 'commonPct', 50);
  var out = [];
  for (var it : list:sort((items ?? []).filter(x => { (x.itemType ?? '') == 'access' && (x.status ?? '') == 'Published' }), 'tier', true)) {
    if (kitCovers(map, path, it) && !overridden(items, '' + (it.code ?? ''))) {
      var hit = {:};
      for (var sn : snaps ?? []) { if (('' + (sn.itemCode ?? '')) == ('' + (it.code ?? ''))) { hit = sn; } }
      var peers = hit.peers ?? 0;
      var hold = hit.holding ?? 0;
      var pct = peers > 0 ? (hold * 100) / peers : 0;
      var elev = (it.sensitivity ?? '') == 'elevated';
      var label = peers < setting(s, 'minPeers', 3) ? '' : (elev ? 'Common, needs a reason and extra approval' : (pct >= rec ? 'Recommended: ' + hold + ' of ' + peers + ' peers have it' : (pct >= com ? 'Common in this team: ' + hold + ' of ' + peers : '')));
      var r = {:};
      r.put('code', it.code ?? '');
      r.put('title', it.title ?? '');
      r.put('group', (it.tier ?? '') == 'Enterprise' ? 'Baseline' : (it.tier ?? ''));
      r.put('fulfiller', it.fulfillerGroup ?? '');
      r.put('sensitivity', it.sensitivity ?? 'standard');
      r.put('rec', label);
      r.put('ticked', !elev && ((it.tier ?? '') == 'Enterprise' || (peers >= setting(s, 'minPeers', 3) && pct >= rec)));
      r.put('due', it.dueOffset ?? 0);
      out.add(r);
    }
  }
  out;
};

var kitByType = function(tasks, t) {
  (tasks ?? []).filter(x => { (x.taskType ?? '') == t });
};

var welcomeText = function(items, tasks, map) {
  var w = kitByType(tasks, 'welcome');
  var note = kitByType(tasks, 'prepare').map(x => { '' + (x.managerNote ?? '') }).filter(x => { !empty(x) });
  var parts = [];
  for (var t : list:sort(w, 'tier', true)) {
    for (var it : items ?? []) { if (('' + (it.code ?? '')) == ('' + (t.itemCode ?? ''))) { parts.add('<b>' + (it.title ?? '') + '</b><br>' + (it.body ?? '')); } }
  }
  if (note.size() > 0) { parts.add('<b>A note from your manager</b><br>' + note[0]); }
  parts.size() == 0 ? 'Your welcome is not ready yet.' : parts.join('<br><br>');
};

// peers: active workers in one org with one job profile (rule 1), else the org and the orgs below it with that job
// profile (rule 3); counts of each access item done for those peers in the kit history; only groups of minPeers or more
var peerRows = function(workers, done, map, s) {
  var minP = setting(s, 'minPeers', 3);
  var keys = (workers ?? []).map(w => { (empty(w.supervisoryOrganization) ? '' : ('' + w.supervisoryOrganization.id)) + '#' + (empty(w.jobProfile) ? '' : ('' + w.jobProfile.id)) }).distinct();
  var heldBy = (done ?? []).map(d => { ('' + (d.hireWid ?? '')) + '#' + ('' + (d.itemCode ?? '')) }).sort();
  var items = (done ?? []).map(d => { '' + (d.itemCode ?? '') }).distinct();
  var today = date:now().format('yyyy-MM-dd');
  var out = [];
  for (var k : keys) {
    var org = k.substringBefore('#');
    var jp = k.substringAfter('#');
    var peers = (workers ?? []).filter(w => { !empty(w.supervisoryOrganization) && ('' + w.supervisoryOrganization.id) == org && !empty(w.jobProfile) && ('' + w.jobProfile.id) == jp });
    var rule = 'org + job profile';
    if (peers.size() < minP) {
      var c = covered(map, org, 'subs').map(r => { '' + r.orgWid });
      peers = (workers ?? []).filter(w => { !empty(w.supervisoryOrganization) && c.contains('' + w.supervisoryOrganization.id) && !empty(w.jobProfile) && ('' + w.jobProfile.id) == jp });
      rule = 'org and below + job profile';
    }
    if (peers.size() >= minP) {
      for (var it : items) {
        var h = 0;
        for (var p : peers) { if (cnt(heldBy, ('' + (empty(p.worker) ? '' : p.worker.id)) + '#' + it) > 0) { h = h + 1; } }
        if (h > 0) { out.add({ 'snapKey': org + ':' + jp + ':' + it + ':' + today, 'orgWid': org, 'jobProfile': jp, 'itemCode': it, 'holding': h, 'peers': peers.size(), 'peerRule': rule, 'asOf': today }); }
      }
    }
  }
  out;
};

var overProv = function(rows) {
  (rows ?? []).filter(r => { (r.holding ?? 0) > 0 && (r.holding ?? 0) <= 2 && (r.peers ?? 0) >= 6 });
};

var chunk = function(rows, part) {
  var lo = part * 100;
  var hi = lo + 100 > (rows ?? []).size() ? (rows ?? []).size() : lo + 100;
  lo < (rows ?? []).size() ? rows.subList(lo, hi) : [];
};

var pkgs = function() {
  json:parse('PKG_JSON');
};

var pkgRows = function(installed, items) {
  var out = [];
  for (var p : pkgs()) {
    var rec = {:};
    for (var i : installed ?? []) { if (('' + (i.code ?? '')) == p.code) { rec = i; } }
    var have = (items ?? []).filter(x => { ('' + (x.packageCode ?? '')) == p.code && (x.origin ?? '') == 'Delivered' });
    var copies = (items ?? []).filter(x => { (x.origin ?? '') == 'Customer' && ('' + (x.overrides ?? '')).startsWith(p.code.replace('PKG:', '') + ':') });
    var older = have.filter(x => { (x.version ?? 1) < p.version }).size();
    out.add({ 'code': p.code, 'name': p.name, 'jurisdiction': p.jurisdiction, 'version': '' + p.version, 'enabled': rec.enabled == true,
              'id': rec.id ?? '', 'status': empty(rec.code) ? 'Not installed' : ('Installed: ' + have.size() + ' of ' + p.items.size() + ' items, ' + copies.size() + ' customer copies' + (older > 0 ? ', ' + older + ' older than the delivered version' : '')) });
  }
  out;
};

// the delivered items to install for the packages ticked on, skipping those already here
var pkgInstall = function(ticked, items, map) {
  var top = '';
  for (var r : map ?? []) { if ((r.tier ?? '') == 'Enterprise' && r.active != false) { top = '' + r.orgWid; } }
  var have = '|' + (items ?? []).map(x => { '' + (x.code ?? '') }).join('|') + '|';
  var out = [];
  for (var p : pkgs()) {
    if ((ticked ?? []).contains(p.code)) {
      for (var it : p.items) {
        if (!have.contains('|' + it.code + '|')) {
          var m = {:};
          m.addAll(it);
          m.put('ownerWid', top);
          if (!empty(top)) { m.put('ownerOrg', { 'id': top }); }
          m.put('scope', 'subs');
          m.put('tier', 'Enterprise');
          m.put('status', 'Published');
          m.put('origin', 'Delivered');
          m.put('packageCode', p.code);
          m.put('processType', p.process);
          m.put('version', p.version);
          m.put('active', true);
          out.add(m);
        }
      }
    }
  }
  out;
};

{
  "cnt": cnt, "first": first, "procName": procName, "procList": procList, "orgRows": orgRows, "mapPart": mapPart, "mapOf": mapOf,
  "tierOf": tierOf, "covered": covered, "reachText": reachText, "reachWorkers": reachWorkers, "deptCount": deptCount,
  "scopeErr": scopeErr, "orgPick": orgPick, "orgSel": orgSel, "setting": setting, "budget": budget, "slots": slots,
  "clsOf": clsOf, "classCount": classCount, "diff": diff, "published": published, "blockTier": blockTier, "reachAll": reachAll,
  "publishErr": publishErr, "summary": summary, "readyRows": readyRows, "mapChecks": mapChecks, "libRows": libRows,
  "dashRows": dashRows, "stillValid": stillValid, "myAnswers": myAnswers, "kitCovers": kitCovers, "overridden": overridden, "tierRank": tierRank,
  "accessRows": accessRows, "kitByType": kitByType, "welcomeText": welcomeText, "peerRows": peerRows, "overProv": overProv,
  "chunk": chunk, "pkgs": pkgs, "pkgRows": pkgRows, "pkgInstall": pkgInstall
}
'''
SCRIPT = SCRIPT.replace("PROC_NAMES", PROC_NAMES).replace("PKG_JSON", PKG_JSON.replace("\\", "\\\\").replace("'", "\\'"))
with open(os.path.join(PRES, 'scripts', 'tier.script'), 'w', encoding='utf-8') as f:
    f.write(SCRIPT.lstrip())


# ---------------------------------------------------------------- endpoints shared by the pages
def app_ep(name, url, auth="sso", exclude=None, fail=True):
    e = {"name": name, "baseUrlType": "app", "authType": auth, "url": url}
    if fail:
        e["failOnStatusCodes"] = FAIL
    if exclude:
        e["exclude"] = exclude
    return e


def wql(name, query, limit=10000):
    return {"name": name, "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
            "url": "<% 'data?limit=" + str(limit) + "&query=' + string:pathEncode('" + query + "') %>"}


def paged(name, coll, auth="sso", pages=3):
    """count + the newest pages of a collection (collections come back oldest first)"""
    eps = [app_ep(name + "Count", coll + "?limit=1", auth)]
    for n in range(pages):
        eps.append({"name": name + "P%d" % n, "baseUrlType": "app", "authType": auth,
                    "url": "<% let t = " + name + "Count.total ?? 0; let st = t - " + str(100 * (n + 1)) + "; '" + coll + "?limit=100&offset=' + (st < 0 ? 0 : st) %>",
                    "exclude": "<% (" + name + "Count.total ?? 0) - " + str(100 * n) + " <= 0 %>"})
    return eps


def all_of(name, pages=3):
    return "list:flatten([" + ", ".join("%sP%d.data ?? []" % (name, n) for n in range(pages)) + "])"


MAP_EPS = paged("map", "dynOrgMaps")
MAP = all_of("map")
SET_EP = app_ep("settings", "dynSettings?limit=1")
ASG_EPS = paged("asg", "dynAssigns", pages=2)
ASGS = all_of("asg", 2)
ME = {"name": "me", "baseUrlType": "workday-api", "url": "common/v1/workers/me", "authType": "sso", "failOnStatusCodes": FAIL}


def page(pid, title, body, eps=(), pageType="VIEW", doms=DOM, out=None, script=None, cancel=None, compact=False):
    p = {"id": pid, "securityDomains": list(doms), "include": ["tier.script"], "endPoints": list(eps)}
    if script:
        p["script"] = script
    if out:
        p["outboundData"] = {"outboundEndPoints": out}
    pres = {"pageType": pageType, "title": {"type": "title", "id": "pageTitle", "label": title},
            "body": {"type": "section", "id": "bodySection", "children": body}}
    if pageType == "EDIT":
        pres["cancelOverride"] = {"taskId": cancel or "FormGovern"}
    p["presentation"] = pres
    write(os.path.join(PRES, pid + '.pmd'), p, compact=compact)


def about(text, fid="aboutFieldSet"):
    return {"type": "fieldSet", "id": fid, "title": "About", "children": [
        {"type": "richText", "id": fid.replace("FieldSet", "RichText"), "value": "<span style=\"color:#374151;font-size:13px\">" + text + "</span>"}]}


def ro(rid, label, value):
    return {"type": "text", "id": rid, "label": label, "enabled": False, "value": X(value)}


def col(cid, label, cell, **kw):
    c = {"type": "column", "columnId": cid, "label": label, "cellTemplate": cell}
    c.update(kw)
    return c


def tcol(cid, label, value):
    return col(cid, label, {"type": "text", "id": cid.replace("Column", "Text"), "enabled": False, "value": X(value)})


def inst(pairs):
    return [{"id": i, "descriptor": d} for i, d in pairs]


def nav_btn(bid, label, task, primary=False, params=None):
    b = {"type": "button", "id": bid, "label": label, "action": "PRIMARY" if primary else "AUXILIARY", "taskReference": {"taskId": task}}
    if params:
        b["taskReference"]["parameterBindings"] = params
    return b


def box(sid, title, children):
    return {"type": "fieldSet", "id": sid, "title": title, "children": children}


# ---------------------------------------------------------------- FormGovern (governance console)
TOOLS = [("assignButton", "Block assignments", "FormAssignments"), ("deptButton", "Departments", "FormDepartments"),
         ("mapButton", "Org map", "FormOrgMap"), ("settingsButton", "Settings", "FormSettings"),
         ("readyButton", "Setup and readiness", "FormReadiness"), ("libButton", "Question library", "FormLibrary"),
         ("dashButton", "Owner dashboard", "FormOwnerDash"), ("purgeButton", "Retention purge", "FormPurge"),
         ("kitButton", "Kit designer", "KitDesigner"), ("queueButton", "Fulfilment queue", "KitQueue"),
         ("pkgButton", "Delivered features", "KitPackages"), ("peersButton", "Access recommendations", "KitPeers")]
GOV_SCRIPT = ("<%\n  var blocks = function() {\n    (forms.data ?? []).filter(f => { (f.kind ?? '') != 'composed' && (f.status ?? '') == 'Published' });\n  };\n"
              "  var byTier = function(t) {\n    blocks().filter(f => { (empty(f.ownerOrg) ? (f.tier ?? 'Team') : tier.tierOf(" + MAP + ", f.ownerOrg.id)) == t }).size();\n  };\n%>")
page("FormGovern", "Forms governance", [
    about("Governance owns the slot budgets, departments, the org map, Restricted questions, enterprise blocks and delivered "
          "features. Blocks are published from Form Studio (Publish). Each tool opens on its own page."),
    box("tierFieldSet", "Blocks by tier", [
        ro("enterpriseText", "Enterprise blocks", "'' + byTier('Enterprise') + ' published; budget ' + tier.budget(settings.data ?? [], 'Enterprise') + ' slots'"),
        ro("departmentText", "Department blocks", "'' + byTier('Department') + ' published; budget ' + tier.budget(settings.data ?? [], 'Department') + ' slots'"),
        ro("teamText", "Team blocks", "'' + byTier('Team') + ' published; budget ' + tier.budget(settings.data ?? [], 'Team') + ' slots'"),
        ro("mapText", "Org map", "'' + (" + MAP + ").size() + ' organizations, ' + (" + MAP + ").filter(r => { (r.tier ?? '') == 'Department' }).size() + ' departments'"),
        ro("domainsText", "Security domains", "'8 of 10 in use: Fill, Author, Govern, Org view, Confidential, Restricted, Integration, Fulfil; 2 kept spare'")]),
    box("toolsFieldSet", "Tools", [nav_btn(b, l, t) for b, l, t in TOOLS])],
    eps=[SET_EP, app_ep("forms", "dynForms?limit=100")] + MAP_EPS, script=GOV_SCRIPT, doms=DOM + ["DynGovern"])

# ---------------------------------------------------------------- FormAssignments
SCOPES = [("org", "Org only"), ("subs", "Org + subordinates")]


def both(field, expr="<% self.value %>"):
    return [{"value": expr, "valueOutBinding": "postA." + field}, {"value": expr, "valueOutBinding": "patchA." + field}]


A_COLS = [
    col("idColumn", "ID", {"type": "text", "id": "aIdText", "enabled": False, "value": "<% ar.id ?? '' %>"}),
    col("familyColumn", "Block family", {"type": "text", "id": "familyText", "value": "<% ar.family ?? '' %>",
                                         "valuesOut": both("family") + both("ref", "<% (self.value ?? '') + ' / ' + (empty(processInstanceList.value) ? '' : processInstanceList.value[0]) %>")}, required=True),
    col("processColumn", "Process", {"type": "instanceList", "id": "processInstanceList", "values": "<% tier.procList() %>",
                                     "selectedValues": "<% empty(ar.processType) ? [] : [ar.processType] %>",
                                     "valuesOut": both("processType", "<% empty(self.value) ? '' : self.value[0] %>")}, required=True),
    col("ownerColumn", "Owner organization", {"type": "instanceList", "id": "ownerInstanceList", "values": X("tier.orgPick(" + MAP + ")"),
                                              "selectedValuesAndDescriptors": X("tier.orgSel(" + MAP + ", ar.ownerWid)"),
                                              "onChange": X("reachReadOnlyText.setValue(tier.reachText(" + MAP + ", empty(self.value) ? '' : self.value[0], empty(scopeInstanceList.value) ? 'org' : scopeInstanceList.value[0])); "
                                                            "var e = tier.scopeErr(" + MAP + ", empty(self.value) ? '' : self.value[0], empty(scopeInstanceList.value) ? 'org' : scopeInstanceList.value[0]); "
                                                            "if (empty(e)) { self.clearError(); scopeInstanceList.clearError(); } else { self.setError(e); }"),
                                              "valuesOut": both("ownerWid", "<% empty(self.value) ? '' : self.value[0] %>") +
                                              both("ownerOrg", "<% empty(self.value) ? null : {'id': self.value[0]} %>") +
                                              both("tier", X("empty(self.value) ? '' : tier.tierOf(" + MAP + ", self.value[0])"))}, required=True),
    col("scopeColumn", "Scope", {"type": "instanceList", "id": "scopeInstanceList", "instanceList": inst(SCOPES),
                                 "selectedValues": "<% [ar.scope ?? 'org'] %>",
                                 "onChange": X("reachReadOnlyText.setValue(tier.reachText(" + MAP + ", empty(ownerInstanceList.value) ? '' : ownerInstanceList.value[0], empty(self.value) ? 'org' : self.value[0])); "
                                               "var e = tier.scopeErr(" + MAP + ", empty(ownerInstanceList.value) ? '' : ownerInstanceList.value[0], empty(self.value) ? 'org' : self.value[0]); "
                                               "if (empty(e)) { self.clearError(); ownerInstanceList.clearError(); } else { self.setError(e); }"),
                                 "valuesOut": both("scope", "<% empty(self.value) ? 'org' : self.value[0] %>")}, required=True),
    col("reachColumn", "Reach", {"type": "readOnlyText", "id": "reachReadOnlyText", "value": X("tier.reachText(" + MAP + ", ar.ownerWid ?? '', ar.scope ?? 'org')")}),
    col("gateColumn", "Gate on", {"type": "checkBox", "id": "gateCheckBox", "value": "<% ar.gateOn ?? true %>", "valuesOut": both("gateOn", "<% self.value ?? false %>")}),
    col("orderColumn", "Section order", {"type": "number", "id": "orderNumber", "value": "<% ar.sectionOrder ?? 1 %>", "valuesOut": both("sectionOrder")}),
    col("activeColumn", "Active", {"type": "checkBox", "id": "activeCheckBox", "value": "<% ar.active ?? true %>", "valuesOut": both("active", "<% self.value ?? false %>")}),
]
page("FormAssignments", "Block assignments", [
    about("Each row attaches a block (its form family) to a process type for an owner organization: Org only, or the org and "
          "every org below it. FormCompose picks every active row whose owner covers the person a request is about, takes "
          "each block's published version and puts them on one form: enterprise first, then department, then team. "
          "Reach shows the organizations and active workers a row covers (from the org map). A team block can only reach "
          "orgs in one department. Rebuild the org map after a reorganization."),
    {"type": "grid", "id": "assignGrid", "label": "Assignments", "rowVariableName": "ar", "deleteEndPoint": "deleteA",
     "rows": X(ASGS), "columns": A_COLS}],
    eps=ASG_EPS + MAP_EPS, pageType="EDIT", doms=DOM + ["DynAuthor"],
    out=[{"name": "postA", "baseUrlType": "app", "url": "dynAssigns", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% !empty(aIdText.value) %>"},
         {"name": "patchA", "baseUrlType": "app", "url": "<% 'dynAssigns/' + aIdText.value %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% empty(aIdText.value) %>"},
         {"name": "deleteA", "baseUrlType": "app", "url": "<% 'dynAssigns/' + aIdText.value %>", "httpMethod": "DELETE", "authType": "sso"}])

# ---------------------------------------------------------------- FormDepartments
D_COLS = [
    col("idColumn", "ID", {"type": "text", "id": "dIdText", "enabled": False, "value": "<% dr.id ?? '' %>"}),
    col("orgColumn", "Organization", {"type": "instanceList", "id": "orgInstanceList", "values": X("tier.orgPick(" + MAP + ")"),
                                      "selectedValuesAndDescriptors": X("tier.orgSel(" + MAP + ", dr.orgWid)"),
                                      "valuesOut": [{"value": "<% empty(self.value) ? '' : self.value[0] %>", "valueOutBinding": b + ".orgWid"} for b in ("postD", "patchD")] +
                                      [{"value": "<% empty(self.value) ? null : {'id': self.value[0]} %>", "valueOutBinding": b + ".org"} for b in ("postD", "patchD")] +
                                      [{"value": "<% empty(self.selectedEntries) ? '' : self.selectedEntries[0].descriptor.substringBefore(' (') %>", "valueOutBinding": b + ".name"} for b in ("postD", "patchD")]}, required=True),
    col("dateColumn", "Effective date", {"type": "date", "id": "effectiveDate", "value": "<% dr.effectiveDate ?? date:now() %>", "dateFormat": "yyyy-MM-dd",
                                         "valuesOut": [{"value": "<% empty(self.value) ? null : self.value.format('yyyy-MM-dd') %>", "valueOutBinding": b + ".effectiveDate"} for b in ("postD", "patchD")]}),
    col("activeColumn", "Active", {"type": "checkBox", "id": "activeCheckBox", "value": "<% dr.active ?? true %>",
                                   "valuesOut": [{"value": "<% self.value ?? false %>", "valueOutBinding": b + ".active"} for b in ("postD", "patchD")]}),
    col("byColumn", "Designated by", {"type": "text", "id": "byText", "enabled": False, "value": "<% dr.designatedBy ?? (me.descriptor ?? '') %>",
                                      "valuesOut": [{"value": "<% self.value %>", "valueOutBinding": b + ".designatedBy"} for b in ("postD", "patchD")]}),
]
page("FormDepartments", "Departments", [
    about("Mark the organizations that are departments. Every worker resolves to the nearest marked organization at or above "
          "their own; the top organization is the enterprise. After a change, rebuild the org map (Org map, OK), then check "
          "Setup and readiness: every organization below the top should resolve to one department."),
    ro("unresolvedText", "Organizations with no department", "'' + (" + MAP + ").filter(r => { r.active != false && empty(r.deptWid) && (r.tier ?? '') != 'Enterprise' }).size() + ' (as of the last org map rebuild)'"),
    {"type": "grid", "id": "deptGrid", "label": "Departments", "rowVariableName": "dr", "deleteEndPoint": "deleteD",
     "rows": "<% depts.data ?? [] %>", "columns": D_COLS}],
    eps=[app_ep("depts", "dynDepts?limit=100"), ME] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynGovern"],
    out=[{"name": "postD", "baseUrlType": "app", "url": "dynDepts", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% !empty(dIdText.value) %>"},
         {"name": "patchD", "baseUrlType": "app", "url": "<% 'dynDepts/' + dIdText.value %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% empty(dIdText.value) %>"},
         {"name": "deleteD", "baseUrlType": "app", "url": "<% 'dynDepts/' + dIdText.value %>", "httpMethod": "DELETE", "authType": "sso"}])

# ---------------------------------------------------------------- FormOrgMap
ORGS = wql("orgs", "SELECT workdayID, name, superiorOrganization, inactive FROM supervisoryOrganizations")
WORKERS = wql("workers", "SELECT worker, supervisoryOrganization, jobProfile FROM workersForHCMReporting(dataSourceFilter=allActiveWorkers)")
ROWS = "tier.orgRows(orgs.data ?? [], depts.data ?? [], workers.data ?? [])"
MAP_OUT = []
for part in range(3):
    for new, method in ((True, "POST"), (False, "PATCH")):
        sel = "tier.mapPart(" + ROWS + ", " + MAP + ", " + ("true" if new else "false") + ", " + str(part) + ")"
        MAP_OUT.append({"name": ("postMap%d" if new else "patchMap%d") % part, "baseUrlType": "app", "url": "dynOrgMaps?bulk=true",
                        "httpMethod": method, "authType": "sso", "failOnStatusCodes": FAIL,
                        "exclude": X(sel + ".size() == 0"), "onSend": X("self.data = {:}; self.data.data = " + sel + "; self.data;")})
page("FormOrgMap", "Org map", [
    about("The org map is a copy of Workday's supervisory hierarchy that FormCompose reads in one call: each organization's "
          "path, depth, department, company, tier and active workers. OK writes it (new organizations added, existing ones "
          "updated; up to 300). Run it after reorganizations and after marking departments; the owner dashboard then shows "
          "blocks whose owner org moved or became inactive."),
    ro("countText", "From Workday", "'' + (orgs.data ?? []).size() + ' supervisory organizations, ' + (workers.data ?? []).size() + ' active workers, ' + (depts.data ?? []).size() + ' departments marked'"),
    ro("planText", "OK will", "'add ' + tier.mapPart(" + ROWS + ", " + MAP + ", true, 0).size() + ' and update ' + tier.mapPart(" + ROWS + ", " + MAP + ", false, 0).size() + ' rows (counts of the first 100 of each)'"),
    {"type": "grid", "id": "previewGrid", "label": "Org map preview", "rowVariableName": "pr", "rows": X(ROWS),
     "columns": [tcol("nameColumn", "Organization", "pr.name ?? ''"), tcol("tierColumn", "Tier", "pr.tier ?? ''"),
                 tcol("deptColumn", "Department", "pr.deptName ?? ''"), tcol("companyColumn", "Company", "pr.companyName ?? ''"),
                 tcol("depthColumn", "Depth", "'' + (pr.depth ?? 0)"), tcol("workersColumn", "Workers", "'' + (pr.workerCount ?? 0)"),
                 tcol("activeColumn", "Active", "pr.active == false ? 'No' : 'Yes'")], "doNotAdd": True, "doNotRemove": True}],
    eps=[ORGS, WORKERS, app_ep("depts", "dynDepts?limit=100")] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynGovern"], out=MAP_OUT)

# ---------------------------------------------------------------- FormSettings
S_FIELDS = [("budgetEnterprise", "Enterprise slots", 12), ("budgetDepartment", "Department slots", 10), ("budgetTeam", "Team slots", 8),
            ("reachThreshold", "Reach that needs governance (workers)", 250), ("defaultValidMonths", "Default validity of reusable answers (months)", 12),
            ("recommendPct", "Recommend access at (% of peers)", 80), ("commonPct", "Show as common at (% of peers)", 50),
            ("minPeers", "Fewest peers for a recommendation", 3), ("retainGeneral", "Keep General answers (months)", 84),
            ("retainConfidential", "Keep Confidential answers (months)", 36), ("retainRestricted", "Keep Restricted answers (months)", 24),
            ("welcomeDaysBefore", "Release the welcome (days before start)", 3)]
S_BODY = "var b = {:}; b.put('settingKey', 'DEFAULT'); " + " ".join("b.put('%s', %sNumber.getValue() ?? %d);" % (f, f, d) for f, _, d in S_FIELDS) + " b;"
page("FormSettings", "Forms settings", [
    about("Slot budgets split the fill page between tiers (the page has 28 slots); a block over its tier's budget can't be "
          "published. The reach threshold sends department blocks that reach more workers to governance. Validity applies "
          "to reusable questions without their own. The access thresholds and minimum peers drive access recommendations; "
          "retention drives the purge."),
    box("settingsFieldSet", "Settings", [
        {"type": "number", "id": f + "Number", "label": l, "value": X("tier.setting(settings.data ?? [], '%s', %d)" % (f, d))} for f, l, d in S_FIELDS])],
    eps=[SET_EP], pageType="EDIT", doms=DOM + ["DynGovern"],
    out=[{"name": "postS", "baseUrlType": "app", "url": "dynSettings", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% !empty(tier.first(settings.data ?? []).id) %>", "onSend": X(S_BODY)},
         {"name": "patchS", "baseUrlType": "app", "url": "<% 'dynSettings/' + (tier.first(settings.data ?? []).id ?? 'none') %>", "httpMethod": "PATCH",
          "authType": "sso", "failOnStatusCodes": FAIL, "exclude": "<% empty(tier.first(settings.data ?? []).id) %>", "onSend": X(S_BODY)}])

# ---------------------------------------------------------------- FormPublish
FORM = "tier.first(formRec.data ?? [])"
FAM = "('' + (" + FORM + ".family ?? (queryParams.form ?? '')))"
PUB = "tier.published(fams.data ?? [])"
PUB_EPS = [app_ep("formRec", "<% 'dynForms?limit=1&code=' + (queryParams.form ?? '').urlEncode() %>", exclude="<% empty(queryParams.form) %>"),
           app_ep("qs", "<% 'dynQuestions?limit=100&formCode=' + (queryParams.form ?? '').urlEncode() %>", exclude="<% empty(queryParams.form) %>"),
           app_ep("fams", "<% 'dynForms?limit=100&family=' + " + FAM + ".urlEncode() %>", exclude="<% empty(queryParams.form) %>"),
           app_ep("oldQs", "<% 'dynQuestions?limit=100&formCode=' + ('' + (" + PUB + ".code ?? 'none')).urlEncode() %>", exclude="<% empty(" + PUB + ".code) %>"),
           app_ep("asgs", "<% 'dynAssigns?limit=100&family=' + " + FAM + ".urlEncode() %>", exclude="<% empty(queryParams.form) %>"),
           SET_EP, ME] + MAP_EPS
ERR = "tier.publishErr(" + MAP + ", settings.data ?? [], " + FORM + ", qs.data ?? [], asgs.data ?? [], govCheckBox.getValue(), reasonText.getValue())"
PUB_BODY = ("var b = {:}; b.put('status', 'Published'); b.put('approvedBy', me.descriptor ?? ''); "
            "b.put('approvedTier', tier.blockTier(" + MAP + ", " + FORM + ", asgs.data ?? [])); b.put('tier', tier.blockTier(" + MAP + ", " + FORM + ", asgs.data ?? [])); "
            "b.put('reachAtApproval', tier.reachAll(" + MAP + ", asgs.data ?? [])); b.put('slotCount', tier.slots(qs.data ?? [])); "
            "b.put('privacyReason', reasonText.getValue() ?? ''); b.put('retentionMonths', retentionNumber.getValue() ?? 84); "
            "b.put('approvedOn', date:now().format('yyyy-MM-dd')); b;")
page("FormPublish", "Publish a block version", [
    about("Opened from Form Studio with ?form=CODE (a draft version). Checks before OK: the block's slots against its tier's "
          "budget, governance approval for enterprise blocks, Restricted questions and department blocks over the reach "
          "threshold, a privacy reason when there are protected questions, and the team scope rule. OK publishes this version "
          "(who approved it, at which tier, reach and slots are recorded) and supersedes the published one. Requests already "
          "running keep the versions they were composed with; new requests get this one."),
    box("checkFieldSet", "This version", [
        ro("formText", "Version", "(queryParams.form ?? '(none: open from Form Studio)') + '  ' + (" + FORM + ".formName ?? '') + ' (' + (" + FORM + ".status ?? '') + ')'"),
        ro("summaryText", "Budget and reach", "tier.summary(" + MAP + ", settings.data ?? [], " + FORM + ", qs.data ?? [], asgs.data ?? [])"),
        ro("diffText", "Changes from the published version", "'' + (" + PUB + ".code ?? 'none') + ': ' + tier.diff(oldQs.data ?? [], qs.data ?? [])"),
        {"type": "text", "id": "reasonText", "label": "Privacy reason (why protected questions are needed)", "value": X(FORM + ".privacyReason ?? ''")},
        {"type": "number", "id": "retentionNumber", "label": "Keep answers for (months)", "value": X(FORM + ".retentionMonths ?? 84")},
        {"type": "checkBox", "id": "govCheckBox", "label": "Governance approval (Forms: Govern)", "value": "<% false %>",
         "onChange": "<% approveCheckBox.clearError() %>"},
        {"type": "checkBox", "id": "approveCheckBox", "label": "I approve this version", "required": True, "value": "<% false %>",
         "onChange": X("var e = " + ERR + "; if (empty(e)) { self.clearError(); } else { self.setError(e); }")}])],
    eps=PUB_EPS, pageType="EDIT", doms=DOM + ["DynAuthor", "DynGovern"], cancel="FormStudio",
    out=[{"name": "publishV", "baseUrlType": "app", "url": "<% 'dynForms/' + (" + FORM + ".id ?? 'none') %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": X("empty(" + FORM + ".id) || approveCheckBox.value != true || !empty(" + ERR + ")"), "onSend": X(PUB_BODY)},
         {"name": "supersede", "baseUrlType": "app", "url": "<% 'dynForms/' + (" + PUB + ".id ?? 'none') %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": X("empty(" + PUB + ".id) || (" + PUB + ".id ?? '') == (" + FORM + ".id ?? '') || approveCheckBox.value != true || !empty(" + ERR + ")"),
          "onSend": "<% self.data = {:}; self.data.status = 'Superseded'; self.data; %>"}])

# ---------------------------------------------------------------- FormReadiness
DEFS = wql("defs", "SELECT businessProcessDefinition, businessProcessType, businessProcessSteps FROM businessProcessDefinitions", 2000)
page("FormReadiness", "Setup and readiness", [
    about("Every definition of each process type the app supports, with its support level: Gate + route (two Service steps, "
          "an approval step and the route marker To Do), Gate only, Form only, or Not supported. Customers often run a "
          "non-default definition, so each one is listed. The checks below the grid read the app's own setup; the last "
          "three need an administrator. Rerun after each Workday release."),
    {"type": "grid", "id": "defsGrid", "label": "Process definitions", "rowVariableName": "rr", "rows": "<% tier.readyRows(defs.data ?? []) %>",
     "columns": [tcol("procColumn", "Process", "rr.process ?? ''"), tcol("defColumn", "Definition", "rr.definition ?? ''"),
                 tcol("levelColumn", "Support level", "rr.level ?? ''"), tcol("checksColumn", "Checks", "rr.checks ?? ''"),
                 tcol("fixColumn", "Fix", "rr.fix ?? ''")]},
    {"type": "grid", "id": "checksGrid", "label": "App setup", "rowVariableName": "cr",
     "rows": X("tier.mapChecks(" + MAP + ", depts.data ?? [], settings.data ?? [])"),
     "columns": [tcol("itemColumn", "Item", "cr.item ?? ''"), tcol("resultColumn", "Result", "cr.result ?? ''"),
                 tcol("detailColumn", "Detail", "cr.detail ?? ''"), tcol("cfixColumn", "Fix", "cr.fix ?? ''")]}],
    eps=[DEFS, app_ep("depts", "dynDepts?limit=100"), SET_EP] + MAP_EPS, doms=DOM + ["DynGovern"])

# ---------------------------------------------------------------- FormLibrary
QALL = wql("qall", "SELECT formCode, qKey, qLabel, libraryKey, classification, reusable, validMonths FROM " + REF + "_dynQuestions WHERE libraryKey is not empty")
page("FormLibrary", "Question library", [
    about("Questions share a library key when they ask the same thing. On a composed form a key is asked once (the first "
          "block, enterprise before department before team, keeps it), and a reusable answer to it is offered to every block "
          "that asks it. Set keys, classification and reuse in Form Studio (Questions)."),
    {"type": "grid", "id": "libGrid", "label": "Library keys", "rowVariableName": "lr", "rows": "<% tier.libRows(qall.data ?? [], []) %>",
     "columns": [tcol("keyColumn", "Key", "lr.key ?? ''"), tcol("labelColumn", "Label", "lr.label ?? ''"),
                 tcol("clsColumn", "Classification", "lr.cls ?? ''"), tcol("reuseColumn", "Reusable", "lr.reusable ?? ''"),
                 tcol("blocksColumn", "Blocks", "lr.blocks ?? ''")]}],
    eps=[QALL], doms=DOM + ["DynAuthor", "DynGovern"])

# ---------------------------------------------------------------- FormOwnerDash
ANS = wql("ans", "SELECT formCode, source FROM " + REF + "_dynAnswers")
page("FormOwnerDash", "Owner dashboard", [
    about("Every published block: its owner org and tier, whether it needs review (owner org inactive or moved, or reach "
          "changed since approval: orgs joined or left the scope), reach at approval and now, answers given, answers reused "
          "and prefill values confirmed."),
    {"type": "grid", "id": "dashGrid", "label": "Blocks", "rowVariableName": "br",
     "rows": X("tier.dashRows(forms.data ?? [], " + MAP + ", " + ASGS + ", ans.data ?? [])"),
     "columns": [tcol("codeColumn", "Block", "br.code ?? ''"), tcol("ownerColumn", "Owner", "br.owner ?? ''"),
                 tcol("tierColumn", "Tier", "br.tier ?? ''"), tcol("statusColumn", "Owner status", "br.status ?? ''"),
                 tcol("reachColumn", "Reach (workers)", "br.reach ?? ''"), tcol("answersColumn", "Answers", "br.answers ?? ''"),
                 tcol("reusedColumn", "Reused", "br.reused ?? ''"), tcol("prefillColumn", "Prefill confirmed", "br.prefill ?? ''")]}],
    eps=[app_ep("forms", "dynForms?limit=100"), ANS] + MAP_EPS + ASG_EPS, doms=DOM + ["DynAuthor"])

# ---------------------------------------------------------------- FormMyAnswers (employees, through the ISU)
PME = {"name": "pme", "baseUrlType": "workday-api", "url": "person/v4/people/me", "authType": "sso", "failOnStatusCodes": FAIL}
MEW = {"name": "mew", "baseUrlType": "workday-wql", "authType": "sso",
       "url": "<% 'data?limit=5&query=' + string:pathEncode('SELECT worker FROM allWorkers WHERE person in (' + (empty(pme.id) ? 'x' : pme.id) + ')') %>"}
MYW = "((mew.data ?? []).size() > 0 && !empty(mew.data[0].worker) ? ('' + mew.data[0].worker.id) : '')"
page("FormMyAnswers", "My answers", [
    about("Answers you gave that forms may reuse, and until when. Tick Clear and OK to stop one being reused: the next form "
          "that asks it asks again. A reused answer is always shown on the form, and you can change it there."),
    {"type": "grid", "id": "myGrid", "label": "Reusable answers", "rowVariableName": "mr", "rows": "<% tier.myAnswers(mine.data ?? []) %>",
     "doNotAdd": True, "doNotRemove": True, "render": "<% tier.myAnswers(mine.data ?? []).size() > 0 %>",
     "columns": [col("idColumn", "ID", {"type": "text", "id": "mIdText", "enabled": False, "value": "<% mr.id ?? '' %>"}),
                 tcol("formColumn", "Form", "mr.formCode ?? ''"), tcol("keyColumn", "Question", "mr.qKey ?? ''"),
                 tcol("valueColumn", "Answer", "mr.textValue ?? ('' + (mr.numberValue ?? ''))"),
                 tcol("untilColumn", "Reused until", "('' + (mr.validUntil ?? '')).truncate(10)"),
                 col("clearColumn", "Clear", {"type": "checkBox", "id": "clearCheckBox", "value": "<% false %>"})]},
    box("noneFieldSet", "Nothing kept", [ro("noneText", "Status", "tier.myAnswers(mine.data ?? []).size() == 0 ? 'No reusable answers are kept for you.' : 'See the grid.'")])],
    eps=[PME, MEW, app_ep("mine", "<% 'dynAnswers?limit=100&subjectWid=' + " + MYW + ".urlEncode() %>", auth="isuAuth", exclude="<% empty(" + MYW + ") %>")],
    pageType="EDIT", doms=FILL + DOM, cancel="DynMyForms",
    out=[{"name": "clearA", "baseUrlType": "app", "url": "<% 'dynAnswers/' + mIdText.value %>", "httpMethod": "PATCH", "authType": "isuAuth",
          "failOnStatusCodes": FAIL, "exclude": "<% clearCheckBox.value != true %>",
          "onSend": "<% self.data = {:}; self.data.validUntil = date:now().minusDays(1).format('yyyy-MM-dd'); self.data; %>"}])

# ---------------------------------------------------------------- FormPurge (launches AnswerPurge)
CUT = "date:now().minusMonths(tier.setting(settings.data ?? [], '%s', %d)).format('yyyy-MM-dd')"
P_EPS = [SET_EP]
for c, coll, f, d in (("G", "dynAnswers", "retainGeneral", 84), ("C", "dynAnswerConfs", "retainConfidential", 36), ("R", "dynAnswerRestrs", "retainRestricted", 24)):
    P_EPS.append({"name": "old" + c, "baseUrlType": "workday-wql", "authType": "sso",
                  "url": "<% 'data?limit=100&query=' + string:pathEncode('SELECT workdayID FROM " + REF + "_" + coll + " WHERE answeredOn < \"' + " + (CUT % (f, d)) + " + '\"') %>"})
IDS = lambda c: "(old%s.data ?? []).map(x => { '' + x.workdayID }).join(',')" % c
page("FormPurge", "Retention purge", [
    about("Deletes answers older than the retention for their class (Forms settings): up to 100 of each class per run. Run "
          "it monthly. Confidential and Restricted answers are listed only for someone with those domains. Deleted answers "
          "can't be brought back."),
    box("purgeFieldSet", "Due for deletion", [
        ro("gText", "General", "'' + (oldG.data ?? []).size() + ' older than ' + " + (CUT % ("retainGeneral", 84))),
        ro("cText", "Confidential", "'' + (oldC.data ?? []).size() + ' older than ' + " + (CUT % ("retainConfidential", 36))),
        ro("rText", "Restricted", "'' + (oldR.data ?? []).size() + ' older than ' + " + (CUT % ("retainRestricted", 24))),
        {"type": "checkBox", "id": "confirmCheckBox", "label": "Delete these answers (can't be undone)", "required": True, "value": "<% false %>"}])],
    eps=P_EPS, pageType="EDIT", doms=DOM + ["DynGovern"],
    out=[{"name": "purge", "baseUrlType": "orchestrate", "url": "/AnswerPurge/launch", "httpMethod": "POST", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% confirmCheckBox.value != true %>",
          "onSend": X("self.data = {:}; self.data.g = " + IDS("G") + "; self.data.c = " + IDS("C") + "; self.data.r = " + IDS("R") + "; self.data;")}])

# ---------------------------------------------------------------- Kit pages
ITEMS_EP = app_ep("items", "dynKitItems?limit=100")
KITTYPES = [("welcome", "Welcome text"), ("learning", "Learning step"), ("access", "Access item")]
SENS = [("standard", "Standard"), ("elevated", "Elevated (needs governance)")]
KSTAT = [("kitDraft", "Draft"), ("kitPublished", "Published")]


def kboth(field, expr="<% self.value %>"):
    return [{"value": expr, "valueOutBinding": "postK." + field}, {"value": expr, "valueOutBinding": "patchK." + field}]


DELIV = "(kr.origin ?? '') == 'Delivered'"
K_COLS = [
    col("idColumn", "ID", {"type": "text", "id": "kIdText", "enabled": False, "value": "<% kr.id ?? '' %>"}),
    col("originColumn", "Origin", {"type": "text", "id": "originText", "enabled": False, "value": "<% kr.origin ?? 'Customer' %>"}),
    col("copyColumn", "Copy to change", {"type": "checkBox", "id": "copyCheckBox", "value": "<% false %>", "enabled": X(DELIV)}),
    col("codeColumn", "Code", {"type": "text", "id": "codeText", "value": "<% kr.code ?? '' %>", "enabled": X("!(" + DELIV + ")"),
                               "valuesOut": kboth("code", "<% copyCheckBox.value == true ? (self.value ?? '') + '-C' : self.value %>")}, required=True),
    col("typeColumn", "Type", {"type": "instanceList", "id": "typeInstanceList", "instanceList": inst(KITTYPES), "selectedValues": "<% [kr.itemType ?? 'learning'] %>",
                               "valuesOut": kboth("itemType", "<% empty(self.value) ? 'learning' : self.value[0] %>")}, required=True),
    col("titleColumn", "Title", {"type": "text", "id": "titleText", "value": "<% kr.title ?? '' %>", "valuesOut": kboth("title")}, required=True),
    col("bodyColumn", "Text", {"type": "text", "id": "bodyText", "value": "<% kr.body ?? '' %>", "valuesOut": kboth("body")}),
    col("ownerColumn", "Owner organization", {"type": "instanceList", "id": "ownerInstanceList", "values": X("tier.orgPick(" + MAP + ")"),
                                              "selectedValuesAndDescriptors": X("tier.orgSel(" + MAP + ", kr.ownerWid)"),
                                              "valuesOut": kboth("ownerWid", "<% empty(self.value) ? '' : self.value[0] %>") +
                                              kboth("ownerOrg", "<% empty(self.value) ? null : {'id': self.value[0]} %>") +
                                              kboth("tier", X("empty(self.value) ? '' : tier.tierOf(" + MAP + ", self.value[0])"))}, required=True),
    col("scopeColumn", "Scope", {"type": "instanceList", "id": "scopeInstanceList", "instanceList": inst(SCOPES), "selectedValues": "<% [kr.scope ?? 'subs'] %>",
                                 "valuesOut": kboth("scope", "<% empty(self.value) ? 'subs' : self.value[0] %>")}),
    col("dueColumn", "Due (days from start)", {"type": "number", "id": "dueNumber", "value": "<% kr.dueOffset ?? 0 %>", "valuesOut": kboth("dueOffset")}),
    col("groupColumn", "Fulfiller group", {"type": "text", "id": "groupText", "value": "<% kr.fulfillerGroup ?? '' %>", "valuesOut": kboth("fulfillerGroup")}),
    col("sensColumn", "Sensitivity", {"type": "instanceList", "id": "sensInstanceList", "instanceList": inst(SENS), "selectedValues": "<% [kr.sensitivity ?? 'standard'] %>",
                                      "valuesOut": kboth("sensitivity", "<% empty(self.value) ? 'standard' : self.value[0] %>")}),
    col("statusColumn", "Status", {"type": "instanceList", "id": "statusInstanceList", "instanceList": inst(KSTAT), "selectedValues": "<% [(kr.status ?? 'Draft') == 'Published' ? 'kitPublished' : 'kitDraft'] %>",
                                   "onChange": "<% (!empty(self.value) && self.value[0] == 'kitPublished' && !empty(sensInstanceList.value) && sensInstanceList.value[0] == 'elevated' && govCheckBox.value != true) ? self.setError('An elevated access item needs governance approval: tick Governance.') : self.clearError() %>",
                                   "valuesOut": kboth("status", "<% (!empty(self.value) && self.value[0] == 'kitPublished') ? 'Published' : 'Draft' %>")}),
    col("govColumn", "Governance", {"type": "checkBox", "id": "govCheckBox", "value": "<% !empty(kr.approvedBy) %>",
                                    "onChange": "<% statusInstanceList.clearError() %>",
                                    "valuesOut": kboth("approvedBy", "<% self.value == true ? (me.descriptor ?? 'governance') : '' %>")}),
    col("processColumn", "Process", {"type": "instanceList", "id": "processInstanceList", "values": "<% tier.procList() %>",
                                     "selectedValues": "<% [kr.processType ?? 'Onboarding'] %>",
                                     "valuesOut": kboth("processType", "<% empty(self.value) ? 'Onboarding' : self.value[0] %>")}),
]
K_COMMON = [{"value": "<% copyCheckBox.value == true ? 'Customer' : (originText.value ?? 'Customer') %>", "valueOutBinding": b + ".origin"} for b in ("postK", "patchK")]
K_COMMON += [{"value": "<% copyCheckBox.value == true ? codeText.value : null %>", "valueOutBinding": "postK.overrides"},
             {"value": "<% true %>", "valueOutBinding": "postK.active"}]
K_COLS[1]["cellTemplate"]["valuesOut"] = K_COMMON
page("KitDesigner", "Kit designer", [
    about("Every part of the onboarding kit: welcome text, learning steps (due days from the start date) and access items "
          "(routed to the fulfiller group). Owner organization and scope work like blocks: the kit for a new hire holds "
          "every published item whose owner covers the hire's organization. Delivered items (from a delivered feature) "
          "can't be edited: tick Copy to change, and OK saves a customer copy that replaces it for new hires. Elevated "
          "access items need governance before they can be published, and add an extra approval to the request."),
    {"type": "grid", "id": "kitGrid", "label": "Kit items", "rowVariableName": "kr", "deleteEndPoint": "deleteK",
     "rows": "<% items.data ?? [] %>", "columns": K_COLS}],
    eps=[ITEMS_EP, ME] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynAuthor"],
    out=[{"name": "postK", "baseUrlType": "app", "url": "dynKitItems", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% !empty(kIdText.value) && copyCheckBox.value != true %>"},
         {"name": "patchK", "baseUrlType": "app", "url": "<% 'dynKitItems/' + kIdText.value %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% empty(kIdText.value) || copyCheckBox.value == true || originText.value == 'Delivered' %>"},
         {"name": "deleteK", "baseUrlType": "app", "url": "<% 'dynKitItems/' + kIdText.value %>", "httpMethod": "DELETE", "authType": "sso"}])

# KitPrepare: the manager's task for one hire (?event=<business process event WID>)
TASKS_EP = app_ep("tasks", "<% 'dynKitTasks?limit=100&bpEvent=' + (queryParams.event ?? 'none') %>", exclude="<% empty(queryParams.event) %>")
PREP = "tier.first(tier.kitByType(tasks.data ?? [], 'prepare'))"
HIRE_ORG = "('' + (" + PREP + ".orgWid ?? ''))"
HIRE = "('' + (" + PREP + ".hireWid ?? ''))"
HIREJP = wql("hire", "SELECT worker, jobProfile, supervisoryOrganization, hireDate FROM allWorkers WHERE workdayID = \"' + " + HIRE + ".replace('\\\\'', '') + '\"", 1)
HIREJP["url"] = "<% 'data?limit=1&query=' + string:pathEncode('SELECT worker, jobProfile, supervisoryOrganization, hireDate FROM allWorkers WHERE workdayID = \"' + " + HIRE + " + '\"') %>"
HIREJP["exclude"] = "<% empty(" + HIRE + ") %>"
SNAPS = app_ep("snaps", "<% 'dynAccessSnaps?limit=100&orgWid=' + " + HIRE_ORG + " %>", exclude="<% empty(" + HIRE_ORG + ") %>", fail=False)
JP = "(((hire.data ?? []).size() > 0 && !empty(hire.data[0].jobProfile)) ? ('' + hire.data[0].jobProfile.id) : '')"
SNAPS_JP = "(snaps.data ?? []).filter(x => { ('' + (x.jobProfile ?? '')) == " + JP + " })"
AROWS = "tier.accessRows(items.data ?? [], " + MAP + ", " + HIRE_ORG + ", " + SNAPS_JP + ", settings.data ?? [])"
PREP_SCRIPT = ("<%\n  var picked = function() {\n    var out = [];\n    var stamp = date:now().format('yyyyMMddHHmmssSSS');\n"
               "    for (var r : accessGrid.rows) {\n      var cm = r.childrenMap;\n"
               "      if (cm.requestColumn.value == true) {\n        var m = {:};\n"
               "        m.put('key', 'KIT:' + stamp + ':' + cm.codeColumn.value);\n        m.put('taskType', 'access');\n"
               "        m.put('hireWid', " + HIRE + ");\n        m.put('newHire', { 'id': " + HIRE + " });\n"
               "        m.put('hirePerson', " + PREP + ".hirePerson ?? '');\n        m.put('itemCode', cm.codeColumn.value);\n"
               "        m.put('title', cm.titleColumn.value);\n        m.put('status', 'requested');\n"
               "        m.put('requestedBy', me.descriptor ?? '');\n        m.put('fulfillerGroup', cm.groupColumn.value);\n"
               "        m.put('bpEvent', queryParams.event ?? '');\n        m.put('source', empty(cm.recColumn.value) ? 'added' : 'recommended');\n"
               "        m.put('sensitivity', cm.sensColumn.value);\n        m.put('reason', cm.reasonColumn.value ?? '');\n"
               "        m.put('orgWid', " + HIRE_ORG + ");\n        m.put('jobProfile', " + JP + ");\n        out.add(m);\n      }\n"
               "      if (cm.requestColumn.value != true && !empty(cm.reasonColumn.value)) {\n"
               "        var n = {:};\n        n.put('key', 'KIT:' + stamp + ':' + cm.codeColumn.value + ':X');\n        n.put('taskType', 'access');\n"
               "        n.put('hireWid', " + HIRE + ");\n        n.put('itemCode', cm.codeColumn.value);\n        n.put('title', cm.titleColumn.value);\n"
               "        n.put('status', 'skipped');\n        n.put('reason', cm.reasonColumn.value);\n        n.put('requestedBy', me.descriptor ?? '');\n"
               "        n.put('bpEvent', queryParams.event ?? '');\n        n.put('source', 'removed');\n        out.add(n);\n      }\n    }\n    out;\n  };\n%>")
page("KitPrepare", "Prepare for your new hire", [
    about("Write a personal note for the welcome page and confirm the access list before the start date. Baseline items "
          "come from the enterprise kit; department and team items from those owners; recommendations come from what peers "
          "in the same organization and job profile hold (counts only, never names). Untick an item only with a reason "
          "(the fulfiller sees it). Elevated items need a reason and get an extra approval. OK sends every access request "
          "to its fulfiller group. Workday roles go through Workday's own role assignment; the kit only tracks them."),
    box("hireFieldSet", "New hire", [
        ro("hireText", "New hire", "(hire.data ?? []).size() > 0 && !empty(hire.data[0].worker) ? ('' + hire.data[0].worker.descriptor) : (empty(queryParams.event) ? 'Open this from the onboarding task (?event=)' : " + HIRE + ")"),
        ro("orgText", "Organization", "(tier.mapOf(" + MAP + ", " + HIRE_ORG + ").name ?? '') + ' (' + (tier.mapOf(" + MAP + ", " + HIRE_ORG + ").deptName ?? '') + ')'"),
        {"type": "textArea", "id": "noteTextArea", "label": "Your note for the welcome page", "value": X(PREP + ".managerNote ?? ''")}]),
    {"type": "grid", "id": "accessGrid", "label": "Access list", "rowVariableName": "xr", "rows": X(AROWS), "doNotAdd": True, "doNotRemove": True,
     "render": X(AROWS + ".size() > 0"),
     "columns": [col("codeColumn", "Item", {"type": "text", "id": "codeText", "enabled": False, "value": "<% xr.code ?? '' %>"}),
                 col("titleColumn", "Title", {"type": "text", "id": "titleText", "enabled": False, "value": "<% xr.title ?? '' %>"}),
                 tcol("groupKindColumn", "From", "xr.group ?? ''"),
                 col("groupColumn", "Fulfiller", {"type": "text", "id": "groupText", "enabled": False, "value": "<% xr.fulfiller ?? '' %>"}),
                 col("sensColumn", "Sensitivity", {"type": "text", "id": "sensText", "enabled": False, "value": "<% xr.sensitivity ?? 'standard' %>"}),
                 col("recColumn", "Recommendation", {"type": "text", "id": "recText", "enabled": False, "value": "<% xr.rec ?? '' %>"}),
                 col("requestColumn", "Request", {"type": "checkBox", "id": "requestCheckBox", "value": "<% xr.ticked ?? false %>",
                                                  "onChange": "<% ((self.value != true && groupKindColumnText.value == 'Baseline') || (self.value == true && sensText.value == 'elevated')) && empty(reasonText.value) ? reasonText.setError('Give a reason: the fulfiller sees it.') : reasonText.clearError() %>"}),
                 col("reasonColumn", "Reason", {"type": "text", "id": "reasonText", "value": "<% '' %>", "onChange": "<% self.clearError() %>"})]}],
    eps=[TASKS_EP, ITEMS_EP, SET_EP, ME, HIREJP, SNAPS] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynFill"], script=PREP_SCRIPT, cancel="DynMyForms",
    out=[{"name": "postAccess", "baseUrlType": "app", "url": "dynKitTasks?bulk=true", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% picked().size() == 0 %>", "onSend": "<% self.data = {:}; self.data.data = picked(); self.data; %>"},
         {"name": "donePrep", "baseUrlType": "app", "url": "<% 'dynKitTasks/' + (" + PREP + ".id ?? 'none') %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% empty(" + PREP + ".id) %>",
          "onSend": "<% self.data = {:}; self.data.managerNote = noteTextArea.getValue() ?? ''; self.data.status = 'done'; self.data.doneBy = me.descriptor ?? ''; self.data.doneOn = date:now().format('yyyy-MM-dd'); self.data; %>"}])
# the tasks grid "From" cell id: tcol makes groupKindColumn -> groupKindText; the request onChange reads it
for p in (os.path.join(PRES, 'KitPrepare.pmd'),):
    t = open(p, encoding='utf-8').read().replace("groupKindColumnText.value", "groupKindText.value")
    open(p, 'w', encoding='utf-8').write(t)

# KitWelcome: the new hire (pre-hires included: matched on their Person WID) or HR
MY_TASKS = app_ep("mytasks", "<% 'dynKitTasks?limit=100&hireWid=' + (empty(queryParams.hire) ? " + MYW + " : queryParams.hire).urlEncode() %>", auth="isuAuth",
                  exclude="<% empty(queryParams.hire) && empty(" + MYW + ") %>")
ALL_TASKS = "(mytasks.data ?? [])"
page("KitWelcome", "Welcome", [
    {"type": "fieldSet", "id": "welcomeFieldSet", "title": "Welcome", "children": [
        {"type": "richText", "id": "welcomeRichText", "value": X("'<span style=\"color:#374151;font-size:14px\">' + tier.welcomeText(items.data ?? [], " + ALL_TASKS + ", []) + '</span>'")}]},
    box("stepsFieldSet", "Your first weeks", [ro("stepsText", "Learning steps", "'' + tier.kitByType(" + ALL_TASKS + ", 'learning').size() + ' steps; open your learning guide to tick them off'"),
                                               nav_btn("guideButton", "Open my learning guide", "KitGuide", True)])],
    eps=[PME, MEW, MY_TASKS, dict(ITEMS_EP, authType="isuAuth")], doms=FILL + DOM)

# KitGuide: learning steps, ticked off by the hire (or their manager with ?hire=)
G_TASKS = "tier.kitByType(mytasks.data ?? [], 'learning')"
page("KitGuide", "Learning guide", [
    about("Steps by due day (days from your start date). Tick a step when it is done and click OK; your manager sees the progress."),
    {"type": "grid", "id": "guideGrid", "label": "Steps", "rowVariableName": "gr", "rows": X("list:sort(" + G_TASKS + ", 'dueOffset', true)"),
     "doNotAdd": True, "doNotRemove": True, "render": X(G_TASKS + ".size() > 0"),
     "columns": [col("idColumn", "ID", {"type": "text", "id": "gIdText", "enabled": False, "value": "<% gr.id ?? '' %>"}),
                 tcol("titleColumn", "Step", "gr.title ?? ''"), tcol("dueColumn", "Due (day)", "'' + (gr.dueOffset ?? 0)"),
                 tcol("statusColumn", "Status", "gr.status ?? ''"),
                 col("doneColumn", "Done", {"type": "checkBox", "id": "doneCheckBox", "value": "<% (gr.status ?? '') == 'done' %>"})]},
    box("noneFieldSet", "Steps", [ro("noneText", "Status", G_TASKS + ".size() == 0 ? 'No learning steps yet.' : ('' + " + G_TASKS + ".filter(x => { (x.status ?? '') == 'done' }).size() + ' of ' + " + G_TASKS + ".size() + ' done')")])],
    eps=[PME, MEW, MY_TASKS], pageType="EDIT", doms=FILL + DOM, cancel="DynMyForms",
    out=[{"name": "tick", "baseUrlType": "app", "url": "<% 'dynKitTasks/' + gIdText.value %>", "httpMethod": "PATCH", "authType": "isuAuth",
          "failOnStatusCodes": FAIL, "exclude": "<% doneCheckBox.value != true %>",
          "onSend": "<% self.data = {:}; self.data.status = 'done'; self.data.doneOn = date:now().format('yyyy-MM-dd'); self.data; %>"}])

# KitQueue: access tasks for one fulfiller group (?group=IT)
ACTIONS = [("keep", "No change"), ("approved", "Approve"), ("declined", "Decline"), ("done", "Mark done")]
Q_TASKS = app_ep("qtasks", "<% 'dynKitTasks?limit=100&fulfillerGroup=' + (queryParams.group ?? 'IT').urlEncode() %>")
Q_ROWS = "(qtasks.data ?? []).filter(x => { (x.taskType ?? '') == 'access' && ['requested', 'approved'].contains(x.status ?? '') })"
page("KitQueue", "Fulfilment queue", [
    about("Access requests routed to one fulfiller group (?group=IT, ?group=Workday%20security). Approve, decline with a "
          "reason, or mark done, then OK. Elevated items need an approval before they can be marked done. The group in the "
          "address only filters the list: who may see it is set by the Dyn Forms Onboarding Fulfil domain."),
    ro("groupText", "Group", "queryParams.group ?? 'IT'"),
    {"type": "grid", "id": "queueGrid", "label": "Requests", "rowVariableName": "qr", "rows": X(Q_ROWS), "doNotAdd": True, "doNotRemove": True,
     "render": X(Q_ROWS + ".size() > 0"),
     "columns": [col("idColumn", "ID", {"type": "text", "id": "qIdText", "enabled": False, "value": "<% qr.id ?? '' %>"}),
                 tcol("titleColumn", "Item", "qr.title ?? ''"), tcol("forColumn", "For", "qr.hireWid ?? ''"),
                 tcol("statusColumn", "Status", "qr.status ?? ''"), tcol("sensColumn", "Sensitivity", "qr.sensitivity ?? 'standard'"),
                 tcol("srcColumn", "Source", "(qr.source ?? '') + (empty(qr.reason) ? '' : ': ' + qr.reason)"),
                 col("actionColumn", "Action", {"type": "instanceList", "id": "actionInstanceList", "instanceList": inst(ACTIONS), "selectedValues": "<% ['keep'] %>",
                                                "onChange": "<% (!empty(self.value) && self.value[0] == 'done' && sensText.value == 'elevated' && statusText.value != 'approved') ? self.setError('Approve an elevated item first.') : self.clearError() %>"}),
                 col("noteColumn", "Reason (decline)", {"type": "text", "id": "noteText", "value": "<% '' %>"})]}],
    eps=[Q_TASKS, ME], pageType="EDIT", doms=DOM + ["DynFulfil"],
    out=[{"name": "act", "baseUrlType": "app", "url": "<% 'dynKitTasks/' + qIdText.value %>", "httpMethod": "PATCH", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": "<% empty(actionInstanceList.value) || actionInstanceList.value[0] == 'keep' %>",
          "onSend": "<% self.data = {:}; var a = actionInstanceList.value[0]; self.data.status = a; if (a == 'approved') { self.data.approvedBy = me.descriptor ?? ''; } if (a == 'done') { self.data.doneBy = me.descriptor ?? ''; self.data.doneOn = date:now().format('yyyy-MM-dd'); } if (a == 'declined') { self.data.reason = noteText.value ?? ''; } self.data; %>"}])

# KitPackages: delivered features
PK_ROWS = "tier.pkgRows(pkgs.data ?? [], items.data ?? [])"
PK_SCRIPT = ("<%\n  var ticked = function() {\n    var out = [];\n    for (var r : pkgGrid.rows) { if (r.childrenMap.enableColumn.value == true) { out.add(r.childrenMap.codeColumn.value); } }\n    out;\n  };\n%>")
page("KitPackages", "Delivered features", [
    about("Ready-made bundles of kit items that a customer switches on and adjusts. Enabling installs the delivered items "
          "(origin Delivered, owned by the top organization, read only); change one with Copy to change in the kit designer, "
          "so a later delivered version never overwrites your copy. Status shows installed items, customer copies and items "
          "older than the delivered version. Delivered text is generic (Canada first) and must be reviewed by your HR or "
          "legal team."),
    {"type": "grid", "id": "pkgGrid", "label": "Packages", "rowVariableName": "pr", "rows": X(PK_ROWS), "doNotAdd": True, "doNotRemove": True,
     "columns": [col("codeColumn", "Code", {"type": "text", "id": "codeText", "enabled": False, "value": "<% pr.code ?? '' %>"}),
                 col("pidColumn", "ID", {"type": "text", "id": "pidText", "enabled": False, "value": "<% pr.id ?? '' %>"}),
                 tcol("nameColumn", "Feature", "pr.name ?? ''"), tcol("jurColumn", "Jurisdiction", "pr.jurisdiction ?? ''"),
                 tcol("verColumn", "Delivered version", "pr.version ?? ''"), tcol("statusColumn", "Status", "pr.status ?? ''"),
                 col("enableColumn", "Enabled", {"type": "checkBox", "id": "enableCheckBox", "value": "<% pr.enabled ?? false %>"})]}],
    eps=[app_ep("pkgs", "dynPackages?limit=100"), ITEMS_EP, ME] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynGovern"], script=PK_SCRIPT,
    out=[{"name": "postPkg", "baseUrlType": "app", "url": "dynPackages", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% !empty(pidText.value) || enableCheckBox.value != true %>",
          "onSend": "<% self.data = {:}; self.data.code = codeText.value; self.data.name = nameText.value; self.data.jurisdiction = jurText.value; self.data.deliveredVersion = ('' + verText.value).toInt(); self.data.enabled = true; self.data.enabledBy = me.descriptor ?? ''; self.data.enabledOn = date:now().format('yyyy-MM-dd'); self.data.readiness = 'Installed'; self.data; %>"},
         {"name": "patchPkg", "baseUrlType": "app", "url": "<% 'dynPackages/' + pidText.value %>", "httpMethod": "PATCH", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": "<% empty(pidText.value) %>",
          "onSend": "<% self.data = {:}; self.data.enabled = enableCheckBox.value == true; self.data.enabledBy = me.descriptor ?? ''; self.data.enabledOn = date:now().format('yyyy-MM-dd'); self.data; %>"},
         {"name": "installItems", "baseUrlType": "app", "url": "dynKitItems?bulk=true", "httpMethod": "POST", "authType": "sso", "failOnStatusCodes": FAIL,
          "exclude": X("tier.pkgInstall(ticked(), items.data ?? [], " + MAP + ").size() == 0"),
          "onSend": X("self.data = {:}; self.data.data = tier.pkgInstall(ticked(), items.data ?? [], " + MAP + "); self.data;")}])

# KitPeers: access snapshot (counts only) from the kit history
DONE = wql("done", "SELECT hireWid, itemCode, status FROM " + REF + "_dynKitTasks WHERE taskType = \"access\" AND status = \"done\"")
PEERS = "tier.peerRows(workers.data ?? [], done.data ?? [], " + MAP + ", settings.data ?? [])"
page("KitPeers", "Access recommendations", [
    about("Builds the access snapshot the manager's prepare task reads: for each organization and job profile with at least "
          "the minimum peers (else the organization and the ones below it), how many peers hold each kit access item, "
          "from the kit's own history of completed requests. Only counts are stored, never who holds what. Items held by "
          "only one or two of six or more peers are listed for IT as possible over-provisioning, not recommended. OK writes "
          "today's snapshot."),
    {"type": "grid", "id": "snapGrid", "label": "Snapshot to write", "rowVariableName": "sr", "rows": X(PEERS), "doNotAdd": True, "doNotRemove": True,
     "columns": [tcol("orgColumn", "Organization", "tier.mapOf(" + MAP + ", sr.orgWid).name ?? sr.orgWid"), tcol("jpColumn", "Job profile", "sr.jobProfile ?? ''"),
                 tcol("itemColumn", "Item", "sr.itemCode ?? ''"), tcol("countColumn", "Holding", "'' + sr.holding + ' of ' + sr.peers"),
                 tcol("ruleColumn", "Peer rule", "sr.peerRule ?? ''")]},
    {"type": "grid", "id": "overGrid", "label": "Possible over-provisioning (for IT)", "rowVariableName": "or1", "rows": X("tier.overProv(" + PEERS + ")"),
     "doNotAdd": True, "doNotRemove": True,
     "columns": [tcol("oOrgColumn", "Organization", "tier.mapOf(" + MAP + ", or1.orgWid).name ?? or1.orgWid"),
                 tcol("oItemColumn", "Item", "or1.itemCode ?? ''"), tcol("oCountColumn", "Holding", "'' + or1.holding + ' of ' + or1.peers")]}],
    eps=[WORKERS, DONE, SET_EP] + MAP_EPS, pageType="EDIT", doms=DOM + ["DynGovern"],
    out=[{"name": "postSnap%d" % n, "baseUrlType": "app", "url": "dynAccessSnaps?bulk=true", "httpMethod": "POST", "authType": "sso",
          "failOnStatusCodes": FAIL, "exclude": X("tier.chunk(" + PEERS + ", %d).size() == 0" % n),
          "onSend": X("self.data = {:}; self.data.data = tier.chunk(" + PEERS + ", %d); self.data;" % n)} for n in range(3)])

# ---------------------------------------------------------------- model tasks (Workday search) and AMD
TASKS = [(13, "FormGovern", "Dynamic Forms Governance", DOM + ["DynGovern"], "/formGovern"),
         (14, "FormMyAnswers", "My Reusable Answers", FILL + DOM, "/formMyAnswers"),
         (15, "KitWelcome", "My Welcome", FILL + DOM, "/kitWelcome"),
         (16, "KitGuide", "My Learning Guide", FILL + DOM, "/kitGuide"),
         (17, "KitQueue", "Onboarding Fulfilment Queue", DOM + ["DynFulfil"], "/kitQueue"),
         (18, "KitPrepare", "Prepare for a New Hire", DOM + ["DynFill"], "/kitPrepare")]
for i, n, l, d, r in TASKS:
    write(os.path.join(MODEL, n + '.task'), {"id": i, "name": n, "label": l, "securityDomains": d, "routePath": r})

PAGES = ["FormGovern", "FormAssignments", "FormDepartments", "FormOrgMap", "FormSettings", "FormPublish", "FormReadiness",
         "FormLibrary", "FormOwnerDash", "FormMyAnswers", "FormPurge", "KitDesigner", "KitPrepare", "KitWelcome", "KitGuide",
         "KitQueue", "KitPackages", "KitPeers"]
amd_path = glob.glob(os.path.join(PRES, '*.amd'))[0]
amd = json.load(open(amd_path, encoding='utf-8'))
have = {t["id"] for t in amd["tasks"]}
for pid in PAGES:
    if pid not in have:
        amd["tasks"].append({"id": pid, "routingPattern": "/" + pid[0].lower() + pid[1:], "page": {"id": pid}})
flows = [f for f in amd.get("flowDefinitions", []) if not f["id"].startswith("tier")]
for pid, back in (("FormAssignments", "FormGovern"), ("FormDepartments", "FormGovern"), ("FormOrgMap", "FormGovern"),
                  ("FormSettings", "FormGovern"), ("FormPublish", "FormStudio"), ("FormPurge", "FormGovern"),
                  ("KitDesigner", "FormGovern"), ("KitPackages", "FormGovern"), ("KitPeers", "FormGovern"),
                  ("KitQueue", "FormGovern"), ("FormMyAnswers", "DynMyForms"), ("KitGuide", "DynMyForms"), ("KitPrepare", "DynMyForms")):
    fid = "tier" + pid + "Flow"
    flows.append({"id": fid, "flowSteps": [
        {"id": fid + "Start", "taskId": pid, "startsFlow": True, "transitions": [{"order": "a", "value": fid + "End", "condition": "<% true %>"}]},
        {"id": fid + "End", "taskId": back, "endsFlow": True}]})
amd["flowDefinitions"] = flows
write(amd_path, amd)

# ---------------------------------------------------------------- Home hub and the employee page: links to the new pages
home_path = os.path.join(PRES, 'Home.pmd')
home = json.load(open(home_path, encoding='utf-8'))
hub = home["presentation"]["body"]
if not any(n.get("task", {}).get("taskId") == "FormGovern" for n in hub["navigationTasks"]):
    hub["navigationTasks"].append({"type": "item", "label": "Governance", "icon": "wd-icon-star", "task": {"taskId": "FormGovern"}})
    for l, t in (("Owner dashboard", "FormOwnerDash"), ("Question library", "FormLibrary"), ("Setup and readiness", "FormReadiness")):
        hub["navigationTasks"].append({"type": "item", "label": l, "icon": "wd-icon-document", "task": {"taskId": t}})
links = hub["additionalLinks"]["links"]
for l, t in (("Block assignments", "FormAssignments"), ("Kit designer", "KitDesigner"), ("Fulfilment queue", "KitQueue")):
    if not any(x["task"]["taskId"] == t for x in links):
        links.append({"type": "task", "label": l, "task": {"taskId": t}})
write(home_path, home)

mf_path = os.path.join(PRES, 'DynMyForms.pmd')
mf = json.load(open(mf_path, encoding='utf-8'))
kids = mf["presentation"]["body"]["children"]
if not any(c.get("id") == "moreFieldSet" for c in kids):
    kids.append(box("moreFieldSet", "More for you", [nav_btn("answersButton", "My reusable answers", "FormMyAnswers"),
                                                     nav_btn("welcomeButton", "My welcome", "KitWelcome", params={"hire": "<% rows().size() > 0 ? ('' + (rows()[0].bpTarget ?? '')) : '' %>"}),
                                                     nav_btn("guideButton", "My learning guide", "KitGuide", params={"hire": "<% rows().size() > 0 ? ('' + (rows()[0].bpTarget ?? '')) : '' %>"})]))
write(mf_path, mf)
print("tiers: 8 business objects, 5 domains, %d pages, %d model tasks" % (len(PAGES), len(TASKS)))
