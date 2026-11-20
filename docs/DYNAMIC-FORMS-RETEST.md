# Dynamic forms: retest checklist after a Workday release

Run this in the dev tenant in the week after each Workday major release (and after any change to the
form pages, FormAssign or FormGate). Each line says what to do, what you should see, and where it was
first proven, so a failure can be compared with a known-good run. Use TEST:... values only.

Before starting: the latest commit on `main` deployed (CI "Check and deploy" green), and the tester
signed in as an ordinary user with the app's domain (not an administrator), plus one approver user.

## 1. Build and load (no data changes)

| # | Do | Expect |
|---|----|--------|
| 1.1 | Push any commit (or rerun the last CI run). | App Hub build succeeds; no new ERROR lines. New WARN lines: read them, they often announce a rule that becomes an error later. |
| 1.2 | Open Fill a form (`dynFormLookup?form=TEST:DYN:REP`), Results (no form, and `?form=TEST:DYN:ADDR@2`), Copy, Seed, Form Studio, My Forms to Fill. Time each with the JSON fetch (`/wday/app/<app>/<tenant>/<app>/<route>`, Accept JSON, routes are case-sensitive, 7 loads, median). | All load. Fill page (30 slots) about 4 s, Results about 4 s with no form and 1 s with one (2026-11-19). More than double: investigate before continuing. |
| 1.3 | DynFormBigLoop with `?form=TEST:DYN:BIG`. | 84 questions, no page error. |

## 2. Filling a form

