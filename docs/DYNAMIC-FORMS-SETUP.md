# Dynamic forms: putting a form on a business process

How to add a form to a Workday business process (Request Time Off, Change Job, Onboarding and so on), and where to put each step. Every rule here was tested live in the dev tenant on 2026-11-19 (details in DYNAMIC-FORMS-NOTES.md, "Acceptance item 1" to "Round 8").

## What goes on the process

| Step | What it is | Who does it |
|---|---|---|
| **Assign** | Service step → Orchestration Service → **FormAssign**, "advance when complete". Inputs: actionEvent = Workday ID, formCode = the form family, worker = WID from Field "Worker". | Run As the forms ISU (TEST_LAB_SUB_ISU in dev) |
| **Fill** | To Do "Fill the form" (optional; the form also shows in My Forms to Fill) | The person the form is for |
| **Gate** | Service step → Orchestration Service → **FormGate**, plus a To Do **Route marker** in parallel with it. Inputs: worker, formCode, noForm, onFail, resultsUrl. The form's own gate policy (Copy page → Set the gate policy) overrides noForm and onFail. | Gate: the forms ISU. Marker group: a group the ISU's work can complete (HR Partner + Initiator in dev) |
| **Route** (optional) | Any later step with condition rule TEST DYN Route HR: the event's `[ROUTE:HR]` marker comment **and** the worker's app route record (TEST:DYN:ROUTE:<worker>, written only by FormGate) | As the process needs |
| **End** | Configure Orchestrations on the definition: **FormEnded** on Cancel, Rescind and Deny (where offered) | Launch user: the forms ISU |

Security for the ISU's group on the process policy: **View All** and **Cancel (Web Service)** (plain Cancel doesn't take integration system groups). On the app domain Use: Developer Toolkit: Report/Task View and Modify, Integration Get and Put. On Dyn Confidential Answers: Integration Get and Put. Plus the Person-field grant FormAssign needs to read the event's Person (bpPerson; see the notes, "ISU bpPerson"). Then Activate Pending Security Policy Changes.

**Find every definition first.** A tenant often runs several definitions of one process (by organization): Launch Onboarding here used "Onboarding for Next Level Enterprise", not the default one. Paste `docs/dynamic-forms-readiness.json` into the Extend Toolkit's **Readiness** page and run it: its "Process definitions" rows list every definition of Request Time Off, Change Job and Onboarding with their Service and To Do step counts, and flag any definition without the form steps. Then open each definition and add the rows below to the setup kit, one per definition.

## Rule 1: where the gate sits decides what "send back" can do

The form policy offers three outcomes when a form is missing or its check fails: **cancel**, **sendback** or **pass**. Send back only works from an approval-type step:

- **Gate after an approval step:** send back returns the request to that approval's sender (Workday's own Send Back). Use this placement when the requester should be able to fix the form and resubmit the same request.
- **Gate before any approval step** (only To Do or Service steps waiting): Workday has no send-back target (`values/sendBack/to` returns 0), so the gate **falls back to cancel** and says so in the marker comment. Treat this placement as a hard stop: the requester starts a new request.

Choose the placement per process and set the form's policy to match. Don't set `sendback` on a form whose gate sits before an approval; it behaves as cancel.

Also check:
- **Put the gate after the last step the requester completes.** A condition rule on the step after the gate is evaluated as the user who completed the step before it. If the requester finishes that step, they can't see the ISU's marker comment and HR routing silently doesn't fire (Request Time Off: gate moved from e to ea, after Final check).
- **Correct doesn't re-run the gate.** Workday's Correct replays no completed Service steps, so a corrected request keeps its original form check. If corrections must be re-checked, put a gate on the correction process too (e.g. Correct Time Off is its own process, with no gate by default).

## Rule 2: every sub-process that routes on the form needs its own marker and gate

