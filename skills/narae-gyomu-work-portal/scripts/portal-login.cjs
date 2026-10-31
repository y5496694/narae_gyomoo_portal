'use strict';
const fs=require('node:fs'),path=require('node:path'),{execFile}=require('node:child_process');
const tool={type:'function',name:'gyomu_portal_login',description:'PC의 DPAPI 보안 문서로 업무포털 자동 로그인을 한 번 시도하고 요청한 나이스·에듀파인 진입을 실제 화면으로 확인한다. 비밀값은 모델·로그에 반환하지 않는다. 최초 로컬 접근 승인과 WXS 추가 보안문서 인증은 사용자 단계로 남긴다.',parameters:{type:'object',properties:{operation:{enum:['status','login']},systems:{type:'array',items:{enum:['neis','edufine']},uniqueItems:true}},required:['operation'],additionalProperties:false}};
const helper=path.join(__dirname,'certificate-profile.ps1');
function config(home){const file=path.join(home,'data/school-profile.json'),defaults={region:'충북',portalUrl:'https://cbe.eduptl.kr/bpm_lgn_lg00_001.do'};return {...defaults,...(fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{})};}
function configure(home,value){
 if(!value||Array.isArray(value)||Object.keys(value).some(k=>!['region','portalUrl','credentialsPath','certificateOrigins'].includes(k)))throw new Error('region, portalUrl, credentialsPath, certificateOrigins만 설정할 수 있습니다. 암호는 DPAPI 보안 문서로 등록하세요.');
 if(!value.region?.trim()||!value.portalUrl)throw new Error('교육청 지역과 확인된 업무포털 주소가 필요합니다.');
 const url=new URL(value.portalUrl);if(url.protocol!=='https:'||url.username||url.password)throw new Error('인증정보 없는 HTTPS 업무포털 주소가 필요합니다.');
 if(value.credentialsPath&&(!path.isAbsolute(value.credentialsPath)||!fs.existsSync(value.credentialsPath)||path.extname(value.credentialsPath).toLowerCase()!=='.clixml'))throw new Error('기존 DPAPI CLIXML 보안 문서의 절대 경로를 지정하세요.');
 if(value.certificateOrigins&&(!Array.isArray(value.certificateOrigins)||value.certificateOrigins.some(o=>{try{const u=new URL(o);return u.protocol!=='https:'||u.origin!==o;}catch{return true;}})))throw new Error('인증서 출처는 확인한 HTTPS origin 문자열 배열이어야 합니다.');
 const file=path.join(home,'data/school-profile.json');fs.mkdirSync(path.dirname(file),{recursive:true});if(fs.existsSync(file)){const backup=path.join(home,'backups','school-profile-'+Date.now()+'.json');fs.mkdirSync(path.dirname(backup),{recursive:true});fs.copyFileSync(file,backup);}fs.writeFileSync(file,JSON.stringify(value,null,2));return {configured:true,region:value.region,customCredentials:Boolean(value.credentialsPath),certificateOriginsConfigured:Boolean(value.certificateOrigins?.length)};
}
function loadProfile(action,cfg,signal){return new Promise((resolve,reject)=>{execFile('powershell.exe',['-NoProfile','-NonInteractive','-File',helper,'-Action',action,...(cfg.credentialsPath?['-Path',cfg.credentialsPath]:[])],{windowsHide:true,encoding:'utf8',maxBuffer:65536,timeout:15000,signal},(error,stdout)=>{if(error)return reject(new Error('로컬 보안 문서를 읽을 수 없습니다. 현재 Windows 계정·DPAPI 등록 상태를 확인하세요.'));try{resolve(JSON.parse(stdout.replace(/^\uFEFF/,'')));}catch{reject(new Error('로컬 보안 문서 응답을 확인할 수 없습니다.'));}});});}
function origin(url){try{return new URL(url).origin;}catch{return '';}}
const normalized=s=>String(s||'').replace(/\s/g,'');
const logged=s=>/로그아웃|Logout/i.test(s?.text||'')&&s?.elements?.some(e=>/^(나이스|K-에듀파인)(?:\s|$|\()/.test(e.label));
const controls='button,a,input,select,[role=button],[role=tab],[role=row],[role=gridcell],label,tr';
async function observe(browser){return browser.execute({action:'snapshot',selector:controls,limit:100,chars:8000});}
async function settle(browser,test,signal,tries=12){
 let screen=await observe(browser);
 for(let i=0;i<tries&&!test(screen);i++){if(signal?.aborted)throw Error('로그인을 중단했습니다.');await browser.execute({action:'wait',ms:350});screen=await observe(browser);}
 return screen;
}
async function authenticatedPortal(browser,portalOrigin,signal){
 for(let attempt=0;attempt<24;attempt++){
  for(const page of browser.context?.pages?.()||[browser.page]){
   if(page?.isClosed?.()||page?.url&&origin(page.url())!==portalOrigin)continue;
   if(page){browser.page=page;browser.frame=null;browser.invalidate?.();}
   const screen=await observe(browser);if(logged(screen))return screen;
  }
  if(signal?.aborted)throw Error('로그인을 중단했습니다.');await browser.execute({action:'wait',ms:350});
 }
 return observe(browser);
}
async function authenticationScreen(browser,allowed,profile,signal){
 const useful=s=>s.elements?.some(e=>e.type==='password'||/하드디스크|이동식 디스크/.test(e.label)||normalized(e.label).includes(normalized(profile.certificate_name)));
 let screen=await observe(browser);if(useful(screen)&&allowed.has(origin(screen.url)))return screen;
 for(let attempt=0;attempt<8;attempt++){
  const pages=browser.context?.pages?.()||[browser.page];
  for(const page of pages){
   if(page?.isClosed?.())continue;
   if(page&&browser.page!==page){browser.page=page;browser.frame=null;browser.invalidate?.();}
   const frames=await browser.execute({action:'frames'});
   for(const frame of frames.frames||[]){
    if(!allowed.has(origin(frame.url)))continue;
    screen=await browser.execute({action:'frame',index:frame.index});screen=await observe(browser);
    if(useful(screen))return screen;
   }
  }
  if(signal?.aborted)throw Error('로그인을 중단했습니다.');await browser.execute({action:'wait',ms:350});
 }
 return screen;
}
function certificateCandidates(screen,label,certificate=false){
 const candidates=(screen.elements||[]).filter(e=>!e.disabled&&normalized(e.label)===normalized(label));if(candidates.length)return candidates;
 return certificate?(screen.elements||[]).filter(e=>!e.disabled&&(e.role==='row'||e.tag==='tr')&&normalized(e.label).includes(normalized(label))):[];
}
async function login({systems=[]},{cfg,browser,readProfile=loadProfile,state={},signal}){
 const portalOrigin=origin(cfg.portalUrl);if(!portalOrigin.startsWith('https://'))throw new Error('확인된 HTTPS 업무포털 주소가 필요합니다.');
 if(browser.attached)return {authenticated:false,complete:false,stage:'dedicated_browser_required',message:'등록된 인증서는 독립 업무 브라우저에서 로그인합니다.'};
 let screen=await observe(browser),profile;
 const stop=(stage,message)=>({authenticated:false,complete:false,stage,message,systems:{neis:false,edufine:false}});
 try{
  if(!logged(screen))for(const page of browser.context?.pages?.()||[]){if(page.isClosed()||origin(page.url())!==portalOrigin)continue;browser.page=page;browser.frame=null;browser.invalidate();const candidate=await browser.execute({action:'snapshot'});if(logged(candidate)){screen=candidate;break;}}
  if(!logged(screen)){
   if(state.attempted)return stop('manual_login_required','이 세션의 자동 로그인은 이미 한 번 시도했습니다. 직접 로그인 후 현재 화면을 다시 확인하세요.');
   if(origin(screen.url)!==portalOrigin)screen=await browser.execute({action:'open',url:cfg.portalUrl});
   screen=await settle(browser,s=>logged(s)||(s.elements||[]).some(e=>/교육행정.*전자서명.*인증서.*로그인/.test(e.label)),signal);
   if(logged(screen))return login({systems},{cfg,browser,readProfile,state,signal});
   const certButton=screen.elements?.filter(e=>!e.disabled&&/교육행정.*전자서명.*인증서.*로그인/.test(e.label));
   if(certButton?.length!==1)return stop('certificate_button_unconfirmed','인증서 로그인 버튼을 유일하게 확인하지 못했습니다. 현재 창에서 직접 로그인하세요.');
   const status=await readProfile('Status',cfg,signal);if(!status.valid||status.certificate_path_exists===false)return stop('profile_required','등록된 보안 문서와 인증서 위치를 먼저 확인해야 합니다.');
   profile=await readProfile('ReadForBrowser',cfg,signal);
   if(profile.region!==cfg.region)return stop('region_mismatch','보안 문서와 업무포털 교육청 설정이 다릅니다.');
   state.attempted=true;
   screen=await browser.execute({action:'click',ref:certButton[0].ref});
   const allowed=new Set([portalOrigin,...(cfg.certificateOrigins||[])]),selected=new Set();
   screen=await authenticationScreen(browser,allowed,profile,signal);
   for(let step=0;step<12;step++){
    if(signal?.aborted)throw new Error('로그인을 중단했습니다.');
    if(logged(screen))break;
    if(!allowed.has(origin(screen.url)))return stop('certificate_origin_unconfirmed','현재 인증서 화면의 출처를 등록된 주소와 대조하지 못했습니다. 직접 로그인하세요.');
    if(/다른 앱 및 서비스|로컬 네트워크.*(?:허용|액세스)/.test(screen.text||''))return stop('first_use_permission','최초 기기·로컬 앱 접근 승인은 사용자가 이 창에서 직접 완료해야 합니다.');
    const labels=[profile.storage_type==='Removable'?'이동식 디스크':'하드디스크',...(profile.storage_type==='Removable'?[profile.disk_label||profile.disk_drive]:[]),profile.storage_name,profile.certificate_name].filter(Boolean);
    const next=labels.find(label=>!selected.has(label)&&certificateCandidates(screen,label,label===profile.certificate_name).length);
    if(next){const candidates=certificateCandidates(screen,next,next===profile.certificate_name);if(candidates.length!==1)return stop('ambiguous_certificate','등록된 인증서·저장소를 유일하게 구분하지 못했습니다.');selected.add(next);await browser.execute({action:'click',ref:candidates[0].ref});screen=await authenticationScreen(browser,allowed,profile,signal);continue;}
    const password=screen.elements?.filter(e=>e.type==='password'&&!e.disabled);
    if(password?.length===1&&selected.has(profile.certificate_name)){
     const observed=browser.ref(password[0].ref);const valid=await observed.locator.evaluate(e=>e.type==='password');if(!valid)return stop('password_field_changed','인증서 암호 입력란이 바뀌었습니다. 자동 재시도하지 않습니다.');
     // This is the only credential input path: no model argument, output,
     // clipboard, screenshots, general browser fill or shell command text.
     try{await observed.locator.fill(profile.password,{timeout:10000});}catch{return stop('password_input_unconfirmed','암호 입력 결과를 확인하지 못했습니다. 직접 로그인하세요.');}finally{profile.password=null;}
     screen=await observe(browser);if(!allowed.has(origin(screen.url)))return stop('certificate_origin_unconfirmed','인증서 확인 직전 출처가 바뀌어 제출하지 않았습니다.');
     const confirm=screen.elements.filter(e=>!e.disabled&&/^(확인|로그인)$/.test(e.label));if(confirm.length!==1)return stop('confirmation_unconfirmed','로그인 확인 버튼이 유일하지 않습니다. 암호 입력 이후 재시도하지 않습니다.');
     state.submitted=true;
     try{await browser.execute({action:'click',ref:confirm[0].ref});}catch{state.clickResultUnconfirmed=true;}
     try{browser.frame=null;screen=await authenticatedPortal(browser,portalOrigin,signal);}catch{return stop('login_result_unknown','자동 로그인 제출 후 결과를 확인하지 못했습니다. 직접 로그인으로 이어가세요.');}
     if(!logged(screen))return stop('login_result_unknown','자동 로그인 제출 후 로그인된 업무포털 화면을 확인하지 못했습니다. 자동 제출은 반복하지 않습니다.');
     break;
    }
    return stop('user_authentication_required','지원되는 브라우저 인증서 선택·암호 화면을 확인하지 못했습니다. 현재 인증창을 보존하고 직접 로그인하세요.');
   }
  }
  if(!logged(screen))return stop('portal_unconfirmed','로그인된 업무포털을 확인하지 못했습니다.');
  const result={authenticated:true,complete:true,stage:'portal_authenticated',systems:{neis:false,edufine:false},observations:{}};
  for(const system of systems){
   screen=await observe(browser);const label=system==='neis'?'나이스':'K-에듀파인',matches=screen.elements?.filter(e=>!e.disabled&&normalized(e.label).replace(/\(새창열림\)$/,'')===label),link=matches?.filter(e=>e.role==='link'||e.tag==='a');
   const targets=(link?.length?link:matches)||[],urlTargets=targets.filter(e=>/^https?:\/\//.test(e.id||''));
   const links=urlTargets.length?urlTargets:targets;
   if(links?.length!==1){result.complete=false;result.stage='system_link_unconfirmed';continue;}
   const portal=browser.page;let entered;
   const product=title=>system==='neis'?/나이스|NEIS/i.test(title||''):/K-에듀파인/.test(title||'');
   for(const page of browser.context?.pages?.()||[]){if(page.isClosed()||page===portal||origin(page.url())===portalOrigin)continue;const title=await page.title();if(product(title)&&!/로그인|SSO LOGIN/i.test(title)){browser.page=page;browser.frame=null;browser.invalidate();entered=await browser.execute({action:'snapshot'});break;}}
   if(!entered){entered=await browser.execute({action:'click',ref:links[0].ref});for(let attempt=0;attempt<12;attempt++){
    for(const page of browser.context?.pages?.()||[]){if(page.isClosed()||page===portal)continue;const title=await page.title();if(product(title)&&!/로그인|SSO LOGIN/i.test(title)){browser.page=page;browser.frame=null;browser.invalidate?.();entered=await observe(browser);break;}}
    if(product(entered.title)&&entered.elements?.length)break;await browser.execute({action:'wait',ms:350});entered=await observe(browser);
   }}
   if(!entered.elements?.length){const frames=await browser.execute({action:'frames'});for(const frame of frames.frames||[]){if(!frame.index||/websocket|webReport|내용없음/i.test(frame.name||''))continue;const candidate=await browser.execute({action:'frame',index:frame.index});if(candidate.elements?.length){entered={...candidate,title:product(candidate.title)?candidate.title:entered.title};break;}}}
   const correct=system==='neis'?/나이스|NEIS/i.test(entered.title||''):/K-에듀파인/.test(entered.title||'');
   result.observations[system]={productTitle:correct,loginTitle:/로그인|SSO LOGIN/i.test(entered.title||''),samePortalOrigin:origin(entered.url)===portalOrigin,controls:entered.elements?.length||0,frames:entered.frames?.length||0,permissionRequired:/다른 앱 및 서비스|로컬 네트워크.*(?:허용|액세스)/.test(entered.text||''),errorPage:/오류|오류코드|접속.*실패|1005/.test(entered.text||'')};
   const evidence=result.observations[system];
   result.systems[system]=Boolean(correct&&!evidence.loginTitle&&!evidence.permissionRequired&&!evidence.errorPage&&entered.elements?.length&&origin(entered.url)!==portalOrigin);
   if(!result.systems[system]){result.complete=false;result.stage='system_screen_unconfirmed';}
   if(browser.page!==portal&&!portal.isClosed()){browser.page=portal;browser.frame=null;browser.invalidate();}
   else if(origin(entered.url)!==portalOrigin){result.complete=false;result.stage='portal_navigation_changed';break;}
  }
  if(result.complete)result.stage='verified';return result;
 }finally{if(profile){profile.password=null;profile=null;}}
}
module.exports={tool,config,configure,loadProfile,login,logged};
