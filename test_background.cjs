const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
async function setup({existing=false, tracked=false, available=true, valid=true, hidden=true, frozen=false, discarded=false, blocked=false, broken=false}={}) {
  const session = tracked ? {tabId:7} : {};
  let enabled = false;
  const count = {create:0,reload:0,sample:0,quota:0,updates:[],problems:[]};
  const tab = {id:7,url:'https://claude.ai/new#settings/usage',frozen,discarded,autoDiscardable:true};
  const event = {addListener(){}};
  const ctx = vm.createContext({URL,AbortSignal,Date,setTimeout,clearTimeout,
    fetch:async(url,options)=>{if(!available) throw Error('offline');
      if(url.endsWith('/quota')) count.quota++;
      const body=JSON.parse(options.body); if(body.problem) count.problems.push(body.problem);
      return {ok:true,json:async()=>({autoOpen:true})};},
    chrome:{
      runtime:{onMessage:event,onInstalled:event,onStartup:event,getManifest:()=>({version:'1.4.0'})},
      storage:{local:{get:async()=>enabled?{key:'test'}:{}},session:{get:async()=>session,set:async v=>Object.assign(session,v),remove:async key=>delete session[key]}},
      alarms:{create(){},onAlarm:event},
      tabs:{onUpdated:event,update:async(id,options)=>{count.updates.push(options);return tab;},get:async()=>tab,query:async()=>existing?[tab]:[],reload:async()=>count.reload++,sendMessage:async(id,msg)=>{
        if(broken) throw Error('no receiver');
        if(msg.type==='sampleNow') count.sample++;
        return {rows:valid?[{label:'week',remaining:74}]:[],hidden,blocked};
      }},
      windows:{create:async options=>{count.create++;assert.equal(options.focused,false);assert.equal(options.state,'minimized');return {tabs:[tab]};}}
    }
  });
  ctx.importScripts = name => vm.runInContext(fs.readFileSync('extension/'+name,'utf8'),ctx);
  vm.runInContext(fs.readFileSync('extension/background.js','utf8'),ctx);
  await new Promise(resolve=>setImmediate(resolve));
  enabled = true;
  return {ctx,count,session,tab};
}
(async()=>{
  let t = await setup();
  await Promise.all([t.ctx.ensureUsageTab(),t.ctx.ensureUsageTab()]);
  assert.equal(t.count.create,1,'concurrent requests create only one window');
  await t.ctx.ensureUsageTab();
  assert.equal(t.count.create,1,'tracked tab is reused');
  t = await setup({existing:true});
  await t.ctx.syncUsage();
  assert.equal(t.count.create,0);
  assert.equal(t.count.reload,1);
  assert.equal(t.count.quota,1,'worker directly delivers without any content timers');
  assert.equal(t.count.updates[0].autoDiscardable,false);
  await t.ctx.syncUsage();
  assert.equal(t.count.quota,2,'next poll delivers again');
  assert.equal(t.count.reload,1,'30-second polling does not reload every time');
  t = await setup({available:false});
  await t.ctx.syncUsage();
  assert.equal(t.count.create,0,'closed app never creates windows');
  t = await setup({tracked:true,valid:false});
  await t.ctx.syncUsage();
  assert.equal(t.count.reload,0,'challenge/unknown page never reloads');
  t = await setup({tracked:true,hidden:false});
  await t.ctx.syncUsage();
  assert.equal(t.count.reload,0,'visible page never reloads');
  t = await setup({tracked:true});
  t.tab.url = 'https://claude.ai/login';
  await t.ctx.syncUsage();
  assert.equal(t.count.create,0,'login tab is kept without duplicates');
  assert.equal(t.count.reload,0);
  t = await setup({tracked:true,frozen:true});
  t.session.valid = true;
  await t.ctx.syncUsage();
  await t.ctx.syncUsage();
  assert.equal(t.count.reload,1,'frozen recovery only attempted once until valid data');
  assert.equal(t.count.quota,0,'frozen state does not fabricate fresh data');
  assert.equal(t.count.problems[0],'sleeping');
  t = await setup({tracked:true,discarded:true});
  await t.ctx.syncUsage();
  assert.equal(t.count.reload,0,'unverified discarded page not repeatedly reloaded');
  t = await setup({tracked:true,blocked:true});
  await t.ctx.syncUsage();
  assert.equal(t.count.reload,0);
  assert.equal(t.count.quota,0);
  assert.equal(t.count.problems[0],'blocked');
  t = await setup({tracked:true,broken:true});
  await t.ctx.syncUsage();
  assert.equal(t.count.problems[0],'reader');
  t = await setup({available:false});
  t.session.protectedTab = {id:7,autoDiscardable:true};
  await t.ctx.syncUsage();
  assert.equal(t.count.updates[0].autoDiscardable,true,'original memory behavior restored when app is closed');
  t = await setup({existing:true});
  let revealCalls=0, resultBody;
  t.ctx.chrome.windows.update=async()=>{};
  t.ctx.chrome.tabs.sendMessage=async(id,message)=>{
    assert.equal(message.type,'revealReset');
    assert.equal(message.identity,'chosen-expiry');
    revealCalls++;
    return {ok:true};
  };
  t.ctx.fetch=async(url,options)=>{resultBody=JSON.parse(options.body);return {ok:true,json:async()=>({})};};
  await t.ctx.handleResetCommand({id:'one',account:'claude',action:'reveal',identity:'chosen-expiry'},'key');
  assert.equal(revealCalls,1);
  assert.equal(resultBody.ok,true);
  assert.match(resultBody.message,/표시했습니다/);
  await t.ctx.handleResetCommand({id:'two',account:'claude',action:'consume',identity:'chosen-expiry'},'key');
  assert.equal(revealCalls,1,'consumption commands are not supported');
  let useCalls=0;
  t.ctx.chrome.tabs.sendMessage=async(id,message)=>{
    assert.equal(id,7);
    assert.equal(message.type,'useReset');
    useCalls++;
    return {ok:false,error:'결과 미확인'};
  };
  await t.ctx.handleResetCommand({id:'use-one',account:'claude',action:'use',identity:'chosen-expiry',tabId:7},'key');
  await t.ctx.handleResetCommand({id:'use-one',account:'claude',action:'use',identity:'chosen-expiry',tabId:7},'key');
  assert.equal(useCalls,1,'persisted request id prevents duplicate execution');
  assert.equal(resultBody.ok,false,'uncertain result is never reported successful');
  console.log('12 background lifecycle scenarios passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
