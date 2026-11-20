"""Dynamic Forms orchestrations, written as flowVersion 3.1.0 JSON (shapes copied from Workday's public samples,
github.com/Workday/Developer-Relations): FormAssign, FormGate, FormEnded (business-process triggered), FormReconcile
(integration system, the safety net) and DynClose (page-launched). Imported by tools/build_app.py."""
import hashlib, json, os

REQ = 'data("start", "request").asJSON()'
NOTES = {"_type": ["List", "Note"], "_value": []}


def S(t, v):
    return {"_type": t, "_value": v}


def expr(typ, source):
    return S(["Expr", typ], {"type": S("Type", typ), "source": S("String", source), "isAuto": S("Boolean", False)})


def node(kind, name, **fields):
    v = {"name": S("Identifier", name), "isDisabled": S("Boolean", False), "errorHandler": S(["Opt", "ErrorHandler"], None)}
    v.update(fields)
    v["notes"] = NOTES
    return S(kind, v)


def values(name, pairs):
    return node("CreateValues", name, values=S(["List", "Assignment"], [
        S("Assignment", {"param": S("Parameter", {"name": S("Identifier", n), "type": S("Type", t), "default": S(["Opt", "Any"], None)}),
                         "expr": expr(t, src)}) for n, t, src in pairs]))


def template(name, text):
    return node("CreateTextTemplate", name, message=S("TextTemplate", text), contentType=S("String", "application/json"),
                formatRef=S(["Opt", "TextFormatRef"], None))


def send(name, method, path, body_ref, retry="_DEFAULT_WORKDAY_RETRY_CONFIG"):
    body = S(["Opt", "DataRefBody"], S("DataRefBody", {"dataRef": expr("Data", body_ref), "contentType": S(["Opt", "String"], None)})) \
        if body_ref else S(["Opt", "DataRefBody"], None)
    return node("SendWorkdayApiRequest", name, body=body, path=expr("String", path), queryParams=S(["List", "QueryParam"], []),
                method=S("HttpMethod", method), headers=S(["List", "Header"], []),
                auth=S("AccessTokenFromInitiatingUser", "AccessTokenFromInitiatingUser"), isChunked=S("Boolean", False),
                connectTimeoutMs=S("Long", 10000), responseTimeoutMs=S("Long", 20000), overallTimeoutMs=S("Long", 60000),
                retryConfigRef=S("RetryConfigRef", retry), tlsConfig=S(["Opt", "TlsConfig"], None),
                proxyConfig=S(["Opt", "ProxyConfig"], None), responseType=S("HttpResponseType", "Any"))


def alerted_check(name, assertion, message, flow_name="FormAssign"):
    """A check that first writes a Dyn Response with formCode ALERT when it is about to fail (2026-11-19), so a failure
    after retries is visible to an admin and to FormReconcile, not only on the event's Orchestrations tab."""
    return [
        values(name + "Msg", [("text", "String", _clean("(" + message + ")", 220)), ("stamp", "String", 'datetime.now("UTC").format("yyyyMMddHHmmssSSS")')]),
        template(name + "Alert", '{"responseKey": "TEST:DYN:ALERT{{data.' + name + 'Msg.stamp}}", "formCode": "ALERT", '
                                 '"status": "Needs attention: ' + flow_name + ': {{data.' + name + 'Msg.text}}", "nextForm": "", "parentKey": "", '
                                 '"bpEvent": "{{data.req.ev}}", "bpTarget": ""}'),
        send(name + "Flag", "POST", '(if (' + assertion + ') data.req.app.append("dynResponses/none/skip") else data.req.app.append("dynResponses"))',
             'data("' + name + 'Alert", "message")'),
        check(name, assertion, message),
    ]


def check(name, assertion, message):
    return node("ContinueOnConditions", name, assertions=S(["List", "Assertion"], [
        S("Assertion", {"assertion": expr("Boolean", assertion), "message": expr("String", message)})]))


def flow(name, nodes, end_ref, domain):
    return {"flowVersion": "3.1.0", "_type": "Flow", "_value": {
        "id": S("String", hashlib.md5(("dynamic-forms:" + name).encode()).hexdigest()),
        "name": S("Identifier", name), "type": S("FlowType", ".maya.FlowSync"),
        "start": S("StartBasic", {"structuredRequest": S(["Opt", "RequestStructure"], None), "hasMultipartData": S("Boolean", False), "notes": NOTES}),
        "end": S("EndSync", {"headers": S(["List", "Header"], []),
                             "body": S(["Opt", "DataRefBody"], S("DataRefBody", {"dataRef": expr("Data", end_ref), "contentType": S(["Opt", "String"], None)})),
                             "notes": NOTES}),
        "nodes": S(["List", "Node"], nodes), "notes": NOTES,
        "resources": S("ResourceProvider", {"fileLikeResources": S(["Map", "Resource"], {}), "credentials": S(["Map", "Credential"], {}),
                                            "xmlNamespaces": S(["Map", "String"], {}), "retryConfigs": S(["Map", ["WithNotes", "RetryConfig"]], {}),
                                            "csvFormats": S(["Map", "CsvFormat"], {}), "pollingConfigs": S(["Map", "PollingConfig"], {})}),
        "defaultWorkdayCredentialRef": S(["Opt", "AccessTokenFromInitiatingUser"], S("AccessTokenFromInitiatingUser", "AccessTokenFromInitiatingUser")),
        "errorHandler": S(["Opt", "ErrorHandler"], None), "cancelBarrier": S(["Opt", "Identifier"], None),
        "defaultLocale": S("Locale", {"value": expr("String", '"""en_US"""')}),
        "securityDomains": S(["Opt", ["List", "String"]], S(["List", "String"], [S("String", d) for d in domain]))}}


# LabRun: creates one Lab item. Body {"itemName", "mode": good|bad, "check": yes|no}. A bad record carries a field the
# business object doesn't have, so Workday refuses it. The run never fails on purpose: a failed run answers plain text
# ("Completed with error: ..."), which breaks the page that launched it (Known Errors). Instead it always answers JSON.
# check=no answers only {"done": true}, like an orchestration that never looks at the call's status (the pitfall);
# check=yes adds ok, status and Workday's error text.
def _lp(label):
    return '(if (lp.existsAndHasValue("' + label + '")) lp.stringParam("' + label + '") else "")'


def _clean(src, n):
    return src + '.normalizeSpace().replace("\\\\", "/").replace("\\"", "\'").truncate(' + str(n) + ')'


EVENTS = 's"""${"/businessProcess/v1/events/"}${data.lp.ev}"""'
def integration_flow(name, nodes):
    f = flow(name, nodes, 'data("subBody", "message")', [])
    v = f["_value"]
    v["type"] = S("FlowType", ".maya.IntegrationFrameworkTrigger")
    v["start"] = S("StartIntegrationFrameworkTrigger", {"parameters": S(["List", "ExprParameter"], []),
                                                         "configureForRetrieval": S("Boolean", False), "notes": NOTES})
    v["end"] = S("EndEmptyMaya", {"notes": NOTES})
    v["securityDomains"] = S(["Opt", ["List", "String"]], None)
    return f


# FormAssign: a business-process orchestration (flow type FlowBusinessProcessTriggered, start/end shapes from Workday's
# capitalProjectPlanning, requestCreditCard and tuitionReimbursement samples). A delivered process launches it from a
# Service step ("Orchestration Service"); the step's Orchestration Data passes actionEvent = Workday ID of the event and,
# optionally, formCode. It assigns that form: one Dyn Response with status "Assigned: <event>", nextForm = the form and
# bpEvent/bpTarget = the event and its target, so it shows under Responses > "Next forms to fill" until someone fills it.
def _param(name, default=None):
    dv = S(["Opt", ["Expr", ["Opt", "Any"]]], expr("String", default) if default else None)
    return S("ExprParameter", {"name": S("Identifier", name), "type": S("Type", "String"), "expr": dv})


_APP = 's"""${"/apps/"}${context.appReferenceId()}${"/v1/"}"""'

# v2 (2026-11-18): the form's family is looked up (Dyn Form family = formCode, indexed) and the Published version's code
# goes into nextForm, so the request keeps that version even after a later one is published. parentKey "FORM:<code>"
# marks which form this assignment is for, so a gate on a process with several forms reads only its own.
def _pinned(src='data.getForms', fallback='data.req.form'):
    """The highest Published version's code among the form's family (versions 1-20), else the code itself."""
    chain = fallback
    for v in range(1, 21):
        chain = (src + '.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.status == \'Published\' && @.version == %d)].code", %s)'
                 % (v, chain))
    return chain


def _extra_assign(i):
    """Assignment for the i-th extra family named in the pinned form's alsoAssign (item 8: several forms on one process).
    Skipped (requests sent to an invalid address) when that slot is empty."""
    x = 'data.xf.x%d' % i
    return [
        send("getForms%d" % i, "GET", 'data.req.app.append("dynForms?limit=100&family=").append((if (%s.isEmpty()) "none" else %s.urlEncode()))' % (x, x), None),
        *alerted_check("xRead%d" % i, '(if (%s.isEmpty()) true else data.getForms%d.responseStatusCode.is2xxStatusCode())' % (x, i),
              '"Could not read the extra form " + %s + ": it was not assigned"' % x),
        values("xa%d" % i, [
            ("pinned", "String", _pinned('data.getForms%d' % i, x)),
            ("sel", "String", '"$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(%s).append("\')].id")' % x)]),
        values("xe%d" % i, [("eid", "String", 'data.getExisting.response.asJSON().stringAtJsonPathWithDefault(data.xa%d.sel, "")' % i)]),
        template("xBody%d" % i, '{"responseKey": "{{data.req.key}}-%d", "formCode": "BP", "status": "Assigned: {{data.evInfo.desc}}", '
                                '"nextForm": "{{data.xa%d.pinned}}", "parentKey": "FORM:{{%s}}", "bpEvent": "{{data.req.ev}}", "bpTarget": "{{data.req.who}}", "bpPerson": "{{data.pp.person}}"}' % (i, i, x)),
        send("createX%d" % i, "POST", '(if (%s.isEmpty().or(data.xe%d.eid.isEmpty().not())) data.req.app.append("dynResponses/none/skip") else data.req.app.append("dynResponses"))' % (x, i), 'data("xBody%d", "message")' % i),
        send("reopenX%d" % i, "PATCH", '(if (%s.isEmpty().or(data.xe%d.eid.isEmpty())) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.xe%d.eid))' % (x, i, i), 'data("xBody%d", "message")' % i),
    ]