| # | Do | Expect |
|---|----|--------|
| 2.1 | Fill TEST:DYN:SMALL: toggle the show-when question, leave a hidden required question empty, check the calculated total. | Hidden questions don't block OK and aren't saved; total updates; one response + its answers saved in one bulk POST. |
| 2.2 | Fill TEST:DYN:LOOKUP2: pick a position through the folders (By manager), an organization, a worker. | Folders show counts; typing searches; saved answers keep their POSITION / SUPERVISORY_ORGANIZATION / WORKER links (Results "Picked record" opens the record). |
| 2.3 | Fill TEST:DYN:STUDIO with `ab12`, then `AB1234`. | First refused with the question's message, second accepted. |
| 2.4 | Fill TEST:DYN:REQ with request type sw. | The SW sub-form appears inline; saved with parentKey = the request. |
| 2.6 | Fill TEST:DYN:REP: dependants 2, tick Full-time student on dependant 2; then try 9. | Two numbered copies; School (2) only; 9 shows 4 copies and the error "At most 4 here"; back to 2 clears it. Answers saved with rowNumber 1/2, formCode TEST:DYN:DEP for the copies. |
| 2.7 | Click OK on any fill, Seed or Copy page. | Lands on Results with no "A failure occurred" (that error meant the Results page itself failed to load). |
| 2.8 | Accessibility: on TEST:DYN:REP enter 9 dependants and read the accessibility tree, then one pass with a real screen reader (NVDA or VoiceOver). | Every field named, copies numbered "(n)", the count box `aria-invalid` with the "At most 4" message in its name, the error announced. Known gaps: date Day/Year parts unnumbered (Workday's widget); Tab after the count skips the new copies (2026-11-19). |
| 2.5 | Fill TEST:DYN:ACC as a user whose Workday language is French (Canada). | Commute shows "Distance domicile-travail (km)"; other questions fall back to English. |

## 3. Delivered business processes

| # | Do | Expect |
|---|----|--------|
| 3.1 | Request Time Off, fill the assigned form with parking = yes. | Event canceled by FormGate; gate record "Stopped: ..."; cancel comment names the reason. |
| 3.2 | Request Time Off, parking = no, commute 120. | Event continues; comment contains `[ROUTE:HR]`; the worker's route record says "Route: HR"; the HR approval step is Awaiting Action. Rule Tester (event related actions → Business Process → Test Rule, TEST DYN Route HR): both rows 1, Yes. |
| 3.3 | Same with commute 5. | Comment `[ROUTE:NORMAL]`; HR step Not Required. |
| 3.4 | Change Job for a worker (the event target is the organization, the worker comes from Field Worker). | Assignment and gate find the worker; route as in 3.2/3.3; the sub-process approval follows the same rule. |
| 3.5 | Two open processes for the same worker, one commute 120 and one commute 5. | Each routes on its own comment (one HR, one normal). |
| 3.6 | A gate with onFail = sendback and a failing form. | Either "Sent back" (the requester gets the step again, fixes the form, resubmits and the gate passes) or "Stopped" with the send-back HTTP status in the gate record. Record which one this release gives. |
| 3.8 | Check the form steps run as the ISU: the event's Process History shows step c (FormAssign) and the gate step completed by TEST_LAB_SUB_ISU, and its Orchestrations tab says Successfully Completed for both. | A green process alone proves nothing: a failed orchestration still advances its step. |
| 3.9 | Hire (or Launch Onboarding) for a test pre-hire. | Onboarding (the definition that actually runs, usually Default) step aa writes an assignment whose bpTarget is the worker, not the pre-hire. |
| 3.10 | Correct an in-progress request whose form steps have run. | No new assignment or gate record: Correct doesn't re-run Service steps. |
| 3.11 | Run TEST:DYN:RECON Integration (Launch / Schedule Integration, Run Now; it also runs hourly). | A RECON record "Reconciled N open assignments: ...; reporting fields filled on N older responses (0 failed)". Any ALERT records since the last run are read and explained. |
| 3.12 | Rescind a completed Change Job that had form steps. | FormEnded closes the assignment at once ("Closed: event Rescinded (closed when it ended)"); before FormEnded, the next FormReconcile run did it ("... (reconciled)"). The GATE record stays. |
| 3.13 | Launch Onboarding for a test hire, fill the form as them (Start Proxy), submit the To Do. | Check which Onboarding definition runs (org-specific first). Gate record "Passed ..." written by the ISU. With an extra form left empty (policy pass) the main form's commute still routes: 120 gives [ROUTE:HR] (fixed 2026-11-19). |
| 3.7 | Open the event as the approver (not the initiator). | The gate comment with the answers is visible in the event's comments; a confidential answer reads `key=(confidential)`, never its value. |
| 3.14 | Forged tag: on a request for a worker whose route record says normal, submit any To Do with the comment `[ROUTE:HR] TEST forged tag check`, then Rule Tester TEST DYN Route HR. | Comments row 1, route record row empty, result **No** (2026-11-19, 645$927). Cancel the request afterwards. |
| 3.15 | Cancel a request with open form assignments (a TEST:DYN:BULK time off). | The event's Orchestrations tab shows "Cancel · FormEnded · Successfully Completed" within seconds; its assignments read "Closed: event Canceled (closed when it ended)" (2026-11-19). Repeat for Rescind on Change Job and Onboarding when a test event allows. |
| 3.16 | Readiness page: paste `docs/dynamic-forms-readiness.json`, Run all. | "Process definitions" rows list every definition of Request Time Off, Change Job and Onboarding with step counts; any definition without Service steps shows Review. Work through the To do rows. |

## 4. Versions and copies

| # | Do | Expect |
|---|----|--------|
| 4.1 | Copy page: new version of TEST:DYN:ACC, add a question, publish it; start a process. | The assignment's Next form is the new version's code. |
| 4.2 | Start a process, then publish one more version, then fill. | The fill page opens the version pinned at assignment, not the newest. |
| 4.3 | Copy page: add questions from another form with a clashing key and a rule on it. | Preview lists `key → key_2` and the rewritten rule; the original form is unchanged afterwards. |
| 4.5 | Copy page: add TEST:DYN:REP's questions to TEST:DYN:REP (preview only, then Cancel). | Preview renames depCount, deps, repNotes to `_2`, says `deps_2` now counts `depCount_2`, and warns the form needs 36 question slots of 30. |
| 4.4 | Export a version as JSON, import it as a new code. | Draft form with the same questions; lookups not approved here are listed in the preview. |

## 5. Security

| # | Do | Expect |
|---|----|--------|
| 5.1 | As a user with the app's domain but not Dyn Confidential Answers (Start Proxy as Teresa Serrano, group TEST:DYN Non-HR App Viewer, View only), open Results for TEST:DYN:ACC and run WQL `SELECT secretText, textValue FROM <appRef>_dynAnswers WHERE formCode = "TEST:DYN:ACC"`. | Confidential column blank; WQL leaves secretText out. |
| 5.2 | As a user with it. | The salary value shows. |
| 5.4 | As an employee (Start Proxy) open My Forms to Fill and fill one assignment. | Only their own assignments; the fill saves through the ISU. A future-dated new hire (before the hire date) gets "not authorized": the Dyn Forms Fill policy grants All Employees (2026-11-19). |
| 5.6 | Fill TEST:DYN:ACC with a confidential number question, then WQL as an HR Administrator: `SELECT qKey, secretText, textValue, numberValue FROM <appRef>_dynAnswers WHERE secretText is not empty`. | The value is only in secretText; textValue, numberValue and dateValue are empty for that row. |
| 5.5 | WQL as an HR Administrator: `SELECT secretText FROM <appRef>_dynAnswers WHERE secretText is not empty`. | Rows come back; as a user outside the group the field is left out. |
| 5.3 | Launch FormGate/FormAssign by URL as a user without the app's domain. | Refused. |

## 6. Reporting

| # | Do | Expect |
|---|----|--------|
| 6.1 | WQL `SELECT worker, COUNT(workdayID) FROM <appRef>_dynAnswers GROUP BY worker` and All Workers `dynAnswer_worker_<appRef>`. | Both return rows; field aliases unchanged (a renamed alias breaks reports and calculated fields). |
| 6.3 | Results: responses carry Form Family, Form Version, Organization; `SELECT family, COUNT(workdayID) FROM <appRef>_dynResponses WHERE formCode not in ("BP", "ALERT", "RECON") AND family is empty GROUP BY family`. | No rows once FormReconcile has run (older responses backfilled). |
| 6.2 | The calculated fields TEST DYN Comment Route HR (contains `[ROUTE:HR]` And Comment by Person is empty) and TEST DYN Event Route HR Comments, and the condition rule TEST DYN Route HR (comments > 0). | Still saved and in use (Rule Usage lists Request Time Off, Change Job and the sub-process). |
| 6.4 | Configure Orchestrations on each definition, and Edit Tenant Setup - Business Processes. | FormEnded rows present (Cancel, Rescind, Deny where offered) with the forms ISU as launch user; the tenant launch user is set. |

## 7. Tiered ownership (plan phases 1 to 5, 2026-11-20)

Setup first: departments marked, org map rebuilt, settings saved, at least one enterprise, one department and one team block published and assigned to the same process type, the process's Service step pointing at FormCompose.

| # | Phase | Do | Expect |
|---|---|---|---|
| 7.1 | 1 | Fill a block with a Confidential question as an employee; then as a user with Use: Dynamic Forms but not Dyn Confidential Answers open Results, the event and its comments. | The answer is a Dyn Answer Confidential row; not on Results for that user; the gate comment shows only General answers. |
| 7.2 | 1 | Same with a Restricted question; open as a manager outside the Restricted group. | Not visible anywhere; never offered for reuse. |
| 7.3 | 1 | Type `[ROUTE:HR]` into a comment on a Request Time Off event by hand (the gate routed normal). Rule Tester, TEST DYN Route HR. | Comments 0, rule No: routing ignores it. A gate run with commute 100+ on another request: comments 1, Yes. |
| 7.4 | 1 | Two open time-off requests for one worker, one HR (commute 120) and one normal (commute 5). | Each routes on its own event; two route records keyed by event. |
| 7.5 | 2 | Request for a worker in a team under a department under the enterprise. | One composed form (Dyn Form kind composed) with three tier sections in order; at most 28 slots; one assignment. |
| 7.6 | 2 | Publish a department block over its budget (11 questions, budget 10). | Publish refused with the slot count. |
| 7.7 | 2 | Publish a new version of a block while a request is open; then fill the open request and start a new one. | The open request keeps its pinned versions; the new request gets a new composed form with the new version. |
| 7.8 | 2 | The same library key in the enterprise and a department block. | Asked once (the enterprise copy). |
| 7.9 | 2 | Run FormCompose twice on one event (send back and resubmit). | The same assignment reopened, no second assignment, the composed form reused. |
| 7.10 | 3 | A question with prefill (title) whose value is right. | Shown first with "Check:" and the value filled; OK keeps it, source prefill. |
| 7.11 | 3 | A reusable answer given on one process, then a second process asks the same key. | Filled in, label "from your earlier answer, kept until <date>"; changeable; source reused. |
| 7.12 | 3 | Change the worker's location (or job title), then start a new request. | The commute answer is not offered again. |
| 7.13 | 3 | My answers: clear one, then start a new request. | Asked again. |
| 7.14 | 4 | Team block with Org + subordinates. | Applies two levels down; not to a sibling org. Reach preview shows the orgs and workers. |
| 7.15 | 4 | Team block whose subordinates scope reaches another department. | Block assignments shows the error; publish refused. |
| 7.16 | 4 | Move an org under the owner org in Workday, rebuild the org map. | The next request includes the block; owner dashboard shows reach changed. |
| 7.17 | 5 | Launch Onboarding for a hire in a test team with the joiner kit enabled and a team access item. | Prepare task and welcome/learning tasks created once; KitPrepare lists baseline + team items, no duplicates. |
| 7.18 | 5 | Untick a baseline item without a reason; then with one. | Error first; then a "removed" row with the reason, visible to the fulfiller. |
| 7.19 | 5 | An elevated item: publish without the governance tick; request it without a reason. | Both refused. |
| 7.20 | 5 | KitQueue ?group=IT: approve, decline with reason, mark done; try done on an unapproved elevated item. | Statuses saved; the elevated one refused. |
| 7.21 | 5 | Cancel the Onboarding before the start. | FormEnded closes the form assignment (kit tasks stay as history; see PROGRESS). |
| 7.22 | Recs | KitPeers with 5 peers (same org and job profile) of whom 4 have an item done; open KitPrepare for a new hire there. | "Recommended: 4 of 5 peers have it", ticked; with 2 peers nothing shown; names never shown. |
| 7.23 | Pkg | Enable the joiner kit; copy one delivered item and change it; start an Onboarding. | Delivered items installed once; the copy replaces the delivered item in the new hire's tasks. |
| 7.24 | 4 | FormPurge with a short retention in settings, then confirm. | AnswerPurge deletes up to 100 per class and answers its status per class. |

## After the run

Write the date, release, tester and any differences in `docs/DYNAMIC-FORMS-NOTES.md`, and move any
platform change into `CLAUDE.md`. Cancel the open test events the run left behind (comment "TEST run
cleanup").
