function readRows() {
  if (!usageURL(location.href) || blockedPage()) return [];
  return quotaRead();
}
function blockedPage() {
  return /just a moment|잠시만 기다리|security verification|보안 확인|verify you are human/i.test(document.title);
}
async function sample() {
  if (!resetAccount(location.href) || blockedPage()) return;
  try {
    const credits = resetSnapshot();
    if (credits) await chrome.runtime.sendMessage({type:'resetSample',credits});
    if (usageURL(location.href)) await chrome.runtime.sendMessage({type:'sample',rows:readRows()});
  } catch { }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type === 'useReset') {
    if (!resetAccount(location.href) || blockedPage()) { reply({ok:false,error:'사용량 화면의 로그인 또는 사람 확인이 필요합니다.'}); return; }
    useReset(message.identity,message.id).then(result=>{reply(result);sample();}).catch(()=>reply({ok:false,error:'사용 결과를 확인할 수 없습니다. 공식 사용량을 확인하세요.'}));
    return true;
  }
  if (message.type === 'resetSnapshot') reply({credits:blockedPage()?null:resetSnapshot()});
  if (message.type === 'revealReset') reply(blockedPage()?{ok:false,error:'로그인 또는 사람 확인이 필요합니다.'}:revealReset(message.identity));
  if (message.type === 'snapshot') reply({rows:readRows(), hidden:document.visibilityState === 'hidden', blocked:blockedPage()});
  if (message.type === 'check') reply({valid:readRows().length > 0, hidden:document.visibilityState === 'hidden'});
  if (message.type === 'sampleNow') { sample(); reply({ok:true}); }

});
setTimeout(sample,1500);
setInterval(sample,15000);
document.addEventListener('visibilitychange',sample);
