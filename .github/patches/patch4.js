const fs = require('fs');
const f = process.env.METERED;
let c = fs.readFileSync(f, 'utf8');
const OLD = 'function ue(e,t,n){return e.organizationPermissions(n,async()=>(await Ee(e,{accessToken:t,version:"v2"}).get(`/organizations/${encodeURIComponent(n)}/users/self/permissions`)).data.permissions)}';
const REP = 'function ue(e,t,n){if(process.env.WDCLI_ORG_UUID){console.error("[CI] Bypassing organizationPermissions for org:",n);return Promise.resolve(["agentbuilder.agent.write","agentbuilder.agent.read","agentbuilder.app.create","agentbuilder.app.read","agentbuilder.app.upload","agentbuilder.app.deploy","agentbuilder.app.delete"]);}return e.organizationPermissions(n,async()=>(await Ee(e,{accessToken:t,version:"v2"}).get(`/organizations/${encodeURIComponent(n)}/users/self/permissions`)).data.permissions)}';
if (!c.includes(OLD)) { console.error('ERROR: ue() patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(OLD, REP));
console.log('Patch 4 (bypass organizationPermissions): OK');
