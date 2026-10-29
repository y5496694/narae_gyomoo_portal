const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../skills/wxs-cli/scripts/wxs_actions.js'), 'utf8');
let count = 0;
function test(name, run) { run(); count++; console.log('PASS ' + name); }
function ctx(extra={}) {
  const pending = [];
  const context = vm.createContext({document:{getElementById(){return null;},getElementsByTagName(){return [];}},frames:[],setTimeout(fn){pending.push(fn);},...extra});
  vm.runInContext(source, context);
  context.flush = () => {while(pending.length) pending.shift()();};
  return context;
}

test('unsupported submission and generic script actions are rejected', () => {
  const c=ctx(); for (const action of ['submit','send','eval']) assert.throws(()=>c.wxsAction(action,{}),/Unsupported/);
});
test('observed final controls only click the matching live form and title', () => {
  for (const [operation,appType,label] of [['submit','sancgian','상신'],['approve','sanckyul','결재']]) {
    let clicked=0;
    const button={tagName:'BUTTON',innerText:label,disabled:false,getAttribute(){return null;},getBoundingClientRect(){return {left:0,right:50,top:0,bottom:20};},click(){clicked++;}};
    const c=ctx({rInfo:{appType,docProcessed:false},document:{getElementById(id){return id==='Sj'?{value:'합성 QA-001'}:null;},getElementsByTagName(){return [button];}}});
    const observed=c.wxsAction('final_buttons',{});assert.equal(observed.length,1);assert.equal(clicked,0);
    assert.throws(()=>c.wxsAction('final_click',{button:observed[0],operation,expected_title:'다른 문서'}),/Title changed/);
    c.wxsAction('final_click',{button:observed[0],operation,expected_title:'합성 QA-001'});c.flush();assert.equal(clicked,1);
    delete c.rInfo.docProcessed;
    assert.throws(()=>c.wxsAction('final_click',{button:observed[0],operation,expected_title:'합성 QA-001'}),/unknown/);
    assert.equal(c.wxsAction('status',{}).processed,null);
    c.rInfo.docProcessed=false;button.disabled=true;
    assert.throws(()=>c.wxsAction('final_click',{button:observed[0],operation,expected_title:'합성 QA-001'}),/button changed/);
  }
});
test('readonly document cannot open write dialogs', () => {
  const c=ctx({rInfo:{appType:'sanckyul',docProcessed:false},fncReportCours(){throw Error('must not call');}});
  assert.throws(()=>c.wxsAction('open_approval',{}),/unprocessed sancgian/);
});
test('task selection uses exact dataset name, not a hardcoded ID', () => {
  let selected=-1, confirmed=0; const names=['다른 과제','가상 과제'];
  const form={dsAList:{rowcount:2,getColumn(i){return names[i];}},fnSelectUnitTkcrd(i){selected=i;},Tab00_Tabpage1_divAuth_btnAuthC01_onclick(){confirmed++;}};
  const c=ctx({nexacro:{getApplication(){return {mainframe:{QuickViewFrame:{form}}};}}});
  c.wxsAction('task_select',{name:'가상 과제'}); c.flush(); assert.equal(selected,1); assert.equal(confirmed,1);
  assert.throws(()=>c.wxsAction('task_select',{name:'과제'}),/exact unique/);
  names[0]='가상 과제'; assert.throws(()=>c.wxsAction('task_select',{name:'가상 과제'}),/exact unique/);
});
test('same-name approvers stop until an exact ID is supplied', () => {
  let clicked=0, participants=1, verified=0;
  const radio = id => ({type:'radio',name:'partSelRadio',value:'가상교사',id,parentNode:{parentNode:{innerText:'가상부서 교사'}} ,click(){clicked++;}});
  const c=ctx({frames:[{document:{getElementsByTagName(){return [radio('mock-A'),radio('mock-B')];}}}],PrtcpList:{toArray(){return Array(participants).fill({});}},fncAdd(){participants++;},fncVerify(){verified++;}});
  assert.throws(()=>c.wxsAction('approval_select',{name:'가상교사'}),/exact unique/); assert.equal(clicked,0);
  c.wxsAction('approval_select',{name:'가상교사',id:'mock-B'});c.flush();assert.equal(clicked,1);assert.equal(verified,1);
  assert.throws(()=>c.wxsAction('approval_select',{name:'가상교사'}),/drafter-only/);
});
test('recipient requires full exact name and preserves an existing list', () => {
  let clicked=0, verified=0; const list=[];
  const nodes=[{name:'orgnztChk',title:'가상교육청 가상센터',checked:false,click(){clicked++;}}];
  const c=ctx({document:{getElementsByTagName(){return nodes;}},RecptList:{all:list},fncAdd(){list.push({});},fncVerify(){verified++;}});
  assert.throws(()=>c.wxsAction('recipient_select',{name:'가상센터'}),/exact unique/);assert.equal(clicked,0);
  c.wxsAction('recipient_select',{name:'가상교육청 가상센터'}); c.flush();assert.equal(clicked,1);assert.equal(verified,1);
  assert.throws(()=>c.wxsAction('recipient_select',{name:'가상교육청 가상센터'}),/list changed/);
});
test('private reasons uncheck reasons not requested', () => {
  const els={othbcLmtt3:{checked:false,click(){this.checked=!this.checked;}}};
  for(let i=1;i<=8;i++)els['othbcAt'+i]={checked:i===3,click(){this.checked=!this.checked;}};
  const c=ctx({rInfo:{appType:'sancgian'},document:{getElementById(id){return els[id];},getElementsByTagName(){return [];}}});
  const result=c.wxsAction('private',{reasons:[6]});assert.equal(result.private,true);assert.equal(JSON.stringify(result.private_reasons),'[6]');
});
test('automatic send only configures an external document; no send occurs', () => {
  let popupCount=0;const box={checked:false};
  const c=ctx({rInfo:{appType:'sancgian'},domHox1:{},get_text(_,path){return path.endsWith('senderName')?'가상학교장':'enforcetype_external';},popup(url){assert.match(url,/retrieveDocSndngScrinAto/);popupCount++;},document:{getElementById(){return box;}}});
  c.wxsAction('open_auto_send',{});c.flush();assert.equal(box.checked,true);assert.equal(popupCount,1);
  assert.throws(()=>c.wxsAction('open_auto_send',{}),/already selected/);
});
test('multiple seals and missing default seal stop', () => {
  let verified=0;const els={signSe2:{checked:true},ocslRadio0:{checked:true}};let inputs=[{id:'ocslRadio0'},{id:'ocslRadio1'}];
  const c=ctx({document:{getElementById(id){return els[id];},getElementsByTagName(){return inputs;}},fncVerify(){verified++;}});
  assert.throws(()=>c.wxsAction('auto_send_confirm',{}),/Multiple/);assert.equal(verified,0);
  inputs=[{id:'ocslRadio0'}];c.wxsAction('auto_send_confirm',{});c.flush();assert.equal(verified,1);
});
test('attachment action keeps native validation and verifies rejection', () => {
  const files=[];let reject=true;const c=ctx({rInfo:{appType:'sancgian'},HsFile:function(path,name,size){Object.assign(this,{path,name,size});},Attach:{fileBox:{files(){return files;}},addFiles(incoming){if(!reject)files.push(...incoming);},onrefresh(){}}});
  assert.throws(()=>c.wxsAction('attach',{path:'mock.pdf',name:'mock.pdf',size:8,expected_count:0}),/rejected/);
  reject=false;const result=c.wxsAction('attach',{path:'mock.pdf',name:'mock.pdf',size:8,expected_count:0});assert.equal(result[0].size,8);
});
test('Prototype-style Array.toJSON does not turn output arrays into strings', () => {
  const c=ctx(); const result=vm.runInContext('Array.prototype.toJSON=function(){return "bad";}; JSON.stringify(wxsPlain({rows:[{name:"mock"}],empty:[]}));',c);
  assert.deepEqual(JSON.parse(result),{rows:[{name:'mock'}],empty:[]});
});
test('temporary save calls only the temporary-save handler', () => {
  let opened=0,saved=0;const input={value:''};const c=ctx({rInfo:{appType:'sancgian'},fncSaveTmpr(){opened++;},fncSave(){saved++;},document:{getElementById(){return input;}}});
  c.wxsAction('open_save',{});c.flush();c.wxsAction('save_name',{name:'가상 초안'});c.flush();assert.equal(opened,1);assert.equal(saved,1);assert.equal(input.value,'가상 초안');
});
console.log(`${count} action tests passed; no real application or network used.`);
