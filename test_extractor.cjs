// Test the actual reader in a minimal DOM, without accounts or network access.
const {execFileSync} = require('node:child_process');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = execFileSync('python', ['-X','utf8','-c','from core import EXTRACT; print(EXTRACT)'], {encoding:'utf8'});
function extract(text, {host='claude.ai', path='/settings/usage', dialog=false}={}) {
  const section={innerText:text,getClientRects:()=>[{}]};
  return JSON.parse(JSON.stringify(vm.runInNewContext(source, {
    location:{hostname:host,pathname:path},
    document:{querySelectorAll:()=>dialog?[section]:[],querySelector:()=>section},
    getComputedStyle:()=>({visibility:'visible'})
  })));
}
assert.deepEqual(extract('Current session\n25% used\nResets in 2 hours'),[{label:'Current session',remaining:75,resetText:'Resets in 2 hours'}]);
assert.equal(extract('이번 주\n30% 남음')[0].remaining,30);
assert.deepEqual(extract('Current session\n25% used',{path:'/chat/example'}),[]);
assert.deepEqual(extract('Current session\n25%'),[]);
assert.deepEqual(extract('Current session\n125% used'),[]);
assert.deepEqual(extract('Usage limits\n5 hours\n40% remaining',{host:'gemini.google.com',path:'/app'}),[]);
const modal = extract('사용량\n현재 세션\n첫 메시지부터 시작됩니다\n0% 사용됨\n이번 주\n재설정: 금요일 오후 12:00\n26% 사용됨\n제한 초기화', {path:'/new',dialog:true});
assert.equal(modal[0].resetText,'첫 메시지부터 시작됩니다');
assert.equal(modal[1].resetText,'재설정: 금요일 오후 12:00');
console.log('8 usage-reader checks passed');
const screenshot = '사용량\n현재 세션\n오후 1:00에 재설정\n2% 사용됨\n이번 주\n오후 12:00에 재설정\n27% 사용됨\n제한 초기화\n전체 초기화\n만료일: 10월 23일\n무료로 초기화\n5시간 초기화\n지금은 없습니다. 새로 받으면 여기에 표시됩니다.\n사용 크레딧\nUS$0';
const credits = extract(screenshot);
assert.equal(credits.length,4);
assert.deepEqual(credits[2],{kind:'resetCredit',label:'전체 초기화',resetText:'만료일: 10월 23일'});
assert.match(credits[3].resetText,/지금은 없습니다/);
assert.equal(extract('현재 세션\n2% 사용됨\n전체 초기화\n만료일: 10월 23일').length,1);
assert.equal(extract('제한 초기화\n전체 초기화\n만료일: 10월 23일').length,0);
assert.equal(extract('현재 세션\n2% 사용됨\n제한 초기화\n사용 크레딧\n전체 초기화\n만료일: 10월 23일').length,1);
const fs = require('node:fs');
const extension = fs.readFileSync('extension/reader.js','utf8');
assert.equal(extension.trim().replace(/^const quotaRead = \(\) => /,'').replace(/;$/,''),source.trim());
console.log('Reset credit extraction and extension parity checks passed');
const withCloud = screenshot.replace('사용 크레딧\nUS$0','클라우드 세션 크레딧\n만료: 11월 5일\n사용 크레딧\nUS$0');
assert.equal(extract(withCloud)[3].resetText,'지금은 없습니다. 새로 받으면 여기에 표시됩니다.');