FORMASSIGN = [
    values("req", [
        ("ev", "String", 'data.start.actionEvent'),
        ("app", "String", _APP),
        ("form", "String", 'data.start.formCode.trim().replace("\'", "").replace("\\"", "")'),
        ("target", "String", 'bp.eventTarget().getIDValues("WID").get(0)'),
        # the worker the process is about, when the step passes it (Change Job's target is the supervisory organization)
        ("who", "String", '(if (data.start.worker.trim().isEmpty()) data.req.target else data.start.worker.trim())'),
        # time + 12 characters of the event's WID: two events assigned in the same millisecond (bulk starts) must not
        # share a key, because the gate finds the filled form by this key
        ("key", "String", '"TEST:DYN:BP" + datetime.now("UTC").format("yyyyMMddHHmmssSSS") + "E" + data.req.ev.substring(16, 28)'),
        ("exSel", "String", '"$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.req.form).append("\')].id")')]),
    # an assignment this event already has (the process was sent back and runs this step again): reopen it with a new
    # responseKey, so earlier fills no longer count and the gate reads only the new one
    send("getExisting", "GET", 'data.req.app.append("dynResponses?limit=100&bpEvent=").append(data.req.ev)', None),
    values("ex", [("eid", "String", 'data.getExisting.response.asJSON().stringAtJsonPathWithDefault(data.req.exSel, "")')]),
    send("getEvent", "GET", 's"""${"/businessProcess/v1/events/"}${data.req.ev}"""', None),
    send("getForms", "GET", 'data.req.app.append("dynForms?limit=100&family=").append(data.req.form.urlEncode())', None),
    # a failed read must stop the run, not look like "no assignment yet" (a duplicate) or "no published version"
    *alerted_check("lookupsOk", 'data.getExisting.responseStatusCode.is2xxStatusCode().and(data.getForms.responseStatusCode.is2xxStatusCode())',
          '"Could not read the existing assignments or the form (" + data.getExisting.responseStatusCode.format("0") + "/" + data.getForms.responseStatusCode.format("0") + "): nothing was assigned"'),
    values("evInfo", [
        ("desc", "String", '(if (data.getEvent.responseStatusCode.is2xxStatusCode()) ' + _clean(
            'data.getEvent.response.asJSON().stringAtJsonPathWithDefault("$.descriptor", "Business process")', 120) + ' else "Business process")'),
        # the highest Published version (checked from 20 down to 1), else the code itself
        ("pinned", "String", '(if (data.getForms.responseStatusCode.is2xxStatusCode()) ' + _pinned() + ' else data.req.form)')]),
    # the target's Person WID (2026-11-19): a new hire before the start date can't be found through workers/me, so
    # the employee pages match assignments on person/v4/people/me. Empty when this run's user can't read allWorkers.
    send("getPerson", "GET", '"/wql/v1/data?limit=1&query=".append(("SELECT person FROM allWorkers WHERE workdayID = \\"" + data.req.who.replace("\\"", "") + "\\"").urlEncode())', None),
    # no person: "?<status>" when Workday refused the query, "?none" when it answered without one (2026-11-19: the
    # ISU's lookups came back empty; this says why). Pages and FormReconcile treat a leading "?" as empty.
    values("pp", [("found", "String", '(if (data.getPerson.responseStatusCode.is2xxStatusCode()) data.getPerson.response.asJSON().stringAtJsonPathWithDefault("$.data[0].person.id", "") else "")'),
                  ("person", "String", '(if (data.pp.found.isEmpty().not()) data.pp.found else (if (data.getPerson.responseStatusCode.is2xxStatusCode()) "?none" else "?".append(data.getPerson.responseStatusCode.format("0")).append(" ").append(' + _clean('data.getPerson.response.toString()', 200) + ')))')]),
    template("assignBody", '{"responseKey": "{{data.req.key}}", "formCode": "BP", "status": "Assigned: {{data.evInfo.desc}}", '
                           '"nextForm": "{{data.evInfo.pinned}}", "parentKey": "FORM:{{data.req.form}}", "bpEvent": "{{data.req.ev}}", "bpTarget": "{{data.req.who}}", "bpPerson": "{{data.pp.person}}"}'),
    send("createAssignment", "POST", '(if (data.ex.eid.isEmpty()) data.req.app.append("dynResponses") else data.req.app.append("dynResponses/").append(data.ex.eid).append("/exists"))', 'data("assignBody", "message")'),
    send("reopenAssignment", "PATCH", '(if (data.ex.eid.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ex.eid))', 'data("assignBody", "message")'),
    *alerted_check("assignSaved", 'data.createAssignment.responseStatusCode.is2xxStatusCode().or(data.reopenAssignment.responseStatusCode.is2xxStatusCode())',
          '"Workday refused the form assignment: " + data.createAssignment.response.toString().truncate(300)'),
    # item 8: the pinned form may name more forms to assign with it (DynForm alsoAssign, "FAMILY1,FAMILY2")
    send("getMain", "GET", 'data.req.app.append("dynForms?limit=1&code=").append(data.evInfo.pinned.urlEncode())', None),
    # a failed read here used to skip the extra forms silently (item 9: one event got 1 of its 2 assignments)
    *alerted_check("mainOk", 'data.getMain.responseStatusCode.is2xxStatusCode()',
          '"Could not read the form\'s extra forms (" + data.getMain.responseStatusCode.format("0") + "): the main form was assigned, the extra forms were not"'),
    values("xf", [("list", "String", 'data.getMain.response.asJSON().stringAtJsonPathWithDefault("$.data[0].alsoAssign", "").replace(" ", "").replace("\'", "").replace("\\"", "")'),
                  ("x1", "String", '(if (data.xf.list.contains(",")) data.xf.list.substringBefore(",") else data.xf.list)'),
                  ("x2", "String", '(if (data.xf.list.contains(",")) data.xf.list.substringAfter(",").substringBefore(",") else "")')]),
] + _extra_assign(1) + _extra_assign(2) + [
    # record on the main assignment which extra forms were expected for this request ("-" = none)
    send("getMainAsg", "GET", 'data.req.app.append("dynResponses?limit=100&bpEvent=").append(data.req.ev)', None),
    values("ma", [("id", "String", 'data.getMainAsg.response.asJSON().stringAtJsonPathWithDefault(data.req.exSel, "")'),
                  ("expected", "String", '(if (data.xf.list.isEmpty()) "-" else data.xf.list)')]),
    template("expBody", '{"alsoExpected": "{{data.ma.expected}}"}'),
    send("saveExpected", "PATCH", '(if (data.ma.id.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ma.id))', 'data("expBody", "message")'),
    *alerted_check("extrasSaved", '(if (data.xf.x1.isEmpty()) true else data.createX1.responseStatusCode.is2xxStatusCode().or(data.reopenX1.responseStatusCode.is2xxStatusCode()))'
          '.and((if (data.xf.x2.isEmpty()) true else data.createX2.responseStatusCode.is2xxStatusCode().or(data.reopenX2.responseStatusCode.is2xxStatusCode())))',
          '"Workday refused an extra form assignment: " + data.createX1.response.toString().truncate(200) + " " + data.createX2.response.toString().truncate(200)'),
]


# FormGate v2 (2026-11-18): a later Service step of the same delivered process. It finds this event's assignment (Dyn
# Response formCode BP, bpEvent = event; with formCode set, only the one whose parentKey is FORM:<formCode>), the LATEST
# response filled from it and its answers, then applies a policy:
#   noForm (no assignment, or not filled) and onFail (the check failed: parking = true): cancel | sendback | pass.
#   sendback posts eventSteps/<in-progress step>/sendBack (to = the first /values/sendBack/to value); if Workday refuses,
#   the gate cancels instead and says why. pass and a successful send-back post a comment.
# Every comment carries [ROUTE:HR] or [ROUTE:NORMAL] (commute 100 km or more), so a step condition can route on THIS
# event (an Action Event calculated field over the event's comments), plus a short answer summary and, when resultsUrl is
# set, a link to the response. It still writes the per-worker route record and a gate record (formCode GATE).
_A = 'data.getAnswers.response.asJSON()'


def _ans(i):
    k = _A + '.stringAtJsonPathWithDefault("$.data[%d].qKey", "")' % i
    v = (_A + '.stringAtJsonPathWithDefault("$.data[%d].textValue", ' % i + _A + '.stringAtJsonPathWithDefault("$.data[%d].refDescriptor", ' % i
         + _A + '.stringAtJsonPathWithDefault("$.data[%d].numberValue", ' % i + _A + '.stringAtJsonPathWithDefault("$.data[%d].dateValue", "-"))))' % i)
    # a confidential answer (DynAnswer.secretText) is never copied into a comment, only "(confidential)"
    sec = _A + '.stringAtJsonPathWithDefault("$.data[%d].secretText", "")' % i
    v = '(if (%s.isEmpty()) %s else "(confidential)")' % (sec, v)
    return '(if (%s.isEmpty()) "" else %s.append("=").append(%s).append("; "))' % (k, k, v)


