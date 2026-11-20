#!/usr/bin/env python3
"""Form Studio (user request 2026-11-17): configure the schema-driven forms of the Dynamic Forms lab.

Pages (all in the Form Studio area of the left panel, each with the Hero card and a Form Studio pill card):
  FormStudio    VIEW  every form with its status, data sources, business object, request settings, question and
                      response counts, and Design / Questions / Fill / Responses buttons per row.
  FormDesigner  EDIT  create or edit one form (?form=<code>): name, status, version, the WQL data sources its
                      questions read, the business object it serves (an app business object or a Workday object),
                      and request framework settings (request type, business process).
  FormQuestions EDIT  the questions of one form in one editable grid (type, label, required, options, regular
                      expression and its message, lookup, prefill, show-when rule, calculation, data source and field,
                      target field, parameters, help), plus a data source -> field finder and a regex tester.
Filling a form is DynFormLookup (?form=<code>); answers show in DynFormResults (?form=<code>).

Run after build_forms.py and build_limits.py, before build_ui.py. Idempotent.
"""
import glob, json, os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
APP = os.path.join(ROOT, 'app')
PRES = os.path.join(APP, 'presentation')
MODEL = os.path.join(APP, 'model')
DOM = ["UseDynamicForms"]
FAIL = [{"code": 400}, {"code": 403}]
REF = json.load(open(os.path.join(APP, 'appManifest.json'), encoding='utf-8'))["referenceId"]


