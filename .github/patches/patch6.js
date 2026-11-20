
const fs = require('fs');
const SDK = process.env.WCP_SDK;
let c = fs.readFileSync(SDK, 'utf8');
const OLD = '                        err = buildApiError("HTTP ".concat(rawResponse.status, " ").concat(rawResponse.statusText), errResponse, requestInfo);';
const REP = '                        if(rawResponse.status===401){const authHdr=req.headers&&(req.headers["Authorization"]||req.headers["authorization"])||"(none)";const wcpHdr=req.headers&&(req.headers["WCP-Authorization"]||req.headers["wcp-authorization"])||"(none)";const hdrs={};try{rawResponse.headers.forEach((v,k)=>{hdrs[k]=v;});}catch(e){}console.error("[CI-401] UNAUTHORIZED URL:",req.url);console.error("[CI-401] Auth header prefix:",authHdr.substring(0,40));console.error("[CI-401] WCP-Auth header prefix:",wcpHdr.substring(0,40));console.error("[CI-401] Request body:",JSON.stringify(req.body));console.error("[CI-401] Response headers:",JSON.stringify(hdrs));console.error("[CI-401] Response body data_1:",JSON.stringify(data_1));}err = buildApiError("HTTP ".concat(rawResponse.status, " ").concat(rawResponse.statusText), errResponse, requestInfo);';
if (!c.includes(OLD)) { console.error('ERROR: wcp-sdk 401 patch target not found'); process.exit(1); }
fs.writeFileSync(SDK, c.replace(OLD, REP));
console.log('Patch 6 (wcp-sdk 401 URL+auth+WCP-auth+reqbody+headers+body logger): OK');