_SUMMARY = '""' + ''.join('.append(%s)' % _ans(i) for i in range(8))
_PARK = _A + '.stringAtJsonPathWithDefault("$.data[?(@.qKey == \'parking\')].textValue", "").equals("true")'
_COMMUTE = _A + '.stringAtJsonPathWithDefault("$.data[?(@.qKey == \'commute\')].numberValue", "0").substringBefore(".")'
FORMGATE = [
    values("req", [("ev", "String", 'data.start.actionEvent'), ("app", "String", _APP),
                   ("target", "String", '(if (data.start.worker.trim().isEmpty()) bp.eventTarget().getIDValues("WID").get(0) else data.start.worker.trim())'),
                   ("form", "String", 'data.start.formCode.trim().replace("\'", "").replace("\\"", "")'),
                   ("noForm", "String", '(if (data.start.noForm.trim().isEmpty()) "cancel" else data.start.noForm.trim())'),
                   ("onFail", "String", '(if (data.start.onFail.trim().isEmpty()) "cancel" else data.start.onFail.trim())'),
                   ("results", "String", 'data.start.resultsUrl.trim()'),
                   ("sel", "String", '(if (data.req.form.isEmpty()) "$.data[?(@.formCode == \'BP\')].responseKey" else "$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.req.form).append("\')].responseKey"))'),
                   ("key", "String", '"TEST:DYN:GATE" + datetime.now("UTC").format("yyyyMMddHHmmssSSS")')]),
    send("getAssign", "GET", 'data.req.app.append("dynResponses?limit=100&bpEvent=").append(data.req.ev)', None),
    values("asg", [("assignKey", "String", 'data.getAssign.response.asJSON().stringAtJsonPathWithDefault(data.req.sel, "")'),
                   ("asgForm", "String", 'data.getAssign.response.asJSON().stringAtJsonPathWithDefault(data.req.sel.replace(".responseKey", ".nextForm"), "")'),
                   ("asgId", "String", 'data.getAssign.response.asJSON().stringAtJsonPathWithDefault(data.req.sel.replace(".responseKey", ".id"), "")')]),
    # the policy set on the assigned form (Copy page > Set the gate policy), else the orchestration's defaults
    send("getForm", "GET", 'data.req.app.append("dynForms?limit=1&code=").append((if (data.asg.asgForm.isEmpty()) "none" else data.asg.asgForm.urlEncode()))', None),
    values("pol", [("fNo", "String", 'data.getForm.response.asJSON().stringAtJsonPathWithDefault("$.data[0].noFormPolicy", "")'),
                   ("fFail", "String", 'data.getForm.response.asJSON().stringAtJsonPathWithDefault("$.data[0].failPolicy", "")'),
                   ("noForm", "String", '(if (data.pol.fNo.isEmpty()) data.req.noForm else data.pol.fNo)'),
                   ("onFail", "String", '(if (data.pol.fFail.isEmpty()) data.req.onFail else data.pol.fFail)')]),
    # item 8: the extra forms named on the assigned form (alsoAssign) must be filled too
    # the extra forms recorded on the assignment when the request started ("-" = none); older assignments without
    # the record fall back to the form's current alsoAssign
    values("xr", [("rec", "String", 'data.getAssign.response.asJSON().stringAtJsonPathWithDefault(data.req.sel.replace(".responseKey", ".alsoExpected"), "").replace(" ", "")')]),
    values("xg", [("list", "String", '(if (data.xr.rec.equals("-")) "" else (if (data.xr.rec.isEmpty()) data.getForm.response.asJSON().stringAtJsonPathWithDefault("$.data[0].alsoAssign", "").replace(" ", "") else data.xr.rec))'),
                  ("x1", "String", '(if (data.xg.list.contains(",")) data.xg.list.substringBefore(",") else data.xg.list)'),
                  ("x2", "String", '(if (data.xg.list.contains(",")) data.xg.list.substringAfter(",").substringBefore(",") else "")'),
                  ("k1", "String", '(if (data.xg.x1.isEmpty()) "" else data.getAssign.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.xg.x1).append("\')].responseKey"), ""))'),
                  ("k2", "String", '(if (data.xg.x2.isEmpty()) "" else data.getAssign.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.xg.x2).append("\')].responseKey"), ""))')]),
    send("countX1", "GET", 'data.req.app.append("dynResponses?limit=1&parentKey=").append((if (data.xg.k1.isEmpty()) "none" else data.xg.k1.urlEncode()))', None),
    send("countX2", "GET", 'data.req.app.append("dynResponses?limit=1&parentKey=").append((if (data.xg.k2.isEmpty()) "none" else data.xg.k2.urlEncode()))', None),
    values("xm", [("m1", "Boolean", '(if (data.xg.x1.isEmpty()) false else (if (data.xg.k1.isEmpty()) true else data.countX1.response.asJSON().numberAtJsonPath("$.total") < 1))'),
                  ("m2", "Boolean", '(if (data.xg.x2.isEmpty()) false else (if (data.xg.k2.isEmpty()) true else data.countX2.response.asJSON().numberAtJsonPath("$.total") < 1))'),
                  ("which", "String", '(if (data.xm.m1) data.xg.x1 else data.xg.x2)')]),
    # the latest response filled from the assignment: collections come back oldest first and JSONPath can't index from
    # the end ("Negative array accessors not supported"), so count first and read the last one by offset
    send("countFilled", "GET", 'data.req.app.append("dynResponses?limit=1&parentKey=").append(data.asg.assignKey.urlEncode())', None),
    values("cnt", [("off", "String", '(data.countFilled.response.asJSON().numberAtJsonPath("$.total") - 1).format("0")')]),
    send("getFilled", "GET", 'data.req.app.append("dynResponses?limit=1&offset=").append(data.cnt.off).append("&parentKey=").append(data.asg.assignKey.urlEncode())', None),
    values("fil", [("filledKey", "String", '(if (data.asg.assignKey.isEmpty()) "" else data.getFilled.response.asJSON().stringAtJsonPathWithDefault("$.data[0].responseKey", ""))')]),
    send("getAnswers", "GET", 'data.req.app.append("dynAnswers?limit=100&responseKey=").append(data.fil.filledKey.urlEncode())', None),
    values("gate", [
        # a lookup that failed even after retries counts as missing (fail closed), never as "nothing extra to check"
        ("readFail", "Boolean", 'data.getAssign.responseStatusCode.is2xxStatusCode().not().or(data.asg.asgForm.isEmpty().not().and(data.getForm.responseStatusCode.is2xxStatusCode().not()))'),
        # the main form was read and filled: its answers are checked even when an extra form (alsoAssign) is missing,
        # so a missing extra with the policy "pass" still routes on the main form's answers (live 2026-11-19 gap)
        ("mainOk", "Boolean", 'data.gate.readFail.not().and(data.asg.assignKey.isEmpty().not()).and(data.fil.filledKey.isEmpty().not())'),
        ("missing", "Boolean", 'data.gate.mainOk.not().or(data.xm.m1).or(data.xm.m2)'),
        ("failed", "Boolean", '(if (data.gate.mainOk) ' + _PARK + ' else false)'),
        ("policy", "String", '(if (data.gate.failed) data.pol.onFail else (if (data.gate.missing) data.pol.noForm else "pass"))'),
        ("reason", "String", '(if (data.gate.readFail) "the form check could not read its records, so it stopped the request to be safe" else (if (data.asg.assignKey.isEmpty()) "no form was assigned to this event" else (if (data.fil.filledKey.isEmpty()) "the assigned form was not filled" else (if (data.gate.failed) "the form asks for a parking permit, which needs HR first" else (if (data.xm.m1.or(data.xm.m2)) "the form ".append(data.xm.which).append(" was not filled") else "form answers checked")))))'),
        ("commute", "String", '(if (data.gate.mainOk) ' + _COMMUTE + ' else "0")'),
        ("hr", "Boolean", 'data.gate.commute.length() > 2'),
        ("tag", "String", '(if (data.gate.hr) "[ROUTE:HR]" else "[ROUTE:NORMAL]")'),
        ("summary", "String", _clean('(if (data.gate.mainOk) ' + _SUMMARY + ' else "")', 400)),
        ("hasUrl", "Boolean", '(if (data.req.results.isEmpty()) false else data.fil.filledKey.isEmpty().not())')]),
    # send back: the step this orchestration runs in, and where Workday lets it go back to
    send("getSteps", "GET", 's"""${"/businessProcess/v1/events/"}${data.req.ev}${"/inProgressSteps"}"""', None),
    send("getTo", "GET", '"/businessProcess/v1/values/sendBack/to/"', None),
    # the same list asked for one step (the parameter name is a guess; the gate record logs both answers)
    send("getTo2", "GET", '"/businessProcess/v1/values/sendBack/to/?eventStep=".append(data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[0].id", "none"))', None),
    values("sb", [("tryIt", "Boolean", 'data.gate.policy.equals("sendback")'),
                  ("stepId", "String", 'data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[0].id", "none")'),
                  ("toId", "String", 'data.getTo.response.asJSON().stringAtJsonPathWithDefault("$.data[0].id", data.getTo2.response.asJSON().stringAtJsonPathWithDefault("$.data[0].id", ""))'),
                  # the parallel To Do "... Route marker" (assigned to the initiator); the gate submits it with the route tag as
                  # its comment, because businessProcess v1 has no POST for event comments (404 S21, live 2026-11-19)
                  ("markId", "String", 'data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.descriptor == \'To Do: TEST:DYN Route marker\')].id", data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.descriptor == \'TEST:DYN Route marker\')].id", data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.businessProcessStep.descriptor == \'TEST:DYN Route marker\')].id", data.getSteps.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.descriptor =~ /.*Route marker.*/)].id", ""))))')]),
    template("sbBody", '{"reason": "TEST form gate: {{data.gate.reason}}. Please correct the form and resubmit.", "to": {"id": "{{data.sb.toId}}"}}'),
    send("sendBack", "POST", '(if (data.sb.tryIt) "/businessProcess/v1/eventSteps/".append(data.sb.stepId).append("/sendBack") else "/businessProcess/v1/eventSteps/none/sendBack")', 'data("sbBody", "message")'),
    values("out", [
        ("sentBack", "Boolean", '(if (data.sb.tryIt) data.sendBack.responseStatusCode.is2xxStatusCode() else false)'),
        ("cancelIt", "Boolean", '(if (data.gate.policy.equals("pass")) false else data.out.sentBack.not())'),
        ("sbInfo", "String", '(if (data.sb.tryIt) "send back " + data.sendBack.responseStatusCode.format("0") + " (steps " + data.getSteps.responseStatusCode.format("0") + ", to " + data.getTo.responseStatusCode.format("0") + "): " + '
                             + _clean('data.sendBack.response.toString()', 200) + '.append(" | to: ").append(' + _clean('data.getTo.response.toString()', 160) + ').append(" | to2 ").append(data.getTo2.responseStatusCode.format("0")).append(": ").append(' + _clean('data.getTo2.response.toString()', 160) + ').append(" | steps: ").append(' + _clean('data.getSteps.response.toString()', 300) + ') else "")'),
        ("decision", "String", '(if (data.out.cancelIt) "Stopped: " else (if (data.out.sentBack) "Sent back: " else "Passed: ")).append(data.gate.reason).append("; policy ").append(data.gate.policy).append("; commute ").append(data.gate.commute).append(" ").append(data.gate.tag).append(" ").append(data.out.sbInfo)'),
        ("path", "String", '(if (data.out.cancelIt) "/businessProcess/v1/events/".append(data.req.ev).append("/cancel") else "/businessProcess/v1/events/none/cancel")')]),
    # Route: one record per worker (responseKey TEST:DYN:ROUTE:<worker WID>, subject = the worker), read by the Worker-based
    # calculated fields. Upsert without a branch: the POST goes to an invalid address when the record exists, the PATCH
    # when it doesn't; both refusals are harmless.
    values("rt", [("rkey", "String", '"TEST:DYN:ROUTE:".append(data.req.ev)')]),
    send("getRoute", "GET", 'data.req.app.append("dynResponses?responseKey=").append(data.rt.rkey.urlEncode())', None),
    values("rr", [("rid", "String", 'data.getRoute.response.asJSON().stringAtJsonPathWithDefault("$.data[0].id", "")'),
                  ("status", "String", '(if (data.gate.hr) "Route: HR" else "Route: normal")')]),
    template("routeBody", '{"responseKey": "{{data.rt.rkey}}", "formCode": "ROUTE", "status": "{{data.rr.status}}", '
                          '"subject": {"id": "{{data.req.target}}"}, "parentKey": "{{data.fil.filledKey}}", "bpEvent": "{{data.req.ev}}", '
                          '"nextForm": "", "bpTarget": "{{data.req.target}}"}'),
    send("createRoute", "POST", '(if (data.rr.rid.isEmpty()) data.req.app.append("dynResponses") else data.req.app.append("dynResponses/").append(data.rr.rid).append("/exists"))', 'data("routeBody", "message")'),
    send("updateRoute", "PATCH", '(if (data.rr.rid.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.rr.rid))', 'data("routeBody", "message")'),
    # the route marker To Do: Submit (stepAction 133d5c88baa64136aab041c1d2e9ed53) with the tag and answers as its comment
    template("actBody", '{"comment": "TEST form gate {{data.gate.tag}} {{data.gate.reason}}. Answers: {{data.gate.summary}}'
                        '{{#if data.gate.hasUrl}} Open: {{data.req.results}}?key={{data.fil.filledKey}}{{/if}}"}'),
    template("markBody", '{"stepAction": {"id": "133d5c88baa64136aab041c1d2e9ed53"}, "comment": "{{data.gate.tag}} TEST form gate: {{data.gate.reason}}. Answers: {{data.gate.summary}}'
                         '{{#if data.gate.hasUrl}} Open: {{data.req.results}}?key={{data.fil.filledKey}}{{/if}}"}'),
    send("mark", "POST", '(if (data.sb.markId.isEmpty()) "/businessProcess/v1/eventSteps/none/toDo" else "/businessProcess/v1/eventSteps/".append(data.sb.markId).append("/toDo"))', 'data("markBody", "message")'),
    # cancel only when stopping (the path goes nowhere otherwise)
    send("act", "POST", 'data.out.path', 'data("actBody", "message")'),
    # a stopped request's assignment is closed, so it leaves "Next forms to fill"
    template("closeBody", '{"status": "Closed: {{data.gate.reason}}"}'),
    send("closeAsg", "PATCH", '(if (data.out.cancelIt.and(data.asg.asgId.isEmpty().not())) data.req.app.append("dynResponses/").append(data.asg.asgId) else data.req.app.append("dynResponses/none"))', 'data("closeBody", "message")'),
    values("actInfo", [("text", "String", 'data.out.decision.append("; marker ").append((if (data.sb.markId.isEmpty()) "none (steps ".append(data.getSteps.responseStatusCode.format("0")).append(" ").append(' + _clean('data.getSteps.response.toString()', 400) + ').append(")") else data.mark.responseStatusCode.format("0"))).append(" ").append(' + _clean('data.mark.response.toString()', 100) + ').append((if (data.out.cancelIt) "; cancel ".append(data.act.responseStatusCode.format("0")).append(" ").append(' + _clean('data.act.response.toString()', 100) + ') else ""))')]),
    template("gateBody", '{"responseKey": "{{data.req.key}}", "formCode": "GATE", "status": "{{data.actInfo.text}}", '
                         '"parentKey": "{{data.fil.filledKey}}", "nextForm": "", "bpEvent": "{{data.req.ev}}", "bpTarget": ""}'),
    send("saveGate", "POST", 'data.req.app.append("dynResponses")', 'data("gateBody", "message")'),
    *alerted_check("actDone", '(if (data.out.cancelIt) data.act.responseStatusCode.is2xxStatusCode() else true)', '"The gate call was refused: " + data.act.response.toString().truncate(300)', "FormGate"),
]


