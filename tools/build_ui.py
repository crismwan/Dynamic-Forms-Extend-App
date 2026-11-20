#!/usr/bin/env python3
"""Shared UI pass (Wave 1 of docs/UI recommendations), run after the page builders and before build_labels.py:

- writes the Tools pill card (presentation/cards/Tools.card) and puts it first on every tool page,
  with a tick on the page you are on;
- makes each page's About box collapsible, starting closed;
- adds field help (guide) to the inputs that confuse;
- writes the error page (ErrorPage.pmd), its AMD task and the SMD error mappings.

Idempotent: running it twice gives the same files. Run: python3 tools/build_ui.py
"""
import glob, json, os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
PRES = os.path.join(ROOT, 'app', 'presentation')

# (task id, pill label) in the order the pills show.
# One order everywhere (pills, Overview tiles, hub links), by job: explore data, check this tenant, learn
# (navigation review 2026-11-16). Ten pills is the pillCard maximum, Home included.
TOOLS = [("Workbench", "WQL Workbench"), ("Explorer", "REST Explorer"),
         ("Apps", "Installed Apps"), ("AppList", "App List"), ("Integrations", "Integrations"), ("Readiness", "Readiness"),
         ("Errors", "Known Errors"), ("Cookbook", "Cookbook"), ("LabOverview", "Tested Live")]
LAB = ["LabButtons", "LabScript", "LabGridJoin", "LabAuditLog", "LabAuditWrite", "LabItems", "LabItemsEdit",
       "LabOrchestration", "LabFiles", "LabFileUpload", "LabEvents"]
PILLS = [("Home", "\u2302 Home")] + TOOLS
PAGES = ["Toolkit"] + [t for t, _ in TOOLS] + LAB
CURRENT = {d: "LabOverview" for d in LAB}   # pages that aren't a tool mark the tool they belong to

# Hero card at the top of each page (UI round 2, wave 7): (icon, title, one line, chip label, chip colour).
# One icon per tool, used everywhere (docs: "Developer Toolkit: UI Recommendations, Round 2"). No apostrophes:
# the text goes into a single-quoted map in the page.
HERO = {
    "Toolkit": ("toolbox", "Developer Toolkit", "Read-only tools for building, checking and moving Workday Extend apps.", "Read only", "green"),
    "Workbench": ("worksheets", "WQL Workbench", "Write and run WQL as yourself, browse data sources and fields, and copy a query as endpoint JSON.", "Read only", "green"),
    "Readiness": ("gauge", "Tenant Readiness and App Health", "Check a tenant before you move an app into it, and test the data calls an app makes.", "Read only", "green"),
    "Apps": ("circuit-board", "Installed Apps", "Every Extend app deployed here: its domains, business objects, business processes and who they reach.", "Read only", "green"),
    "AppList": ("clipboard-checklist", "App List", "All installed apps in one grid to sort, filter and export to Excel.", "Read only", "green"),
    "Explorer": ("radio-tower", "REST Explorer", "Call a Workday REST GET or a Graph query and copy it as endpoint JSON.", "Read only", "green"),
    "Integrations": ("electric-plug", "Integrations", "Every integration system here: EIB, Studio or connector, its schedule, last run and the last 30 days of runs.", "Read only", "green"),
    "Errors": ("data-refresh", "Known Errors", "Build, deploy and runtime errors from real projects, with their cause and fix.", "Reference", "blue"),
    "LabOverview": ("checkmarked-page", "Tested Live", "Demos that run Cookbook patterns in this tenant, so you can see them work before you copy them.", "All 10 passed", "green"),
    "Cookbook": ("lightbulb", "Pattern Cookbook", "Copyable patterns for the questions Extend developers ask most.", "Reference", "blue"),
}

# Demo pages (Tested Live): each gets its own hero (name, the Cookbook pattern it proves, last result) and the Demos
# card with itself ticked, so a demo leads to the next without going back (navigation review 2026-11-16).
_LAB = json.load(open(os.path.join(ROOT, 'tools', 'lab_demos.json'), encoding='utf-8'))
for _pg, _d in _LAB["demos"].items():
    HERO[_pg] = ("checkmarked-page", _d["name"], "Proves the Cookbook pattern: " + _d["pattern"] + ".", "Passed " + _LAB["lastRun"], "green")
