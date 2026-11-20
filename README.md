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
  && python3 tools/build_studio.py && python3 tools/build_import.py && python3 tools/build_tiers.py \
  && python3 tools/build_labels.py
node tools/check.js
```

CI ("Check and deploy") runs the same build, checks that the committed files match, and on main uploads and deploys.
It signs in with copied developer tokens (secrets `WD_DEV_TOKEN`, 1 hour, and `WD_WCP_TOKEN`, 8 hours) stored on
**this** repository, crismwan/Dynamic-Forms-Extend-App (the Extend Toolkit repo has its own copies).

## Refreshing tokens

When a run fails at the token step, in Windows PowerShell:

```powershell
wdcli auth login -e personal
wdcli account switch
wdcli app deploy dynamicforms_kwswrv    # answer y to a login prompt; this also redeploys the version in App Hub
$c = Get-Content -Raw "$env:LOCALAPPDATA\@workday\wdcli\config.json" | ConvertFrom-Json
$c.wcpTenantAccessToken.'kpmcxyjpdr_extdev' | gh secret set WD_DEV_TOKEN -R crismwan/Dynamic-Forms-Extend-App
$c.wcpAccessToken | gh secret set WD_WCP_TOKEN -R crismwan/Dynamic-Forms-Extend-App
```

Then rerun the workflow within the hour (the tenant token lasts 1 hour). A run on a docs-only commit skips the
deploy: rerun the last run that changed the app, or dispatch it (Actions > Check and deploy > Run workflow, action deploy).

## Docs

- `docs/DYNAMIC-FORMS-SETUP.md`: putting a form on a business process (steps, security, routing, FormEnded).
- `docs/DYNAMIC-FORMS-RETEST.md`: the retest checklist after each Workday release.
- `docs/dynamic-forms-readiness.json`: a check list for the Extend Toolkit's Readiness page (every process definition).
- `docs/DYNAMIC-FORMS-NOTES.md`: project notes and history.
- `docs/TIERED-DESIGN.md`, `docs/TIERED-PROGRESS.md`: the tiered ownership build and its status.