# DynClose (acceptance item 9 clean-up, 2026-11-19): close the form assignments of one business process event.
# Body {"ev": <event WID>}. A page can't PATCH an app business object through a deferred endpoint (the bulk page's
# PATCH failed with "A failure occurred"), so the page launches this per event. Only BP assignments are touched.
_CA = 'data.getAsg.response.asJSON()'
DYNCLOSE = [
    values("req", [("ev", "String", REQ + '.stringAtJsonPathWithDefault("$.ev", "none").replace("/", "").replace("?", "")'), ("app", "String", _APP)]),
    send("getAsg", "GET", 'data.req.app.append("dynResponses?limit=10&bpEvent=").append(data.req.ev)', None),
    values("ids", [
        ("a", "String", '(if (' + _CA + '.stringAtJsonPathWithDefault("$.data[0].formCode", "").equals("BP")) ' + _CA + '.stringAtJsonPathWithDefault("$.data[0].id", "") else "")'),
        ("b", "String", '(if (' + _CA + '.stringAtJsonPathWithDefault("$.data[1].formCode", "").equals("BP")) ' + _CA + '.stringAtJsonPathWithDefault("$.data[1].id", "") else "")'),
        ("c", "String", '(if (' + _CA + '.stringAtJsonPathWithDefault("$.data[2].formCode", "").equals("BP")) ' + _CA + '.stringAtJsonPathWithDefault("$.data[2].id", "") else "")')]),
    template("closeBody", '{"status": "Closed: TEST:DYN:BULK cleanup"}'),
    send("closeA", "PATCH", '(if (data.ids.a.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ids.a))', 'data("closeBody", "message")'),
    send("closeB", "PATCH", '(if (data.ids.b.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ids.b))', 'data("closeBody", "message")'),
    send("closeC", "PATCH", '(if (data.ids.c.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ids.c))', 'data("closeBody", "message")'),
    values("out", [("n", "String", '((if (data.closeA.responseStatusCode.is2xxStatusCode()) 1 else 0) + (if (data.closeB.responseStatusCode.is2xxStatusCode()) 1 else 0) + (if (data.closeC.responseStatusCode.is2xxStatusCode()) 1 else 0)).format("0")'),
                   ("found", "String", _CA + '.numberAtJsonPath("$.total").format("0")')]),
    template("answer", '{"closed": {{data.out.n}}, "found": {{data.out.found}}}'),
]


# FormEnded (2026-11-19): launched by Workday when a request with form steps is cancelled or rescinded (Configure
# Orchestrations on the business process, actions Cancel and Rescind; launch configuration parameter actionEvent =
# the event's Workday ID). It closes that event's still-open form assignments at once, so My Forms to Fill no longer
# lists them until the nightly FormReconcile. Only BP assignments whose status starts "Assigned" are touched (a filled
# or already-closed one keeps its status). Up to 5 per event (a main form plus up to 4 extras).
_EA = 'data.getAsg.response.asJSON()'
def _ended_id(i):
    return ('(if (' + _EA + '.stringAtJsonPathWithDefault("$.data[%d].formCode", "").equals("BP").and(' % i + _EA +
            '.stringAtJsonPathWithDefault("$.data[%d].status", "").startsWith("Assigned"))) ' % i + _EA +
            '.stringAtJsonPathWithDefault("$.data[%d].id", "") else "")' % i)
FORMENDED = [
    values("req", [("ev", "String", 'data.start.actionEvent.trim().replace("/", "").replace("?", "")'), ("app", "String", _APP)]),
    send("getEv", "GET", '"/businessProcess/v1/events/".append((if (data.req.ev.isEmpty()) "none" else data.req.ev))', None),
    values("evs", [("status", "String", '(if (data.getEv.responseStatusCode.is2xxStatusCode()) data.getEv.response.asJSON().stringAtJsonPathWithDefault("$.status.descriptor", "ended") else "ended")')]),
    send("getAsg", "GET", 'data.req.app.append("dynResponses?limit=20&bpEvent=").append((if (data.req.ev.isEmpty()) "none" else data.req.ev))', None),
    values("ids", [(c, "String", _ended_id(i)) for i, c in enumerate("abcde")]),
    template("closeBody", '{"status": "Closed: event {{data.evs.status}} (closed when it ended)"}'),
    *[send("close" + c.upper(), "PATCH", '(if (data.ids.%s.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ids.%s))' % (c, c),
           'data("closeBody", "message")') for c in "abcde"],
]


# Retry with back-off for the form orchestrations (2026-11-19, after acceptance item 9 lost one extra assignment in a
# 50-event burst: the calls used _DEFAULT_WORKDAY_RETRY_CONFIG, which retries nothing). Shapes from Workday's public
# samples (tuitionReimbursement CreateOneTimePayment, stock-notifications StockRetrieval). 2xx and the 4xx answers other
# than 429 count as final (the deliberate ".../none" skip addresses answer 404, and a real refusal won't change on a
# retry); 429/503 wait for Retry-After, 429 and 5xx back off 2 s, 4 s, 8 s, up to 4 retries.
FORM_RETRY = "formRetry"


def _codes(*c):
    return S("StatusCodeCondition", {"codes": S(["List", "Int"], [S("Int", x) for x in c])})


def _policy(name, conds, backoff=None):
    return S("RetryPolicy", {"nameProp": S("String", name), "conditions": S(["List", "Condition"], conds),
                             "maxRetries": S(["Opt", "Int"], None),
                             "backOffStrategy": S(["Opt", "CustomBackOff"], backoff) if backoff else S(["Opt", "BackOffStrategy"], None)})


def _range(a, b):
    return S("ResponseCodeRange", {"begin": S("Int", a), "end": S("Int", b)})


