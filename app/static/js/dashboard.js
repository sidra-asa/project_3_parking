'use strict';
let dailyChart = null;
let lastRequest = 0;
const number = n => Number(n || 0).toLocaleString('zh-TW');

function dashboardQuery() {
  const params = new URLSearchParams();
  for (const [key, id] of [['vehicle_type', 'vehicleType'], ['start_date', 'startDate'], ['end_date', 'endDate']]) {
    const value = document.getElementById(id).value;
    if (value) params.set(key, value);
  }
  return params.toString();
}

async function loadDashboard() {
  const start = document.getElementById('startDate').value;
  const end = document.getElementById('endDate').value;
  if (start > end) { notify('開始日期不得晚於結束日期', true); return; }
  const requestId = ++lastRequest;
  try {
    const q = dashboardQuery();
    const paths = ['overview', 'daily-trend', 'by-identity', 'area-utilization'];
    const results = await Promise.all(paths.map(p => requestJSON(`/analytics/${p}?${q}`)));
    if (requestId !== lastRequest) return;
    const [overview, daily, identity, areas] = results.map(r => r.data);
    document.getElementById('m-total').textContent = number(overview.total_records);
    // The Miniworld does not transfer registered vehicle ownership, so each plate is in one identity group.
    document.getElementById('m-plates').textContent = number(identity.reduce((n, item) => n + item.distinct_plates, 0));
    document.getElementById('m-duration').textContent = `${(overview.avg_duration_minutes / 60).toFixed(1)} 小時`;
    document.getElementById('m-peak').textContent = areas.length ? `${Math.max(...areas.map(a => a.peak_rate))}%` : '—';
    if (dailyChart) dailyChart.destroy();
    dailyChart = new Chart(document.getElementById('chartDaily'), {
      type: 'line',
      data: {
        labels: daily.map(item => item.date.slice(5)),
        datasets: [{label:'進場車次', data:daily.map(item => item.count), borderColor:'#376caa', backgroundColor:'rgba(55,108,170,.10)', fill:true, tension:.25, pointRadius:2}]
      },
      options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true, ticks:{precision:0}}}}
    });
  } catch(e) {
    if (requestId === lastRequest) notify(`載入總覽失敗：${e.message}`, true);
  }
}

document.getElementById('filters').addEventListener('submit', event => {
  event.preventDefault();
  loadDashboard();
});
loadDashboard();
