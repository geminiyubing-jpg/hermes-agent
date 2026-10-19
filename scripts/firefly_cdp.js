
const http = require('http');
const WebSocket = require('ws');
const PORT = parseInt(process.argv[3]);
let ws=null, mid=0; const pending={};
function cmd(method, params){
  return new Promise((res)=>{
    const id=++mid; pending[id]=res;
    ws.send(JSON.stringify({id, method, params: params||{}}));
  });
}
function ev(expr){ return cmd('Runtime.evaluate',{expression:expr, returnByValue:true, awaitPromise:true}).then(r=>r.result.result.value); }
(async()=>{
  const steps = JSON.parse(process.argv[2]);
  for(const s of steps){
    if(s.tab){
      const tabs = await new Promise((res)=>{http.get(`http://127.0.0.1:${PORT}/json/list`,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));});});
      const t = tabs.find(t=>t.type==='page' && t.url.includes(s.tab));
      if(!t){ console.log((s.tag||'')+' TAB-NOT-FOUND'); continue; }
      if(ws) ws.close();
      ws = new WebSocket(t.webSocketDebuggerUrl, {agent:false});
      ws.on('message', m=>{ const j=JSON.parse(m); if(pending[j.id]){ pending[j.id](j); delete pending[j.id]; } });
      await new Promise(r=>ws.on('open', r));
      if(s.tag) console.log(s.tag, 'attached');
    }
    if(s.nav){ await cmd('Page.navigate',{url:s.nav}); }
    if(s.sleep){ await new Promise(r=>setTimeout(r, s.sleep)); }
    if(s.wait){ await ev('(function(){var t0=Date.now(),max=25000;return new Promise(function(resolve){function chk(){var b=document.body&&document.body.innerText||"";if(b.trim().length>150&&Date.now()-t0>3000){resolve("ready")}else if(Date.now()-t0>max){resolve("timeout")}else{setTimeout(chk,800)}}chk()})})()'); }
    if(s.eval){ const v = await ev(s.eval); console.log(s.tag||'', typeof v==='string' ? v : JSON.stringify(v)); }
    if(s.shot){ const r = await cmd('Page.captureScreenshot',{format:'jpeg',quality:55});
      require('fs').writeFileSync(s.shot, Buffer.from(r.result.data,'base64')); console.log('SHOT '+s.shot); }
  }
  process.exit(0);
})().catch(e=>{ console.error('ERR', e.message); process.exit(1); });
