'use strict';
const charts = {};
const identityNames = {STUDENT:'學生', FACULTY:'教師', STAFF:'行政人員', VISITOR:'校外訪客'};
const seriesColors = {CAR:'#376caa', MOTORCYCLE:'#d49a45', TERM:'#376caa', SUMMER:'#38a095'};
let querySequence = 0;

function formatNumber(v) { return Number(v || 0).toLocaleString('zh-TW'); }
function analysisQuery() {
  const params = new URLSearchParams();
  for (const [key, id] of [['start_date','startDate'], ['end_date','endDate'], ['vehicle_type','vehicleType']]) {
    const value = document.getElementById(id).value;
    if (value) params.set(key, value);
  }
  return params.toString();
}
function drawChart(id, kind, labels, datasets, horizontal=false) {
  charts[id]?.destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type:kind,
    data:{labels, datasets},
    options:{responsive:true, maintainAspectRatio:false, indexAxis:horizontal?'y':'x',
      plugins:{legend:{display:datasets.length>1,position:'bottom'}},
      scales:{y:{beginAtZero:true, ticks:{precision:0}},x:{ticks:{maxRotation:35,minRotation:0}}}}
  });
}
function dataset(label, values, color) {
  return {label, data:values, borderColor:color, backgroundColor:color, borderWidth:2, borderRadius:3, tension:.25};
}
function drawIdentity(rows) {
  const names = Object.keys(identityNames);
  drawChart('chartIdentity','bar',names.map(n => identityNames[n]),[
    dataset('汽車',names.map(n => rows.find(r => r.identity_type===n && r.vehicle_type==='CAR')?.trips || 0),seriesColors.CAR),
    dataset('機車',names.map(n => rows.find(r => r.identity_type===n && r.vehicle_type==='MOTORCYCLE')?.trips || 0),seriesColors.MOTORCYCLE)
  ]);
  const host = document.getElementById('identitySummary');
  host.replaceChildren();
  const table = document.createElement('table'); table.className = 'table table-sm mb-0';
  const head = table.createTHead().insertRow();
  for (const text of ['身分', '進場車次', '不同車牌', '平均停放']) {
    const cell = document.createElement('th'); cell.scope = 'col'; cell.textContent = text; head.append(cell);
  }
  const body = table.createTBody();
  for (const name of names) {
    const parts = rows.filter(r => r.identity_type===name);
    const trips = parts.reduce((n,r) => n+r.trips, 0);
    const plates = parts.reduce((n,r) => n+r.distinct_plates, 0);
    const closed = parts.reduce((n,r) => n+r.closed_trips, 0);
    const hours = closed ? parts.reduce((n,r) => n+r.avg_duration_hours*r.closed_trips, 0)/closed : 0;
    const tr = body.insertRow();
    for (const text of [identityNames[name], formatNumber(trips), formatNumber(plates), `${hours.toFixed(1)} 小時`]) tr.insertCell().textContent = text;
  }
  host.append(table);
}
function drawPhase(rows) {
  drawChart('chartHourPhase','line',rows.map(r=>`${String(r.hour).padStart(2,'0')}:00`),[
    dataset('學期間（6/1–6/14）',rows.map(r=>r.term),seriesColors.TERM),
    dataset('暑假（6/15–6/28）',rows.map(r=>r.summer),seriesColors.SUMMER)
  ]);
}
function drawDuration(rows) {
  drawChart('durationChart','bar',rows.map(r=>r.duration),[dataset('車次',rows.map(r=>r.count),seriesColors.CAR)]);
}
function drawAreas(rows) {
  const top = [...rows].sort((a,b)=>b.peak_rate-a.peak_rate).slice(0,10);
  drawChart('chartPeak','bar',top.map(r=>r.area_name),[dataset('尖峰占用率 (%)',top.map(r=>r.peak_rate),seriesColors.SUMMER)],true);
}
function drawPermits(data) {
  document.getElementById('permitStats').textContent = `${formatNumber(data.used)} / ${formatNumber(data.issued_paid)} 張曾使用（${data.usage_rate}%）`;
  document.getElementById('permitUsage').textContent = `在選定期間內完全未使用：${formatNumber(data.unused)} 張。`;
}
function drawRevenue(rows) {
  const top = [...rows].sort((a,b)=>b.amount-a.amount).slice(0,10);
  drawChart('revenueChart','bar',top.map(r=>r.area_name),[dataset('收入（元）',top.map(r=>r.amount),seriesColors.CAR)],true);
}

