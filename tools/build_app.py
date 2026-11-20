#!/usr/bin/env python3
"""Builds the Dynamic Forms app's own frame: the security domain, the Home hub (and its model task), the shared Hero
and Steps cards, the error page with its SMD mappings, the forms orchestrations (tools/forms_flows.py) and the AMD's
tasks and data providers. Run it first (CI does):
  python3 tools/build_app.py && python3 tools/build_browse.py && python3 tools/build_forms.py \
    && python3 tools/build_studio.py && python3 tools/build_labels.py
Moved out of the Extend Toolkit app on 2026-11-19 (the toolkit had reached Extend's model limits for the plan).
"""
import glob, json, os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
APP = os.path.join(ROOT, 'app')
PRES = os.path.join(APP, 'presentation')
MODEL = os.path.join(APP, 'model')
ORCH = os.path.join(APP, 'orchestration')
DOM = ["UseDynamicForms"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forms_flows


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


# ---- model: the app's domain and the Home task ----
write(os.path.join(MODEL, 'UseDynamicForms.securitydomain'), {
    "id": 1, "name": "UseDynamicForms", "label": "Use: Dynamic Forms",
    "enabledForPageSecurity": True, "enabledForOrchestrationSecurity": True})
write(os.path.join(MODEL, 'Home.task'), {"id": 2, "name": "Home", "label": "Dynamic Forms", "securityDomains": DOM,
                                         "routePath": "/"})

# ---- orchestrations ----
forms_flows.write_forms(write, ORCH, DOM)

# ---- shared cards ----
write(os.path.join(PRES, 'cards', 'Hero.card'), {
    "id": "Hero", "parameters": ["heroTitle", "heroLine", "heroIcon", "chipLabel", "chipColor"],
    "header": {"title": "<% heroTitle %>", "icon": "<% heroIcon ?: null %>",
               "indicator": {"label": "<% chipLabel ?: null %>", "color": "<% chipColor ?: null %>"}},
    "body": {"type": "simpleCard", "value": "<% heroLine %>"}})
write(os.path.join(PRES, 'cards', 'Steps.card'), {
    "id": "Steps", "parameters": ["stepsTitle", "stepsText"],
    "header": {"title": "<% stepsTitle %>", "icon": "wd-accent-resources"},
    "body": {"type": "simpleCard", "value": "<% stepsText %>"}})

# ---- Home: a hub. Hub items open VIEW pages only (CLAUDE.md, hub widget); EDIT pages are additional links. ----
nav = [
    {"type": "item", "label": "Form Studio", "icon": "wd-icon-folder-close", "task": {"taskId": "FormStudio"}},
    {"type": "item", "label": "Results", "icon": "wd-icon-document", "task": {"taskId": "DynFormResults"}},
    {"type": "item", "label": "My Forms to Fill", "icon": "wd-icon-checkboxes", "task": {"taskId": "DynMyForms"}},
]
links = [("Fill a form", "DynFormLookup"), ("Design a form", "FormDesigner"), ("Copy, version or import", "DynFormCopy"),
         ("Seed test forms", "DynFormSeed"), ("Bulk test", "DynFormBulk")]
write(os.path.join(PRES, 'Home.pmd'), {"id": "Home", "securityDomains": DOM, "presentation": {
    "pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Dynamic Forms"},
    "body": {"type": "hub", "id": "formsHub", "label": "Dynamic Forms", "icon": "wd-accent-clipboard-checklist",
             "initialTask": {"taskId": "FormStudio"}, "navigationTasks": nav,
             "additionalLinks": {"title": "More", "links": [
                 {"type": "task", "label": l, "task": {"taskId": t}} for l, t in links]}}}})

# ---- error page (a page with no securityDomains loads for anyone, so people without access can read why) ----
ERROR_TEXT = {
    "401": "Your Workday session has ended. Sign in again, then reopen the page.",
    "403": "You do not have access to this page. Dynamic Forms needs the security domain Use: Dynamic Forms "
           "(or Dyn Forms Fill for My Forms): ask your security administrator.",
    "404": "That page does not exist in this app. It may have been renamed: open Dynamic Forms from the search.",
    "500": "Workday could not load this page. Try again; if it happens again, note the time and tell the forms team.",
}