RETRY_CONFIGS = {FORM_RETRY: S(["WithNotes", "RetryConfig"], {"value": S("RetryConfig", {
    "name": S("String", "FormRetry"), "maxTotalRetries": S("Int", 4),
    "successResponseCodeRanges": S(["List", "ResponseCodeRange"], [_range(200, 299), _range(400, 428), _range(430, 499)]),
    "defaultBackOff": S("BackOff", {"intervalMs": S("Long", 2000), "factor": S("Decimal", 2.0), "maxBackOffMs": S("Long", 30000)}),
    "retryPolicies": S(["List", "RetryPolicy"], [
        _policy("Throttled with Retry-After", [_codes(429, 503), S("HeaderCondition", {"header": S("String", "Retry-After")})],
                S("CustomBackOff", {"interval": S("RetryAfterHeaderInterval", "RetryAfterHeaderInterval"), "maxBackOffMs": S("Long", 30000)})),
        _policy("Throttled or server error", [_codes(429, 500, 502, 503, 504)])])}), "notes": NOTES})}


def _retrying(nodes):
    """The same nodes with every Workday call on the FormRetry config."""
    def walk(n):
        if isinstance(n, dict):
            if n.get("_type") == "RetryConfigRef" and n.get("_value") == "_DEFAULT_WORKDAY_RETRY_CONFIG":
                n["_value"] = FORM_RETRY
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(nodes)
    return nodes


def _alert_handler(name, stop):
    """Global error handler for a form orchestration (2026-11-19): when the run fails even after FormRetry, write a Dyn
    Response with formCode ALERT ("Needs attention: ...", bpEvent = the event) that the reconciliation and the admin
    pages list. The gate also stops the request (fail closed): a failed check must never let a request through.
    Wrapper shape from Workday's samples (orchestrationToolkit GlobalErrorHandlerDemo, UpdateServiceDatesBoomerang)."""
    nodes = [
        # the handler sees no step's data (App Hub: "no upstream component with id start/req"), only globals
        values("err", [("who", "String", 'bp.eventTarget().getIDValues("WID").get(0)'),
                       ("app", "String", _APP),
                       ("stamp", "String", 'datetime.now("UTC").format("yyyyMMddHHmmssSSS")')]),
        template("alertBody", '{"responseKey": "TEST:DYN:ALERT{{data.err.stamp}}", "formCode": "ALERT", '
                              '"status": "Needs attention: ' + name + ' failed at {{data._orchestration.processingError.locationPath}}", "nextForm": "", "parentKey": "", '
                              '"bpEvent": "", "bpTarget": "{{data.err.who}}"}'),
        send("saveAlert", "POST", 'data.err.app.append("dynResponses")', 'data("alertBody", "message")'),
    ]
    # stop is unused: the handler can't read the event's ID, so it can't cancel; the gate's known failures already
    # fail closed in the main flow (readFail, actDone)
    return S(["Opt", "ErrorHandler"], S("ErrorHandler", {
        "name": S("Identifier", "_globalErrorHandler"), "isDisabled": S("Boolean", False),
        "strategy": S("ErrorHandlerStrategy", "GlobalErrorHandler"), "nodes": S(["List", "Node"], nodes), "notes": NOTES}))


def bp_flow(name, nodes, params=None):
    f = flow(name, nodes, 'data("assignBody", "message")', [])
    v = f["_value"]
    v["type"] = S("FlowType", ".maya.FlowBusinessProcessTriggered")
    v["start"] = S("StartBusinessProcess", {"parameters": S(["List", "ExprParameter"], params or [
        _param("actionEvent"), _param("formCode", 's"""TEST:DYN:ADDR"""')]), "notes": NOTES})
    v["end"] = S("EndEmptyMaya", {"notes": NOTES})
    v["securityDomains"] = S(["Opt", ["List", "String"]], None)
    v["resources"]["_value"]["retryConfigs"] = S(["Map", ["WithNotes", "RetryConfig"]], RETRY_CONFIGS)
    v["errorHandler"] = _alert_handler(name, name == "FormGate")
    _retrying(v["nodes"])
    _retrying(v["errorHandler"])
    return f


def loop(name, iterator, group_nodes, folds):
    """A Loop over a Json iterator; folds = [(name, json_expr)] (shapes from Workday's samples: employeeRelations
    intGeneratePDFandAttachments, capitalProjectPlanning RequestApproval)."""
    J = ["Json", S(["Opt", "JsonSchemaRef"], None)]
    fv = [S("JsonFoldValue", {"nameProp": S("Identifier", f[0]), "data": S(["Expr", J], {"type": S("Type", J), "source": S("String", f[1]), "isAuto": S("Boolean", False)}),
                              "condition": S(["Opt", ["Expr", "Boolean"]], expr("Boolean", f[2]) if len(f) > 2 else None)}) for f in folds]
    return node("Loop", name,
                inputData=S(["Expr", ["Iterator", ["Opt", "Any"]]], {"type": S("Type", ["Iterator", J]), "source": S("String", iterator), "isAuto": S("Boolean", False)}),
                filter=S(["Opt", ["Expr", "Boolean"]], None),
                aggregateNode=S(["Opt", "Aggregate"], S("Aggregate", {"name": S("Identifier", name + "Folds"), "isDisabled": S("Boolean", False),
                                                                      "failOnEmptyStream": S("Boolean", False), "foldValues": S(["List", "FoldValue"], fv), "notes": NOTES})),
                earlyStopCondition=S(["Opt", "EarlyStopCondition"], None), sorts=S(["List", "SortedBy"], []), locale=S(["Opt", "Locale"], None),
                group=S("ImplicitGroup", {"name": S("Identifier", "_group_" + name), "isDisabled": S("Boolean", False),
                                          "errorHandler": S(["Opt", "ErrorHandler"], None), "nodes": S(["List", "Node"], group_nodes), "notes": NOTES}))


# FormCompose (2026-11-20, tiered ownership plan, replaces FormAssign on processes set up with blocks): a Service step
# launches it with actionEvent, processType and (for organization-targeted processes) worker. It
#   1. finds the subject's supervisory organization (common/v1/workers) and its row on the org map (Dyn Org Map:
#      path "|top|...|org|", department, company);
#   2. reads the block assignments for the process type (Dyn Assign) and keeps those whose owner org covers the
#      subject: scope "org" = the owner org itself, "subs" = the owner org or any org below it (its WID on the path);
#      with no org map row only enterprise assignments apply;
#   3. pins each matching block family's published version and lists them "tierRank:code" (1 enterprise,
#      2 department, 3 team);
#   4. reuses the composed form with the same compose key (process + pinned blocks) or creates it (Dyn Form kind
#      composed), so the fill page reads one record and the blocks' questions;
#   5. creates (or, when the process was sent back, reopens) one assignment for the event, with the subject's org,
#      department, company and the pinned versions recorded;
#   6. on Onboarding, also composes the onboarding kit: one welcome task, the manager's prepare task and a task per
#      learning step whose kit item covers the hire (same owner org + scope rule). Access items wait for the manager.
# Every write checks for an existing record of this event first, so a second run changes nothing.
_ITEM = 'data.asgs.item'
_KIT = 'data.kits.item'


def _covers(item):
    g = lambda k: item + '.stringAtJsonPathWithDefault("$.%s", "")' % k
    # active is a BOOLEAN: stringAtJsonPath on it fails the run (live 2026-11-20, "FormCompose failed at asgs.a"),
    # so test the item's JSON text instead.
    return ('(if (%s) false else (if (data.om.path.isEmpty()) %s.equals("Enterprise") else '
            '(if (%s.equals("subs")) data.om.path.contains("|".append(%s).append("|")) else %s.equals(data.om.org))))'
            % (item + '.toString().replace(" ", "").contains("\\"active\\":false")', g("tier"), g("scope"), g("ownerWid"), g("ownerWid")))