async function loadAnalysis() {
  const start = document.getElementById('startDate').value;
  const end = document.getElementById('endDate').value;
  if (start > end) { notify('開始日期不得晚於結束日期',true); return; }
  const sequence = ++querySequence;
  try {
    const query = analysisQuery();
    const vehicleType = document.getElementById('vehicleType').value;
    const fixedQuery = vehicleType ? `vehicle_type=${encodeURIComponent(vehicleType)}` : '';
    const endpoints = [
      `/analytics/by-identity?${query}`,
      `/analytics/by-hour-phase?${fixedQuery}`,
      `/analytics/duration?${query}`,
      `/analytics/area-utilization?${query}`,
      `/analytics/permit-utilization?${query}`,
      `/analytics/revenue?${query}`
    ];
    const results = await Promise.all(endpoints.map(url => requestJSON(url)));
    if (sequence !== querySequence) return;
    const [identity, phases, durations, areas, permits, revenues] = results.map(r=>r.data);
    drawIdentity(identity);
    drawPhase(phases);
    drawDuration(durations);
    drawAreas(areas);
    drawPermits(permits);
    drawRevenue(revenues);
    // Charts in hidden tab panels need to resize when their tab becomes visible.
    requestAnimationFrame(() => Object.values(charts).forEach(c => c.resize()));
    await loadSnapshot();
  } catch(e) {
    if (sequence === querySequence) notify(`統計分析載入失敗：${e.message}`,true);
  }
}

function formatTime(value) {
  return new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false});
}
function drawOccupancy(data) {
  document.getElementById('snapshotSummary').textContent = `查詢時間：${formatTime(data.at)}，共 ${formatNumber(data.total_occupied)} 台在場；以下顯示占用率最高的 12 個停車區。`;
  const host = document.getElementById('occupancyList'); host.replaceChildren();
  for (const area of [...data.areas].sort((a,b)=>b.occupancy_rate-a.occupancy_rate).slice(0,12)) {
    const wrap = document.createElement('div'); wrap.className='col-md-6 col-xl-4';
    const label = document.createElement('div'); label.className='d-flex justify-content-between align-items-center mb-2 occ-title';
    const name = document.createElement('span'); name.textContent = area.area_name;
    const value = document.createElement('span'); value.textContent = `${area.occupied}/${area.capacity}（${area.occupancy_rate}%）`;
    label.append(name,value);
    const progress = document.createElement('div'); progress.className='progress occ-bar';
    const bar = document.createElement('div');
    bar.className=`progress-bar ${area.occupancy_rate>=90?'bg-danger':area.occupancy_rate>=75?'bg-warning':'bg-primary'}`;
    bar.style.width=`${Math.max(0,Math.min(area.occupancy_rate,100))}%`;
    bar.setAttribute('role','progressbar');
    bar.setAttribute('aria-valuenow',area.occupancy_rate);
    bar.setAttribute('aria-valuemin','0'); bar.setAttribute('aria-valuemax','100');
    progress.append(bar); wrap.append(label,progress); host.append(wrap);
  }
}
async function loadSnapshot() {
  const value = document.getElementById('snapshotAt').value;
  if (!value) return;
  try {
    const params = new URLSearchParams({at:`${value}:00+08:00`});
    const type = document.getElementById('vehicleType').value;
    if (type) params.set('vehicle_type',type);
    const result = await requestJSON(`/analytics/occupancy-at?${params.toString()}`);
    drawOccupancy(result.data);
  } catch(e) { notify(`歷史占用查詢失敗：${e.message}`,true); }
}

document.getElementById('detailFilters').addEventListener('submit',e=>{e.preventDefault();loadAnalysis();});
document.getElementById('snapshotForm').addEventListener('submit',e=>{e.preventDefault();loadSnapshot();});
document.querySelectorAll('#analyticsTabs [data-bs-toggle="pill"]').forEach(tab => {
  tab.addEventListener('shown.bs.tab',() => requestAnimationFrame(()=>Object.values(charts).forEach(chart=>chart.resize())));
});
loadAnalysis();
