// Patch 2 (commands bundle): always take the AOS deploy path (POST /aos/v1/deploy), as for a standard Extend app.
const fs = require('fs');
const f = process.env.CMDS;
let c = fs.readFileSync(f, 'utf8');
const old = 'await a.hasPermission(this,"agentbuilder.agent.write",i.organizationUuid)';
const rep = '(false /* CI: force AOS deploy path, not DevTools */)';
if (!c.includes(old)) { console.error('ERROR: hasPermission patch target not found'); process.exit(1); }
fs.writeFileSync(f, c.replace(old, rep));
console.log('Patch 2 (force AOS deploy path): OK');
