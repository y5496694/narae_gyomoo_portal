'use strict';
const {createHash,randomUUID}=require('node:crypto');
const {edufineHost}=require('../../narae-gyomu-work-portal/scripts/regions.cjs');
const hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
// A bounded DOM projection, evaluated by the browser adapter. Never read app data sets.
function stateDOM(root){
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('[aria-hidden=true],[inert]');};
 const base=root+'.divWork.form.',nodes=[...document.querySelectorAll('[id]')].filter(e=>e.id.startsWith(base)&&visible(e));
 return {root,url:location.origin+location.pathname,fields:nodes.filter(e=>e.matches('input:not([type=password]):not([type=file]),textarea,select')).map(e=>({id:e.id,value:e.value,readOnly:Boolean(e.readOnly),disabled:Boolean(e.disabled)})),
  cells:nodes.filter(e=>/\.(grdBgtDtl|grdPrdlstDtl|grdFileUpload)\.body\.gridrow_\d+\.cell_\d+_\d+:text$/.test(e.id)).map(e=>({id:e.id,text:e.innerText.replace(/\s+/g,' ').trim()}))};
}
async function execute(browser,c){
 const u=new URL(browser.scope().url());if(u.protocol!=='https:'||!edufineHost(u.hostname))throw Error('금융 품의 전용 동작은 현재 교육청 에듀파인에서만 지원합니다.');
 browser.requisitionReceipts||=new Map();
 if(c.action==='requisition-observe'){
  if(typeof c.root!=='string'||!/^mainframe\.[\w.]+\.winId_[\w]+\.form$/.test(c.root))throw Error('관찰한 품의 MDI 경로가 필요합니다.');
  const value=await browser.scope().evaluate(stateDOM,c.root);return {...value,digest:hash(value)};
 }
 if(c.action==='requisition-confirm'){
  const r=browser.requisitionReceipts.get(c.id),d=browser.pendingDialog;
  if(!r||r.page!==browser.page||r.origin!==u.origin||!d||d.page!==r.page||d.id!==c.dialogId||d.message!==c.message||r.dialogs.has(d.id))throw Error('직전 품의 동작에 묶인 실제 확인창이 아닙니다.');
  if(/암호|인증서|서명|로그인|결제|지급|송금|전송|발송/.test(d.message))throw Error('인증·지급·발송 확인창은 품의 처리로 수락하지 않습니다.');
  const expected=r.operation==='save'?/저장|등록/:r.operation==='delete'?/삭제/:/결재|상신|기안/;
  if(d.type==='confirm'&&!expected.test(d.message))throw Error('품의 작업과 다른 확인창입니다.');
  r.dialogs.add(d.id);const result=await browser.handleDialog({action:'dialog',decision:'accept',expectedId:d.id,expectedMessage:d.message});
  return {id:r.id,operation:r.operation,confirmed:true,serverVerified:false,dialogId:d.id,result};
 }
 if(c.action!=='requisition-click'||!['save','delete','approval-request','query'].includes(c.operation))throw Error('지원하지 않는 품의 전용 동작입니다.');
 const s=await execute(browser,{action:'requisition-observe',root:c.root}),get=suffix=>s.fields.find(f=>f.id===c.root+'.divWork.form.'+suffix)?.value;
 if(c.digest!==s.digest)throw Error('검토 후 품의 입력값이 달라졌습니다.');
 const number=get('divMain.form.edtCnsulNo:input')||'',title=get('divMain.form.edtCnsulSj:input')||'';
 if(c.operation!=='query'&&(title!==c.title||number!==(c.number||'')))throw Error('품의번호·제목이 검토 대상과 다릅니다.');
 if(['delete','approval-request'].includes(c.operation)&&!number)throw Error('저장된 품의번호를 확인해야 합니다.');
 const {entry,locator}=browser.ref(c.ref),prefix=c.root+'.divWork.form.';
 const expected={save:['divAuth0.form.btnAuthR02'],delete:['divAuth0.form.btnAuthR01'],query:['divAuth.form.btnAuthS01']};
 const allowed=c.operation==='approval-request'?entry.id.startsWith(prefix+'divAuth0.form.')&&entry.label.replace(/\s/g,'').startsWith('결재요청'):(expected[c.operation]||[]).some(id=>entry.id===prefix+id);
 if(!allowed||entry.disabled||!await locator.isVisible()||!await locator.isEnabled())throw Error('관찰한 품의 전용 버튼이 아닙니다.');
 const key=hash({page:s.url,root:c.root,operation:c.operation,digest:c.digest});browser.requisitionAttempts||=new Set();
 if(c.operation!=='query'&&browser.requisitionAttempts.has(key))throw Error('이미 실행한 품의 동작입니다. 재실행하지 말고 서버 목록으로 확인하세요.');
 browser.requisitionAttempts.add(key);const id=randomUUID(),r={id,operation:c.operation,origin:u.origin,page:browser.page,root:c.root,title,number,dialogs:new Set(),network:[],started:Date.now()};browser.requisitionReceipts.set(id,r);
 const response=async req=>{try{const ru=new URL(req.url());if(ru.origin!==u.origin||!['xhr','fetch'].includes(req.resourceType()))return;const res=await req.response();r.network.push({path:ru.pathname,status:res.status()});}catch{}};
 r.page.on('requestfinished',response);setTimeout(()=>r.page.off('requestfinished',response),20000).unref?.();
 const pending=await browser.withDialog(()=>locator.click());
 if(!pending){await new Promise(resolve=>setTimeout(resolve,500));browser.invalidate();}
 return {id,operation:c.operation,attempted:true,serverVerified:false,networkCompleted:r.network,...(browser.pendingDialog?{nativeDialog:browser.dialogState()}:{}),...(!browser.pendingDialog?{screen:await browser.snapshot()}:{} )};
}
module.exports={execute,stateDOM,hash};
