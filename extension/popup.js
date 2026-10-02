const status = document.getElementById('status');
chrome.storage.local.get('key').then(({key}) => { if(key) status.textContent='연결 코드가 저장되어 있습니다.'; });
document.getElementById('pair').addEventListener('click',async () => {
  status.textContent='앱 연결 확인 중…';
  try {
    const result = await chrome.runtime.sendMessage({type:'pair',key:document.getElementById('key').value});
    status.textContent=result.ok?'연결 완료! 사용량 탭을 자동 준비합니다.':result.error||'연결 실패';
    if(result.ok) document.getElementById('key').value='';
  } catch { status.textContent='앱을 실행한 뒤 다시 연결해 주세요.'; }
});
document.getElementById('usage').addEventListener('click',() => chrome.tabs.create({url:'https://claude.ai/settings/usage'}));
document.getElementById('codex-usage').addEventListener('click',() => chrome.tabs.create({url:'https://chatgpt.com/settings/usage?tab=overview'}));
