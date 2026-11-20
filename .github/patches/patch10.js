
const fs = require('fs');
const f = process.env.CMDS;
let c = fs.readFileSync(f, 'utf8');
const OLD = 'connector.post(`/apps/${e.appUuid}/deploy`,{versionId:e.versionId,tenantAlias:e.tenant.tenantAlias},{orgUuid:e.orgUuid,headers:{"Deploy-Tenant-Authorization":`Bearer ${e.tenantAccessToken}`}})';
const REP = 'connector.post(`/apps/${e.appUuid}/deploy`,{versionId:e.versionId,tenantAlias:e.tenant.tenantAlias},{orgUuid:e.orgUuid,headers:{"Deploy-Tenant-Authorization":`Bearer ${e.tenantAccessToken}`,"org-id":e.orgUuid}})';
if (!c.includes(OLD)) { console.error('ERROR: deployApplication patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(OLD, REP));
console.log('Patch 10 (add org-id header to deploy POST): OK');