def write(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def X(expr):
    return "<% " + expr + " %>"


def esc(s):
    return s.replace("'", "")


# ---- what the app has, read at build time (the page can't list an app's own business objects) ----
BOS = []
for f in sorted(glob.glob(os.path.join(MODEL, '*.businessobject'))):
    b = json.load(open(f, encoding='utf-8'))
    if b["name"].startswith("Probe"):
        continue
    fields = ", ".join("%s (%s%s)" % (x["name"], x["type"], " to " + x["target"] if x.get("target") else "") for x in b.get("fields", []))
    BOS.append(("app:" + b["name"], "App: " + b["label"], fields))
WORKDAY = [("WORKER", "Worker"), ("SUPERVISORY_ORGANIZATION", "Supervisory Organization"), ("POSITION", "Position"),
           ("POSITION_RESTRICTIONS", "Position Restrictions"), ("LOCATION", "Location"), ("COST_CENTER", "Cost Center"),
           ("COMPANY", "Company"), ("JOB_PROFILE", "Job Profile"), ("CUSTOM_ORGANIZATION", "Custom Organization")]
TARGETS = [(i, d) for i, d, _ in BOS] + [("workday:" + i, "Workday: " + d) for i, d in WORKDAY]
BPS = [("noProcess", "None")]
for f in sorted(glob.glob(os.path.join(MODEL, '*.businessprocess'))):
    b = json.load(open(f, encoding='utf-8'))
    if not b["name"].startswith("Probe"):
        BPS.append((b["name"][0].lower() + b["name"][1:], b["label"]))
STATUSES = [("draft", "Draft"), ("approved", "Approved"), ("retired", "Retired")]
TYPES = [("text", "Text"), ("number", "Number"), ("date", "Date"), ("choice", "Choice (from Options)"),
         ("yesno", "Yes / No"), ("lookup", "Lookup (from a source)"),
         ("subform", "Sub-form here (Options = its form code; Show when = trigger)"),
         ("nextform", "Next form after OK (Options = its form code; Show when = trigger)")]
LOOKUPS = [("noLookup", "None"), ("orgs", "Supervisory organizations"), ("positions", "Positions"),
           ("workers", "Workers (search as you type)"), ("domains", "Security domains (4,000+)")]
PREFILLS = [("noPrefill", "None"), ("name", "Name"), ("title", "Business title"), ("location", "Location"),
            ("email", "Work email"), ("org", "Own organization (lookups)")]
OPS = [("eq", "equals"), ("ne", "does not equal"), ("filled", "is filled in")]


def inst(pairs):
    return [{"id": i, "descriptor": d} for i, d in pairs]


# ---- helper script: pure functions, each defined before its first caller ----
target_map = ", ".join("'%s': '%s'" % (i, esc(f) or "No fields") for i, _, f in BOS)
target_names = ", ".join("'%s': '%s'" % (i, esc(d)) for i, d in TARGETS)
SCRIPT = r'''
var tierIn = function(map, wid) {
  var t = '';
  for (var r : map ?? []) { if (('' + (r.orgWid ?? '')) == ('' + (wid ?? ''))) { t = '' + (r.tier ?? ''); } }
  t;
};

var first = function(d) {
  (d ?? []).size() > 0 ? d.get(0) : {:};
};

var txt = function(v) {
  empty(v) ? '' : '' + v;
};

var csv = function(s) {
  empty(s) ? [] : ('' + s).split(',').map(x => { x.trim() }).filter(x => { !empty(x) });
};

var dsSel = function(s) {
  csv(s).map(a => { { 'id': a, 'descriptor': a } });
};

var dsJoin = function(ids) {
  empty(ids) ? '' : ids.join(',');
};

var pickOne = function(v) {
  empty(v) ? '' : v[0];
};

var one = function(v, fallback) {
  empty(v) ? [fallback] : [v];
};

var countFor = function(rows, code) {
  var r = (rows ?? []).filter(x => { (x.formCode ?? '') == code });
  r.size() == 0 ? '0' : '' + (r.get(0)['COUNT(workdayID)'] ?? '0');
};

var targetName = function(t) {
  var m = {TARGET_NAMES};
  empty(t) ? '' : (m.get(t) ?? t);
};

var targetFields = function(t) {
  var m = {TARGET_MAP};
  empty(t) ? 'Pick a business object in Design to see its fields here.' :
    (t.startsWith('workday:') ? 'A Workday object: link an answer to it with a SINGLE_INSTANCE field that targets ' + t.substringAfter('workday:') + '.' :
      (m.get(t) ?? 'Not an app business object in this build.'));
};

var requestText = function(f) {
  (f.requestFramework ?? false) ? ('Yes' + (empty(f.requestType) ? '' : ': ' + f.requestType) + (empty(f.businessProcess) || f.businessProcess == 'noProcess' ? '' : ' (' + f.businessProcess + ')')) : 'No';
};

var dsCount = function(s) {
  csv(s).size() == 0 ? 'None' : csv(s).join(', ');
};

var dsList = function(res) {
  (res ?? []).map(x => { { 'id': x.alias ?? x.id, 'descriptor': (x.descriptor ?? '') + ' (' + (x.alias ?? '') + ')' } });
};

var dsIdList = function(res) {
  (res ?? []).map(x => { { 'id': x.id, 'descriptor': x.alias ?? x.id } });
};

var fieldList = function(res) {
  (res ?? []).map(x => { { 'id': x.alias ?? x.id, 'descriptor': (x.alias ?? '') + ' (' + (x.type ?? '') + ') ' + (x.descriptor ?? '') } });
};

var dsQuery = function(q, appOnly) {
  var s = ('' + (q ?? '')).replace('\'', '').replace('\\', '').trim();
  (appOnly == true) ? '{REF} ' + s : s;
};

var dsPick = function(res, useId) {
  (res ?? []).map(x => { { 'id': (useId ? x.id : x.alias), 'descriptor': (x.alias ?? '') + ' · ' + (empty(x.primaryBusinessObject) ? '' : (x.primaryBusinessObject.descriptor ?? '')) } });
};

var typeCode = function(t) {
  ('' + (t ?? '')).lowerCase().substringBefore(' ').substringBefore('-') + 'Type';
};

var relOf = function(x) {
  empty(x.relatedBusinessObject) ? '' : ('' + (x.relatedBusinessObject.descriptor ?? ''));
};

var fieldPick = function(res, types, rel) {
  var r = ('' + (rel ?? '')).lowerCase().trim();
  (res ?? []).filter(x => { (empty(types) || types.contains(typeCode(x.type))) && (empty(r) || relOf(x).lowerCase().contains(r)) })
    .map(x => { { 'id': x.alias ?? x.id, 'descriptor': (x.alias ?? '') + ' · ' + (x.type ?? '') + (empty(relOf(x)) ? '' : ' of ' + relOf(x)) } });
};

var targets = function(kind) {
  var all = {TARGET_LIST};
  var k = empty(kind) ? 'all' : kind[0];
  all.filter(t => { k == 'all' || (k == 'workday' ? t.id.startsWith('workday:') : !t.id.startsWith('workday:')) });
};

var tRow = function(id, desc) {
  var m = {:};
  m.put('id', id);
  m.put('descriptor', desc);
  m.put('search', (desc + ' ' + id).lowerCase());
  m.put('wd', id.startsWith('workday:'));
  m.put('app', !id.startsWith('workday:'));
  m;
};

var targetRows = function() {
  {TARGET_LIST}.map(t => { tRow(t.id, t.descriptor) });
};

var tDef = function(id, label, kind, key) {
  var m = {:};
  m.put('id', id);
  m.put('label', label);
  m.put('kind', kind);
  m.put('key', key);
  m;
};

var targetDefs = function() {
  [tDef('appObjects', 'This app\'s business objects', 'flag', 'app'), tDef('workdayObjects', 'Workday objects', 'flag', 'wd'), tDef('az', 'A to Z', 'az', '')];
};

var targetSel = function(t) {
  empty(t) ? [] : [tRow(t, targetName(t))];
};

var targetFind = function(q, kind) {
  var s = ('' + (q ?? '')).lowerCase().trim();
  targets(kind).filter(t => { empty(s) || ('' + t.descriptor).lowerCase().contains(s) || ('' + t.id).lowerCase().contains(s) });
};

var copyText = function(dsEntries, fieldId) {
  var ds = empty(dsEntries) ? '' : ('' + (dsEntries[0].descriptor ?? '')).substringBefore(' · ');
  empty(fieldId) ? (empty(ds) ? 'Pick a data source, then a field.' : 'Data source: ' + ds + '. Now pick a field.') : 'Data source: ' + ds + '   Source field: ' + fieldId[0];
};

var codeErr = function(v) {
  var s = txt(v);
  empty(s) ? '' : (s.contains(' ') ? 'No spaces: use colons, e.g. HR:LEAVE:REQUEST.' : (s.upperCase() != s ? 'Use capital letters, e.g. HR:LEAVE:REQUEST.' : ''));
};

var rxTest = function(rx, sample) {
  empty(rx) ? 'Type a regular expression and a sample answer.' : (validate:match(rx, txt(sample)) ? 'Matches: this answer would be accepted.' : 'Does not match: the fill page would show the question message.');
};

{
  "first": first, "tierIn": tierIn, "txt": txt, "csv": csv, "dsSel": dsSel, "dsJoin": dsJoin, "pickOne": pickOne, "one": one,
  "countFor": countFor, "targetName": targetName, "targetFields": targetFields, "requestText": requestText,
  "dsCount": dsCount, "dsList": dsList, "dsIdList": dsIdList, "fieldList": fieldList, "dsQuery": dsQuery, "dsPick": dsPick, "typeCode": typeCode, "relOf": relOf,
  "fieldPick": fieldPick, "targets": targets, "tRow": tRow, "targetRows": targetRows, "tDef": tDef, "targetDefs": targetDefs, "targetSel": targetSel, "targetFind": targetFind, "copyText": copyText,
  "codeErr": codeErr, "rxTest": rxTest
}
'''.replace("{TARGET_MAP}", "{" + target_map + "}").replace("{TARGET_NAMES}", "{" + target_names + "}").replace(
    "{TARGET_LIST}", "[" + ", ".join("{'id': '%s', 'descriptor': '%s'}" % (i, esc(d)) for i, d in TARGETS) + "]").replace("{REF}", REF)
with open(os.path.join(PRES, 'scripts', 'fs.script'), 'w', encoding='utf-8') as f:
    f.write(SCRIPT.lstrip())

# ---- shared furniture: hero (the toolkit's Hero card) and the Form Studio pills ----
NAV = [("FormStudio", "Forms"), ("FormDesigner", "New form"), ("DynFormLookup", "Fill a form"),
       ("DynFormResults", "Responses"), ("Home", "⌂ Home")]
write(os.path.join(PRES, 'cards', 'StudioNav.card'), {
    "id": "StudioNav", "parameters": ["activeStudio", "studioTitle"] + ["pill" + t for t, _ in NAV],
    "header": {"title": "<% studioTitle %>", "icon": "wd-accent-media-file"},
    "body": {"type": "pillCard", "pills": [
        {"label": X("activeStudio == \"" + t + "\" ? \"✓ \" + pill" + t + " : pill" + t), "taskReference": {"taskId": t}} for t, _ in NAV]}})


def top(active, title, line, chip, color, steps=None):
    nav = "<% {'activeStudio': '" + active + "', 'studioTitle': 'Form Studio', " + ", ".join("'pill" + t + "': '" + l + "'" for t, l in NAV) + "} %>"
    cards = [{"type": "card", "cardId": "Hero", "parameters": "<% {'heroTitle': '" + title + "', 'heroLine': '" + line +
              "', 'heroIcon': 'wd-accent-media-file', 'chipLabel': '" + chip + "', 'chipColor': '" + color + "'} %>"},
             {"type": "card", "cardId": "StudioNav", "parameters": nav}]
    if steps:
        cards.append({"type": "card", "cardId": "Steps", "parameters": "<% {'stepsTitle': 'Start here', 'stepsText': '" + steps + "'} %>"})
    return {"type": "cardContainer", "id": "toolsCardContainer", "layout": "grid", "cards": cards}


def about(text):
    return {"type": "fieldSet", "id": "aboutFieldSet", "title": "About", "collapsible": True, "initializeCollapsed": True,
            "children": [{"type": "richText", "id": "aboutRichText", "value": "<span style=\"color:#374151;font-size:13px\">" + text + "</span>"}]}


def col(cid, label, cell, **kw):
    c = {"type": "column", "columnId": cid, "label": label, "cellTemplate": cell}
    c.update(kw)
    return c


import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkcol import link_col


def ro(cid, value):
    return {"type": "text", "id": cid, "enabled": False, "value": value}


def wql(name, query):
    return {"name": name, "baseUrlType": "workday-wql", "authType": "sso",
            "url": X("'data?limit=1000&query=' + string:pathEncode('" + query + "')")}


FORMS_EP = {"name": "forms", "baseUrlType": "app", "url": "dynForms?limit=100", "authType": "sso", "failOnStatusCodes": FAIL}
FORM_EP = {"name": "formRec", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
           "url": X("'dynForms?limit=1&code=' + (queryParams.form ?? '').urlEncode()"), "exclude": X("empty(queryParams.form)")}
DS_SEARCH = {"name": "dsFind", "baseUrlType": "workday-wql", "authType": "sso", "deferred": True,
             "url": X("'dataSources?limit=100&searchString=' + string:pathEncode(q)")}
KINDS = [("all", "All business objects"), ("app", "This app's business objects"), ("workday", "Workday objects")]
FTYPES = [("textType", "Text"), ("numericType", "Number"), ("dateType", "Date"), ("booleanType", "Yes / No"),
          ("currencyType", "Currency"), ("singleType", "Single instance"), ("multiType", "Multi-instance")]
F = "fs.first(formRec.data ?? [])"

# ---- FormStudio: the list ----
def btn(bid, label, task, primary=False):
    return {"type": "button", "id": bid, "label": label, "action": "PRIMARY" if primary else "AUXILIARY",
            "taskReference": {"taskId": task, "parameterBindings": {"form": "<% fr.code %>"}}}


studio = {"id": "FormStudio", "securityDomains": DOM, "include": ["fs.script"],
          "endPoints": [FORMS_EP,
                        wql("qCounts", "SELECT formCode, COUNT(workdayID) FROM " + REF + "_dynQuestions GROUP BY formCode"),
                        wql("rCounts", "SELECT formCode, COUNT(workdayID) FROM " + REF + "_dynResponses GROUP BY formCode")],
          "presentation": {"pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Form Studio"},
                           "body": {"type": "section", "id": "bodySection", "children": [
                               top("FormStudio", "Form Studio", "Build forms from records: questions, rules, lookups and where the answers go. Nothing is coded per form.",
                                   "Dynamic Forms", "blue",
                                   "1. New form: name it, pick its data sources and the business object it serves. 2. Questions: add rows, types, rules and lookups. 3. Fill a form to try it, then read Responses."),
                               about("A form is a DynForm record; its questions are DynQuestion records that one fill page interprets at run time "
                                     "(a pool of question slots). Design sets the form, Questions edits its questions in one grid, Fill opens it, "
                                     "Responses lists what was saved. Limits: about 30 to 40 questions per page, 100 questions per form, "
                                     "100 records per save. Test forms start with TEST:DYN."),
                               {"type": "grid", "id": "formsGrid", "label": "Forms", "rowVariableName": "fr",
                                "render": X("(forms.data ?? []).size() > 0"),
                                "rows": X("list:sort(forms.data ?? [], 'code', true)"),
                                "columns": [
                                    link_col("codeColumn", "Code", "fr.id", "fr.code ?? ''"),
                                    col("nameColumn", "Name", ro("nameText", "<% fr.formName ?? '' %>"), sortableAndFilterable="true"),
                                    col("statusColumn", "Status", ro("statusText", "<% ['approved', 'published'].contains((fr.status ?? '').lowerCase()) ? '✓ ' + fr.status : (['retired', 'superseded'].contains((fr.status ?? '').lowerCase()) ? '✕ ' + fr.status : '○ ' + (fr.status ?? 'Draft')) %>"), sortableAndFilterable="true"),
                                    col("tierColumn", "Owner and tier", ro("tierText", "<% (fr.kind ?? '') == 'composed' ? 'Composed: ' + (fr.blocks ?? '') : ((empty(fr.ownerOrg) ? '' : ('' + fr.ownerOrg.descriptor + ', ')) + (fr.tier ?? '')) %>")),
                                    col("targetColumn", "Business object", ro("targetText", "<% fs.targetName(fr.targetObject) %>"), sortableAndFilterable="true"),
                                    col("sourcesColumn", "Data sources", ro("sourcesText", "<% fs.dsCount(fr.dataSources) %>")),
                                    col("requestColumn", "Request", ro("requestText", "<% fs.requestText(fr) %>")),
                                    col("questionsColumn", "Questions", ro("questionsCountText", "<% fs.countFor(qCounts.data, fr.code ?? '') %>")),
                                    col("responsesColumn", "Responses", ro("responsesCountText", "<% fs.countFor(rCounts.data, fr.code ?? '') %>")),
                                    col("designColumn", "Design", btn("designButton", "Design", "FormDesigner", True)),
                                    col("editQuestionsColumn", "Questions", btn("questionsButton", "Questions", "FormQuestions")),
                                    col("fillColumn", "Fill", btn("fillButton", "Fill", "DynFormLookup")),
                                    col("answersColumn", "Responses", btn("answersButton", "Responses", "DynFormResults")),
                                    col("publishColumn", "Publish", btn("publishButton", "Publish", "FormPublish"))]},
                               {"type": "fieldSet", "id": "emptyFieldSet", "title": "No forms yet", "render": X("(forms.data ?? []).size() == 0"),
                                "children": [{"type": "text", "id": "emptyText", "enabled": False, "value": "<% 'Use New form above to make the first one.' %>"}]}]}}}
