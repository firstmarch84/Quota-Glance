const quotaRead = () => (() => {
 const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
 const dialog = [...document.querySelectorAll('[role="dialog"], dialog')].find(e => visible(e) && /usage|사용\s*한도|사용량/i.test(e.innerText));
 const isClaudeUsage = location.hostname === 'claude.ai' && /^\/settings\/usage\/?$/.test(location.pathname);
 let section = location.hostname === 'claude.ai' ? (dialog || (isClaudeUsage ? document.querySelector('main') : null)) : null;
 if (!section) return [];
 const lines = section.innerText.split('\n').map(s => s.trim()).filter(Boolean);
 const rows = [];
 for (let i=0; i<lines.length; i++) {
   const line = lines[i];
   let m = line.match(/^(\d{1,3}(?:\.\d+)?)\s*%\s*(used|remaining|left|사용됨|사용|남음|남았습니다|남은)(?:\s.*)?$/i);
   let reverse = line.match(/^(사용량|사용됨|사용|남은\s*한도|남음|remaining|used)\s*[:：]?\s*(\d{1,3}(?:\.\d+)?)\s*%$/i);
   if (!m && !reverse) continue;
   const n = Number(m ? m[1] : reverse[2]);
   if (n < 0 || n > 100) continue;
   const direction = m ? m[2] : reverse[1];
   const prev = lines.slice(Math.max(0,i-4),i);
   const isLabel = s => /session|week|hour|세션|주간|이번\s*주|시간|all models|모든\s*모델|sonnet|pro|thinking/i.test(s) && !/reset|초기화|재설정|갱신/i.test(s) && s.length<90;
   const label = [...prev].reverse().find(isLabel);
   if (!label) continue;
   const before = prev.slice(prev.lastIndexOf(label)+1);
   const after = [];
   for (const s of lines.slice(i+1,i+4)) { if (isLabel(s) || /%/.test(s)) break; after.push(s); }
   const nearby = [...before,...after].find(s => /reset|초기화|재설정|갱신|첫.*시작/i.test(s) && !/^(제한 초기화|reset limits)$/i.test(s));
   rows.push({label, remaining: /remaining|left|남/i.test(direction) ? n : 100-n, resetText: nearby || ''});
 }
 return rows.slice(0,8);
})();
