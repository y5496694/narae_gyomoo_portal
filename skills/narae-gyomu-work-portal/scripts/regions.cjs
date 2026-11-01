'use strict';
// Addresses: vendor's maintained education-system support directory, checked
// 2026-11-01. Chungbuk and Gyeonggi are also cross-checked against board guides.
const sources={directory:'https://www.blsoft.co.kr/menu7/index.html?pg=neis-address',chungbuk:'https://www.cbe.go.kr/cbe/cm/cntnts/cntntsView.do?cntntsId=35660&mi=11772',gyeonggi:'https://goeia.go.kr/flexer/html/UPLOAD/BBS/B29/%28%EB%B0%B0%ED%8F%AC%EC%9A%A9%292024%20%ED%95%99%EB%85%84%EC%B4%88%20%EB%82%98%EC%9D%B4%EC%8A%A4%20%EC%82%AC%EC%9A%A9%EC%9E%90%20%EC%97%B0%EC%88%98%EB%AC%BC%2820240216%EC%88%98%EC%A0%95%29_hwp_files/Sections1.html'};
const definitions=[
 ['sen','서울','서울특별시교육청'],['pen','부산','부산광역시교육청'],['dge','대구','대구광역시교육청'],['ice','인천','인천광역시교육청'],['gen','광주','광주광역시교육청'],['dje','대전','대전광역시교육청'],['use','울산','울산광역시교육청'],['sje','세종','세종특별자치시교육청'],['goe','경기','경기도교육청'],['kwe','강원','강원특별자치도교육청'],['cbe','충북','충청북도교육청'],['cne','충남','충청남도교육청'],['jbe','전북','전북특별자치도교육청'],['jne','전남','전라남도교육청'],['gbe','경북','경상북도교육청'],['gne','경남','경상남도교육청'],['jje','제주','제주특별자치도교육청']
];
const regions=definitions.map(([id,region,label])=>Object.freeze({id,region,label,portalUrl:`https://${id}.eduptl.kr/bpm_lgn_lg00_001.do`,neisUrl:`https://${id}.neis.go.kr/`,edufineUrl:`https://klef.${id}.go.kr/`,evpnUrl:`https://evpn.${id==='gbe'?'gbe.kr':id+'.go.kr'}/`,sources:[sources.directory,...(id==='cbe'?[sources.chungbuk]:id==='goe'?[sources.gyeonggi]:[])],addressChecked:'2026-11-01',liveTested:id==='cbe'}));
function resolve(value){const region=regions.find(r=>[r.id,r.region,r.label,r.label.replace('특별자치',''),r.label.replace('특별자치도','도')].includes(String(value||'').trim()));if(!region)throw new Error('17개 시도교육청 중 지역을 선택하세요.');return region;}
function portalHost(host){return regions.some(r=>new URL(r.portalUrl).hostname===host);}
function edufineHost(host){return regions.some(r=>new URL(r.edufineUrl).hostname===host);}
module.exports={regions,resolve,portalHost,edufineHost};
