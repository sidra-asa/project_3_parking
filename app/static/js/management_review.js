'use strict';
function fill(tbody,items,toCells,columns){const host=document.getElementById(tbody);host.replaceChildren();if(!items.length){const tr=host.insertRow(),td=tr.insertCell();td.colSpan=columns;td.textContent='沒有符合條件的紀錄';}for(const item of items){const tr=host.insertRow();for(const value of toCells(item))tr.insertCell().textContent=String(value??'—');}}
const fmt=t=>t?new Date(t).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}):'—';
async function load(){try{const val=document.getElementById('reviewAt').value;if(!val)return;const p=new URLSearchParams({as_of:`${val}:00+08:00`});const d=(await requestJSON(`/management/pending?${p}`)).data;
 document.getElementById('reviewNote').textContent=`查詢快照：${fmt(d.as_of)}。每類最多顯示前 50 筆，僅供課堂模擬。`;
 document.getElementById('cPermits').textContent=d.unpaid_permits.length;
 document.getElementById('cRecords').textContent=d.unpaid_records.length;
 document.getElementById('cLong').textContent=d.long_stays.length;
 fill('unpaidPermits',d.unpaid_permits,r=>[r.permit_id,r.plate_no,r.name,r.academic_year,`${r.permit_fee} 元`],5);
 fill('unpaidRecords',d.unpaid_records,r=>[r.record_id,r.plate_no,r.area_name,fmt(r.exit_time),`${r.parking_fee} 元`],5);
 fill('longStays',d.long_stays,r=>[r.record_id,r.plate_no,r.area_name,fmt(r.entry_time),`${r.parked_hours} h`],5);
}catch(e){notify(`待處理查詢失敗：${e.message}`,true);}}
document.getElementById('reviewForm').addEventListener('submit',e=>{e.preventDefault();load();});load();
