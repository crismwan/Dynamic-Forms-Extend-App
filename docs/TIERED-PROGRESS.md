# Tiered ownership plan: progress

Status of every item in "Dynamic Forms: tiered ownership plan" except the legal, UBC and partner-tenant gate (out of scope by request). **Built** = in the repo, static checks pass, deployed when noted. **Live** = tested in the dev tenant with fictitious data. Design: `TIERED-DESIGN.md`.

Last update: 2026-11-20. Code pushed (commit "Tiered ownership, phases 1-5"); **not yet deployed**: the deploy tokens had expired. Tenant security for the new domains: approved by the user on 2026-11-20, not yet set up (the in-app browser disconnected).

## Phase 0

| Item | Status |
|---|---|
| Design doc: data model, domains, limits | Built: TIERED-DESIGN.md (14 objects, 8 domains, 11 tasks, 36 pages, 10 Workday instance fields) |
| Setup guide v2: support levels, subject mapping, readiness, calculated fields | Built: DYNAMIC-FORMS-SETUP.md, "Tiered ownership setup" |
| Security tests: forged tag, non-HR confidential, Restricted, two open processes | Routing changed (below); tests listed in DYNAMIC-FORMS-RETEST.md section 7, run after deploy |
| Progress tracker | This file |

## Phase 1: secure core

| Item | Status |
|---|---|
| Classified answers (General / Confidential / Restricted objects and domains) | Built |
| Question classification | Built (Form Studio > Questions: Classification) |
| Owner org and tier on blocks | Built (Design: Ownership) |
| Block assignment object and editor (reach preview, team scope rule) | Built (FormAssignments) |
| Org map and department designation | Built (FormOrgMap, FormDepartments). Refresh is a page (OK), not a nightly job: computing paths needs the whole hierarchy, which an orchestration can't loop over recursively. Run it after reorganizations. |
| Event-keyed routing | **Live (tenant change, 2026-11-20):** TEST DYN Comment Route HR now also requires Comment by Person is empty; rule TEST DYN Route HR dropped the worker key. Route record keyed by event in FormGate (built). Rule Tester on a cancelled event (645$1010) read empty: retest on a fresh request after deploy (RETEST 7.3) |
| Enterprise blocks | Built (owner = top org, tier Enterprise; compose falls back to enterprise blocks without an org map row) |
| Gate comments General only | Built (structural) |

## Phase 2: composition

| Item | Status |
|---|---|
| FormCompose (subject org, matching blocks, pinned versions, cached composed form, one assignment) | Built (orchestration FormCompose) |
| Slot budgets | Built: checked at publish (FormPublish) per tier from Forms settings |
| Pinned versions | Built: the composed form names exact versions; a later publish creates a new compose key |
| Publish and approve | Built: FormPublish (diff, budget, reach, classes, privacy reason, governance approval, supersedes the old version). As a page OK, not a business process: an Extend BP on Dyn Form would need its own policy and definition setup; the page records the same audit fields |
| Readiness scan | Built: FormReadiness (every definition, support level, fix) |
| Same library question in two tiers asked once | Built (df.merge) |

## Phase 3: prefill and reuse

| Item | Status |
|---|---|
| Prefill from Workday, shown first to confirm | Built ("Check:" first; existing prefill sources: name, title, location, email, organization) |
| Reusable answers with validity | Built: validUntil = answered + validMonths; offered while valid |
| Reset triggers | Built as a context check (location and job title when answered vs now) instead of a nightly AnswerFreshness job: same effect, nothing to schedule |
| My answers page | Built (FormMyAnswers, employees through the ISU) |

## Phase 4

| Item | Status |
|---|---|
| Team blocks and Org + subordinates scope | Built (path match) |
| Reach preview | Built (orgs and active workers, per assignment) |
| Owner dashboard (needs review, reach then and now, answers, reuse, prefill) | Built (FormOwnerDash). Completion rate and gate failures per block are not split by block (the gate records are per request) |
| Retention purge | Built: FormPurge page + AnswerPurge orchestration (100 per class per run). Run monthly by hand: a scheduled run needs date arithmetic in WQL that isn't proven |
| Screen-reader pass | Not run with a real screen reader (accessibility-tree check of the fill page done 2026-11-19, see NOTES) |

## Phase 5: onboarding kit

| Item | Status |
|---|---|
| Kit item and kit task objects | Built |
| Kit designer (owner org + scope, elevated needs governance, copy-on-edit) | Built (KitDesigner) |
| KitCompose (welcome, learning, prepare tasks) | Built inside FormCompose (processType Onboarding) |
| Manager's prepare task (note, access list, recommendations, reasons) | Built (KitPrepare, ?event=) |
| Welcome page | Built (KitWelcome); released when the manager writes the note; no date-based release (below) |
| Learning guide | Built (KitGuide) |
| Fulfilment queue | Built (KitQueue, ?group=). Who sees which group's tasks needs the Fulfil domain with per-group groups; the page filters by group |
| AccessRoute | Built: KitPrepare OK creates each request with its fulfiller group |
| WelcomeRelease, KitReminders (daily) | **Not built.** Needs the hire's start date read by the ISU every day and email; email is unproven (the plan's own check). |
| Email | Not built (plan: unproven; falls back to the welcome page) |

## Delivered features and access recommendations

| Item | Status |
|---|---|
| Package object, Origin and Overrides on blocks, questions, kit items | Built |
| Delivered features page (enable, install, compare) | Built (KitPackages), wave 1: joiner, mover, leaver |
| Copy-on-edit | Built for kit items (KitDesigner). Blocks: copy through Copy, version or import (origin Customer) |
| Access snapshot (counts only, groups of 3+, fallback to org and below) | Built (KitPeers), from the kit's own history. Job family rule not built (no job family field confirmed in workersForHCMReporting). Workday role assignments not read (needs security reads) |
| Over-provisioning list | Built (KitPeers) |
| Segregation of duties | Not built (no rules to read in this tenant) |
| Home card "You have 2 forms to fill" | Not built: a Workday Home card runs as the employee, who has no access to app data (Fill pages read through the ISU) |

## Next

1. Deploy (refresh tokens).
2. Security setup (approved): Restricted group, new domains, ISU worker-data Get; activate.
3. Org map: mark departments, rebuild; settings OK.
4. Live tests: RETEST section 7.