A condition rule reads **its own event's** comments. The marker sits on the parent event, so a parent's `[ROUTE:HR]` never reaches a sub-process (seen live: Change Job's "Change Organization Assignments for Worker" stayed Not Required on the HR route).

For each sub-process that should route or stop on the form:

1. Add a **Route marker** To Do and a **FormGate** Service step to the sub-process definition (same inputs and Run As as the parent), before the step that routes.
2. Add the ISU's group to the sub-process's own policy (View All, Cancel (Web Service)) and activate.
3. Point the sub-process step's condition at TEST DYN Route HR (its own marker comment, plus the worker's route record).
4. Give a sub-process that the person fills in themselves (Onboarding) its own **FormAssign** too: the parent's assignment points at the parent's target (for Hire, the pre-hire, which the new worker never sees).
5. Check which definition actually runs: a sub-process can run under its **Default Definition** rather than the org-specific one (Onboarding did). Add the steps to whichever runs, or both.

Sub-processes that only need the form to exist (no routing, no stop) need nothing: the parent's gate already covers the request.

## Setup kit: one sheet per process

Copy this for each process and fill in one row per process and per sub-process from Rule 2:

| Process / sub-process | Definition (one row each) | Assign step | Gate step (order) | Gate after an approval? (send back possible) | Marker group | Condition rules that read the marker | ISU on policy (View All, Cancel WS) | Tested |
|---|---|---|---|---|---|---|---|---|
| Request Time Off | Default Definition (only one) | c | ea | no → policy cancel or pass | HR Partner + Initiator | f "TEST DYN Route HR" | yes | 2026-11-19 |
| Change Job | Default Definition | aa | ac | | HR Partner + Initiator | | | |
| Change Job | Simplified for Data Entry | **none** | **none** | | | | | Readiness: 0 Service |
| ↳ Change Organization Assignments for Worker | | n/a | **needs its own** | | | | | |
| Hire (Next Level Enterprise) | org-specific | none (moved to Onboarding) | | | | | yes (View All) | |
| ↳ Onboarding | Onboarding (Default Definition) | aa | ac | | | | yes | 2026-11-19 |
| ↳ Onboarding | Onboarding for Next Level Enterprise (runs for that org) | aa | ac | | | | yes | 2026-11-19 |
| ↳ Onboarding | Onboarding (Location Change) | **none** | **none** | | | | | Readiness: 0 Service |
| ↳ Onboarding | Onboarding (Promotion for Job Change) | **none** | **none** | | | | | Readiness: 0 Service |

Before signing a process off: run one request through each route (form filled and passing, check failing, form not filled), and one request that a different user approves, and open the event's Orchestrations tab to confirm every FormAssign / FormGate run says Successfully Completed. A failed run still advances the step, so a green process alone proves nothing.

## Why routing needs two keys

A marker comment alone can be forged: anyone who can comment on the event can type `[ROUTE:HR]`, and Workday records the gate's comment under the gate's Run As person, so a "written by the ISU" filter can't tell them apart (the Comment object has no account or step field). Workday also offers no app link to Request Time Off or Change Job events (View Business Objects Available to Extend). So the rule also requires the app's route record for the worker, which only FormGate writes and only HR Administrators and the forms ISU can change. Tested live 2026-11-19: a real HR request routes (comment 1, record 1), a hand-typed tag on a worker whose record says normal does not (comment 1, record 0). Left over: with two open requests for one worker, the record reflects the latest gate run.

## When a request ends

FormEnded closes a request's open form assignments the moment it is cancelled, rescinded or denied ("Closed: event Canceled (closed when it ended)"). Set it up per definition (Configure Orchestrations): one launch configuration per process type (Orchestration FormEnded, Business Process Type, parameter actionEvent = Determine WID at Runtime → Business Process Event), and on each action row User to Perform Orchestration Launches = the forms ISU. The tenant-wide Edit Tenant Setup - Business Processes → User to perform Orchestration Launches must be set first, or the launch configuration won't save.

## Safety net

- **FormReconcile** (integration system TEST:DYN:RECON Integration, hourly) closes assignments whose event ended and creates missing extra assignments; it writes a RECON summary record per run.
- **ALERT records** (formCode ALERT on the Results page) mark every FormAssign or FormGate run that stopped; check them after a bulk start or a release.