def line(code, text):
    return {"type": "text", "id": f"error{code}Text", "enabled": False, "label": code, "value": f"<% '{text}' %>",
            "visible": f"<% queryParams.errorCode == '{code}' %>"}


general = {"type": "text", "id": "errorGeneralText", "enabled": False, "label": "What happened",
           "value": "<% 'The page could not be shown. 403 usually means a missing security domain (Use: Dynamic Forms); "
                    "404 a page that does not exist; 500 a Workday error.' %>",
           "visible": "<% empty(queryParams.errorCode) || !['401', '403', '404', '500'].contains(queryParams.errorCode) %>"}
write(os.path.join(PRES, 'ErrorPage.pmd'), {"id": "ErrorPage", "presentation": {
    "pageType": "VIEW", "title": {"type": "title", "id": "pageTitle", "label": "Something went wrong"},
    "body": {"type": "section", "id": "bodySection", "children": [
        {"type": "cardContainer", "id": "heroCardContainer", "layout": "grid", "cards": [{"type": "card", "cardId": "Hero",
         "parameters": "<% {'heroTitle': 'Something went wrong', 'heroLine': 'The page could not be shown. The reason is below.', 'heroIcon': 'wd-accent-data-refresh', 'chipLabel': empty(queryParams.errorCode) ? 'Error' : ('Error ' + queryParams.errorCode), 'chipColor': 'red'} %>"}]},
        {"type": "section", "id": "homeLinkSection", "children": [
            {"type": "button", "id": "homeButton", "label": "Back to Home", "action": "PRIMARY", "taskReference": {"taskId": "Home"}}]},
        {"type": "fieldSet", "id": "errorFieldSet", "title": "What happened",
         "children": [general] + [line(c, t) for c, t in ERROR_TEXT.items()]}]}}})

# ---- AMD: keep only tasks whose page exists; Home and ErrorPage; data providers ----
amd_path = glob.glob(os.path.join(PRES, '*.amd'))[0]
amd = json.load(open(amd_path, encoding='utf-8'))
pages = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(PRES, '*.pmd'))}
pages |= {"DynFormFill", "DynFormBigLoop", "DynFormSeed", "DynFormResults", "DynFormLookup", "FormStudio", "FormDesigner",
          "FormQuestions", "DynFormNext", "FormOpen", "DynFormCopy", "DynFormBulk", "DynMyForms", "DynMyFill"}
amd["tasks"] = [t for t in amd["tasks"] if t["page"]["id"] in pages or t["page"]["id"].startswith(("Dyn", "Form"))]
for tid, route in (("Home", "/"), ("ErrorPage", "/errorPage")):
    if not any(t["id"] == tid for t in amd["tasks"]):
        amd["tasks"].append({"id": tid, "routingPattern": route, "page": {"id": tid}})
amd["flowDefinitions"] = [f for f in amd.get("flowDefinitions", [])
                          if all(s["taskId"].startswith(("Dyn", "Form")) for s in f["flowSteps"])]
for key, value in (("orchestrate", "<% `{{apiGatewayEndpoint}}/orchestrate/v1/apps/{{site.applicationId}}/orchestrations` %>"),
                   ("app", "<% `{{apiGatewayEndpoint}}/apps/{{site.applicationId}}/v1/` %>")):
    if not any(d["key"] == key for d in amd["dataProviders"]):
        amd["dataProviders"].append({"key": key, "value": value})
write(amd_path, amd)

smd_path = glob.glob(os.path.join(PRES, '*.smd'))[0]
smd = json.load(open(smd_path, encoding='utf-8'))
smd["errorPageConfigurations"] = [{"statusCode": c, "page": {"id": "ErrorPage"}} for c in ERROR_TEXT]
write(smd_path, smd)
print('app frame: domain, Home hub, cards, ErrorPage, orchestrations, AMD')