FORMCOMPOSE = [
    values("req", [
        ("ev", "String", 'data.start.actionEvent'),
        ("app", "String", _APP),
        ("pt", "String", 'data.start.processType.trim().replace("\'", "").replace("\\"", "").replace("|", "")'),
        ("target", "String", 'bp.eventTarget().getIDValues("WID").get(0)'),
        ("who", "String", '(if (data.start.worker.trim().isEmpty()) data.req.target else data.start.worker.trim())'),
        ("stamp", "String", 'datetime.now("UTC").format("yyyyMMddHHmmssSSS")'),
        ("key", "String", '"TEST:DYN:BP" + data.req.stamp + "E" + data.req.ev.substring(16, 28)')]),
    send("getExisting", "GET", 'data.req.app.append("dynResponses?limit=100&bpEvent=").append(data.req.ev)', None),
    values("ex", [("eid", "String", 'data.getExisting.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:COMPOSED\')].id", "")')]),
    send("getEvent", "GET", 's"""${"/businessProcess/v1/events/"}${data.req.ev}"""', None),
    send("getWorker", "GET", '"/common/v1/workers/".append(data.req.who)', None),
    values("sw", [("org", "String", '(if (data.getWorker.responseStatusCode.is2xxStatusCode()) data.getWorker.response.asJSON().stringAtJsonPathWithDefault("$.primarySupervisoryOrganization.id", "") else "")')]),
    # A worker read that fails (the run-as account can't see the worker) would quietly leave only enterprise blocks:
    # record an ALERT and carry on (live 2026-11-20: empty subjectOrg, only the enterprise block composed).
    values("wkMsg", [("stamp", "String", 'datetime.now("UTC").format("yyyyMMddHHmmssSSS")'),
                     ("code", "String", 'data.getWorker.responseStatusCode.format("0")')]),
    template("wkAlert", '{"responseKey": "TEST:DYN:ALERT{{data.wkMsg.stamp}}W", "formCode": "ALERT", '
                        '"status": "Needs attention: FormCompose could not read the worker (HTTP {{data.wkMsg.code}}), so only enterprise blocks were used. Give the run-as account Get on worker data.", '
                        '"nextForm": "", "parentKey": "", "bpEvent": "{{data.req.ev}}", "bpTarget": "{{data.req.who}}"}'),
    send("wkFlag", "POST", '(if (data.sw.org.isEmpty().not()) data.req.app.append("dynResponses/none/skip") else data.req.app.append("dynResponses"))',
         'data("wkAlert", "message")'),
    send("getMap", "GET", 'data.req.app.append("dynOrgMaps?limit=1&orgWid=").append((if (data.sw.org.isEmpty()) "none" else data.sw.org))', None),
    values("om", [("org", "String", 'data.sw.org'),
                  ("path", "String", 'data.getMap.response.asJSON().stringAtJsonPathWithDefault("$.data[0].path", "")'),
                  ("dept", "String", _clean('data.getMap.response.asJSON().stringAtJsonPathWithDefault("$.data[0].deptName", "")', 120)),
                  ("company", "String", _clean('data.getMap.response.asJSON().stringAtJsonPathWithDefault("$.data[0].companyName", "")', 120)),
                  ("orgName", "String", _clean('data.getMap.response.asJSON().stringAtJsonPathWithDefault("$.data[0].name", "")', 120))]),
    send("getAssigns", "GET", 'data.req.app.append("dynAssigns?limit=100&processType=").append(data.req.pt.urlEncode())', None),
    *alerted_check("readsOk", 'data.getExisting.responseStatusCode.is2xxStatusCode().and(data.getAssigns.responseStatusCode.is2xxStatusCode())',
                   '"Could not read the assignments or block assignments (" + data.getExisting.responseStatusCode.format("0") + "/" + data.getAssigns.responseStatusCode.format("0") + "): nothing was composed"', "FormCompose"),
    loop("asgs", 'data.getAssigns.response.asJSON().iterator("$.data[*]")', [
        values("a", [("fam", "String", _ITEM + '.stringAtJsonPathWithDefault("$.family", "")'),
                     ("tier", "String", _ITEM + '.stringAtJsonPathWithDefault("$.tier", "Team")'),
                     ("hit", "Boolean", _covers(_ITEM) + '.and(data.a.fam.isEmpty().not())'),
                     ("rank", "String", '(if (data.a.tier.equals("Enterprise")) "1" else (if (data.a.tier.equals("Department")) "2" else "3"))')]),
        send("getFam", "GET", 'data.req.app.append("dynForms?limit=100&family=").append((if (data.a.hit) data.a.fam.urlEncode() else "none"))', None),
        values("ap", [("pinned", "String", '(if (data.a.hit.and(data.getFam.responseStatusCode.is2xxStatusCode())) ' + _pinned('data.getFam', '""') + ' else "")'),
                      ("keep", "Boolean", 'data.a.hit.and(data.ap.pinned.isEmpty().not())')]),
        template("blockOut", '{"c": "{{data.a.rank}}:{{data.ap.pinned}}"}'),
    ], [("blocks", 'data.blockOut.message.asJSON()', 'data.ap.keep')]),
    values("bl", [("t", "String", 'data.asgs.blocks.toString().replace(" ", "")'),
                  ("list", "String", 'data.bl.t.replace("[", "").replace("]", "").replace("{\\"c\\":\\"", "").replace("\\"}", "")'),
                  ("any", "Boolean", 'data.bl.list.isEmpty().not()'),
                  ("ckey", "String", 'data.req.pt.append("|").append(data.bl.list)')]),
    *alerted_check("someBlock", 'data.bl.any', '"No published block applies to this request (process " + data.req.pt + ", organization " + data.om.orgName + "): nothing was assigned"', "FormCompose"),
    send("getCached", "GET", 'data.req.app.append("dynForms?limit=1&composeKey=").append(data.bl.ckey.urlEncode())', None),
    values("cc", [("found", "String", 'data.getCached.response.asJSON().stringAtJsonPathWithDefault("$.data[0].code", "")'),
                  ("code", "String", '(if (data.cc.found.isEmpty()) "TEST:DYN:CMP:".append(data.req.stamp) else data.cc.found)')]),
    template("cmpBody", '{"code": "{{data.cc.code}}", "family": "{{data.cc.code}}", "formName": "Composed form: {{data.req.pt}}", "version": 1, '
                        '"status": "Published", "kind": "composed", "blocks": "{{data.bl.list}}", "composeKey": "{{data.bl.ckey}}", "processType": "{{data.req.pt}}"}'),
    send("createCmp", "POST", '(if (data.cc.found.isEmpty()) data.req.app.append("dynForms") else data.req.app.append("dynForms/none/skip"))', 'data("cmpBody", "message")'),
    *alerted_check("cmpOk", 'data.cc.found.isEmpty().not().or(data.createCmp.responseStatusCode.is2xxStatusCode())',
                   '"Workday refused the composed form: " + data.createCmp.response.toString().truncate(300)', "FormCompose"),
    values("evInfo", [("desc", "String", '(if (data.getEvent.responseStatusCode.is2xxStatusCode()) ' + _clean(
        'data.getEvent.response.asJSON().stringAtJsonPathWithDefault("$.descriptor", "Business process")', 120) + ' else "Business process")')]),
    send("getPerson", "GET", '"/wql/v1/data?limit=1&query=".append(("SELECT person FROM allWorkers WHERE workdayID = \\"" + data.req.who.replace("\\"", "") + "\\"").urlEncode())', None),
    values("pp", [("person", "String", '(if (data.getPerson.responseStatusCode.is2xxStatusCode()) data.getPerson.response.asJSON().stringAtJsonPathWithDefault("$.data[0].person.id", "") else "")')]),
    template("assignBody", '{"responseKey": "{{data.req.key}}", "formCode": "BP", "status": "Assigned: {{data.evInfo.desc}}", "nextForm": "{{data.cc.code}}", '
                           '"parentKey": "FORM:COMPOSED", "bpEvent": "{{data.req.ev}}", "bpTarget": "{{data.req.who}}", "bpPerson": "{{data.pp.person}}", '
                           '"subjectOrg": "{{data.om.org}}", "department": "{{data.om.dept}}", "company": "{{data.om.company}}", "pinned": "{{data.bl.list}}", '
                           '"processType": "{{data.req.pt}}", "orgName": "{{data.om.orgName}}", "alsoExpected": "-"}'),
    send("createAssignment", "POST", '(if (data.ex.eid.isEmpty()) data.req.app.append("dynResponses") else data.req.app.append("dynResponses/none/skip"))', 'data("assignBody", "message")'),
    send("reopenAssignment", "PATCH", '(if (data.ex.eid.isEmpty()) data.req.app.append("dynResponses/none") else data.req.app.append("dynResponses/").append(data.ex.eid))', 'data("assignBody", "message")'),
    *alerted_check("assignSaved", 'data.createAssignment.responseStatusCode.is2xxStatusCode().or(data.reopenAssignment.responseStatusCode.is2xxStatusCode())',
                   '"Workday refused the composed form assignment: " + data.createAssignment.response.toString().truncate(300)', "FormCompose"),
    # ---- onboarding kit (phase 5) ----
    values("kc", [("on", "Boolean", 'data.req.pt.equals("Onboarding")')]),
    send("getKitDone", "GET", 'data.req.app.append("dynKitTasks?limit=1&bpEvent=").append((if (data.kc.on) data.req.ev else "none"))', None),
    send("getKits", "GET", 'data.req.app.append("dynKitItems?limit=100&processType=").append((if (data.kc.on) "Onboarding" else "none"))', None),
    values("kd", [("fresh", "Boolean", 'data.kc.on.and(data.getKitDone.responseStatusCode.is2xxStatusCode()).and(data.getKitDone.response.asJSON().numberAtJsonPath("$.total") < 1)')]),
    loop("kits", 'data.getKits.response.asJSON().iterator("$.data[*]")', [
        values("k", [("itype", "String", _KIT + '.stringAtJsonPathWithDefault("$.itemType", "")'),
                     ("status", "String", _KIT + '.stringAtJsonPathWithDefault("$.status", "")'),
                     ("hit", "Boolean", _covers(_KIT) + '.and(data.k.status.equals("Published"))'),
                     ("code", "String", _clean(_KIT + '.stringAtJsonPathWithDefault("$.code", "")', 80)),
                     ("title", "String", _clean(_KIT + '.stringAtJsonPathWithDefault("$.title", "")', 200)),
                     ("due", "String", _KIT + '.stringAtJsonPathWithDefault("$.dueOffset", "0").substringBefore(".")'),
                     ("tier", "String", _KIT + '.stringAtJsonPathWithDefault("$.tier", "")'),
                     # a customer copy (origin Customer, overrides = this code) replaces a delivered item for new hires
                     ("ov", "Boolean", 'data.getKits.response.toString().replace(" ", "").contains("\\"overrides\\":\\"".append(data.k.code).append("\\""))'),
                     ("welcome", "Boolean", 'data.k.itype.equals("welcome")'),
                     ("learning", "Boolean", 'data.k.itype.equals("welcome").not()')]),
        template("kitOut", '{"key": "KIT:{{data.req.stamp}}:{{data.k.code}}", "taskType": "{{data.k.itype}}", "hireWid": "{{data.req.who}}", "newHire": {"id": "{{data.req.who}}"}, '
                           '"itemCode": "{{data.k.code}}", "title": "{{data.k.title}}", "status": "{{#if data.k.welcome}}scheduled{{/if}}{{#if data.k.learning}}open{{/if}}", '
                           '"bpEvent": "{{data.req.ev}}", "dueOffset": {{data.k.due}}, "tier": "{{data.k.tier}}", "source": "baseline", "orgWid": "{{data.om.org}}", "hirePerson": "{{data.pp.person}}"}'),
    ], [("tasks", 'data.kitOut.message.asJSON()', 'data.k.hit.and(data.k.itype.equals("access").not()).and(data.k.ov.not())')]),
    template("prepBody", '{"key": "KIT:{{data.req.stamp}}:PREPARE", "taskType": "prepare", "hireWid": "{{data.req.who}}", "newHire": {"id": "{{data.req.who}}"}, '
                         '"title": "Prepare for the new hire: personal note and access list", "status": "open", "bpEvent": "{{data.req.ev}}", "orgWid": "{{data.om.org}}", "source": "baseline", "hirePerson": "{{data.pp.person}}"}'),
    send("createPrep", "POST", '(if (data.kd.fresh) data.req.app.append("dynKitTasks") else data.req.app.append("dynKitTasks/none/skip"))', 'data("prepBody", "message")'),
    values("kb", [("t", "String", 'data.kits.tasks.toString()'), ("any", "Boolean", 'data.kd.fresh.and(data.kb.t.length() > 2)')]),
    template("kitBulk", '{"data": {{data.kits.tasks}}}'),
    send("createKit", "POST", '(if (data.kb.any) data.req.app.append("dynKitTasks?bulk=true") else data.req.app.append("dynKitTasks/none/skip"))', 'data("kitBulk", "message")'),
    *alerted_check("kitSaved", '(if (data.kd.fresh) data.createPrep.responseStatusCode.is2xxStatusCode().and((if (data.kb.any) data.createKit.responseStatusCode.is2xxStatusCode() else true)) else true)',
                   '"Workday refused the onboarding kit tasks: " + data.createPrep.response.toString().truncate(150) + " " + data.createKit.response.toString().truncate(150)', "FormCompose"),
]


