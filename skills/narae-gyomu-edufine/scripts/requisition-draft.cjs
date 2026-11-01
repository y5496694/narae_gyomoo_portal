'use strict';
const {createHash}=require('node:crypto');
const fingerprint=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
function day(value,label){if(value===undefined||typeof value==='string'&&!value.trim())return undefined;const parsed=typeof value==='string'?new Date(value+'T00:00:00Z'):null;if(typeof value!=='string'||!/^20\d{2}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(parsed.getTime())||parsed.toISOString().slice(0,10)!==value)throw Error(label+'는 실제 YYYY-MM-DD 날짜여야 합니다.');return value;}
function text(value,label,max=4000){if(value===undefined||typeof value==='string'&&!value.trim())return undefined;if(typeof value!=='string'||value.length>max)throw Error(label+'의 내용을 확인하세요.');return value.trim();}
const optionalText=(value,label,max)=>text(value,label,max)??'';
function integer(value,label){if(!/^(?:0|[1-9]\d*)$/.test(String(value))||!Number.isSafeInteger(Number(value)))throw Error(label+'는 원 단위의 0 이상 정수여야 합니다.');return BigInt(value);}
function itemAmount(quantity,unitPrice){const match=String(quantity).match(/^(0|[1-9]\d*)(?:\.(\d{1,6}))?$/);if(!match)throw Error('수량은 소수점 여섯 자리 이내의 양수여야 합니다.');const scale=10n**BigInt(match[2]?.length||0),q=BigInt(match[1]+(match[2]||''));if(q<=0n)throw Error('수량은 양수여야 합니다.');const n=q*integer(unitPrice,'예산단가');if(n%scale!==0n)throw Error('소수 원 금액을 임의 반올림할 수 없습니다. 수량·단가·확정금액을 확인하세요.');const result=n/scale;if(result>BigInt(Number.MAX_SAFE_INTEGER))throw Error('금액 범위를 초과했습니다.');return Number(result);}
function prepareDraft(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input))throw Error('품의 작성안 객체가 필요합니다.');
 const draft={title:text(input.title,'제목',500),overview:text(input.overview,'개요'),requestDate:day(input.requestDate,'요구일자'),completionDate:day(input.completionDate,'완료요구일자')},missing=[];
 for(const key of ['title','overview','requestDate','completionDate'])if(draft[key]===undefined)missing.push(key);
 if(draft.requestDate&&draft.completionDate&&draft.requestDate>draft.completionDate)throw Error('완료요구일자는 요구일자보다 앞설 수 없습니다.');
 if(input.items!==undefined&&(!Array.isArray(input.items)||input.items.length>100))throw Error('품목 배열은 100개 이내로 지정하세요.');
 draft.items=(input.items||[]).map((i,index)=>{if(!i||typeof i!=='object'||Array.isArray(i))throw Error('품목 객체가 필요합니다.');const amount=itemAmount(i.quantity,i.unitPrice);if(i.amount!==undefined&&integer(i.amount,'품목 금액')!==BigInt(amount))throw Error((index+1)+'번째 품목의 수량×단가와 금액이 다릅니다.');const name=text(i.name,'품목 내용',500);if(name===undefined)throw Error('품목 내용이 필요합니다.');return {name,specification:optionalText(i.specification,'규격',500),unit:optionalText(i.unit,'단위',50),quantity:String(i.quantity),unitPrice:Number(integer(i.unitPrice,'예산단가')),amount};});
 if(!draft.items.length)missing.push('items');
 const total=draft.items.reduce((sum,i)=>sum+BigInt(i.amount),0n);if(total>BigInt(Number.MAX_SAFE_INTEGER))throw Error('총금액 범위를 초과했습니다.');draft.total=Number(total);
 if(input.total!==undefined&&integer(input.total,'총금액')!==total)throw Error('지정한 총금액과 품목 합계가 다릅니다.');
 draft.budget=text(input.budget,'예산 항목',500);
 if(!draft.budget)missing.push('budget');
 return {draft,missing,arithmeticVerified:draft.items.length>0,digest:fingerprint(draft),saved:false,submitted:false,budgetSelected:false,remaining:['현재 권한의 실제 예산 선택과 가용액 확인','품목·첨부의 실제 입력 및 대조','명시한 저장 단계와 결재요청의 각각의 결과 확인']};
}
module.exports={prepareDraft,itemAmount,fingerprint};
