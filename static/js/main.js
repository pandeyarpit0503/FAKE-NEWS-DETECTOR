document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('analysisForm');
    const results = document.getElementById('results');
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const text = document.getElementById('textInput').value;
        const url = document.getElementById('urlInput').value;
        const btn = document.getElementById('analyzeBtn');
        const spinner = document.getElementById('loading');
        
        if (!text && !url) {
            alert('Please enter text or a URL');
            return;
        }
        
        // Show loading
        btn.disabled = true;
        spinner.classList.remove('d-none');
        results.classList.add('d-none');
        
        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text, url})
            });
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            displayResults(data);
            
        } catch (error) {
            alert('Analysis failed: ' + error.message);
        } finally {
            btn.disabled = false;
            spinner.classList.add('d-none');
        }
    });
});

function displayResults(data) {
    const results = document.getElementById('results');
    const scoreValue = document.getElementById('scoreValue');
    const scoreCircle = document.getElementById('scoreCircle');
    const badge = document.getElementById('predictionBadge');
    const explanation = document.getElementById('explanation');
    const indicators = document.getElementById('indicators');
    
    // Animate score
    animateValue(scoreValue, 0, data.trust_score, 1000);
    
    // Set colors based on score
    let color, badgeClass;
    if (data.trust_score >= 80) {
        color = '#10b981';
        badgeClass = 'badge-real';
    } else if (data.trust_score >= 50) {
        color = '#f59e0b';
        badgeClass = 'badge-partial';
    } else {
        color = '#ef4444';
        badgeClass = 'badge-fake';
    }
    
    scoreCircle.style.background = `conic-gradient(${color} ${data.trust_score}%, #18181c 0%)`;
    badge.className = `badge rounded-pill fs-6 ${badgeClass}`;
    badge.textContent = data.prediction;
    
    explanation.textContent = data.explanation;
    
    // Confidence and timing
    const confVal = typeof data.confidence === 'number' ? data.confidence * 100 : data.confidence;
    document.getElementById('confidenceVal').textContent = 
        Math.round(confVal) + '%';
    document.getElementById('processingTime').textContent = data.processing_time;
    
    // Indicators
    indicators.innerHTML = '';
    if (data.indicators && data.indicators.length > 0) {
        data.indicators.forEach(ind => {
            const div = document.createElement('div');
            div.className = 'indicator-item';
            div.innerHTML = ind.indexOf('<i') === 0 ? ind : `<i class="fas fa-exclamation-circle"></i> ${ind}`;
            indicators.appendChild(div);
        });
    } else {
        indicators.innerHTML = '<div class="text-success"><i class="fas fa-check-circle"></i> No red flags detected</div>';
    }

    // Verified sources (trusted news sites)
    const sourcesSection = document.getElementById('verifiedSourcesSection');
    const sourcesList = document.getElementById('verifiedSourcesList');
    if (data.verified_sources && data.verified_sources.length > 0) {
        sourcesSection.classList.remove('d-none');
        sourcesList.innerHTML = data.verified_sources.map(src => `
            <a href="${src.url}" target="_blank" rel="noopener" class="verified-source-item">
                <i class="fas fa-external-link-alt me-2"></i>
                <strong>${escapeHtml(src.name)}</strong>
                ${src.title ? `<span class="text-muted d-block ms-4 mt-1 small">${escapeHtml(src.title)}</span>` : ''}
            </a>
        `).join('');
    } else {
        sourcesSection.classList.add('d-none');
        sourcesList.innerHTML = '';
    }
    
    const resultsCard = results.querySelector('.card');
    resultsCard.classList.remove('animate-fade-in-up');
    void resultsCard.offsetWidth; // reflow to re-trigger animation
    resultsCard.classList.add('animate-fade-in-up');

    results.classList.remove('d-none');
    results.scrollIntoView({behavior: 'smooth'});
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}