# FormReconcile (2026-11-19, after acceptance item 9): the safety net behind FormAssign, run on a schedule from an
# integration system (Launch / Schedule Integration). It reads every open form assignment (Dyn Response formCode BP,
# status "Assigned...", up to 200 per run, WQL) and for each one reads its business process event:
#   - the event has ended (completed, cancelled, denied): the assignment is closed ("Closed: event <status>
#     (reconciled)"), so it leaves "Next forms to fill";
#   - the event is in progress and its form names extra forms (alsoAssign) that this event has no assignment for: the
#     missing assignment is created (pinned to the family's published version, key "...-1R"/"-2R") and an ALERT record
#     says what was repaired, so an admin sees it;
#   - the event can't be read (no access, 404): nothing is changed and it is counted as unreadable.
# Every run writes one summary record (formCode RECON): checked, closed, added, unreadable.
_RI = 'data.rows.item'
_RS = lambda k: _RI + '.stringAtJsonPathWithDefault("$.%s", "")' % k


def _rec_extra(i):
    x, need = 'data.rx.x%d' % i, 'data.rh.need%d' % i
    return [
        send("getFam%d" % i, "GET", 'data.cfg.app.append("dynForms?limit=100&family=").append((if (%s) %s.urlEncode() else "none"))' % (need, x), None),
        values("rp%d" % i, [("pinned", "String", _pinned('data.getFam%d' % i, x))]),
        template("addBody%d" % i, '{"responseKey": "{{data.r.key}}-%dR", "formCode": "BP", "status": "Assigned: {{data.st.desc}}", '
                                  '"nextForm": "{{data.rp%d.pinned}}", "parentKey": "FORM:{{%s}}", "bpEvent": "{{data.r.ev}}", "bpTarget": "{{data.r.who}}"}' % (i, i, x)),
        send("add%d" % i, "POST", '(if (%s) data.cfg.app.append("dynResponses") else data.cfg.app.append("dynResponses/none/skip"))' % need, 'data("addBody%d", "message")' % i),
    ]


RECONCILE = [
    values("cfg", [("app", "String", _APP),
                   ("query", "String", '"SELECT workdayID, responseKey, bpEvent, bpTarget, bpPerson, nextForm, parentKey, alsoExpected FROM ".append(context.appReferenceId()).append("_dynResponses WHERE formCode = \\"BP\\" AND status startswith \\"Assigned\\"")'),
                   ("stamp", "String", 'datetime.now("UTC").format("yyyyMMddHHmmssSSS")')]),
    send("getOpen", "GET", '"/wql/v1/data?limit=200&query=".append(data.cfg.query.urlEncode())', None),
    check("openOk", 'data.getOpen.responseStatusCode.is2xxStatusCode()', '"Could not list the open form assignments: " + data.getOpen.response.toString().truncate(300)'),
    loop("rows", 'data.getOpen.response.asJSON().iterator("$.data[*]")', [
        values("r", [("id", "String", _RS("workdayID")), ("ev", "String", _RS("bpEvent")), ("who", "String", _RS("bpTarget")),
                     ("form", "String", _RS("nextForm")), ("key", "String", _RS("responseKey")), ("pk", "String", _RS("parentKey")),
                     ("exp", "String", _RS("alsoExpected")), ("per", "String", _RS("bpPerson")),
                     # an extra assignment this reconciliation created earlier ("...-1R"/"-2R"): its main assignment's key
                     ("mine", "Boolean", 'data.r.key.endsWith("-1R").or(data.r.key.endsWith("-2R"))'),
                     ("mainKey", "String", '(if (data.r.mine) data.r.key.substring(0, data.r.key.length() - 3) else "")'),
                     ("fam", "String", 'data.r.pk.replace("FORM:", "")')]),
        send("getEv", "GET", '"/businessProcess/v1/events/".append((if (data.r.ev.isEmpty()) "none" else data.r.ev))', None),
        values("st", [("read", "Boolean", 'data.getEv.responseStatusCode.is2xxStatusCode()'),
                      ("status", "String", '(if (data.st.read) data.getEv.response.asJSON().stringAtJsonPathWithDefault("$.status.descriptor", "") else "")'),
                      ("desc", "String", '(if (data.st.read) ' + _clean('data.getEv.response.asJSON().stringAtJsonPathWithDefault("$.descriptor", "Business process")', 120) + ' else "Business process")'),
                      ("open", "Boolean", 'data.st.status.contains("Progress")'),
                      ("ended", "Boolean", 'data.st.read.and(data.st.status.isEmpty().not()).and(data.st.open.not())')]),
        # an open assignment saved before bpPerson existed: look up its target's person (so a new hire finds it)
        send("getPer", "GET", '"/wql/v1/data?limit=1&query=".append((if (data.r.per.isEmpty().or(data.r.per.startsWith("?")).and(data.r.who.isEmpty().not())) ("SELECT person FROM allWorkers WHERE workdayID = \\"" + data.r.who.replace("\\"", "") + "\\"") else "SELECT person FROM allWorkers WHERE workdayID = \\"none\\"").urlEncode())', None),
        values("rpn", [("pid", "String", '(if (data.getPer.responseStatusCode.is2xxStatusCode()) data.getPer.response.asJSON().stringAtJsonPathWithDefault("$.data[0].person.id", "") else "")'),
                       ("set", "Boolean", 'data.r.per.isEmpty().or(data.r.per.startsWith("?")).and(data.rpn.pid.isEmpty().not())')]),
        template("perBody", '{"bpPerson": "{{data.rpn.pid}}"}'),
        send("setPer", "PATCH", '(if (data.rpn.set) data.cfg.app.append("dynResponses/").append(data.r.id) else data.cfg.app.append("dynResponses/none"))', 'data("perBody", "message")'),
        template("closeBody", '{"status": "Closed: event {{data.st.status}} (reconciled)"}'),
        send("closeStale", "PATCH", '(if (data.st.ended) data.cfg.app.append("dynResponses/").append(data.r.id) else data.cfg.app.append("dynResponses/none"))', 'data("closeBody", "message")'),
        # the extra forms recorded on this main assignment when the request started (FormAssign's alsoExpected;
        # "-" or empty = nothing to check, so older assignments are never given forms they didn't start with)
        values("rx", [("list", "String", '(if (data.st.open.and(data.r.exp.equals("-").not())) data.r.exp.replace(" ", "").replace("\'", "").replace("\\"", "") else "")'),
                      ("x1", "String", '(if (data.rx.list.contains(",")) data.rx.list.substringBefore(",") else data.rx.list)'),
                      ("x2", "String", '(if (data.rx.list.contains(",")) data.rx.list.substringAfter(",").substringBefore(",") else "")')]),
        send("getSibs", "GET", 'data.cfg.app.append("dynResponses?limit=100&bpEvent=").append((if (data.rx.list.isEmpty()) "none" else data.r.ev))', None),
        values("rh", [("sibsOk", "Boolean", 'data.getSibs.responseStatusCode.is2xxStatusCode()'),
                      ("need1", "Boolean", 'data.rh.sibsOk.and(data.rx.x1.isEmpty().not()).and(data.getSibs.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.rx.x1).append("\')].id"), "").isEmpty())'),
                      ("need2", "Boolean", 'data.rh.sibsOk.and(data.rx.x2.isEmpty().not()).and(data.getSibs.response.asJSON().stringAtJsonPathWithDefault("$.data[?(@.formCode == \'BP\' && @.parentKey == \'FORM:".append(data.rx.x2).append("\')].id"), "").isEmpty())')]),
    ] + _rec_extra(1) + _rec_extra(2) + [
        # an extra assignment this reconciliation created whose main assignment doesn't expect that form (it was added
        # before expectations were recorded, 2026-11-19): close it
        send("getMainRow", "GET", 'data.cfg.app.append("dynResponses?limit=1&responseKey=").append((if (data.r.mine) data.r.mainKey.urlEncode() else "none"))', None),
        values("rm", [("mexp", "String", 'data.getMainRow.response.asJSON().stringAtJsonPathWithDefault("$.data[0].alsoExpected", "")'),
                      ("drop", "Boolean", 'data.r.mine.and(data.st.ended.not()).and(data.getMainRow.responseStatusCode.is2xxStatusCode()).and(data.rm.mexp.contains(data.r.fam).not())')]),
        template("dropBody", '{"status": "Closed: not expected for this request (reconciled)"}'),
        send("dropExtra", "PATCH", '(if (data.rm.drop) data.cfg.app.append("dynResponses/").append(data.r.id) else data.cfg.app.append("dynResponses/none"))', 'data("dropBody", "message")'),
        values("ra", [("added", "String", '(if (data.rh.need1.and(data.add1.responseStatusCode.is2xxStatusCode())) data.rx.x1.append(" ") else "").append((if (data.rh.need2.and(data.add2.responseStatusCode.is2xxStatusCode())) data.rx.x2 else "")).trim()'),
                      ("failed", "String", '(if (data.rh.need1.and(data.add1.responseStatusCode.is2xxStatusCode().not())) data.rx.x1.append(" ") else "").append((if (data.rh.need2.and(data.add2.responseStatusCode.is2xxStatusCode().not())) data.rx.x2 else "")).trim()'),
                      ("flag", "Boolean", 'data.ra.added.isEmpty().not().or(data.ra.failed.isEmpty().not())'),
                      ("action", "String", '(if (data.st.ended.and(data.closeStale.responseStatusCode.is2xxStatusCode())) "closed" else (if (data.rm.drop.and(data.dropExtra.responseStatusCode.is2xxStatusCode())) "dropped" else (if (data.ra.added.isEmpty().not()) "added" else (if (data.st.read.not()) "unreadable" else (if (data.ra.failed.isEmpty().not()) "failed" else "ok")))))')]),
        template("alertBody", '{"responseKey": "TEST:DYN:ALERT{{data.cfg.stamp}}-{{data.r.key}}", "formCode": "ALERT", '
                              '"status": "Reconciled: {{data.st.desc}}: added {{data.ra.added}}; could not add {{data.ra.failed}}", "nextForm": "", "parentKey": "{{data.r.key}}", '
                              '"bpEvent": "{{data.r.ev}}", "bpTarget": "{{data.r.who}}"}'),
        send("saveAlert", "POST", '(if (data.ra.flag) data.cfg.app.append("dynResponses") else data.cfg.app.append("dynResponses/none/skip"))', 'data("alertBody", "message")'),
        template("rowOut", '{"key": "{{data.r.key}}", "action": "{{data.ra.action}}"}'),
    ], [("results", 'data.rowOut.message.asJSON()')]),
    # Backfill (2026-11-19, acceptance item 3): responses saved before the flat reporting fields existed get them now,
    # up to 200 per run: family and formVersion from formCode ("FAM@2" -> FAM / 2, "FAM" -> FAM / 1) and orgName from the
    # subject's primary supervisory organization, so a report can group every response by form, version and department.
    values("bf", [("query", "String", '"SELECT workdayID, formCode, subject FROM ".append(context.appReferenceId()).append("_dynResponses WHERE family is empty AND formCode not in (\\"BP\\", \\"ALERT\\", \\"RECON\\")")')]),
    send("getOld", "GET", '"/wql/v1/data?limit=200&query=".append(data.bf.query.urlEncode())', None),
    loop("old", 'data.getOld.response.asJSON().iterator("$.data[*]")', [
        values("o", [("id", "String", 'data.old.item.stringAtJsonPathWithDefault("$.workdayID", "")'),
                     ("fc", "String", 'data.old.item.stringAtJsonPathWithDefault("$.formCode", "")'),
                     ("fam", "String", '(if (data.o.fc.contains("@")) data.o.fc.substringBefore("@") else data.o.fc)'),
                     ("ver", "String", '(if (data.o.fc.contains("@").and(data.o.fc.substringAfter("@").isEmpty().not())) data.o.fc.substringAfter("@") else "1")'),
                     ("who", "String", 'data.old.item.stringAtJsonPathWithDefault("$.subject.id", "")')]),
        send("getWho", "GET", '"/common/v1/workers/".append((if (data.o.who.isEmpty()) "none" else data.o.who))', None),
        values("og", [("name", "String", '(if (data.getWho.responseStatusCode.is2xxStatusCode()) ' + _clean('data.getWho.response.asJSON().stringAtJsonPathWithDefault("$.primarySupervisoryOrganization.descriptor", "")', 200) + ' else "")')]),
        template("fillBody", '{"family": "{{data.o.fam}}", "formVersion": {{data.o.ver}}, "orgName": "{{data.og.name}}"}'),
        send("fillOld", "PATCH", 'data.cfg.app.append("dynResponses/").append((if (data.o.id.isEmpty()) "none" else data.o.id))', 'data("fillBody", "message")'),
        values("od", [("done", "String", '(if (data.fillOld.responseStatusCode.is2xxStatusCode()) "yes" else "no")')]),
        template("oldOut", '{"done": "{{data.od.done}}"}'),
    ], [("filled", 'data.oldOut.message.asJSON()')]),
    values("sum", [("t", "String", 'data.rows.results.toString()'),
                   ("bt", "String", 'data.old.filled.toString()'),
                   ("backfilled", "String", '(data.sum.bt.replace("\\"yes\\"", "\\"yes\\"#").length() - data.sum.bt.length()).toString()'),
                   ("notFilled", "String", '(data.sum.bt.replace("\\"no\\"", "\\"no\\"#").length() - data.sum.bt.length()).toString()'),
                   ("checked", "String", '(data.sum.t.replace("\\"action\\"", "\\"action\\"#").length() - data.sum.t.length()).toString()'),
                   ("closed", "String", '(data.sum.t.replace("\\"closed\\"", "\\"closed\\"#").length() - data.sum.t.length()).toString()'),
                   ("added", "String", '(data.sum.t.replace("\\"added\\"", "\\"added\\"#").length() - data.sum.t.length()).toString()'),
                   ("dropped", "String", '(data.sum.t.replace("\\"dropped\\"", "\\"dropped\\"#").length() - data.sum.t.length()).toString()'),
                   ("unreadable", "String", '(data.sum.t.replace("\\"unreadable\\"", "\\"unreadable\\"#").length() - data.sum.t.length()).toString()'),
                   ("failed", "String", '(data.sum.t.replace("\\"failed\\"", "\\"failed\\"#").length() - data.sum.t.length()).toString()')]),
    template("sumBody", '{"responseKey": "TEST:DYN:RECON{{data.cfg.stamp}}", "formCode": "RECON", '
                        '"status": "Reconciled {{data.sum.checked}} open assignments: {{data.sum.closed}} closed (event ended), {{data.sum.added}} repaired, {{data.sum.dropped}} closed as not expected, '
                        '{{data.sum.failed}} could not be repaired, {{data.sum.unreadable}} events unreadable; reporting fields filled on {{data.sum.backfilled}} older responses ({{data.sum.notFilled}} failed)", "nextForm": "", "parentKey": "", "bpEvent": "", "bpTarget": ""}'),
    send("saveSum", "POST", 'data.cfg.app.append("dynResponses")', 'data("sumBody", "message")'),
    check("sumSaved", 'data.saveSum.responseStatusCode.is2xxStatusCode()', '"Could not save the reconciliation summary: " + data.saveSum.response.toString().truncate(300)'),
]