HERO["LabFileUpload"] = ("checkmarked-page", "Upload a file", "Part of the Store and download a file demo: upload a CSV, then OK.", "Passed " + _LAB["lastRun"], "green")


# "Start here" card in the top row of tool pages that have no card of their own there: three short steps and where
# to go next, so the half-empty row tells a first-time user what to do (UI review 2026-11-16). No apostrophes.
STEPS = {
    "Workbench": "1. Pick an example or type WQL, then Run. 2. Not sure of a name? Search Data sources and fields below, tick fields and Write SELECT. 3. Copy the endpoint JSON into a page. REST paths: REST Explorer.",
    "Explorer": "1. Pick an example or type a GET path, then Send GET. 2. Read the summary and the JSON. 3. Copy the endpoint JSON into a page. Graph type lookup below lists any Graph type and its fields.",
    "Readiness": "1. Make a check list with node tools/scan_app.js, paste it or pick a saved one. 2. Run tenant checks, health checks or both. 3. Fix each Fail, then compare with results from another tenant.",
    "Integrations": "1. Systems with failures come first. 2. Sort, filter or export the grid. 3. To see which business process step runs an integration, use Business process routing in Installed Apps.",
    "AppList": "1. Sort, filter or export the grid to Excel. 2. Open takes an app to Installed Apps for its domains, business objects, processes and who has access.",
    "Cookbook": "1. Pick a pattern above, or open one from the gallery below. 2. Copy the snippet and read its trap. 3. Tested Live runs many of these patterns in this tenant.",
}


def steps_card():
    return {"id": "Steps", "parameters": ["stepsTitle", "stepsText"],
            "header": {"title": "<% stepsTitle %>", "icon": "wd-accent-resources"},
            "body": {"type": "simpleCard", "value": "<% stepsText %>"}}


# Field help: widget id -> (title, text). Shown after Start guided tours (the "?" in the page banner).
GUIDES = {
    "accessNameText": ("Check access for", "A person's name as Workday shows it. Show app then adds a column saying "
                       "whether one of their security groups has each domain, and through which group."),
    "limitNumber": ("Rows per page", "Up to 1,000 rows per call. Use Next page for more."),
    "offsetNumber": ("Start at row", "The row the page starts from. Previous page and Next page change it for you."),
    "checkListTextArea": ("Check list", "Make one with node tools/scan_app.js <app folder> in the toolkit's repository, "
                                        "or pick a saved check list above."),
    "pathText": ("GET path", "Relative to the API gateway, e.g. common/v1/workers/me. A path Workday answers with 404 "
                             "or 500 leaves a page error until you reload the page. Add ?path=<path> to this page's "
                             "address to share a GET."),
}


def write_json(path, data):
    open(path, 'w', encoding='utf-8').write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def tools_card():
    def pill(task):
        # .card scripts take double-quoted literals only (CLAUDE.md, simpleCard). The label comes in as a parameter,
        # so the page can bind it to presentationLabels (build_labels.py) and French users see it in French.
        return {"label": f'<% activeTool == "{task}" ? "\u2713 " + pill{task} : pill{task} %>', "taskReference": {"taskId": task}}
    return {"id": "Tools", "parameters": ["activeTool", "toolsTitle"] + ["pill" + t for t, _ in PILLS],
            "header": {"title": "<% toolsTitle %>", "icon": "wd-accent-toolbox"},
            "body": {"type": "pillCard", "pills": [pill(t) for t, _ in PILLS]}}


def kpi_card():
    # A count tile with a status chip (UI round 2, wave 8).
    return {"id": "Kpi", "parameters": ["kpiCount", "kpiLabel", "kpiNote", "chipLabel", "chipColor", "kpiIcon"],
            "header": {"title": "<% kpiCount %>", "subtitle": "<% kpiLabel %>", "icon": "<% kpiIcon ?: null %>",
                       "indicator": {"label": "<% chipLabel ?: null %>", "color": "<% chipColor ?: null %>"}},
            "body": {"type": "simpleCard", "value": "<% kpiNote %>"}}


