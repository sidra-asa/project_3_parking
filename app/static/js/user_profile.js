'use strict';
const profileTime = value => value ? new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}) : '尚未離場';
function profileNode(tag,cls,text) {const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
async function loadProfile() {
  try {
    const data=(await requestJSON(`/campus-users/${PROFILE_USER_ID}/profile`)).data;
    const identities={STUDENT:'學生',FACULTY:'教師',STAFF:'行政人員'};
    document.getElementById('personTitle').textContent=data.user.name;
    document.getElementById('personMeta').textContent=`${identities[data.user.identity_type]||data.user.identity_type} · ${data.user.department} · 人員編號 ${data.user.user_id}`;
    document.getElementById('profileTrips').textContent=data.total_records.toLocaleString('zh-TW');
    document.getElementById('profileHours').textContent=`${data.total_hours} 小時`;
    document.getElementById('profileArea').textContent=data.favorite_area||'無紀錄';
    const host=document.getElementById('vehicleCards');host.replaceChildren();
    if (!data.vehicles.length) host.append(profileNode('p','text-secondary','尚未登記車輛'));
    for (const vehicle of data.vehicles) {
      const col=profileNode('div','col-md-6');
      const card=profileNode('div','border rounded-3 p-3 h-100');
      card.append(profileNode('h3','h6 fw-bold',`${vehicle.plate_no} · ${vehicle.vehicle_type==='CAR'?'汽車':'機車'}`));
      if (!vehicle.permits.length) card.append(profileNode('p','small text-secondary mb-1','尚無學年度停車證'));
      for (const permit of vehicle.permits) {
        card.append(profileNode('p','small text-secondary mb-1',`${permit.academic_year} 學年度 · ${permit.permit_fee} 元 · ${permit.paid_at?'已付款':'未付款'}（${permit.valid_from}～${permit.valid_to}）`));
      }
      col.append(card);host.append(col);
    }
    const body=document.getElementById('recentRecords');body.replaceChildren();
    if (!data.recent_records.length) {
      const row=body.insertRow(),cell=row.insertCell();cell.colSpan=5;cell.textContent='目前沒有停車紀錄';
    }
    for (const record of data.recent_records) {
      const row=body.insertRow();
      for (const value of [record.plate_no,record.area_name,profileTime(record.entry_time),profileTime(record.exit_time),record.parking_fee==null?'未結算':`${record.parking_fee} 元`]) row.insertCell().textContent=value;
    }
  } catch(e) {notify(`人員資料載入失敗：${e.message}`,true);}
}
loadProfile();
