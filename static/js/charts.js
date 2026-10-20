const chartColors = ['#4f46e5', '#0891b2', '#f59e0b', '#16a34a', '#e11d48', '#64748b'];
const chartInstances = [];

async function loadAnalytics() {
  const healthNode = document.getElementById('health-status');
  fetch('/health').then(async (response) => {
    const health = await response.json();
    healthNode.innerHTML = response.ok
      ? '<i class="fa-solid fa-circle-check mr-2 text-emerald-600"></i>Healthy'
      : '<i class="fa-solid fa-triangle-exclamation mr-2 text-amber-600"></i>Degraded';
    healthNode.title = health.database === 'connected' ? 'Database connected' : 'Database unavailable';
  }).catch(() => { healthNode.textContent = 'Unavailable'; });
  const params = new URLSearchParams({ days: document.getElementById('analytics-days').value });
  const linkId = document.getElementById('analytics-link').value;
  if (linkId) params.set('link_id', linkId);
  const response = await fetch(`/api/analytics?${params}`, { credentials: 'same-origin' });
  if (!response.ok) throw new Error('Analytics could not be loaded.');
  const data = await response.json();
  document.getElementById('metric-clicks').textContent = data.total_clicks.toLocaleString();
  document.getElementById('metric-visitors').textContent = data.unique_visitors.toLocaleString();
  document.getElementById('metric-active').textContent = data.active_links.toLocaleString();
  document.getElementById('metric-expiring').textContent = data.expiring_links.toLocaleString();
  document.getElementById('metric-bots').textContent = data.bot_hits_filtered.toLocaleString();
  chartInstances.splice(0).forEach((chart) => chart.destroy());
  const options = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: { color: '#64748b' } }, y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0, color: '#64748b' } } } };
  chartInstances.push(new Chart(document.getElementById('timeline-chart'), { type: 'line', data: { labels: data.timeline.labels, datasets: [{ data: data.timeline.values, borderColor: chartColors[0], backgroundColor: '#4f46e51c', fill: true, tension: .34, pointRadius: 3, pointHoverRadius: 5 }] }, options }));
  chartInstances.push(new Chart(document.getElementById('device-chart'), { type: 'doughnut', data: { labels: data.devices.labels, datasets: [{ data: data.devices.values, backgroundColor: chartColors.slice(0, 3), borderWidth: 0, hoverOffset: 5 }] }, options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, color: '#475569', padding: 18 } } } } }));
  chartInstances.push(new Chart(document.getElementById('geo-chart'), { type: 'bar', data: { labels: data.geography.labels, datasets: [{ data: data.geography.values, backgroundColor: chartColors[1], borderRadius: 5, maxBarThickness: 24 }] }, options: { ...options, indexAxis: 'y' } }));
  chartInstances.push(new Chart(document.getElementById('channel-chart'), { type: 'bar', data: { labels: data.channels.labels, datasets: [{ data: data.channels.values, backgroundColor: chartColors[2], borderRadius: 5, maxBarThickness: 30 }] }, options }));
}

document.getElementById('analytics-days').addEventListener('change', () => loadAnalytics().catch((error) => showToast(error.message, true)));
document.getElementById('analytics-link').addEventListener('change', () => loadAnalytics().catch((error) => showToast(error.message, true)));
loadAnalytics().catch((error) => showToast(error.message, true));