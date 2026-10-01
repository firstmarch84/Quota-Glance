// Simulate a background page whose timeout/interval callbacks never run.
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
let listener;
let pushes = 0;
const section = {innerText:'사용량\n현재 세션\n3% 사용됨',getClientRects:()=>[{}]};
const ctx = vm.createContext({
  URL,
  location:{href:'https://claude.ai/new#settings/usage',hostname:'claude.ai',pathname:'/new'},
  document:{title:'Claude',visibilityState:'hidden',querySelectorAll:()=>[section],querySelector:()=>null,addEventListener(){}},
  getComputedStyle:()=>({visibility:'visible'}),
  setTimeout(){},setInterval(){},
  chrome:{runtime:{sendMessage:async()=>{pushes++;},onMessage:{addListener:fn=>{listener=fn;}}}}
});
for(const name of ['routing.js','reader.js','content.js']) vm.runInContext(fs.readFileSync('extension/'+name,'utf8'),ctx);
let snapshot;
listener({type:'snapshot'},{},value=>snapshot=value);
assert.equal(snapshot.rows[0].remaining,97);
assert.equal(snapshot.hidden,true);
assert.equal(pushes,0,'snapshot works with all page timers suspended');
ctx.document.title = '잠시만 기다리십시오';
listener({type:'snapshot'},{},value=>snapshot=value);
assert.equal(snapshot.blocked,true);
assert.equal(snapshot.rows.length,0);
console.log('2 timer-independent content scenarios passed');
