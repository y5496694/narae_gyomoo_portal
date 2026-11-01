'use strict';
const {createHash,randomUUID}=require('node:crypto');
const {edufineHost}=require('../../narae-gyomu-work-portal/scripts/regions.cjs');
const hash=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
// A bounded DOM projection, evaluated by the browser adapter. Never read app data sets.
function stateDOM(root){
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.closest('[aria-hidden=true],[inert]');};
 const base=root+'.divWork.form.',nodes=[...document.querySelectorAll('[id]')].filter(e=>e.id.startsWith(base)&&visible(e));
 return {root,url:location.origin+location.pathname,fields:nodes.filter(e=>e.matches('input:not([type=password]):not([type=file]),textarea,select')).map(e=>({id:e.id,value:e.value,readOnly:Boolean(e.readOnly),disabled:Boolean(e.disabled)})),
  cells:nodes.filter(e=>/\.(grdBgtDtl|grdPrdlstDtl|grdFileUpload)\.body\.gridrow_\d+\.cell_\d+_\d+(?::text|\.(?:celledit0?|cellmaskedit0?|cellcombo\.comboedit):input)$/.test(e.id)).map(e=>({id:e.id,text:(e.value??e.innerText).replace(/\s+/g,' ').trim()}))};
}
async function htmlDialog(browser,r){
 const s=await browser.snapshot({selector:'[id$=".txtMsgContent:textarea"],[id$=".btnOk"],[id$=".btnCancel"],[id$=".btnCancle"]',limit:100,chars:200}),fields=s.elements?.filter(e=>/\.(?:NAA|FAA)\d{4}\.form\.txtMsgContent:textarea$/.test(e.id));
 if(!fields?.length)return null;if(fields.length!==1)throw Error('품의 안내창을 하나로 확인하지 못했습니다.');const field=fields[0],root=field.id.replace(/\.txtMsgContent:textarea$/,''),buttons=(s.elements||[]).filter(e=>e.id.startsWith(root+'.')&&/\.btn(?:Ok|Cancel|Cancle)$/.test(e.id));
 if(!root.startsWith(r.root.replace(/\.form$/,'')))throw Error('다른 품의 창의 안내입니다.');
 const message=field.value??field.label;return {id:hash({root,message,buttons:buttons.map(e=>e.id)}),kind:'html',root,message,confirmation:buttons.some(b=>/\.btn(?:Cancel|Cancle)$/.test(b.id)),buttons};
}
function watchRequests(r){
 if(r.listener)r.page.off('requestfinished',r.listener);
 const listener=async req=>{try{const u=new URL(req.url());if(u.origin!==r.origin||req.method()!=='POST'||/sessionCheck|UseTime|heartbeat/i.test(u.pathname)||!['xhr','fetch'].includes(req.resourceType()))return;const res=await req.response();r.network.push({path:u.pathname,method:'POST',status:res.status()});}catch{}};
 r.listener=listener;r.page.on('requestfinished',listener);setTimeout(()=>r.page.off('requestfinished',listener),20000).unref?.();
}
async function execute(browser,c){
 const u=new URL(browser.scope().url());if(u.protocol!=='https:'||!edufineHost(u.hostname))throw Error('금융 품의 전용 동작은 현재 교육청 에듀파인에서만 지원합니다.');
 browser.requisitionReceipts||=new Map();
 if(c.action==='requisition-status'||c.action==='requisition-observe'&&c.id){const r=browser.requisitionReceipts.get(c.id);if(!r||r.page!==browser.page||r.origin!==u.origin)throw Error('현재 창의 품의 동작 기록이 필요합니다.');return {id:r.id,operation:r.operation,networkCompleted:[...r.network],nativeDialog:browser.dialogState()||await htmlDialog(browser,r)};}
 if(browser.pendingDialog&&c.action!=='requisition-confirm')throw Error('직전 품의 동작의 확인창부터 처리하세요.');
 if(c.action==='requisition-observe'){
  if(typeof c.root!=='string'||!/^mainframe\.[\w.]+\.winId_[\w]+\.form$/.test(c.root))throw Error('관찰한 품의 MDI 경로가 필요합니다.');
  const value=await browser.scope().evaluate(stateDOM,c.root);return {...value,digest:hash(value)};
 }
 if(c.action==='requisition-confirm'){
  const r=browser.requisitionReceipts.get(c.id),d=browser.pendingDialog;
  if(!r||r.page!==browser.page||r.origin!==u.origin)throw Error('직전 품의 동작에 묶인 실제 확인창이 아닙니다.');
  const dialog=d?{...d,confirmation:d.type==='confirm'}:await htmlDialog(browser,r);
  if(!dialog||dialog.id!==c.dialogId||dialog.message!==c.message||r.dialogs.has(dialog.id)||d&&d.page!==r.page)throw Error('직전 품의 동작에 묶인 실제 확인창이 아닙니다.');
  if(/암호|인증서|서명|로그인|결제|지급|송금|전송|발송/.test(dialog.message))throw Error('인증·지급·발송 확인창은 품의 처리로 수락하지 않습니다.');
  const expected=r.operation==='save'?/저장|등록/:r.operation==='delete'?/삭제/:r.operation==='reset'?/^신규 등록하시겠습니까\?/:/결재|상신|기안/;
  if(dialog.confirmation&&!expected.test(dialog.message))throw Error('품의 작업과 다른 확인창입니다.');
  const validationRejected=r.operation==='save'&&!dialog.confirmation&&/^(?:제목|개요|요구일자|완료요구일자|내용|수량|예상단가|예상금액)\s*항목은 필수입력사항입니다\.$/.test(dialog.message)&&!r.network.some(n=>n.method==='POST');
  r.dialogs.add(dialog.id);watchRequests(r);let result;
  if(d)result=await browser.handleDialog({action:'dialog',decision:'accept',expectedId:d.id,expectedMessage:d.message});
  else {const button=dialog.buttons.find(e=>e.id.endsWith('.btnOk'));if(!button)throw Error('실제 확인 버튼이 없습니다.');await browser.withDialog(()=>browser.ref(button.ref).locator.click());await new Promise(resolve=>setTimeout(resolve,300));browser.invalidate();result={handled:true};}
  if(validationRejected){const key=r.key||hash({page:u.origin+u.pathname,root:r.root,operation:r.operation,digest:c.expectedDigest});browser.requisitionAttempts.delete(key);r.validationRejected=true;}
  const next=browser.pendingDialog?browser.dialogState():await htmlDialog(browser,r);
  return {id:r.id,operation:r.operation,confirmed:true,serverVerified:false,dialogId:dialog.id,result,...(next?{nativeDialog:next}:{}),validationRejected,safeRetryAllowed:validationRejected};
 }
 if(c.action!=='requisition-click'||!['save','delete','reset','query'].includes(c.operation))throw Error('지원하지 않는 품의 전용 동작입니다.');
 const s=await execute(browser,{action:'requisition-observe',root:c.root}),get=suffix=>s.fields.find(f=>f.id===c.root+'.divWork.form.'+suffix)?.value;
 if(c.digest!==s.digest)throw Error('검토 후 품의 입력값이 달라졌습니다.');
 const number=get('divMain.form.edtCnsulNo:input')||'',title=get('divMain.form.edtCnsulSj:input')||'';
 if(c.operation!=='query'&&(title!==c.title||number!==(c.number||'')))throw Error('품의번호·제목이 검토 대상과 다릅니다.');
 if(['delete','reset'].includes(c.operation)&&!number)throw Error('저장된 품의번호를 확인해야 합니다.');
 const {entry,locator}=browser.ref(c.ref),prefix=c.root+'.divWork.form.';
 const expected={save:['divAuth0.form.btnAuthR02'],delete:['divAuth0.form.btnAuthR01'],query:['divAuth.form.btnAuthS01']};
 const allowed=c.operation==='reset'?entry.id.startsWith(prefix+'divAuth0.form.')&&entry.label.replace(/\s/g,'')==='신규':(expected[c.operation]||[]).some(id=>entry.id===prefix+id);
 if(!allowed||entry.disabled||!await locator.isVisible()||!await locator.isEnabled())throw Error('관찰한 품의 전용 버튼이 아닙니다.');
 const key=hash({page:s.url,root:c.root,operation:c.operation,digest:c.digest});browser.requisitionAttempts||=new Set();
 if(c.operation!=='query'&&browser.requisitionAttempts.has(key))throw Error('이미 실행한 품의 동작입니다. 재실행하지 말고 서버 목록으로 확인하세요.');
 browser.requisitionAttempts.add(key);const id=randomUUID(),r={id,key,operation:c.operation,origin:u.origin,page:browser.page,root:c.root,title,number,dialogs:new Set(),network:[],started:Date.now()};browser.requisitionReceipts.set(id,r);watchRequests(r);
 const pending=await browser.withDialog(()=>locator.click());
 if(!pending){await new Promise(resolve=>setTimeout(resolve,500));browser.invalidate();}
 const dialog=browser.pendingDialog?browser.dialogState():await htmlDialog(browser,r);
 return {id,operation:c.operation,attempted:true,serverVerified:false,networkCompleted:r.network,...(dialog?{nativeDialog:dialog}:{}),...(!browser.pendingDialog?{screen:await browser.snapshot()}:{} )};
}
module.exports={execute,stateDOM,hash};
