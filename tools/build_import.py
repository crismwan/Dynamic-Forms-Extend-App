#!/usr/bin/env python3
"""Builds DynFormImport: copy every form definition (dynForms + dynQuestions) from another app's forms objects into this
app. It reads the source through WQL (data sources <sourceApp>_dynForms / _dynQuestions), which works across apps for a
user with the source app's domain, where the source app's REST API does not (a page can't read another app's business
objects). Forms already here (same code and version) are skipped, and so are their questions; so a rerun adds nothing.
Questions go in bulk POSTs of up to 100 (12 endpoints = 1,200 questions).
Added 2026-11-19 to move the forms out of the Extend Toolkit app.
"""
import json, os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
APP = os.path.join(ROOT, 'app')
DOM = ["UseDynamicForms"]
FAIL = [{"code": 400}, {"code": 403}]
SOURCE = "developertoolkitappv1_kwswrv"
# the fields the source app (Extend Toolkit) has: later fields (tiered ownership, 2026-11-20) exist only here
FORM_FIELDS = [f["name"] for f in json.load(open(os.path.join(APP, 'model', 'DynForm.businessobject')))["fields"] if f["id"] <= 15]
Q_FIELDS = [f["name"] for f in json.load(open(os.path.join(APP, 'model', 'DynQuestion.businessobject')))["fields"] if f["id"] <= 22]
INTS = {"version", "sortOrder"}
BOOLS = {"requestFramework", "required", "confidential"}
CHUNKS = 12
# Only the onboarding forms belong in this app (user, 2026-11-19): TEST:DYN:ADDR (all versions) and TEST:DYN:SW (its
# alsoAssign extra form). Import copies only these; DynFormPrune deletes every other form and question here.
KEEP = ["TEST:DYN:ADDR", "TEST:DYN:SW"]
KEEPS = "|" + "|".join(KEEP) + "|"


def wql(name, query):
    return {"name": name, "baseUrlType": "workday-wql", "authType": "sso", "failOnStatusCodes": FAIL,
            "url": "<% 'data?limit=10000&query=' + string:pathEncode('" + query + "') %>"}


def mapper(fields):
    parts = []
    for f in fields:
        if f in INTS:
            parts.append(f"if (!empty(r.{f})) {{ m.{f} = ('' + r.{f}).substringBefore('.').toInt(); }}")
        elif f in BOOLS:
            parts.append(f"m.{f} = ('' + (r.{f} ?? false)) == 'true';")
        else:
            parts.append(f"if (!empty(r.{f})) {{ m.{f} = '' + r.{f}; }}")
    return " ".join(parts)


KEEPFN = ("var keep = function(c) { '" + KEEPS + "'.contains('|' + ('' + (c ?? '')).substringBefore('@') + '|'); }; ")
SCRIPT = ("<% " + KEEPFN + "var have = function() { '|' + (mine.data ?? []).map(f => { (f.code ?? '') + '#' + (f.version ?? '') }).join('|') + '|'; }; "
          "var keyOf = function(r) { (r.code ?? '') + '#' + ('' + (r.version ?? '')).substringBefore('.'); }; "
          "var newForms = function() { var h = have(); (srcForms.data ?? []).filter(r => { !h.contains('|' + keyOf(r) + '|') && keep(r.code) }); }; "
          "var haveCodes = function() { '|' + (mineQ.data ?? []).map(q => { q.formCode ?? '' }).distinct().join('|') + '|'; }; "
          "var newQs = function() { var h = haveCodes(); (srcQs.data ?? []).filter(r => { !h.contains('|' + (r.formCode ?? '') + '|') && keep(r.formCode) }); }; "
          "var formRow = function(r) { var m = {:}; " + mapper(FORM_FIELDS) + " m.copiedFrom = 'import:" + SOURCE + "'; m; }; "
          "var qRow = function(r) { var m = {:}; " + mapper(Q_FIELDS) + " m; }; "
          "var chunk = function(i) { var all = newQs(); var a = i * 100; a >= all.size() ? [] : all.subList(a, (a + 100) > all.size() ? all.size() : (a + 100)).map(r => { qRow(r) }); }; %>")

outbound = [{"name": "postForms", "baseUrlType": "app", "url": "dynForms?bulk=true", "httpMethod": "POST", "authType": "sso",
             "failOnStatusCodes": FAIL, "exclude": "<% newForms().size() == 0 %>",
             "onSend": "<% self.data = {:}; self.data.data = newForms().map(r => { formRow(r) }); self.data; %>"}]
for i in range(CHUNKS):
    outbound.append({"name": f"postQuestions{i + 1}", "baseUrlType": "app", "url": "dynQuestions?bulk=true", "httpMethod": "POST",
                     "authType": "sso", "failOnStatusCodes": FAIL, "exclude": f"<% newQs().size() <= {i * 100} %>",
                     "onSend": f"<% self.data = {{:}}; self.data.data = chunk({i}); self.data; %>"})

