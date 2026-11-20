const fs = require('fs');
const f = process.env.METERED;
let c = fs.readFileSync(f, 'utf8');
const OLD = 'async function Ve(e,t,n=!1){const r=await L(e),i=await new Y().getAccountForCommand(e,t),o=await new l.OctopaasConnector(y.wcpApiGatewayHostname(e.configFile)).getTenantsForOrg(i,r);return n?o.filter(a=>Ii(a.environmentType)):o}';
const REP = 'async function Ve(e,t,n=!1){if(process.env.WDCLI_ORG_UUID){const tenants=[{lookupAlias:process.env.WD_TENANT,tenantAlias:process.env.WD_TENANT,environmentType:(process.env.WD_ENV_TYPE||"WCPDEV"),displayName:process.env.WD_TENANT,tenantUrl:process.env.WD_TENANT_URL}];console.error("[CI] Bypassing getTenantsForOrg, returning hardcoded tenant list");return n?tenants.filter(a=>Ii(a.environmentType)):tenants;}const r=await L(e),i=await new Y().getAccountForCommand(e,t),o=await new l.OctopaasConnector(y.wcpApiGatewayHostname(e.configFile)).getTenantsForOrg(i,r);return n?o.filter(a=>Ii(a.environmentType)):o}';
if (!c.includes(OLD)) { console.error('ERROR: Ve() patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(OLD, REP));
console.log('Patch 5 (bypass getTenantsForOrg): OK');
