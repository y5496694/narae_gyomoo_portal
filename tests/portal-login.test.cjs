'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {login}=require('../skills/narae-gyomu-work-portal/scripts/portal-login.cjs');
const cfg={region:'가상',portalUrl:'https://portal.test/login'};
function fixture({iframe=false,unknownOrigin=false,ambiguous=false}={}){
 const secret='SYNTHETIC_SECRET_MUST_NOT_APPEAR',profile={region:'가상',storage_type:'HardDisk',certificate_name:'가상 인증서',password:secret};
 let stage=0,frame=0,waits=0;const calls=[],portal={url:()=>cfg.portalUrl,isClosed:()=>false};
 const screen=()=>stage===0?{url:cfg.portalUrl,elements:[{ref:'l',label:'교육행정 전자서명 인증서 로그인'}]}:stage===1?{url:unknownOrigin?'https://untrusted.test/auth':cfg.portalUrl,elements:[{ref:'disk',label:'하드디스크'}]}:stage===2?{url:cfg.portalUrl,elements:[{ref:'cert',tag:iframe?'tr':'button',label:iframe?'개인 가상 인증서 유효함':'가상 인증서'},...(ambiguous?[{ref:'cert2',tag:'tr',label:'개인 가상 인증서 유효함'}]:[])]}:stage===3?{url:cfg.portalUrl,elements:[{ref:'pw',type:'password'},{ref:'ok',label:'확인'}]}:{url:'https://portal.test/main',text:'Logout',elements:[{ref:'n',label:'나이스',tag:'a'},{ref:'e',label:'K-에듀파인',tag:'a'}]};
 const browser={page:portal,context:{pages:()=>[portal]},invalidate(){},ref:ref=>{assert.equal(ref,'pw');return {locator:{evaluate:async()=>true,fill:async value=>{assert.equal(value,secret);calls.push({privateFill:true});}}};},execute:async a=>{
  calls.push(a);
  if(a.action==='frames')return {frames:[{index:0,url:cfg.portalUrl},{index:1,url:unknownOrigin?'https://untrusted.test/auth':cfg.portalUrl}]};
  if(a.action==='frame')frame=a.index;
  if(a.action==='wait'&&stage===4&&++waits===2)stage=5;
  if(a.action==='click'){if(a.ref==='l')stage=1;if(a.ref==='disk')stage=2;if(a.ref==='cert')stage=3;if(a.ref==='ok')stage=4;}
  if(iframe&&stage>0&&stage<4&&frame===0)return {url:cfg.portalUrl,elements:[]};
  if(stage===4)return {url:cfg.portalUrl,title:'SSO LOGIN',elements:[]};
  return screen();
 }};
 return {browser,profile,calls,secret};
}
test('DPAPI secret stays in local password input, iframe navigation and delayed SSO are observed',async()=>{
 const f=fixture({iframe:true});let reads=0;
 const result=await login({}, {cfg,browser:f.browser,state:{},readProfile:async action=>{reads++;return action==='Status'?{valid:true,certificate_path_exists:true}:f.profile;}});
 assert.equal(result.authenticated,true);assert.equal(result.complete,true);assert.equal(f.profile.password,null);assert.equal(reads,2);
 assert.equal(f.calls.filter(a=>a.action==='click'&&a.ref==='ok').length,1);assert.equal(f.calls.filter(a=>a.privateFill).length,1);
 assert(!JSON.stringify({calls:f.calls,result}).includes(f.secret));assert(!f.calls.some(a=>a.action==='fill'));
});
test('unapproved origin and ambiguous certificate cannot receive the secret or submit',async()=>{
 for(const options of [{unknownOrigin:true},{ambiguous:true,iframe:true}]){
  const f=fixture(options);const result=await login({}, {cfg,browser:f.browser,state:{},readProfile:async a=>a==='Status'?{valid:true}:f.profile});
  assert.equal(result.complete,false);assert.equal(f.profile.password,null);assert(!f.calls.some(a=>a.privateFill||a.ref==='ok'));
 }
});
test('an uncertain attempt is not reset and attached personal browsers are not used',async()=>{
 const f=fixture();f.browser.execute=async()=>({url:cfg.portalUrl,elements:[{ref:'l',label:'교육행정 전자서명 인증서 로그인'}]});const state={};
 const deps={cfg,browser:f.browser,state,readProfile:async a=>a==='Status'?{valid:true}:f.profile};
 assert.equal((await login({},deps)).complete,false);assert.equal((await login({},deps)).stage,'manual_login_required');
 f.browser.attached=true;assert.equal((await login({},deps)).stage,'dedicated_browser_required');
});

