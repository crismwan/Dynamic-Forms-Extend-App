// Patch 1 (metered bundle): the tenant token comes from WDCLI_TENANT_TOKEN instead of a browser PKCE login.
const fs = require('fs');
const f = process.env.METERED;
let c = fs.readFileSync(f, 'utf8');
const old = 'fi=async(e,t)=>{const n=Bt(e,t);';
const rep = 'fi=async(e,t)=>{if(process.env.WDCLI_TENANT_TOKEN){return process.env.WDCLI_TENANT_TOKEN;}const n=Bt(e,t);';
if (!c.includes(old)) { console.error('ERROR: fi patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(old, rep));
console.log('Patch 1 (tenant token env var): OK');
