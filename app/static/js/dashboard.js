'use strict';
const charts={};
function params() {
  const sp=new URLSearchParams();
  for (const [key,id] of [['vehicle_type','vehicleType'],['start_date','startDate'],['end_date','endDate']]) {
    const value=document.getElementById(id).value;
    if (value) sp.set(key,value);
  }
  return '?' + sp.toString();
}
function draw(id,type,labels,values,label) {
  if (charts[id]) charts[id].destroy();
  charts[id]=new Chart(document.getElementById(id),{
    type,data:{labels,datasets:[{label,data:values,backgroundColor:'#417db8',borderColor:'#276aa5',borderWidth:2,borderRadius:5,tension:.3,fill:false}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{y:{beginAtZero:true,ticks:{precision:0}}}}
  });
}
async function loadDashboard() {
  try {
    const p=params();
    const names=['overview','by-area','by-hour','duration','occupancy','permits','revenue'];
    const responses=await Promise.all(names.map(n=>requestJSON(`/analytics/${n}${p}`)));
    const out=Object.fromEntries(names.map((n,i)=>[n,responses[i].data]));
    document.getElementById('m-total').textContent=out.overview.total_records.toLocaleString();
    document.getElementById('m-open').textContent=out.overview.currently_parked.toLocaleString();
    document.getElementById('m-duration').textContent=`${(out.overview.avg_duration_minutes/60).toFixed(1)} 小時`;
    document.getElementById('m-areas').textContent=out.occupancy.length;
    const topAreas=[...out['by-area']].sort((a,b)=>b.count-a.count).slice(0,10);
    draw('chartArea','bar',topAreas.map(r=>r.area_name),topAreas.map(r=>r.count),'停車次數');
    draw('chartHour','line',out['by-hour'].map(r=>`${r.hour}:00`),out['by-hour'].map(r=>r.count),'車次');
    draw('chartDuration','bar',out.duration.map(r=>r.duration),out.duration.map(r=>r.count),'車次');
    const topRevenue=[...out.revenue].sort((a,b)=>b.amount-a.amount).slice(0,10);
    draw('chartRevenue','bar',topRevenue.map(r=>r.area_name),topRevenue.map(r=>r.amount),'元');
    const host=document.getElementById('occupancyList'); host.replaceChildren();
    for (const item of [...out.occupancy].sort((a,b)=>b.occupancy_rate-a.occupancy_rate)) {
      const wrap=document.createElement('div');wrap.className='col-md-6 col-xl-4';
      const label=document.createElement('div');label.className='d-flex justify-content-between align-items-center mb-2 occ-title';
      const name=document.createElement('span');name.textContent=item.area_name;
      const val=document.createElement('span');val.textContent=`${item.occupied}/${item.capacity} (${item.occupancy_rate}%)`;
      label.append(name,val);
      const progress=document.createElement('div'); progress.className='progress occ-bar';
      const bar=document.createElement('div');bar.className=`progress-bar ${item.occupancy_rate >= 90 ? 'bg-danger':item.occupancy_rate>=75 ? 'bg-warning':'bg-primary'}`;
      bar.style.width=`${Math.min(item.occupancy_rate,100)}%`;bar.setAttribute('role','progressbar');
      bar.setAttribute('aria-valuenow',item.occupancy_rate);bar.setAttribute('aria-valuemin',0);bar.setAttribute('aria-valuemax',100);
      progress.append(bar);wrap.append(label,progress);host.append(wrap);
    }
    const tbody=document.getElementById('permitsTable');tbody.replaceChildren();
    if (!out.permits.length) { const row=tbody.insertRow();const cell=row.insertCell();cell.colSpan=3;cell.textContent='尚無停車證資料'; }
    for (const permit of out.permits) { const tr=tbody.insertRow();
      for (const value of [permit.academic_year,permit.issued,permit.paid]) tr.insertCell().textContent=value;
    }
  } catch(e) {notify(`分析載入失敗：${e.message}`,true);}
}
document.getElementById('filters').addEventListener('submit',e=>{e.preventDefault();loadDashboard();});
loadDashboard();
