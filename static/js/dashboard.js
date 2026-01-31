let distributionChart, trendsChart;

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadHistory();
    // Refresh every 30 seconds
    setInterval(loadStats, 30000);
});

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        // Update counters
        document.getElementById('totalCount').textContent = data.total_analyzed;
        document.getElementById('fakeCount').textContent = data.fake_count;
        document.getElementById('realCount').textContent = data.real_count;
        document.getElementById('partialCount').textContent = data.partial_count;
        
        // Update charts
        updateDistributionChart(data);
        updateTrendsChart(data.daily_trends);
        
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadHistory() {
    try {
        const response = await fetch('/api/history?limit=10');
        const data = await response.json();
        
        const tbody = document.getElementById('historyBody');
        tbody.innerHTML = '';
        
        data.forEach(item => {
            const row = document.createElement('tr');
            let badgeClass = 'bg-secondary';
            if (item.prediction === 'Real') badgeClass = 'bg-success';
            else if (item.prediction === 'Fake') badgeClass = 'bg-danger';
            else if (item.prediction === 'Partially Correct') badgeClass = 'bg-warning';
            
            row.innerHTML = `
                <td>${new Date(item.date).toLocaleDateString()}</td>
                <td>${item.headline.substring(0, 50)}...</td>
                <td><span class="badge ${badgeClass}">${item.prediction}</span></td>
                <td>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar ${item.trust_score > 60 ? 'bg-success' : item.trust_score > 40 ? 'bg-warning' : 'bg-danger'}" 
                             style="width: ${item.trust_score}%">
                            ${item.trust_score}
                        </div>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

const chartTextColor = '#a1a1aa';
const chartGridColor = 'rgba(45, 45, 54, 0.8)';

function updateDistributionChart(data) {
    const ctx = document.getElementById('distributionChart').getContext('2d');
    
    if (distributionChart) distributionChart.destroy();
    
    distributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Real', 'Fake', 'Partial'],
            datasets: [{
                data: [data.real_count, data.fake_count, data.partial_count],
                backgroundColor: ['#22c55e', '#ef4444', '#eab308'],
                borderColor: '#1e1e24',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: chartTextColor }
                }
            }
        }
    });
}

function updateTrendsChart(trends) {
    const ctx = document.getElementById('trendsChart').getContext('2d');
    
    if (trendsChart) trendsChart.destroy();
    
    const labels = trends.map(t => t.date);
    const values = trends.map(t => t.count);
    
    trendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Articles Analyzed',
                data: values,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: chartGridColor },
                    ticks: { color: chartTextColor }
                },
                x: {
                    grid: { color: chartGridColor },
                    ticks: { color: chartTextColor }
                }
            },
            plugins: {
                legend: { labels: { color: chartTextColor } }
            }
        }
    });
}