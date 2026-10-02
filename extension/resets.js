// Reset actions are dispatched only after confirmation in the desktop app.
function resetAccount(url) {
  try {
    const u = new URL(url);
    if (u.origin === 'https://chatgpt.com' && u.pathname.replace(/\/$/,'') === '/settings/usage') return 'codex';
    if (usageURL(url)) return 'claude';
  } catch {}
  return null;
}
function resetEntries() {
  const account = resetAccount(location.href);
  const visible = e => e && e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const entries = [];
  if (account === 'claude') {
    for (const id of ['resets-full','resets-session']) {
      const node = document.getElementById(id);
      if (!visible(node)) continue;
      const lines = node.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
      const button = [...node.querySelectorAll('button')].find(b=>/무료로 초기화|Reset for free/i.test(b.innerText));
      const detail = lines.filter(s=>/만료|expir|지금은 없습니다|none available|no resets/i.test(s)).join(' · ');
      if (!detail) continue;
      entries.push({label:id==='resets-full'?'전체 초기화':'5시간 초기화',detail,button,node});
    }
  } else if (account === 'codex') {
    for (const panel of document.querySelectorAll('[role="tabpanel"]')) {
      const tab = document.getElementById(panel.getAttribute('aria-labelledby'));
      if (!visible(panel) || !tab || !/사용 가능|available/i.test(tab.innerText)) continue;
      for (const node of panel.children) {
        const button = [...node.querySelectorAll('button')].find(b=>/초기화 사용|Use reset/i.test(b.innerText));
        if (!button) continue;
        const lines = node.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
        const label = lines.find(s=>/전체 재설정|전체 초기화|5시간|주간|full reset|weekly|5.hour/i.test(s));
        const expiry = document.getElementById(button.getAttribute('aria-describedby'));
        const detail = expiry?.getAttribute('title') || lines.find(s=>/만료|expir/i.test(s));
        if (label && detail) entries.push({label,detail,button,node});
      }
    }
  }
  return entries.slice(0,16).map(e=>({...e, identity:JSON.stringify([e.label,e.detail]), available:!!e.button && !e.button.disabled && e.button.getAttribute('aria-disabled')!=='true'}));
}
function resetSnapshot() {
  const known = resetAccount(location.href)==='claude'
    ? document.getElementById('resets-full') || document.getElementById('resets-session')
    : [...document.querySelectorAll('[role="tabpanel"]')].some(panel=>{
        const tab=document.getElementById(panel.getAttribute('aria-labelledby'));
        return panel.getClientRects().length && tab && /사용 가능|available/i.test(tab.innerText);
      });
  if (!known) return null;
  return resetEntries().map(({label,detail,identity,available})=>({label,detail,identity,available}));
}
function revealReset(identity) {
  const matches = resetEntries().filter(e=>e.identity===identity);
  if (matches.length !== 1) return {ok:false,error:'초기화권 정보가 변경되었거나 구분할 수 없습니다. 목록을 다시 확인하세요.'};
  const entry = matches[0];
  entry.node.scrollIntoView({block:'center',behavior:'smooth'});
  entry.node.style.outline = '3px solid #e9a566';
  setTimeout(()=>{entry.node.style.outline='';},15000);
  return {ok:true,available:entry.available};
}

let resetExecuting = false;
const resetRequests = new Set();
async function useReset(identity, requestId) {
  if (!requestId || resetExecuting || resetRequests.has(requestId)) return {ok:false,error:'이미 처리 중이거나 처리한 요청입니다.'};
  const matches = resetEntries().filter(e=>e.identity===identity);
  if (matches.length!==1 || !matches[0].available) return {ok:false,error:'선택한 초기화권이 변경되었거나 지금 사용할 수 없습니다. 목록을 다시 확인하세요.'};
  const entry = matches[0];
  resetRequests.add(requestId);
  resetExecuting = true;
  const readNotices = () => [...document.querySelectorAll('[role="status"], [role="alert"]')].filter(e=>e.getClientRects().length).map(e=>e.innerText);
  const previousNotices = new Set(readNotices());
  try {
    entry.button.click();
    await new Promise(resolve=>setTimeout(resolve,1200));
    // Some sites add a confirmation. Only a unique, explicit reset action in a
    // dialog naming this reset type may be confirmed; never generic OK buttons.
    const dialogs = [...document.querySelectorAll('[role="dialog"], [role="alertdialog"], dialog')]
      .filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden' && e.innerText.includes(entry.label));
    const confirmations = [...new Set(dialogs.flatMap(dialog=>[...dialog.querySelectorAll('button')]
      .filter(button=>button!==entry.button && /^(초기화 사용|초기화하기|지금 초기화|재설정|Use reset|Reset now|Confirm reset)$/i.test(button.innerText.trim()) && !button.disabled && button.getAttribute('aria-disabled')!=='true')))];
    if (confirmations.length===1 && confirmations[0]!==entry.button) {
      confirmations[0].click();
      await new Promise(resolve=>setTimeout(resolve,1200));
    }
    const notices = readNotices().filter(text=>!previousNotices.has(text)).join('\n');
    if (!/실패|오류|failed|error/i.test(notices) && /초기화(?:가 |가 성공적으로 | )?(?:완료|되었습니다)|재설정되었습니다|limits? (have been |was |were )?reset|reset (applied|successful)/i.test(notices)) {
      return {ok:true,message:'공식 화면에서 초기화 완료 안내를 확인했습니다. 사용량을 다시 조회합니다.'};
    }
    return {ok:false,error:'사용 요청을 전송했습니다. 완료는 아직 확인되지 않았습니다. 공식 사용량에서 결과 또는 추가 확인 안내를 확인하세요. 중복 사용을 막기 위해 자동 재시도하지 않습니다.'};
  } finally {
    resetExecuting = false;
  }
}