write(os.path.join(PRES, 'FormStudio.pmd'), studio)

# ---- FormDesigner: one form ----
new = "empty(queryParams.form)"
designer = {"id": "FormDesigner", "securityDomains": DOM, "include": ["fs.script", "browse.script"],
            "endPoints": [FORM_EP, DS_SEARCH, {"name": "omap", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL, "url": "dynOrgMaps?limit=100"}],
            "outboundData": {"outboundEndPoints": [
                {"name": "postForm", "baseUrlType": "app", "url": "dynForms", "httpMethod": "POST", "authType": "sso",
                 "failOnStatusCodes": FAIL, "exclude": X("!empty(" + F + ".id)"), "onSend": "<% formBody() %>"},
                {"name": "patchForm", "baseUrlType": "app", "url": X("'dynForms/' + " + F + ".id"), "httpMethod": "PATCH",
                 "authType": "sso", "failOnStatusCodes": FAIL, "exclude": X("empty(" + F + ".id)"), "onSend": "<% formBody() %>"}]},
            "script": "<%\n  var formBody = function() {\n    var b = {:};\n"
                      "    b.put('code', codeText.getValue());\n"
                      "    b.put('formName', nameText.getValue());\n"
                      "    b.put('description', descriptionTextArea.getValue() ?? '');\n"
                      "    b.put('status', fs.pickOne(statusInstanceList.getValue()));\n"
                      "    b.put('version', versionNumber.getValue() ?? 1);\n"
                      "    b.put('dataSources', fs.dsJoin(dataSourcesInstanceList.getValue()));\n"
                      "    b.put('targetObject', fs.pickOne(targetInstanceList.getValue()));\n"
                      "    b.put('requestFramework', requestCheckBox.getValue() ?? false);\n"
                      "    b.put('requestType', requestTypeText.getValue() ?? '');\n"
                      "    b.put('businessProcess', fs.pickOne(processInstanceList.getValue()));\n"
                      "    if (!empty(ownerInstanceList.getValue())) { b.put('ownerOrg', { 'id': ownerInstanceList.getValue()[0] }); b.put('tier', fs.tierIn(omap.data ?? [], ownerInstanceList.getValue()[0])); }\n"
                      "    b.put('retentionMonths', retentionNumber.getValue() ?? 84);\n"
                      "    if (empty(" + F + ".id)) { b.put('origin', 'Customer'); }\n"
                      "    b;\n  };\n%>",
            "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Design a form"},
                             "cancelOverride": {"taskId": "FormStudio"},
                             "body": {"type": "section", "id": "bodySection", "children": [
                                 top("FormDesigner", "Design a form", "Name the form, pick the data its questions read and the business object or request it serves.",
                                     "Edit", "orange"),
                                 about("OK saves the form record (a new one, or the one in the address ?form=CODE). Then open Questions from Forms "
                                       "to add its questions. Data sources are WQL data sources: type part of a name to search, pick several. "
                                       "The business object is where the answers are meant to land, either one of this app's business objects "
                                       "or a Workday object linked through a SINGLE_INSTANCE field."),
                                 {"type": "fieldSet", "id": "formFieldSet", "title": "Form", "children": [
                                     {"type": "text", "id": "codeText", "label": "Code", "required": True, "enabled": X(new),
                                      "value": X(F + ".code ?? ''"),
                                      "onChange": "<% empty(fs.codeErr(self.getValue())) ? self.clearError() : self.setError(fs.codeErr(self.getValue())) %>"},
                                     {"type": "text", "id": "nameText", "label": "Name", "required": True, "value": X(F + ".formName ?? ''")},
                                     {"type": "textArea", "id": "descriptionTextArea", "label": "Description", "value": X(F + ".description ?? ''")},
                                     {"type": "instanceList", "id": "statusInstanceList", "label": "Status", "required": True,
                                      "instanceList": inst(STATUSES), "selectedValues": X("fs.one((" + F + ".status ?? 'draft').lowerCase(), 'draft')")},
                                     {"type": "number", "id": "versionNumber", "label": "Version", "value": X(F + ".version ?? 1")}]},
                                 {"type": "fieldSet", "id": "ownerFieldSet", "title": "Ownership (tiered blocks)", "children": [
                                     {"type": "instanceList", "id": "ownerInstanceList", "label": "Owner organization (sets the tier)",
                                      "values": "<% (omap.data ?? []).filter(r => { r.active != false }).map(r => { { 'id': r.orgWid, 'descriptor': (r.name ?? '') + ' (' + (r.tier ?? '') + ')' } }) %>",
                                      "selectedValuesAndDescriptors": X("empty(" + F + ".ownerOrg) ? [] : [{'id': " + F + ".ownerOrg.id, 'descriptor': " + F + ".ownerOrg.descriptor ?? ''}]")},
                                     {"type": "number", "id": "retentionNumber", "label": "Keep answers for (months)", "value": X(F + ".retentionMonths ?? 84")},
                                     {"type": "readOnlyText", "id": "ownerHelpReadOnlyText", "label": "How blocks reach people",
                                      "value": "<% 'Attach this block to a process in Block assignments (Governance), with an owner organization and scope. Publish each version from Form Studio.' %>"}]},
                                 {"type": "fieldSet", "id": "sourcesFieldSet", "title": "Where the data comes from", "children": [
                                     {"type": "instanceList", "id": "dataSourcesInstanceList", "label": "Data sources (type to search)",
                                      "multiSelect": True, "values": "<% browse.dsRoot() %>",
                                      "selectedValuesAndDescriptors": X("fs.dsSel(" + F + ".dataSources)"),
                                      "dynamicMonikerLevels": "<% if (browse.dsNoCall(self.promptSelections)) { return browse.dsLevel(self.promptSelections, [], false); } return browse.dsLevel(self.promptSelections, dsFind.invoke({'q': browse.dsLevelQuery(self.promptSelections)}).data, false); %>",
                                      "onSearch": "<% empty(event.query) ? [] : fs.dsPick(dsFind.invoke({'q': fs.dsQuery(event.query, sourcesAppOnlyCheckBox.getValue())}).data, false) %>"},
                                     {"type": "checkBox", "id": "sourcesAppOnlyCheckBox", "label": "Search only this app's data sources",
                                      "value": "<% false %>"}]},
                                 {"type": "fieldSet", "id": "usedFieldSet", "title": "Where it is used", "children": [
                                     {"type": "instanceList", "id": "targetInstanceList", "label": "Business object (click to browse or type to search)",
                                      "values": "<% browse.folderRoot(fs.targetDefs(), fs.targetRows()) %>",
                                      "selectedValuesAndDescriptors": X("fs.targetSel(" + F + ".targetObject)"),
                                      "dynamicMonikerLevels": "<% browse.folderLevel(fs.targetDefs(), fs.targetRows(), self.promptSelections) %>",
                                      "onSearch": "<% browse.folderFind(fs.targetRows(), event.query) %>"},
                                     {"type": "checkBox", "id": "requestCheckBox", "label": "Part of a request framework",
                                      "value": X(F + ".requestFramework ?? false")},
                                     {"type": "text", "id": "requestTypeText", "label": "Request type", "value": X(F + ".requestType ?? ''")},
                                     {"type": "instanceList", "id": "processInstanceList", "label": "Business process",
                                      "instanceList": inst(BPS), "selectedValues": X("fs.one(" + F + ".businessProcess, 'noProcess')")}]}]}}}
