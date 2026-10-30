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
test('current numbered approval rows exclude recall history in the same table',()=>{
  const rows=[{innerText:'결재경로표-'},{innerText:'2결재가상 교장대기'},{innerText:'1기안가상 교사대기'},{innerText:'-결재가상 교장-'},{innerText:'-기안가상 교사회수'}, {innerText:'3결재교장합성교장(mock)-0.0'}];
  const c=ctx({rInfo:{appType:'sancgian',docProcessed:false},document:{getElementById(){return null;},getElementsByTagName(tag){return tag==='table'?[{innerText:'결재경로표-',rows}]:[];}}});
  assert.deepEqual(Array.from(c.wxsAction('status',{}).approval_rows),['2결재가상 교장대기','1기안가상 교사대기']);
});

test('PDF open uses only the unique observed read-only server path',()=>{
  const files=[{name:'합성.pdf',path:'observed-server-path',atSancbox:true}];
  const opened=[];
  const c=ctx({rInfo:{appType:'sancview'},Attach:{fileBox:{files(){return files;}},open(path){opened.push(path);}}});
  for(const name of ['없는.pdf','실행.exe'])assert.throws(()=>c.wxsAction('attachment_open',{name}));
  files.push({...files[0]});assert.throws(()=>c.wxsAction('attachment_open',{name:'합성.pdf'}));files.pop();
  files[0].atSancbox=false;assert.throws(()=>c.wxsAction('attachment_open',{name:'합성.pdf'}));
  files[0].atSancbox=true;c.rInfo.appType='sancgian';assert.throws(()=>c.wxsAction('attachment_open',{name:'합성.pdf'}));
  assert.equal(opened.length,0);c.rInfo.appType='sancview';
  assert.equal(c.wxsAction('attachment_open',{name:'합성.pdf'}).handler_returned,true);
  assert.deepEqual(opened,['observed-server-path']);
});
test('route review proof requires the original native guard and processing gate',()=>{
 const c=ctx({rInfo:{appType:'sancgian',docProcessed:false},pInfo:{appr_inited:false},lang_chkApprLine:'합성 경로 안내',
   Validator:{validate:function(){if(!pInfo.appr_inited){alert(lang_chkApprLine);showApprProperty();throw $break;}}},
   fncValidate:function(){try{Validator.validate(domHox1);}catch(e){return false;}},
   fncSanctn:function(){var valiResult = fncValidate();if(valiResult){showDocSanctnProc();}}});
 let proof=c.wxsAction('route_review_status',{});assert.equal(proof.reviewed,false);assert.equal(proof.guard,true);assert.equal(proof.processing_gate,true);
 c.pInfo.appr_inited=true;assert.equal(c.wxsAction('route_review_status',{}).reviewed,true);
 c.Validator.validate=function(){};assert.equal(c.wxsAction('route_review_status',{}).guard,false);
});
test('task selection uses exact dataset name, not a hardcoded ID', () => {
  let selected=-1, confirmed=0; const names=['다른 과제','가상 과제'];
  const form={dsAList:{rowcount:2,getColumn(i){return names[i];}},fnSelectUnitTkcrd(i){selected=i;},Tab00_Tabpage1_divAuth_btnAuthC01_onclick(){confirmed++;}};
  const c=ctx({nexacro:{getApplication(){return {mainframe:{QuickViewFrame:{form}}};}}});
  c.wxsAction('task_select',{name:'가상 과제'}); c.flush(); assert.equal(selected,1); assert.equal(confirmed,1);
  assert.throws(()=>c.wxsAction('task_select',{name:'과제'}),/exact unique/);
  names[0]='가상 과제'; assert.throws(()=>c.wxsAction('task_select',{name:'가상 과제'}),/exact unique/);
});
test('task lookup includes retention without exposing unrelated dataset columns', () => {
  const rows=[{tkcrdId:'mock-task',tkcrdNm:'가상 개별화교육',dcryPrsrvPdSeCd:'30',dcryPrsrvPdSeNm:'30년',unrelated:'private'}];
  const form={dsAList:{rowcount:1,getColumn(i,key){return rows[i][key];}},Tab00_Tabpage1_divAuth_btnAuthC01_onclick(){}};
  const c=ctx({nexacro:{getApplication(){return {mainframe:{QuickViewFrame:{form}}};}}});
  assert.deepEqual(JSON.parse(JSON.stringify(c.wxsAction('task_options',{}))),{candidates:['가상 개별화교육'],rows:[{tkcrdId:'mock-task',tkcrdNm:'가상 개별화교육',dcryPrsrvPdSeCd:'30',dcryPrsrvPdSeNm:'30년'}]});
  form.dsAList.rowcount=0;
  assert.equal(c.wxsAction('ready',{kind:'open_task'}),true);
  assert.equal(c.wxsAction('task_options',{}).rows.length,0);
});