page = {"id": "DynFormImport", "securityDomains": DOM, "script": SCRIPT, "endPoints": [
    wql("srcForms", "SELECT workdayID, " + ", ".join(FORM_FIELDS) + " FROM " + SOURCE + "_dynForms"),
    wql("srcQs", "SELECT workdayID, " + ", ".join(Q_FIELDS) + " FROM " + SOURCE + "_dynQuestions"),
    {"name": "mine", "baseUrlType": "app", "url": "dynForms?limit=100", "authType": "sso", "failOnStatusCodes": FAIL},
    wql("mineQ", "SELECT formCode FROM ' + '" + json.load(open(os.path.join(APP, 'appManifest.json')))["referenceId"] + "_dynQuestions")],
    "outboundData": {"outboundEndPoints": outbound},
    "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Import forms from another app"},
                     "cancelOverride": {"taskId": "Home"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "importFieldSet", "title": "What OK will copy", "children": [
                             {"type": "text", "id": "sourceText", "label": "From app", "enabled": False, "value": "<% '" + SOURCE + "' %>"},
                             {"type": "text", "id": "formsText", "label": "Forms to copy", "enabled": False,
                              "value": "<% '' + newForms().size() + ' of ' + (srcForms.data ?? []).size() + ' (the rest are here already)' %>"},
                             {"type": "text", "id": "questionsText", "label": "Questions to copy", "enabled": False,
                              "value": "<% '' + newQs().size() + ' of ' + (srcQs.data ?? []).size() + (newQs().size() > " + str(CHUNKS * 100) + " ? ' (over the limit: run it again after OK)' : '') %>"},
                             {"type": "text", "id": "codesText", "label": "Form codes", "enabled": False,
                              "value": "<% newForms().map(r => { keyOf(r) }).join(', ') %>"}]}]}}}

path = os.path.join(APP, 'presentation', 'DynFormImport.pmd')
open(path, 'w', encoding='utf-8').write(json.dumps(page, indent=2, ensure_ascii=False) + '\n')

amd_path = [os.path.join(APP, 'presentation', f) for f in os.listdir(os.path.join(APP, 'presentation')) if f.endswith('.amd')][0]
amd = json.load(open(amd_path, encoding='utf-8'))
if not any(t["id"] == "DynFormImport" for t in amd["tasks"]):
    amd["tasks"].append({"id": "DynFormImport", "routingPattern": "/dynFormImport", "page": {"id": "DynFormImport"}})
    open(amd_path, 'w', encoding='utf-8').write(json.dumps(amd, indent=2, ensure_ascii=False) + '\n')
APPREF = json.load(open(os.path.join(APP, 'appManifest.json')))["referenceId"]
PSCRIPT = ("<% " + KEEPFN +
           "var allQs = function() { list:flatten([ownQs0.data ?? [], ownQs1.data ?? [], ownQs2.data ?? []]); }; "
           "var dropForms = function() { (ownForms.data ?? []).filter(r => { !keep(r.code) }); }; "
           "var dropQs = function() { allQs().filter(r => { !keep(r.formCode) }); }; "
           "var ids = function(l) { l.map(r => { r.id }).join(','); }; "
           "var part = function(i) { var all = dropQs(); var a = i * 100; a >= all.size() ? '' : ids(all.subList(a, (a + 100) > all.size() ? all.size() : (a + 100))); }; %>")
prune = {"id": "DynFormPrune", "securityDomains": DOM, "script": PSCRIPT, "endPoints": [
    {"name": "ownForms", "baseUrlType": "app", "url": "dynForms?limit=100", "authType": "sso", "failOnStatusCodes": FAIL},
    {"name": "ownQs0", "baseUrlType": "app", "url": "dynQuestions?limit=100", "authType": "sso", "failOnStatusCodes": FAIL},
    {"name": "ownQs1", "baseUrlType": "app", "url": "dynQuestions?limit=100&offset=100", "authType": "sso"},
    {"name": "ownQs2", "baseUrlType": "app", "url": "dynQuestions?limit=100&offset=200", "authType": "sso"}],
    "outboundData": {"outboundEndPoints": [
        {"name": "launchPrune", "baseUrlType": "orchestrate", "url": "/FormPrune/launch", "httpMethod": "POST", "authType": "sso",
         "failOnStatusCodes": FAIL, "exclude": "<% dropForms().size() + dropQs().size() == 0 %>",
         "onSend": "<% self.data = {:}; self.data.forms = ids(dropForms()); self.data.q1 = part(0); self.data.q2 = part(1); self.data.q3 = part(2); self.data; %>"}]},
    "presentation": {"pageType": "EDIT", "title": {"type": "title", "id": "pageTitle", "label": "Keep only the onboarding forms"},
                     "cancelOverride": {"taskId": "Home"},
                     "body": {"type": "section", "id": "bodySection", "children": [
                         {"type": "fieldSet", "id": "pruneFieldSet", "title": "What OK will delete", "children": [
                             {"type": "text", "id": "keepText", "label": "Kept", "enabled": False, "value": "<% '" + ", ".join(KEEP) + " (every version)' %>"},
                             {"type": "text", "id": "dropFormsText", "label": "Forms to delete", "enabled": False,
                              "value": "<% '' + dropForms().size() + ' of ' + (ownForms.data ?? []).size() %>"},
                             {"type": "text", "id": "dropQsText", "label": "Questions to delete", "enabled": False,
                              "value": "<% '' + dropQs().size() + ' of ' + allQs().size() + (allQs().size() >= 300 ? ' (300 read: run it again after OK)' : '') %>"},
                             {"type": "text", "id": "dropCodesText", "label": "Form codes", "enabled": False,
                              "value": "<% dropForms().map(r => { (r.code ?? '') + '@' + ('' + (r.version ?? '')).substringBefore('.') }).join(', ') %>"}]}]}}}
open(os.path.join(APP, 'presentation', 'DynFormPrune.pmd'), 'w', encoding='utf-8').write(json.dumps(prune, indent=2, ensure_ascii=False) + '\n')
amd = json.load(open(amd_path, encoding='utf-8'))
if not any(t["id"] == "DynFormPrune" for t in amd["tasks"]):
    amd["tasks"].append({"id": "DynFormPrune", "routingPattern": "/dynFormPrune", "page": {"id": "DynFormPrune"}})
    open(amd_path, 'w', encoding='utf-8').write(json.dumps(amd, indent=2, ensure_ascii=False) + '\n')
print('DynFormImport and DynFormPrune pages')