test('a service product title cannot turn a permission or error page into verified login',async()=>{
 for(const text of ['다른 앱 및 서비스 접근 허용','접속 실패 오류코드 1005','페이지가 작동하지 않습니다. HTTP ERROR 500']){
  const portal={isClosed:()=>false},popup={isClosed:()=>false};let screen={url:'https://portal.test/main',text:'로그아웃',elements:[{ref:'n',tag:'a',label:'나이스'}]};
  const browser={page:portal,invalidate(){},execute:async a=>{if(a.action==='click'){browser.page=popup;screen={url:'https://neis.test/main',title:'나이스',text,elements:[{label:'확인'}]};}return screen;}};
  const result=await login({systems:['neis']},{cfg,browser});
  assert.equal(result.authenticated,true);assert.equal(result.complete,false);assert.equal(result.systems.neis,false);
  if(text.includes('HTTP ERROR')){assert.equal(result.observations.neis.httpStatus,500);assert.equal(result.observations.neis.errorPage,true);assert.match(result.message,/인증은 완료.*HTTP 500/);}
 }
});

test('a current server login screen takes precedence over an older main tab',async()=>{
 const f=fixture(),actual=f.browser.page,stale={url:()=> 'https://portal.test/main',isClosed:()=>false},execute=f.browser.execute;let reads=0;
 f.browser.context.pages=()=>[stale,actual];f.browser.execute=async a=>f.browser.page===stale?{url:stale.url(),text:'Logout',elements:[{label:'나이스'}]}:execute(a);
 const result=await login({}, {cfg,browser:f.browser,state:{},readProfile:async a=>{reads++;return a==='Status'?{valid:true}:f.profile;}});
 assert.equal(result.authenticated,true);assert.equal(reads,2);assert.equal(f.calls.filter(a=>a.privateFill).length,1);assert.equal(f.browser.page,actual);
});
test('a notification category with the system name is not a service launch link',async()=>{
 const calls=[],screen={url:'https://portal.test/main',text:'Logout',elements:[{label:'나이스'},{label:'K-에듀파인',tag:'a',id:'2',href:'javascript:void(0)',ref:'filter'}]},browser={execute:async a=>{calls.push(a);return screen;}};
 const result=await login({systems:['edufine']},{cfg,browser});assert.equal(result.complete,false);assert.equal(result.stage,'system_link_unconfirmed');assert(!calls.some(a=>a.action==='click'));
});

test('an observed informational notice is dismissed before reading credentials',async()=>{
 const f=fixture(),execute=f.browser.execute;let notice=true,reads=0;
 f.browser.execute=async a=>{if(a.action==='click'&&a.ref==='notice-close'){notice=false;f.calls.push(a);return execute({action:'snapshot'});}return notice?{url:cfg.portalUrl,dialog:'서비스 이용 안내',elements:[{ref:'notice-close',label:'전체닫기'}]}:execute(a);};
 const result=await login({}, {cfg,browser:f.browser,state:{},readProfile:async a=>{assert.equal(notice,false);reads++;return a==='Status'?{valid:true}:f.profile;}});
 assert.equal(result.complete,true);assert.equal(reads,2);assert.equal(f.calls.filter(a=>a.ref==='notice-close').length,1);
});

test('searching other portal tabs refreshes notice refs on the original page',async()=>{
 const f=fixture(),execute=f.browser.execute,original=f.browser.page,other={url:()=>cfg.portalUrl,isClosed:()=>false};let serial=0,currentRef,notice=true;
 f.browser.context.pages=()=>[original,other];
 f.browser.execute=async a=>{if(a.action==='click'&&a.ref.startsWith('notice-')){assert.equal(f.browser.page,original);assert.equal(a.ref,currentRef);notice=false;return execute({action:'snapshot'});}if(f.browser.page===other)return {url:cfg.portalUrl,text:'미인증',elements:[]};if(notice){currentRef='notice-'+ ++serial;return {url:cfg.portalUrl,dialog:'서비스 안내',elements:[{ref:currentRef,label:'전체닫기'}]};}return execute(a);};
 const result=await login({}, {cfg,browser:f.browser,state:{},readProfile:async a=>a==='Status'?{valid:true}:f.profile});assert.equal(result.complete,true);assert.equal(f.browser.page,original);
});

test('local certificate access is opt-in, dedicated and scoped to the configured HTTPS portal',async()=>{
 const f=fixture(),grants=[];f.browser.context.grantPermissions=async(...args)=>grants.push(args);
 const deps={cfg,browser:f.browser,state:{},readProfile:async a=>a==='Status'?{valid:true}:f.profile};
 await login({},deps);assert.equal(grants.length,0);
 await login({allow_local_access:true},deps);assert.deepEqual(grants,[[['local-network-access'],{origin:'https://portal.test'}]]);
 f.browser.attached=true;await login({allow_local_access:true},deps);assert.equal(grants.length,1);
});
