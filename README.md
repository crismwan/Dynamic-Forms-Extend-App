# Dynamic Forms (Workday Extend app)

Schema-driven forms on Workday business processes: forms are records (DynForm, DynQuestion), one generated fill page
renders any of them, and orchestrations attach them to delivered processes:

- **FormAssign** (Service step): creates the form assignment for the request.
- **FormGate** (Service step): checks the answers, cancels or routes the request, writes the route record.
- **FormEnded** (Configure Orchestrations, on Cancel / Rescind / Deny): closes the request's open forms at once.
- **FormReconcile** (integration system, hourly): the safety net for anything missed.

Moved out of the Extend Toolkit app on 2026-11-19. The plan it is growing into: "Dynamic Forms: tiered ownership plan".

## Build

```
python3 tools/build_app.py && python3 tools/build_browse.py && python3 tools/build_forms.py \
  && python3 tools/build_studio.py && python3 tools/build_import.py && python3 tools/build_labels.py
node tools/check.js
```

CI ("Check and deploy") runs the same build, checks that the committed files match, and on main uploads and deploys.
It signs in with copied developer tokens (secrets `WD_DEV_TOKEN`, 1 hour, and `WD_WCP_TOKEN`, 8 hours); refresh them with
CLAUDE.md, "Deploy decision guide", route 1, using `-R crismwan/Dynamic-Forms-Extend-App`.

## Docs

- `docs/DYNAMIC-FORMS-SETUP.md`: putting a form on a business process (steps, security, routing, FormEnded).
- `docs/DYNAMIC-FORMS-RETEST.md`: the retest checklist after each Workday release.
- `docs/dynamic-forms-readiness.json`: a check list for the Extend Toolkit's Readiness page (every process definition).
- `docs/DYNAMIC-FORMS-NOTES.md`: project notes and history.