write(os.path.join(PRES, 'FormDesigner.pmd'), designer)

# ---- FormQuestions: the question grid of one form ----
def cell_out(field, expr="<% self.value %>"):
    return [{"value": expr, "valueOutBinding": "postQ." + field}, {"value": expr, "valueOutBinding": "patchQ." + field}]


def tcell(cid, field, value=None):
    return {"type": "text", "id": cid, "value": value or "<% qr." + field + " ?? '' %>", "valuesOut": cell_out(field)}


def icell(cid, field, pairs, default):
    return {"type": "instanceList", "id": cid, "instanceList": inst(pairs),
            "selectedValues": "<% [qr." + field + " ?? '" + default + "'] %>",
            "valuesOut": cell_out(field, "<% empty(self.value) ? '" + default + "' : self.value[0] %>")}


key_cell = tcell("keyText", "qKey")
key_cell["valuesOut"] += [{"value": "<% queryParams.form ?? '' %>", "valueOutBinding": "postQ.formCode"}]
CLASSES = [("general", "General"), ("confidential", "Confidential (HR only)"), ("restricted", "Restricted (named group; governance only)")]
RESETS = [("resetLocJob", "Location or job changes"), ("resetLocation", "Location changes"), ("resetJob", "Job changes"), ("resetNever", "Only when it expires")]
QCOLS = [
    col("idColumn", "ID", {"type": "text", "id": "qIdText", "enabled": False, "value": "<% qr.id ?? '' %>"}),
    col("orderColumn", "Order", {"type": "number", "id": "orderNumber", "value": "<% qr.sortOrder ?? 1 %>", "valuesOut": cell_out("sortOrder")}, required=True),
    col("keyColumn", "Key", key_cell, required=True),
    col("typeColumn", "Type", icell("typeInstanceList", "qType", TYPES, "text"), required=True),
    col("labelColumn", "Label", tcell("labelText", "qLabel"), required=True),
    col("requiredColumn", "Required", {"type": "checkBox", "id": "requiredCheckBox", "value": "<% qr.required ?? false %>",
                                       "valuesOut": cell_out("required", "<% self.value ?? false %>")}),
    col("optionsColumn", "Options (a=A|b=B)", tcell("optionsText", "qOptions")),
    col("regexColumn", "Regular expression", tcell("regexText", "regex")),
    col("regexMessageColumn", "Message if no match", tcell("regexMessageText", "regexMessage")),
    col("lookupColumn", "Lookup", icell("lookupInstanceList", "lookup", LOOKUPS, "noLookup")),
    col("prefillColumn", "Prefill", icell("prefillInstanceList", "prefill", PREFILLS, "noPrefill")),
    col("showKeyColumn", "Show when key", tcell("showKeyText", "showKey")),
    col("showOpColumn", "is", icell("showOpInstanceList", "showOp", OPS, "eq")),
    col("showValueColumn", "value", tcell("showValueText", "showValue")),
    col("calcColumn", "Calculation (sum:a,b)", tcell("calcText", "calc")),
    col("dataSourceColumn", "Data source", tcell("dataSourceText", "dataSource")),
    col("sourceFieldColumn", "Source field", tcell("sourceFieldText", "sourceField")),
    col("targetFieldColumn", "Target field", tcell("targetFieldText", "targetField")),
    col("paramsColumn", "Parameters (k=v;k=v)", tcell("paramsText", "params")),
    col("helpColumn", "Help", tcell("helpText", "help")),
    # tiered ownership (2026-11-20): storage class, shared library key, reuse
    col("classColumn", "Classification", icell("classInstanceList", "classification", CLASSES, "general")),
    col("libraryColumn", "Library key", tcell("libraryText", "libraryKey")),
    col("reusableColumn", "Reusable", {"type": "checkBox", "id": "reusableCheckBox", "value": "<% qr.reusable ?? false %>",
                                       "valuesOut": cell_out("reusable", "<% self.value ?? false %>")}),
    col("validColumn", "Valid for months", {"type": "number", "id": "validNumber", "value": "<% qr.validMonths ?? 12 %>", "valuesOut": cell_out("validMonths")}),
    col("resetsColumn", "Resets when", icell("resetsInstanceList", "resetsWhen", RESETS, "resetLocJob")),
]
QS_EP = {"name": "qs", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
         "url": X("'dynQuestions?limit=100&formCode=' + (queryParams.form ?? '').urlEncode()"), "exclude": X("empty(queryParams.form)")}