# FormPrune (2026-11-19): deletes form definitions this app should not hold (the move copied all 19 Extend Toolkit forms;
# only the onboarding forms stay). Body {"forms": "<id>,<id>", "q1": "...", "q2": "...", "q3": "..."}: comma-joined WIDs
# chosen on the DynFormPrune page, each list up to 100 (the bulk DELETE limit). An empty list deletes nothing.
def _ids(key):
    return (REQ + '.stringAtJsonPathWithDefault("$.' + key + '", "").replace("\\"", "").replace("\\\\", "").replace(" ", "")')


def _bulk_body(key):
    return ('"{\\"data\\": [{\\"id\\": \\"".append(data.req.' + key + '.replace(",", "\\"}, {\\"id\\": \\"")).append("\\"}]}")')


PRUNE = [values("req", [("app", "String", _APP)] + [(k, "String", _ids(k)) for k in ("forms", "q1", "q2", "q3")]),
         values("bodies", [(k, "String", _bulk_body(k)) for k in ("forms", "q1", "q2", "q3")])]
for k, coll in (("q1", "dynQuestions"), ("q2", "dynQuestions"), ("q3", "dynQuestions"), ("forms", "dynForms")):
    PRUNE.append(template(k + "Body", "{{data.bodies." + k + "}}"))
    PRUNE.append(send("del_" + k, "DELETE", '(if (data.req.' + k + '.isEmpty()) data.req.app.append("' + coll + '/none") else data.req.app.append("' + coll + '?bulk=true"))',
                      'data("' + k + 'Body", "message")'))
PRUNE.append(values("out", [(k, "String", '(if (data.req.' + k + '.isEmpty()) "skipped" else data.del_' + k + '.responseStatusCode.format("0"))') for k in ("forms", "q1", "q2", "q3")]))
PRUNE.append(template("answer", '{"forms": "{{data.out.forms}}", "q1": "{{data.out.q1}}", "q2": "{{data.out.q2}}", "q3": "{{data.out.q3}}"}'))


# AnswerPurge (2026-11-20, retention): Body {"g": "<id>,...", "c": "...", "r": "..."} from the FormPurge page: the
# General, Confidential and Restricted answers past their retention (up to 100 each). Deleted in bulk; an empty list
# deletes nothing.
PURGE = [values("req", [("app", "String", _APP)] + [(k, "String", _ids(k)) for k in ("g", "c", "r")]),
         values("bodies", [(k, "String", _bulk_body(k)) for k in ("g", "c", "r")])]
for k, coll in (("g", "dynAnswers"), ("c", "dynAnswerConfs"), ("r", "dynAnswerRestrs")):
    PURGE.append(template(k + "Body", "{{data.bodies." + k + "}}"))
    PURGE.append(send("del_" + k, "DELETE", '(if (data.req.' + k + '.isEmpty()) data.req.app.append("' + coll + '/none") else data.req.app.append("' + coll + '?bulk=true"))',
                      'data("' + k + 'Body", "message")'))
PURGE.append(values("out", [(k, "String", '(if (data.req.' + k + '.isEmpty()) "skipped" else data.del_' + k + '.responseStatusCode.format("0"))') for k in ("g", "c", "r")]))
PURGE.append(template("answer", '{"general": "{{data.out.g}}", "confidential": "{{data.out.c}}", "restricted": "{{data.out.r}}"}'))


def write_forms(write, ORCH, DOM):
    write(os.path.join(ORCH, 'AnswerPurge.orchestration'), flow("AnswerPurge", PURGE, 'data("answer", "message")', DOM))
    os.makedirs(ORCH, exist_ok=True)
    write(os.path.join(ORCH, 'FormPrune.orchestration'), flow("FormPrune", PRUNE, 'data("answer", "message")', DOM))
    write(os.path.join(ORCH, 'DynClose.orchestration'), flow("DynClose", DYNCLOSE, 'data("answer", "message")', DOM))
    write(os.path.join(ORCH, 'FormAssign.orchestration'), bp_flow("FormAssign", FORMASSIGN, [
        _param("actionEvent"), _param("formCode", 's"""TEST:DYN:ADDR"""'), _param("worker", '""')]))
    rf = integration_flow("FormReconcile", RECONCILE)
    rf["_value"]["resources"]["_value"]["retryConfigs"] = S(["Map", ["WithNotes", "RetryConfig"]], RETRY_CONFIGS)
    _retrying(rf["_value"]["nodes"])
    write(os.path.join(ORCH, 'FormReconcile.orchestration'), rf)
    write(os.path.join(ORCH, 'FormEnded.orchestration'), bp_flow("FormEnded", FORMENDED, [_param("actionEvent")]))
    write(os.path.join(ORCH, 'FormCompose.orchestration'), bp_flow("FormCompose", FORMCOMPOSE, [
        _param("actionEvent"), _param("processType", 's"""TimeOff"""'), _param("worker", '""')]))
    write(os.path.join(ORCH, 'FormGate.orchestration'), bp_flow("FormGate", FORMGATE, [
        _param("actionEvent"), _param("worker", '""'), _param("formCode", '""'), _param("noForm", 's"""cancel"""'),
        _param("onFail", 's"""cancel"""'), _param("resultsUrl", '""')]))

