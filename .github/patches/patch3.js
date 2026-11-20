// Patch 3 (metered bundle): skip getOrganizations when WDCLI_ORG_UUID is set (it needs a different token type).
const fs = require('fs');
const f = process.env.METERED;
let c = fs.readFileSync(f, 'utf8');
const old = 'async getUserAccounts(t){const n=await L(t);return Ee(t,{accessToken:n,version:"v2"}).getOrganizations()}';
const rep = 'async getUserAccounts(t){if(process.env.WDCLI_ORG_UUID){const uuid=process.env.WDCLI_ORG_UUID;console.error("[CI] Bypassing getOrganizations, using WDCLI_ORG_UUID:",uuid);return{total:1,userUuid:"ci",userOrganizations:[{organizationUuid:uuid,organizationShortId:process.env.WD_ACCOUNT,organizationName:(process.env.WD_ORG_NAME||process.env.WD_ACCOUNT),organizationType:"Customer",tenantPrefix:(process.env.WD_TENANT_PREFIX||""),associationType:"PRIMARY",region:(process.env.WD_REGION||"scylla:us")}]};}const n=await L(t);return Ee(t,{accessToken:n,version:"v2"}).getOrganizations()}';
if (!c.includes(old)) { console.error('ERROR: getUserAccounts patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(old, rep));
console.log('Patch 3 (bypass getOrganizations): OK');