FIELDS_EP = {"name": "fieldFind", "baseUrlType": "workday-wql", "authType": "sso", "deferred": True,
             "url": X("'dataSources/' + string:pathEncode(ds) + '/fields?limit=100&searchString=' + string:pathEncode(q)")}
DS_ID_SEARCH = DS_SEARCH
FIELDS_PAGE = {"name": "fieldsPage", "baseUrlType": "workday-wql", "authType": "sso", "deferred": True,
               "url": X("'dataSources/' + ds + '/fields?limit=100&offset=' + off")}
FINDER_SCRIPT = ("<%\n  var loadFinder = function() {\n"
                 "    finderReadOnlyText.setValue(fs.copyText(finderSourceInstanceList.selectedEntries, []));\n"
                 "    if (empty(finderSourceInstanceList.getValue())) {\n      finderStoreText.setValue('');\n"
                 "      finderLoadedReadOnlyText.setValue('Pick a data source to browse its fields.');\n    } else {\n"
                 "      var ds = string:pathEncode(finderSourceInstanceList.getValue()[0]);\n"
                 "      var first = fieldsPage.invoke({'ds': ds, 'off': '0'});\n      var all = first.data ?? [];\n"
                 "      var total = first.total ?? all.size();\n"
                 "      for (var o : [100, 200, 300, 400]) {\n        if (o < total) { all = list:flatten([all, (fieldsPage.invoke({'ds': ds, 'off': '' + o}).data ?? [])]); }\n      }\n"
                 "      finderStoreText.setValue(browse.fieldPack(all));\n"
                 "      finderLoadedReadOnlyText.setValue('' + all.size() + ' of ' + total + ' fields in the folders' + (all.size() < total ? '; typing searches all of them.' : '.'));\n"
                 "    }\n  };\n%>")