def status_chart_card():
    return {"id": "StatusChart", "parameters": ["slices", "total"],
            "header": {"title": "Checks by status", "icon": "wd-accent-gauge"},
            "body": {"type": "chartCard", "chart": {
                "type": "donutChart2", "data": "<% slices %>", "dataVariableName": "slice", "title": "<% total %>",
                "sliceSizeDataSet": {"name": "Checks", "value": "<% slice[\"count\"] %>"},
                "sliceColorDataSet": {"name": "Status", "value": "<% slice[\"status\"] %>"},
                "showPercentLabels": False, "animateOnLoad": True}}}


def app_tile():
    # Installed Apps: one tile per app; Open reloads the page with ?ref= (UI round 2).
    return {"id": "AppTile", "parameters": ["appRef", "appStatus", "appLine", "chipColor", "openLabel"],
            "header": {"title": "<% appRef %>", "icon": "wd-accent-circuit-board",
                       "indicator": {"label": "<% appStatus %>", "color": "<% chipColor %>"}},
            "body": {"type": "simpleCard", "value": "<% appLine %>"},
            "footer": [{"label": "<% openLabel %>", "taskReference": {"taskId": "Apps", "parameterBindings": {"ref": "<% appRef %>"}}}]}


def object_tile():
    # Installed Apps detail: one tile per business object, with a link to query it.
    return {"id": "ObjectTile", "parameters": ["boName", "boRecords", "boLine", "boAlias"],
            "header": {"title": "<% boName %>", "subtitle": "<% boRecords %>", "icon": "wd-accent-worksheets"},
            "body": {"type": "simpleCard", "value": "<% boLine %>"},
            "footer": [{"label": "Query in WQL Workbench", "taskReference": {"taskId": "Workbench", "parameterBindings": {"ds": "<% boAlias %>"}}}]}


def tool_tile(task):
    # Home launcher tile: one static card per tool (a card footer's taskId isn't scripted).
    icon, _, _, _, _ = HERO[task]
    return {"id": "Tile" + task, "parameters": ["tileTitle", "tileLine", "openLabel"],
            "header": {"title": "<% tileTitle %>", "icon": "wd-accent-" + icon},
            "body": {"type": "simpleCard", "value": "<% tileLine %>"},
            "footer": [{"label": "<% openLabel %>", "taskReference": {"taskId": task}}]}


def launcher_container():
    return {"type": "cardContainer", "id": "launcherCardContainer", "layout": "grid",
            "cards": [{"type": "card", "cardId": "Tile" + t,
                       "parameters": "<% {'tileTitle': '" + HERO[t][1] + "', 'tileLine': '" + HERO[t][2] + "', 'openLabel': 'Open'} %>"}
                      for t, _ in TOOLS if t != "AppList"]}   # App List sits in the hub panel beside it; 9 tiles fill 3 rows


def tools_container(current):
    return {"type": "cardContainer", "id": "toolsCardContainer", "layout": "grid",
            "cards": [{"type": "card", "cardId": "Tools", "parameters": "<% {'activeTool': '" + current + "', 'toolsTitle': 'Tools', " +
                       ", ".join("'pill" + t + "': '" + l + "'" for t, l in PILLS) + "} %>"}]}


def hero_card():
    return {"id": "Hero", "parameters": ["heroTitle", "heroLine", "heroIcon", "chipLabel", "chipColor"],
            "header": {"title": "<% heroTitle %>", "icon": "<% heroIcon ?: null %>",
                       "indicator": {"label": "<% chipLabel ?: null %>", "color": "<% chipColor ?: null %>"}},
            "body": {"type": "simpleCard", "value": "<% heroLine %>"}}


