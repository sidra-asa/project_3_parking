'use strict';
const fmtDt=t=>t?new Date(t).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}):'尚未離場';
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
async function load(){try{const d=(await requestJSON(`/campus-users/${PROFILE_USER_ID}/profile`)).data;
 document.getElementById('personTitle').textContent=`${d.user.name}（ID ${d.user.user_id}）`;
 const names={STUDENT:'學生',FACULTY:'教師',STAFF:'行政人員'};
 document.getElementById('personMeta').textContent=`${names[d.user.identity_type]||d.user.identity_type} · ${d.user.department}`;
 document.getElementById('profileTrips').textContent=d.total_records.toLocaleString('zh-TW');
 document.getElementById('profileHours').textContent=`${d.total_hours} 小時`;
 document.getElementById('profileArea').textContent=d.favorite_area||'無紀錄';
 const host=document.getElementById('vehicleCards');host.replaceChildren();
 if(!d.vehicles.length)host.append(node('p','text-secondary','沒有登記車輛'));
 for(const v of d.vehicles){const wrap=node('div','col-md-6');const card=node('div','border rounded-3 p-3 h-100');
 card.append(node('h3','h6 fw-bold',`${v.plate_no} · ${v.vehicle_type==='CAR'?'汽車':'機車'}`));
 for(const p of v.permits){card.append(node('p','small text-secondary mb-1',`${p.academic_year} 學年度 · ${p.permit_fee} 元 · ${p.paid_at?'已付款':'未付款'}（${p.valid_from}～${p.valid_to}）`));}
 wrap.append(card);host.append(wrap);}
 const table=document.getElementById('recentRecords');table.replaceChildren();
 if(!d.recent_records.length){const tr=table.insertRow();const c=tr.insertCell();c.colSpan=5;c.textContent='目前無停車紀錄';}
 for(const r of d.recent_records){const tr=table.insertRow();for(const t of [r.plate_no,r.area_name,fmtDt(r.entry_time),fmtDt(r.exit_time),r.parking_fee==null?'未結算':`${r.parking_fee} 元`])tr.insertCell().textContent=t;}
}catch(e){notify(`載入失敗：${e.message}`,true);}}
load();
