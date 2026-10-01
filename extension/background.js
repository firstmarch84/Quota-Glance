importScripts('routing.js');
const ENDPOINT = 'http://127.0.0.1:48721';
async function deliver(path, body, key) {
  const response = await fetch(ENDPOINT + path, {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+key},
    body:JSON.stringify(body), signal:AbortSignal.timeout(4000)
  });
  if (!response.ok) throw new Error(response.status === 401 ? '연결 코드가 다릅니다. 앱에서 다시 복사하세요.' : '앱 연결 실패');
  return response.json();
}
chrome.runtime.onMessage.addListener((message,sender,reply) => {
  (async () => {
    const {key} = await chrome.storage.local.get('key');
    if (message.type==='pair' && !sender.tab) {
      const next = String(message.key||'').trim();
      if (!/^[\w-]{40,60}$/.test(next)) throw new Error('앱에서 복사한 연결 코드를 붙여 넣으세요.');
      await deliver('/pair',{version:chrome.runtime.getManifest().version},next);
      await chrome.storage.local.set({key:next});
      await ensureUsageTab();
      return reply({ok:true});
    }
    if (!sender.tab || !key) return reply({ok:false,error:'앱 연결을 먼저 완료하세요.'});
    if (message.type==='sample') {
      const account = routeAccount(sender);
      if (!account) return reply({ok:false});
      if (!Array.isArray(message.rows)) return reply({ok:false});
      await deliver('/quota',{account,rows:message.rows},key);
      if (account==='claude') await chrome.storage.session.set({tabId:sender.tab.id,lastRead:Date.now(),valid:message.rows.length>0});
      return reply({ok:true,account});
    }
    reply({ok:false});
  })().catch(error => reply({ok:false,error:error.message.includes('fetch')?'Quota Glance 앱을 먼저 실행하세요.':error.message}));
  return true;
});
let preparing;
function ensureUsageTab() {
  if (preparing) return preparing;
  preparing = (async () => {
    const {tabId} = await chrome.storage.session.get('tabId');
    if (tabId != null) {
      try { return await chrome.tabs.get(tabId); } catch { }
    }
    const existing = (await chrome.tabs.query({url:'https://claude.ai/*'})).find(tab => usageURL(tab.url));
    if (existing) {
      await chrome.storage.session.set({tabId:existing.id});
      return existing;
    }
    const window = await chrome.windows.create({url:'https://claude.ai/settings/usage',state:'minimized',focused:false});
    const tab = window.tabs?.[0];
    if (tab) await chrome.storage.session.set({tabId:tab.id});
    return tab;
  })().finally(() => { preparing = null; });
  return preparing;
}
// Alarms run in the extension worker, independently of page interval throttling.
const ensureAlarm = () => { chrome.alarms.create('usage-refresh',{periodInMinutes:0.5}); syncUsage(); };
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.runtime.onStartup.addListener(ensureAlarm);
function askTab(id) {
  return new Promise((resolve,reject) => {
    const timeout = setTimeout(() => reject(new Error('reader-timeout')), 5000);
    chrome.tabs.sendMessage(id,{type:'snapshot'}).then(resolve,reject).finally(() => clearTimeout(timeout));
  });
}
async function protectTab(tab) {
  const {protectedTab} = await chrome.storage.session.get('protectedTab');
  if (!protectedTab || protectedTab.id !== tab.id) {
    await releaseTab();
    await chrome.storage.session.set({protectedTab:{id:tab.id,autoDiscardable:tab.autoDiscardable !== false}});
  }
  await chrome.tabs.update(tab.id,{autoDiscardable:false});
}
async function releaseTab() {
  const {protectedTab} = await chrome.storage.session.get('protectedTab');
  if (!protectedTab) return;
  try { await chrome.tabs.update(protectedTab.id,{autoDiscardable:protectedTab.autoDiscardable}); } catch { }
  await chrome.storage.session.remove('protectedTab');
}
let syncing;
function syncUsage(refresh=true) {
  if (syncing) return syncing;
  syncing = runSync(refresh).finally(() => { syncing = null; });
  return syncing;
}
async function runSync(refresh) {
  let key;
  try {
    ({key} = await chrome.storage.local.get('key'));
    if (!key) return;
    let state;
    try { state = await deliver('/pair',{version:chrome.runtime.getManifest().version},key); }
    catch { await releaseTab(); return; }
    if (!state.autoOpen) return;
    const tab = await ensureUsageTab();
    if (!tab || !usageURL(tab.url)) { await releaseTab(); return; }
    await protectTab(tab);
    if (tab.status === 'loading') return;
    const saved = await chrome.storage.session.get(['valid','recoveryAttempted','lastReload']);
    // A previously verified usage tab can be restored once, without taking focus.
    // Do not repeatedly reload an unknown or authentication screen.
    if (tab.discarded || tab.frozen) {
      if (saved.valid && !saved.recoveryAttempted) {
        await chrome.storage.session.set({recoveryAttempted:true,lastReload:Date.now()});
        await chrome.tabs.reload(tab.id);
      }
      await reportProblem(key,'sleeping');
      return;
    }
    const current = await askTab(tab.id);
    if (!Array.isArray(current?.rows)) throw new Error('reader-version');
    if (current.blocked) {
      await chrome.storage.session.set({valid:false});
      await reportProblem(key,'blocked');
      return;
    }
    // Deliver the observation here; do not depend on setInterval inside the tab.
    await deliver('/quota',{account:'claude',rows:current.rows},key);
    await chrome.storage.session.set({tabId:tab.id,lastRead:Date.now(),valid:current.rows.length>0});
    if (!current.rows.length) return;
    await chrome.storage.session.set({recoveryAttempted:false});
    if (refresh && current.hidden && Date.now()-(saved.lastReload||0)>=60000) {
      await chrome.storage.session.set({lastReload:Date.now()});
      await chrome.tabs.reload(tab.id);
    }
  } catch {
    if (key) await reportProblem(key,'reader').catch(()=>{});
  }
}
async function reportProblem(key, problem) {
  await deliver('/pair',{version:chrome.runtime.getManifest().version,problem},key);
}
ensureAlarm();
chrome.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name==='usage-refresh') await syncUsage();
});
chrome.tabs.onUpdated.addListener((tabId, change, tab) => {
  if (change.status==='complete' && usageURL(tab.url)) syncUsage(false);
});
