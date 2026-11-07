'use strict';
const reviewTime = t => t ? new Date(t).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}) : '—';

function drawReviewRows(target, items, getValues, resource, colCount) {
  const tbody = document.getElementById(target);
  tbody.replaceChildren();
  if (!items.length) {
    const row = tbody.insertRow();
    const cell = row.insertCell(); cell.colSpan=colCount; cell.textContent='沒有符合條件的紀錄';
    return;
  }
  for (const item of items) {
    const row = tbody.insertRow();
    for (const value of getValues(item)) row.insertCell().textContent=String(value ?? '—');
    const cell = row.insertCell();
    const link = document.createElement('a');
    link.className='btn btn-sm btn-outline-primary'; link.textContent='查看紀錄';
    link.href=`/manage/${resource}?q=${encodeURIComponent(item.plate_no)}`;
    link.setAttribute('aria-label',`查看 ${item.plate_no} 的相關紀錄`);
    cell.append(link);
  }
}
async function loadReview() {
  const value=document.getElementById('reviewAt').value;
  if (!value) return;
  try {
    const params=new URLSearchParams({as_of:`${value}:00+08:00`});
    const result=await requestJSON(`/management/pending?${params}`);
    const data=result.data;
    document.getElementById('reviewNote').textContent=`歷史查詢時間：${reviewTime(data.as_of)}。每類最多顯示 50 筆；僅供查看，不會自動修改或催繳。點選查看紀錄後，將以車牌搜尋相關資料。`;
    document.getElementById('cPermits').textContent=data.unpaid_permits.length;
    document.getElementById('cRecords').textContent=data.unpaid_records.length;
    document.getElementById('cLong').textContent=data.long_stays.length;
    drawReviewRows('unpaidPermits',data.unpaid_permits,r=>[r.plate_no,r.name,r.academic_year,`${r.permit_fee} 元`,r.permit_id],'parking-permits',6);
    drawReviewRows('unpaidRecords',data.unpaid_records,r=>[r.plate_no,r.area_name,reviewTime(r.exit_time),`${r.parking_fee} 元`,r.record_id],'parking-records',6);
    drawReviewRows('longStays',data.long_stays,r=>[r.plate_no,r.area_name,reviewTime(r.entry_time),`${r.parked_hours} 小時`,r.record_id],'parking-records',6);
  } catch(e) {notify(`異常紀錄查詢失敗：${e.message}`,true);}
}
document.getElementById('reviewForm').addEventListener('submit',e=>{e.preventDefault();loadReview();});
loadReview();
