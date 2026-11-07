'use strict';
const charts = {};
const labels = {STUDENT:'學生',FACULTY:'教師',STAFF:'行政人員',VISITOR:'校外訪客'};
const colors = {term:'#376caa',summer:'#38a095',CAR:'#376caa',MOTORCYCLE:'#d49a45'};
function qparams() {
  const params = new URLSearchParams();
  for (const [key,id] of [['vehicle_type','vehicleType'],['start_date','startDate'],['end_date','endDate']]) {
    const v = document.getElementById(id).value;
    if (v) params.set(key,v);
  }
  return '?' + params.toString();
}
function number(n) {return Number(n||0).toLocaleString('zh-TW');}
function draw(id,type,items,datasets,horizontal=false,percent=false) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type, data:{labels:items,datasets}, options:{responsive:true,maintainAspectRatio:false,indexAxis:horizontal?'y':'x',
      plugins:{legend:{display:datasets.length>1,position:'bottom'}},
      scales:{y:{beginAtZero:true,ticks:{precision:percent?1:0}},x:{ticks:{maxRotation:45,minRotation:0}}}}
  });
}
function dataset(label,data,color) {return {label,data,backgroundColor:color,borderColor:color,borderWidth:2,borderRadius:3,tension:.25};}
function renderOccupancy(data) {
  const host=document.getElementById('occupancyList');host.replaceChildren();
  document.getElementById('snapshotSummary').textContent = `快照：${new Date(data.at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false})}，共 ${number(data.total_occupied)} 台在場`;
  for (const item of [...data.areas].sort((a,b)=>b.occupancy_rate-a.occupancy_rate).slice(0,12)) {
    const wrap=document.createElement('div');wrap.className='col-md-6 col-xl-4';
    const label=document.createElement('div');label.className='d-flex justify-content-between align-items-center mb-2 occ-title';
    const name=document.createElement('span');name.textContent=item.area_name;
    const val=document.createElement('span');val.textContent=`${item.occupied}/${item.capacity} (${item.occupancy_rate}%)`;
    label.append(name,val);
    const progress=document.createElement('div'); progress.className='progress occ-bar';
    const bar=document.createElement('div');bar.className=`progress-bar ${item.occupancy_rate>=90?'bg-danger':item.occupancy_rate>=75?'bg-warning':'bg-primary'}`;
    bar.style.width=`${Math.min(item.occupancy_rate,100)}%`;
    bar.setAttribute('role','progressbar');bar.setAttribute('aria-valuenow',item.occupancy_rate);
    bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');
    progress.append(bar);wrap.append(label,progress);host.append(wrap);
  }
}
async function loadSnapshot() {
  try {
    const val=document.getElementById('snapshotAt').value;
    if (!val) return;
    const p=new URLSearchParams({at:`${val}:00+08:00`});
    const vt=document.getElementById('vehicleType').value;if(vt)p.set('vehicle_type',vt);
    renderOccupancy((await requestJSON(`/analytics/occupancy-at?${p.toString()}`)).data);
  } catch(e) {notify(`快照查詢失敗：${e.message}`,true);}
}
async function loadDashboard() {
  const start=document.getElementById('startDate').value,end=document.getElementById('endDate').value;
  if (start && end && start>end) {notify('開始日期不得晚於結束日期',true);return;}
  try {
    const p=qparams();
    const names=['overview','daily-trend','by-identity','area-utilization','by-hour-phase'];
    const results=await Promise.all(names.map(n=>requestJSON(`/analytics/${n}${p}`)));
    const d=Object.fromEntries(names.map((n,i)=>[n,results[i].data]));
    document.getElementById('m-total').textContent=number(d.overview.total_records);
    const plateCount=d['by-identity'].reduce((s,r)=>s+r.distinct_plates,0);
    // Distinct plates may appear under two groups only if vehicle registration changed;
    // this Miniworld never transfers registrations, so the group sum is valid here.
    document.getElementById('m-plates').textContent=number(plateCount);
    document.getElementById('m-duration').textContent=`${(d.overview.avg_duration_minutes/60).toFixed(1)} h`;
    const peaks=[...d['area-utilization']].sort((a,b)=>b.peak_rate-a.peak_rate);
    document.getElementById('m-peak').textContent=peaks.length?`${peaks[0].peak_rate}%`:'—';
    const daily=d['daily-trend'];
    draw('chartDaily','bar',daily.map(r=>r.date.slice(5)),[
      dataset('學期間',daily.map(r=>r.phase==='TERM'?r.count:0),colors.term),
      dataset('暑假',daily.map(r=>r.phase==='SUMMER'?r.count:0),colors.summer)]);
    const all=['STUDENT','FACULTY','STAFF','VISITOR'];
    draw('chartIdentity','bar',all.map(r=>labels[r]),[
      dataset('汽車',all.map(identity=>d['by-identity'].find(r=>r.identity_type===identity&&r.vehicle_type==='CAR')?.trips||0),colors.CAR),
      dataset('機車',all.map(identity=>d['by-identity'].find(r=>r.identity_type===identity&&r.vehicle_type==='MOTORCYCLE')?.trips||0),colors.MOTORCYCLE)]);
    const summary=document.getElementById('identitySummary');summary.replaceChildren();
    const table=document.createElement('table');table.className='table table-sm mb-0';
    const thead=table.createTHead(),th=thead.insertRow();
    for(const name of ['身分','車次','車牌數','平均停留'])th.insertCell().textContent=name;
    const tbody=table.createTBody();
    for(const identity of all){
      const parts=d['by-identity'].filter(r=>r.identity_type===identity);
      const trips=parts.reduce((n,r)=>n+r.trips,0), plates=parts.reduce((n,r)=>n+r.distinct_plates,0);
      const closed=parts.reduce((n,r)=>n+r.closed_trips,0);
      const avg=closed?parts.reduce((n,r)=>n+r.avg_duration_hours*r.closed_trips,0)/closed:0;
      const tr=tbody.insertRow();for(const value of [labels[identity],number(trips),number(plates),`${avg.toFixed(1)} h`])tr.insertCell().textContent=value;
    }
    summary.append(table);
    const top=peaks.slice(0,10);
    draw('chartPeak','bar',top.map(r=>r.area_name),[
      dataset('最高占用率 (%)',top.map(r=>r.peak_rate),colors.summer)],true,true);
    const hours=d['by-hour-phase'];
    draw('chartHourPhase','line',hours.map(r=>`${String(r.hour).padStart(2,'0')}:00`),[
      dataset('學期間',hours.map(r=>r.term),colors.term),
      dataset('暑假',hours.map(r=>r.summer),colors.summer)]);
    await loadSnapshot();
  } catch(e) {notify(`分析載入失敗：${e.message}`,true);}
}
document.getElementById('filters').addEventListener('submit',e=>{e.preventDefault();loadDashboard();});
document.getElementById('snapshotForm').addEventListener('submit',e=>{e.preventDefault();loadSnapshot();});
loadDashboard();