test('task search uses the UI search control and never selects or confirms', () => {
  let clicked=0,confirmed=0;
  const input={value:'',set_value(value){this.value=value;}};
  const form={dsAList:{rowcount:0},Tab00:{Tabpage1:{form:{divSearch:{form:{edtTaskNm:input}},divAuth:{form:{btnAuthS01:{click(){clicked++;}}}}}}},Tab00_Tabpage1_divAuth_btnAuthC01_onclick(){confirmed++;}};
  const c=ctx({nexacro:{getApplication(){return {mainframe:{QuickViewFrame:{form}}};}}});
  assert.throws(()=>c.wxsAction('task_search',{query:''}),/search text/);
  c.wxsAction('task_search',{query:'개별화'});assert.equal(input.value,'개별화');assert.equal(clicked,0);
  c.flush();assert.equal(clicked,1);assert.equal(confirmed,0);
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
function routeFixture() {
  const participants=[{ID:'drafter'}], selects={};let selected=null, verified=0;
  const names=['가상 연구부장','가상 교감','가상 교장'];
  const radios=names.map((name,index)=>({type:'radio',name:'partSelRadio',value:name,id:'person-'+index,click(){selected=this;}}));
  const c=ctx({rInfo:{appType:'sancgian'},frames:[{document:{getElementsByTagName(){return radios;}}}],
    document:{getElementById(id){return selects[id];},getElementsByTagName(){return [];}},
    PrtcpList:{toArray(){return participants;}},fncAdd(){
      const index=participants.length;
      if(index>1){selects['draft'+(index-1)].value='review';participants[index-1].role='review';}
      participants.push({ID:selected.id,name:selected.value,role:'approve'});
      selects['draft'+index]={value:'approve',parentNode:{parentNode:{innerText:selected.value}},options:[{text:'검토',value:'review'},{text:'결재',value:'approve'}]};
    },fncVerify(){verified++;}});
  return {c,participants,radios,selects,verified:()=>verified,route:names.map((name,index)=>({name,id:'person-'+index,role:index===2?'결재':'검토'}))};
}
test('approval route preserves drafter, appends exact people in order and uses native role choices', () => {
  const f=routeFixture();f.c.wxsAction('approval_route',{route:f.route});
  assert.equal(f.verified(),0);f.c.flush();assert.equal(f.verified(),1);
  assert.deepEqual(f.participants,[{ID:'drafter'},{ID:'person-0',name:'가상 연구부장',role:'review'},{ID:'person-1',name:'가상 교감',role:'review'},{ID:'person-2',name:'가상 교장',role:'approve'}]);
});
test('approval route resolves every person before adding and never overwrites existing people', () => {
  for(const issue of ['missing','duplicate','drafter','existing','wrong-role']) {
    const f=routeFixture();
    if(issue==='missing')f.route[2].name='없는 사용자';
    if(issue==='duplicate')f.route[1]={...f.route[0]};
    if(issue==='drafter')f.radios[0].id='drafter';
    if(issue==='existing')f.participants.push({ID:'existing'});
    if(issue==='wrong-role')f.route[0].role='결재';
    const count=f.participants.length;
    assert.throws(()=>f.c.wxsAction('approval_route',{route:f.route}));f.c.flush();
    assert.equal(f.participants.length,count);assert.equal(f.verified(),0);
  }
});
test('unexpected native add order stops before approval confirmation', () => {
  const f=routeFixture();f.c.fncAdd=()=>f.participants.push({ID:'wrong-person'});
  assert.throws(()=>f.c.wxsAction('approval_route',{route:f.route}),/order changed/);
  f.c.flush();assert.equal(f.verified(),0);
});
test('partial disclosure uses the observed radio and exact requested reasons', () => {
  const els={};
  for(let i=1;i<=3;i++)els['othbcLmtt'+i]={checked:i===3,click(){for(let j=1;j<=3;j++)els['othbcLmtt'+j].checked=j===i;}};
  for(let i=1;i<=8;i++)els['othbcAt'+i]={checked:i===3,click(){this.checked=!this.checked;}};
  const c=ctx({rInfo:{appType:'sancgian'},document:{getElementById(id){return els[id];},getElementsByTagName(){return [];}}});
  const result=c.wxsAction('disclosure',{mode:'partial',reasons:[6]});
  assert.equal(result.disclosure,'partial');assert.equal(result.private,false);assert.equal(JSON.stringify(result.private_reasons),'[6]');
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
  const files=[];let reject=true;const c=ctx({rInfo:{appType:'sancgian',applID:'6010'},hsattach:{},HsFile:function(path,name,size){Object.assign(this,{path,name,size});},Attach:{syncNew:function(){},fileBox:{files(){return files;}},addFiles(incoming){if(!reject)files.push(...incoming);},onrefresh(){}}});
  assert.throws(()=>c.wxsAction('attach',{path:'mock.pdf',name:'mock.pdf',size:8,expected_count:0}),/rejected/);
  reject=false;const result=c.wxsAction('attach',{path:'mock.pdf',name:'mock.pdf',size:8,expected_count:0});assert.equal(result[0].size,8);
});
test('Prototype-style Array.toJSON does not turn output arrays into strings', () => {
  const c=ctx(); const result=vm.runInContext('Array.prototype.toJSON=function(){return "bad";}; JSON.stringify(wxsPlain({rows:[{name:"mock"}],empty:[]}));',c);
  assert.deepEqual(JSON.parse(result),{rows:[{name:'mock'}],empty:[]});
});
test('processing confirmation uses only the observed same form and excludes script content', () => {
  let clicked=0,removed=0;
  const button={innerText:'확인',disabled:false,getBoundingClientRect(){return {left:0,right:40,top:0,bottom:20};},click(){clicked++;}};
  const secretScript={parentNode:{removeChild(){removed++;}}};
  const fields=[{id:'enfcmtRules',name:'enfcmtRules',type:'checkbox',value:'on',checked:false,disabled:false,getBoundingClientRect(){return {left:0,right:10,top:0,bottom:10};}}];
  const clone={get innerText(){return removed?'결재올림 확인':'secret script';},querySelectorAll(){return [secretScript];}};
  const c=ctx({location:{pathname:'/bms/cz/cb/snd/retrieveDocSanctn.do'},document:{title:'문서처리',body:{cloneNode(){return clone;}},getElementById(id){return id==='aSubmit'?button:null;},querySelectorAll(){return fields;}}});
  const state=c.wxsAction('processing_status',{});assert.equal(state.text,'결재올림 확인');
  fields[0].checked=true;assert.throws(()=>c.wxsAction('processing_click',{expected:state}),/changed/);assert.equal(clicked,0);
  const posting=c.wxsAction('processing_status',{});assert.throws(()=>c.wxsAction('processing_click',{expected:posting}),/posting/);
  fields[0].checked=false;const current=c.wxsAction('processing_status',{}),serialized=JSON.stringify(current);
  vm.runInContext('Array.prototype.toJSON=function(){return "legacy-array";};',c);
  const expected=vm.runInContext('JSON.parse('+JSON.stringify(serialized)+')',c);
  const proof=c.wxsAction('processing_preflight',{expected});assert.equal(proof.exact_state,true);assert.equal(proof.legacy_gate_passed,false);
  c.wxsAction('processing_click',{expected});c.flush();assert.equal(clicked,1);
});
test('temporary save calls only the temporary-save handler', () => {
  let opened=0,saved=0;const input={value:''};const c=ctx({rInfo:{appType:'sancgian'},fncSaveTmpr(){opened++;},fncSave(){saved++;},document:{getElementById(){return input;}}});
  c.wxsAction('open_save',{});c.flush();c.wxsAction('save_name',{name:'가상 초안'});c.flush();assert.equal(opened,1);assert.equal(saved,1);assert.equal(input.value,'가상 초안');
});
test('existing attachment repair stages verified bytes in native edit map without submitting', () => {
  const map = new Map(), files = [{FID:'synthetic-id', name:'synthetic.pdf', size:4, path:'sancbox://synthetic', atSancbox:true}];
  let checks=0;
  const c=ctx({rInfo:{appType:'sancgian',docProcessed:false}, MultiDraft:{attachMap:map}, pInfo:{},
    FileManager:{GetFile(path){checks++;assert.equal(path,'D:\\test\\synthetic.pdf');return {Size:4,DateLastModified:'2026-01-01'};}},
    Attach:{fileBox:{files(){return files;}},syncNew:function(){var aObj,oid;if(aObj && aObj.flag)hsattach.AddFlashFile(aObj.filePath, oid);}}});
  const before=c.wxsAction('attachment_staging_status',{});
  const spec={id:'synthetic-id',name:'synthetic.pdf',path:'D:\\test\\synthetic.pdf',size:4};
  assert.throws(()=>c.wxsAction('attachment_stage_replacements',{expected:[],files:[spec]}),/changed/);
  assert.equal(map.size,0);assert.equal(checks,0);
  const staged=c.wxsAction('attachment_stage_replacements',{expected:before.files,files:[spec]});
  assert.equal(staged.files[0].staged.flag,true);assert.equal(map.get('synthetic-id').filePath,spec.path);
  assert.throws(()=>c.wxsAction('attachment_stage_replacements',{expected:staged.files,files:[spec]}),/already staged/);
  assert.equal(checks,1);
});
test('standard draft registers file bytes against native object IDs after native sync, once', () => {
  const files=[],uploads=[];let nativeCalls=0;
  const attach={element:{setAttachNameByGroup(){}},appendTo(){},
    fileBox:{files(){return files;},fileListAtGroup(group){assert.equal(group,0);return files;}},
    addFiles(incoming){files.push(...incoming);},onrefresh(){},
    syncNew:function(){nativeCalls++;var file={atPc:true};if(file.atPc)this.appendTo();this.element.setAttachNameByGroup();return ['native-id'];}};
  const c=ctx({rInfo:{appType:'sancgian',applID:'2020'},Attach:attach,
    HsFile:function(path,name,size){Object.assign(this,{path,name,size,atPc:true});},
    hsattach:{AddFlashFile(path,id){uploads.push({path,id});}},FileManager:{GetFile(){return {Size:4};}}});
  c.wxsAction('attach',{path:'mock.pdf',name:'mock.pdf',size:4,expected_count:0});
  assert.equal(uploads.length,0);assert.equal(nativeCalls,0);
  attach.syncNew(null,null,null,null,null,null,false,1);
  assert.equal(nativeCalls,1);assert.deepEqual(uploads,[{path:'mock.pdf',id:'native-id'}]);
  c.FileManager.GetFile=()=>({Size:5});
  assert.throws(()=>attach.syncNew(null,null,null,null,null,null,false,1),/changed before/);
  assert.equal(nativeCalls,1);assert.equal(uploads.length,1);
});
test('standard upload adapter preserves native data-collection registration without duplicating it', () => {
  const files=[],uploads=[];
  const attach={element:{setAttachNameByGroup(){}},appendTo(){},
    fileBox:{files(){return files;},fileListAtGroup(){return files;}},addFiles(incoming){files.push(...incoming);},onrefresh(){},
    syncNew:function(){
      const ids=[];
      for(let i=0;i<files.length;i++){
        const file=files[i],id='synthetic-object-'+i;
        if(file.atPc){this.appendTo();this.element.setAttachNameByGroup();if(file.misfileid)c.hsattach.AddFlashFile(file.path,id);}
        ids.push(id);
      }
      return ids;
    }};
  const c=ctx({rInfo:{appType:'sancgian',applID:'2020'},Attach:attach,
    HsFile:function(path,name,size){Object.assign(this,{path,name,size,atPc:true});},
    hsattach:{AddFlashFile(path,id){uploads.push({path,id});}},FileManager:{GetFile(){return {Size:4};}}});
  c.wxsAction('attach',{path:'normal.pdf',name:'normal.pdf',size:4,expected_count:0});
  files.push({path:'collection.pdf',name:'collection.pdf',size:4,atPc:true,misfileid:'synthetic-collection'});
  attach.syncNew();
  assert.equal(uploads.length,2);
  assert.deepEqual(uploads.map(item=>item.path).sort(),['collection.pdf','normal.pdf']);
});
console.log(`${count} action tests passed; no real application or network used.`);
