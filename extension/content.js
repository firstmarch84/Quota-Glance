function readRows() {
  if (!usageURL(location.href) || blockedPage()) return [];
  return quotaRead();
}
function blockedPage() {
  return /just a moment|잠시만 기다리|security verification|보안 확인|verify you are human/i.test(document.title);
}
async function sample() {
  if (!usageURL(location.href)) return;
  try { await chrome.runtime.sendMessage({type:'sample',rows:readRows()}); } catch { }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type === 'snapshot') reply({rows:readRows(), hidden:document.visibilityState === 'hidden', blocked:blockedPage()});
  if (message.type === 'check') reply({valid:readRows().length > 0, hidden:document.visibilityState === 'hidden'});
  if (message.type === 'sampleNow') { sample(); reply({ok:true}); }

});
setTimeout(sample,1500);
setInterval(sample,15000);
document.addEventListener('visibilitychange',sample);