questions = {"id": "FormQuestions", "securityDomains": DOM, "include": ["fs.script", "browse.script"], "script": FINDER_SCRIPT,
             "endPoints": [FORM_EP, QS_EP, DS_ID_SEARCH, FIELDS_EP, FIELDS_PAGE],
             "outboundData": {"outboundEndPoints": [
                 {"name": "postQ", "baseUrlType": "app", "url": "dynQuestions", "httpMethod": "POST", "authType": "sso",
                  "failOnStatusCodes": FAIL, "exclude": "<% !empty(qIdText.value) || (fs.first(formRec.data ?? []).status ?? '') == 'Published' %>"},
                 {"name": "patchQ", "baseUrlType": "app", "url": "<% 'dynQuestions/' + qIdText.value %>", "httpMethod": "PATCH",
                  "authType": "sso", "failOnStatusCodes": FAIL, "exclude": "<% empty(qIdText.value) || (fs.first(formRec.data ?? []).status ?? '') == 'Published' %>"},
                 {"name": "deleteQ", "baseUrlType": "app", "url": "<% 'dynQuestions/' + qIdText.value %>", "httpMethod": "DELETE",
                  "authType": "sso", "exclude": "<% (fs.first(formRec.data ?? []).status ?? '') == 'Published' %>"}]},
             "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Form questions"},
                              "cancelOverride": {"taskId": "FormStudio"},
                              "body": {"type": "section", "id": "bodySection", "children": [
                                  top("FormStudio", "Form questions", "Every question of one form in one grid: add, change or remove rows, then OK.",
                                      "Edit", "orange"),
                                  about("Open this from Forms (Questions). + adds a row, the bin removes one; OK saves every row (new rows are created, "
                                        "changed rows updated, removed rows deleted). Order sets the position on the fill page. "
                                        "Type Lookup reads its options from the Lookup source. A regular expression is checked as the person types "
                                        "(text questions), and its message shows when the answer does not match. Show when hides the question until "
                                        "another key has that value. Data source, Source field, Target field and Parameters record where the "
                                        "answer comes from and goes; use the finder below to look up names."),
                                  {"type": "fieldSet", "id": "formFieldSet", "title": "Form", "children": [
                                      {"type": "readOnlyText", "id": "formReadOnlyText", "label": "Form",
                                       "value": X("empty(queryParams.form) ? 'Open this page from Forms: no form in the address.' : (queryParams.form + '  ' + (" + F + ".formName ?? '(not found)'))")},
                                      {"type": "readOnlyText", "id": "publishedReadOnlyText", "label": "Editing",
                                       "value": X("(fs.first(formRec.data ?? []).status ?? '') == 'Published' ? 'This version is published and read only: OK saves nothing. Copy it to a new version (Copy, version or import) to change it.' : 'Draft: changes are saved on OK.'")},
                                      {"type": "readOnlyText", "id": "targetReadOnlyText", "label": "Business object",
                                       "value": X("fs.targetName(" + F + ".targetObject)")},
                                      {"type": "readOnlyText", "id": "targetFieldsReadOnlyText", "label": "Its fields (for Target field)",
                                       "value": X("fs.targetFields(" + F + ".targetObject)")},
                                      {"type": "readOnlyText", "id": "sourcesReadOnlyText", "label": "Form data sources",
                                       "value": X("fs.dsCount(" + F + ".dataSources)")}]},
                                  {"type": "fieldSet", "id": "finderFieldSet", "title": "Find a data source field", "collapsible": True,
                                   "initializeCollapsed": True, "children": [
                                      {"type": "checkBox", "id": "finderAppOnlyCheckBox", "label": "Search only this app's data sources",
                                       "value": "<% false %>"},
                                      {"type": "instanceList", "id": "finderSourceInstanceList", "label": "Data source (click to browse or type to search)",
                                       "values": "<% browse.dsRoot() %>",
                                       "dynamicMonikerLevels": "<% if (browse.dsNoCall(self.promptSelections)) { return browse.dsLevel(self.promptSelections, [], true); } return browse.dsLevel(self.promptSelections, dsFind.invoke({'q': browse.dsLevelQuery(self.promptSelections)}).data, true); %>",
                                       "onSearch": "<% empty(event.query) ? [] : fs.dsPick(dsFind.invoke({'q': fs.dsQuery(event.query, finderAppOnlyCheckBox.getValue())}).data, true) %>",
                                       "onChange": "<% loadFinder() %>"},
                                      {"type": "readOnlyText", "id": "finderLoadedReadOnlyText", "label": "Fields",
                                       "value": "<% 'Pick a data source to browse its fields.' %>"},
                                      {"type": "text", "id": "finderStoreText", "label": "Loaded fields", "visible": False, "value": "<% '' %>"},
                                      {"type": "instanceList", "id": "finderTypeInstanceList", "label": "Field types (none picked: all)",
                                       "multiSelect": True, "instanceList": inst(FTYPES)},
                                      {"type": "text", "id": "finderRelatedText", "label": "Instance of (part of a business object name)"},
                                      {"type": "instanceList", "id": "finderFieldInstanceList", "label": "Field (click to browse or type to search)",
                                       "values": "<% browse.folderRoot(browse.fieldDefs(), []) %>",
                                       "dynamicMonikerLevels": "<% browse.folderLevel(browse.fieldDefs(), browse.fieldFilter(browse.fieldRows(finderStoreText.getValue()), finderTypeInstanceList.getValue(), finderRelatedText.getValue()), self.promptSelections) %>",
                                       "onSearch": "<% (empty(event.query) || empty(finderSourceInstanceList.getValue())) ? [] : fs.fieldPick(fieldFind.invoke({'ds': finderSourceInstanceList.getValue()[0], 'q': fs.dsQuery(event.query, false)}).data, finderTypeInstanceList.getValue(), finderRelatedText.getValue()) %>",
                                       "onChange": "<% finderReadOnlyText.setValue(fs.copyText(finderSourceInstanceList.selectedEntries, self.value)) %>"},
                                      {"type": "readOnlyText", "id": "finderReadOnlyText", "label": "Copy into the grid",
                                       "value": "<% 'Pick a data source, then a field.' %>"}]},
                                  {"type": "fieldSet", "id": "regexFieldSet", "title": "Try a regular expression", "collapsible": True,
                                   "initializeCollapsed": True, "children": [
                                      {"type": "text", "id": "regexTryText", "label": "Regular expression",
                                       "onChange": "<% regexResultReadOnlyText.setValue(fs.rxTest(self.getValue(), sampleText.getValue())) %>"},
                                      {"type": "text", "id": "sampleText", "label": "Sample answer",
                                       "onChange": "<% regexResultReadOnlyText.setValue(fs.rxTest(regexTryText.getValue(), self.getValue())) %>"},
                                      {"type": "readOnlyText", "id": "regexResultReadOnlyText", "label": "Result",
                                       "value": "<% 'Type a regular expression and a sample answer.' %>"}]},
                                  {"type": "grid", "id": "questionsGrid", "label": "Questions", "rowVariableName": "qr",
                                   "deleteEndPoint": "deleteQ", "columns": QCOLS,
                                   "rows": X("list:sort(qs.data ?? [], 'sortOrder', true)")}]}}}
