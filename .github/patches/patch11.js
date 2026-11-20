
const fs = require('fs');
const f = process.env.METERED;
let c = fs.readFileSync(f, 'utf8');
const OLD = 'Pt=e=>{const t=process.env.WDCLI_DTS_API_GATEWAY;return(t?new ti(t):new l.DevToolsConnector(y.devtoolsHostname(e.configFile))).attachAuthToken(Ge(e))}';
const REP = 'Pt=e=>{const t=process.env.WDCLI_DTS_API_GATEWAY;const conn=(t?new ti(t):new l.DevToolsConnector(y.devtoolsHostname(e.configFile)));conn.setDefaultHeader("User-Agent","wdcli/"+(process.env.WDCLI_VERSION||"1.9.43"));return conn.attachAuthToken(Ge(e))}';
if (!c.includes(OLD)) { console.error('ERROR: Pt patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(OLD, REP));
console.log('Patch 11 (add User-Agent header to DevToolsConnector): OK');