def hero_container(page_id):
    icon, title, line, chip, color = HERO[page_id]
    for s in (title, line, chip):
        assert "'" not in s, s
    params = ("<% {'heroTitle': '" + title + "', 'heroLine': '" + line + "', 'heroIcon': 'wd-accent-" + icon +
              "', 'chipLabel': '" + chip + "', 'chipColor': '" + color + "'} %>")
    return {"type": "cardContainer", "id": "heroCardContainer", "layout": "grid",
            "cards": [{"type": "card", "cardId": "Hero", "parameters": params}]}


def walk(node, fn):
    if isinstance(node, dict):
        fn(node)
        for v in node.values():
            walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            walk(v, fn)


HEADER_CARDS = ("areaCardContainer", "appTilesCardContainer")   # page containers whose cards move up into the top row
# Not summary (KPI) cards: in the top row they stretch to the Tools card's height (Integrations, live 2026-11-16).


def patch_page(page_id):
    path = os.path.join(PRES, page_id + '.pmd')
    page = json.load(open(path, encoding='utf-8'))
    body = page["presentation"]["body"]["children"]
    # One container for the cards at the top, so they share a row on wide screens (a container per card left
    # three quarters of the row empty, live 2026-11-16): hero, then the Tools pills (or, on Home, a tile per tool),
    # then any page card that belongs up there (HEADER_CARDS).
    extra = [card for c in body if c.get("id") in HEADER_CARDS for card in c.get("cards", [])]
    # Idempotent: a second run finds the page cards already in the top row, not in their own container.
    extra += [card for c in body if c.get("id") == "toolsCardContainer" for card in c.get("cards", [])
              if card.get("cardId") not in ("Hero", "Tools", "Steps") and not (page_id in LAB and card.get("cardId") == "Demos") and not str(card.get("cardId", "")).startswith("Tile")]
    # A data-driven card list (dynamicCards) moves up too; a container holds one, so the first one found wins.
    dyn = next((c["dynamicCards"] for c in body if c.get("id") in HEADER_CARDS + ("toolsCardContainer",) and c.get("dynamicCards")), None)
    body[:] = [c for c in body if c.get("id") not in ("toolsCardContainer", "heroCardContainer", "launcherCardContainer") + HEADER_CARDS]
    cards = hero_container(page_id)["cards"] if page_id in HERO else []
    if page_id == "Toolkit":
        cards += launcher_container()["cards"]
    else:
        cards += tools_container(CURRENT.get(page_id, page_id))["cards"]
        if page_id in LAB:
            demo = _LAB["parts"].get(page_id, page_id)
            cards.append({"type": "card", "cardId": "Demos",
                          "parameters": "<% {'demosTitle': 'Other demos', 'activeDemo': '" + demo + "'} %>"})
        if page_id in STEPS:
            assert "'" not in STEPS[page_id], page_id
            cards.append({"type": "card", "cardId": "Steps",
                          "parameters": "<% {'stepsTitle': 'Start here', 'stepsText': '" + STEPS[page_id] + "'} %>"})
    top = {"type": "cardContainer", "id": "toolsCardContainer", "layout": "grid", "cards": cards + extra}
    if dyn:
        top["dynamicCards"] = dyn
    body.insert(0, top)

    def fix(n):
        if n.get("type") == "fieldSet" and n.get("id") == "aboutFieldSet":
            n["collapsible"] = True
            n["initializeCollapsed"] = True
        if n.get("id") in GUIDES and n.get("type") != "guide":
            title, text = GUIDES[n["id"]]
            n["guide"] = {"type": "guide", "id": n["id"] + "Guide", "title": title, "text": text}
    walk(page["presentation"], fix)
    write_json(path, page)


ERROR_TEXT = {
    "401": "Your Workday session has ended. Sign in again, then reopen the page.",
    "403": "You do not have access to this page. The toolkit needs the security domain Use: Developer Toolkit: "
           "ask your security administrator to add one of your security groups to it.",
    "404": "That page does not exist in this app. It may have been renamed: use the Tools card above.",
    "500": "Workday could not load this page. Try again; if it happens again, note the time and look the message "
           "up in Known Errors.",
}