write(os.path.join(PRES, 'FormQuestions.pmd'), questions)

# FormOpen: opened from a form record's related actions ("Open Form"); the four Studio actions for that form.
def _btn(bid, label, task, action="AUXILIARY"):
    return {"type": "button", "id": bid, "label": label, "action": action,
            "taskReference": {"taskId": task, "parameterBindings": {"form": "<% rec.code ?? '' %>"}}}


form_open = {"id": "FormOpen", "securityDomains": DOM, "endPoints": [
    {"name": "rec", "baseUrlType": "app", "authType": "sso", "failOnStatusCodes": FAIL,
     "url": "<% 'dynForms/' + (queryParams.taskObjectId ?? '') %>"}],
    "presentation": {"pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Open a form"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "formFieldSet", "title": "Form", "children": [
                             {"type": "text", "id": "codeText", "label": "Code", "enabled": False, "value": "<% rec.code ?? '' %>"},
                             {"type": "text", "id": "nameText", "label": "Name", "enabled": False, "value": "<% rec.formName ?? '' %>"},
                             {"type": "text", "id": "statusText", "label": "Status", "enabled": False, "value": "<% rec.status ?? '' %>"},
                             _btn("fillButton", "Fill this form", "DynFormLookup", "PRIMARY"),
                             _btn("designButton", "Design", "FormDesigner"),
                             _btn("questionsButton", "Questions", "FormQuestions"),
                             _btn("responsesButton", "Responses", "DynFormResults")]}]}}}
