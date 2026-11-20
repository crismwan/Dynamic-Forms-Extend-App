#!/usr/bin/env python3
"""Points the app at a real App Hub app: sets appManifest.json id + referenceId and renames the AMD/SMD to match.

  python3 tools/set_app.py <referenceId> <appId>

The reference ID and app ID come from App Hub (`wdcli app list`, or `wdcli app info <referenceId>`), after the app
was created there once (see README: "First deploy"). Safe to run again with the same values.
"""
import glob, json, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app'))
if len(sys.argv) != 3:
    sys.exit(__doc__)
ref, app_id = sys.argv[1], sys.argv[2]
if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,}', ref):
    sys.exit(f'not a reference ID: {ref}')
if not re.fullmatch(r'[0-9a-f]{32}', app_id):
    sys.exit(f'not an app ID (32 hex characters): {app_id}')

man_path = os.path.join(ROOT, 'appManifest.json')
man = json.load(open(man_path))
old = man['referenceId']
man['referenceId'], man['id'] = ref, app_id
open(man_path, 'w').write(json.dumps(man, indent=4) + '\n')

for ext in ('amd', 'smd'):
    files = glob.glob(os.path.join(ROOT, 'presentation', f'*.{ext}'))
    if len(files) != 1:
        sys.exit(f'expected one .{ext} file, found {len(files)}')
    src = files[0]
    d = json.load(open(src))
    for k in ('applicationId', 'id', 'siteId'):
        if k in d:
            d[k] = ref
    dst = os.path.join(ROOT, 'presentation', f'{ref}.{ext}')
    open(dst, 'w').write(json.dumps(d, indent=2) + '\n')
    if os.path.abspath(src) != os.path.abspath(dst):
        os.remove(src)
print(f'app: {old} -> {ref} (id {app_id})')
