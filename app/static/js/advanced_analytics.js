'use strict';
let durationChart, revenueChart;
function qs(){const p=new URLSearchParams();for(const [key,id] of [['start_date','startDate'],['end_date','endDate'],['vehicle_type','vehicleType']]){const v=document.getElementById(id).value;if(v)p.set(key,v);}return p.toString();}
function graph(canvas,old,labels,values,label){if(old)old.destroy();return new Chart(document.getElementById(canvas),{type:'bar',data:{labels,datasets:[{label,data:values,backgroundColor:'#376caa',borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}});}
async function load(){try{const p=qs();const [u,d,r]=await Promise.all(['permit-utilization','duration','revenue'].map(n=>requestJSON(`/analytics/${n}?${p}`)));
 const stats=u.data;document.getElementById('permitStats').textContent=`${stats.used.toLocaleString()}/${stats.issued_paid.toLocaleString()} 張曾使用（${stats.usage_rate}%）`;
 document.getElementById('permitUsage').textContent=`期間完全未使用：${stats.unused.toLocaleString()} 張。此處只統計指定期間內有效、且已付款的學年證。`;
 durationChart=graph('durationChart',durationChart,d.data.map(x=>x.duration),d.data.map(x=>x.count),'車次');
 const rs=[...r.data].sort((a,b)=>b.amount-a.amount).slice(0,10);
 revenueChart=graph('revenueChart',revenueChart,rs.map(x=>x.area_name),rs.map(x=>x.amount),'收入（元）');
}catch(e){notify(`載入失敗：${e.message}`,true);}}
document.getElementById('detailFilters').addEventListener('submit',e=>{e.preventDefault();load();});load();