write(os.path.join(PRES, 'FormOpen.pmd'), form_open)
write(os.path.join(MODEL, 'OpenForm.task'), {"id": 11, "name": "OpenForm", "label": "Open Form", "securityDomains": DOM,
                                             "businessObject": "DynForm", "routePath": "/formOpen/{taskObjectId}"})

# ---- AMD: tasks and flows (OK goes back to Forms) ----
amd_path = glob.glob(os.path.join(PRES, '*.amd'))[0]
amd = json.load(open(amd_path, encoding='utf-8'))
have = {t["id"] for t in amd["tasks"]}
for pid in ["FormStudio", "FormDesigner", "FormQuestions"]:
    if pid not in have:
        amd["tasks"].append({"id": pid, "routingPattern": "/" + pid[0].lower() + pid[1:], "page": {"id": pid}})
if "FormOpen" not in have:
    amd["tasks"].append({"id": "FormOpen", "routingPattern": "/formOpen/{taskObjectId}", "page": {"id": "FormOpen"}})
flows = [f for f in amd.get("flowDefinitions", []) if f["id"] not in ("formDesignerFlow", "formQuestionsFlow")]
for pid in ["FormDesigner", "FormQuestions"]:
    fid = pid[0].lower() + pid[1:] + "Flow"
    flows.append({"id": fid, "flowSteps": [
        {"id": fid + "Start", "taskId": pid, "startsFlow": True,
         "transitions": [{"order": "a", "value": fid + "End", "condition": "<% true %>"}]},
        {"id": fid + "End", "taskId": "FormStudio", "endsFlow": True}]})
amd["flowDefinitions"] = flows
write(amd_path, amd)
print('form studio: FormStudio, FormDesigner, FormQuestions; %d business objects, %d targets' % (len(BOS), len(TARGETS)))
