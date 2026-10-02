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
 const result = rows.slice(0,8);
 // Only read the dedicated reset section, never infer coupons from reset times.
 const start = lines.findIndex(s => /^(제한 초기화|사용 한도 초기화|Reset limits|Usage limit resets|Limit resets)$/i.test(s));
 if (start >= 0 && result.length) {
   const end = lines.findIndex((s,i) => i > start && /^(사용 크레딧|클라우드 세션 크레딧|Usage credits|Cloud session credits|Extra usage)$/i.test(s));
   const resetLines = lines.slice(start+1,end < 0 ? undefined : end);
   for (let i=0; i<resetLines.length && result.length<16; i++) {
     if (!/^(전체 초기화|전체 재설정|5\s*시간 초기화|Full reset|Full resets|5[- ]hour reset|5[- ]hour resets)$/i.test(resetLines[i])) continue;
     const details = [];
     for (const s of resetLines.slice(i+1)) {
       if (/^(전체 초기화|전체 재설정|5\s*시간 초기화|Full resets?|5[- ]hour resets?)$/i.test(s)) break;
       if (/만료|expir|지금은 없습니다|새로 받으면|none available|no resets/i.test(s) && s.length <= 200) details.push(s);
     }
     if (details.length) result.push({kind:'resetCredit',label:resetLines[i],resetText:details.join(' · ').slice(0,200)});
   }
 }
 return result;
})();