def error_page():
    def line(code, text):
        return {"type": "text", "id": f"error{code}Text", "enabled": False, "label": code,
                "value": f"<% '{text}' %>",
                "visible": f"<% queryParams.errorCode == '{code}' %>"}
    general = {"type": "text", "id": "errorGeneralText", "enabled": False, "label": "What happened",
               "value": "<% 'The page could not be shown. 403 usually means a missing security domain (Use: "
                        "Developer Toolkit); 404 a page that does not exist; 500 a Workday error. Open the toolkit "
                        "Home and try again, or ask for access.' %>",
               "visible": "<% empty(queryParams.errorCode) || !['401', '403', '404', '500'].contains(queryParams.errorCode) %>"}
    return {
        "id": "ErrorPage",
        "presentation": {
            "pageType": "VIEW",
            "title": {"type": "title", "id": "pageTitle", "label": "Something went wrong"},
            "body": {"type": "section", "id": "bodySection", "children": [
                {"type": "cardContainer", "id": "heroCardContainer", "layout": "grid", "cards": [{"type": "card", "cardId": "Hero",
                 "parameters": "<% {'heroTitle': 'Something went wrong', 'heroLine': 'The page could not be shown. The reason is below.', 'heroIcon': 'wd-accent-data-refresh', 'chipLabel': empty(queryParams.errorCode) ? 'Error' : ('Error ' + queryParams.errorCode), 'chipColor': 'red'} %>"}]},
                {"type": "section", "id": "homeLinkSection", "children": [
                    {"type": "button", "id": "homeButton", "label": "Back to Home", "action": "PRIMARY",
                     "taskReference": {"taskId": "Home"}}]},
                {"type": "fieldSet", "id": "errorFieldSet", "title": "What happened", "children":
                    [general] + [line(c, t) for c, t in ERROR_TEXT.items()]},
            ]},
        },
    }


write_json(os.path.join(PRES, 'cards', 'Tools.card'), tools_card())
write_json(os.path.join(PRES, 'cards', 'Hero.card'), hero_card())
write_json(os.path.join(PRES, 'cards', 'Steps.card'), steps_card())
write_json(os.path.join(PRES, 'cards', 'Kpi.card'), kpi_card())
write_json(os.path.join(PRES, 'cards', 'AppTile.card'), app_tile())
write_json(os.path.join(PRES, 'cards', 'ObjectTile.card'), object_tile())
write_json(os.path.join(PRES, 'cards', 'StatusChart.card'), status_chart_card())
for t_, _ in TOOLS:
    write_json(os.path.join(PRES, 'cards', 'Tile' + t_ + '.card'), tool_tile(t_))
for p in PAGES:
    patch_page(p)
write_json(os.path.join(PRES, 'ErrorPage.pmd'), error_page())

amd_path = glob.glob(os.path.join(PRES, '*.amd'))[0]
amd = json.load(open(amd_path, encoding='utf-8'))
if not any(t["id"] == "AppList" for t in amd["tasks"]):
    amd["tasks"].append({"id": "AppList", "routingPattern": "/appList", "page": {"id": "AppList"}})
if not any(t["id"] == "Cookbook" for t in amd["tasks"]):
    amd["tasks"].append({"id": "Cookbook", "routingPattern": "/cookbook", "page": {"id": "Cookbook"}})
if not any(t["id"] == "ErrorPage" for t in amd["tasks"]):
    amd["tasks"].append({"id": "ErrorPage", "routingPattern": "/errorPage", "page": {"id": "ErrorPage"}})
write_json(amd_path, amd)

smd_path = glob.glob(os.path.join(PRES, '*.smd'))[0]
smd = json.load(open(smd_path, encoding='utf-8'))
smd["errorPageConfigurations"] = [{"statusCode": c, "page": {"id": "ErrorPage"}} for c in ERROR_TEXT]
write_json(smd_path, smd)
print('ui pass: Tools card on', len(PAGES), 'pages, collapsible About, guides, ErrorPage, SMD error mappings')
