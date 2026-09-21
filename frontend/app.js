/**
 * GeM Tender AI Agent — Dashboard Application
 * Loads JSON results, renders tender cards, handles search & filtering.
 */

// ─── State ─────────────────────────────────────────────────────────
let allBids = [];
let filteredBids = [];
let currentFilter = 'all';
let searchQuery = '';

// ─── File Loading ──────────────────────────────────────────────────

function loadFromFile() {
    document.getElementById('fileInput').click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const data = JSON.parse(e.target.result);
            loadData(data);
            // Update button state
            document.getElementById('loadFileBtn').classList.add('file-selector__btn--active');
            document.getElementById('loadDemoBtn').classList.remove('file-selector__btn--active');
        } catch (err) {
            alert('Invalid JSON file. Please select a valid results file.');
            console.error('JSON parse error:', err);
        }
    };
    reader.readAsText(file);
}

function loadDemo() {
    const demoData = generateDemoData();
    loadData(demoData);
    document.getElementById('loadDemoBtn').classList.add('file-selector__btn--active');
    document.getElementById('loadFileBtn').classList.remove('file-selector__btn--active');
}

function loadData(data) {
    allBids = data.bids || [];
    const generatedAt = data.generated_at || new Date().toISOString();

    // Update header meta
    const meta = document.getElementById('headerMeta');
    const date = new Date(generatedAt);
    meta.innerHTML = `
        <span class="header__meta-item">📅 ${date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
        <span class="header__meta-item">🕐 ${date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span>
        <span class="header__meta-item">🎯 ${allBids.length} Relevant Tenders</span>
    `;

    // Show stats and toolbar
    document.getElementById('statsGrid').style.display = '';
    document.getElementById('toolbar').style.display = '';

    // Update stats
    updateStats();

    // Render tenders
    currentFilter = 'all';
    searchQuery = '';
    document.getElementById('searchInput').value = '';
    // Reset filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.filter-btn[data-filter="all"]').classList.add('active');

    filterTenders();
}

// ─── Stats ─────────────────────────────────────────────────────────

function updateStats() {
    const high = allBids.filter(b => b.ai_confidence === 'high').length;
    const medium = allBids.filter(b => b.ai_confidence === 'medium').length;
    const low = allBids.filter(b => b.ai_confidence === 'low').length;

    animateCounter('statTotal', allBids.length);
    animateCounter('statHigh', high);
    animateCounter('statMedium', medium);
    animateCounter('statLow', low);
}

function animateCounter(elementId, target) {
    const el = document.getElementById(elementId);
    const duration = 600;
    const startTime = performance.now();
    const startValue = parseInt(el.textContent) || 0;

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(startValue + (target - startValue) * eased);
        el.textContent = current;
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// ─── Filtering ─────────────────────────────────────────────────────

function setFilter(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    filterTenders();
}

function filterTenders() {
    searchQuery = (document.getElementById('searchInput').value || '').toLowerCase().trim();

    filteredBids = allBids.filter(bid => {
        // Confidence filter
        if (currentFilter !== 'all' && bid.ai_confidence !== currentFilter) {
            return false;
        }

        // Search query
        if (searchQuery) {
            const searchableText = [
                bid.bid_number,
                bid.title,
                bid.department,
                bid.items,
                bid.ai_reason,
                bid.matched_product,
                bid.full_description,
            ].filter(Boolean).join(' ').toLowerCase();

            return searchableText.includes(searchQuery);
        }

        return true;
    });

    renderTenders();
}

// ─── Rendering ─────────────────────────────────────────────────────

function renderTenders() {
    const grid = document.getElementById('tendersGrid');

    if (filteredBids.length === 0) {
        if (allBids.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state__icon">📄</div>
                    <div class="empty-state__title">No Results Loaded</div>
                    <div class="empty-state__text">
                        Load a JSON results file from the backend output, or click "Load Demo Data" to preview the dashboard.
                    </div>
                </div>
            `;
        } else {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state__icon">🔍</div>
                    <div class="empty-state__title">No Matching Tenders</div>
                    <div class="empty-state__text">
                        Try adjusting your search query or filter criteria.
                    </div>
                </div>
            `;
        }
        return;
    }

    grid.innerHTML = filteredBids.map((bid, i) => renderTenderCard(bid, i)).join('');
}

function renderTenderCard(bid, index) {
    const confidence = bid.ai_confidence || 'unknown';
    const bidNumber = escapeHtml(bid.bid_number || 'N/A');
    const title = escapeHtml(bid.title || 'No title available');
    const department = escapeHtml(bid.department || 'N/A');
    const quantity = escapeHtml(bid.quantity || 'N/A');
    const startDate = escapeHtml(bid.start_date || 'N/A');
    const endDate = escapeHtml(bid.end_date || 'N/A');
    const bidValue = escapeHtml(bid.bid_value || 'N/A');
    const reason = escapeHtml(bid.ai_reason || '');
    const matchedProduct = escapeHtml(bid.matched_product || '');
    const detailLink = bid.detail_link || '#';

    const confidenceLabels = {
        high: '🟢 High',
        medium: '🟡 Medium',
        low: '🔴 Low',
        fallback: '⚪ Keyword',
    };

    return `
        <div class="tender-card tender-card--${confidence}" style="animation-delay: ${index * 0.05}s">
            <div class="tender-card__header">
                <div>
                    <div class="tender-card__bid-number">${bidNumber}</div>
                </div>
                <span class="tender-card__badge tender-card__badge--${confidence}">
                    ${confidenceLabels[confidence] || confidence}
                </span>
            </div>
            <div class="tender-card__title">${title}</div>
            <div class="tender-card__details">
                <div class="tender-card__detail">
                    <span class="tender-card__detail-label">Department</span>
                    <span class="tender-card__detail-value">${department}</span>
                </div>
                <div class="tender-card__detail">
                    <span class="tender-card__detail-label">Quantity</span>
                    <span class="tender-card__detail-value">${quantity}</span>
                </div>
                <div class="tender-card__detail">
                    <span class="tender-card__detail-label">Start Date</span>
                    <span class="tender-card__detail-value">${startDate}</span>
                </div>
                <div class="tender-card__detail">
                    <span class="tender-card__detail-label">End Date</span>
                    <span class="tender-card__detail-value">${endDate}</span>
                </div>
                <div class="tender-card__detail">
                    <span class="tender-card__detail-label">Bid Value</span>
                    <span class="tender-card__detail-value">${bidValue}</span>
                </div>
            </div>
            <div class="tender-card__footer">
                <div class="tender-card__reason">${reason}</div>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    ${matchedProduct ? `<span class="tender-card__product-tag">🏷️ ${matchedProduct}</span>` : ''}
                    <a href="${escapeHtml(detailLink)}" target="_blank" rel="noopener" class="tender-card__link">
                        View on GeM →
                    </a>
                </div>
            </div>
        </div>
    `;
}

// ─── Utilities ─────────────────────────────────────────────────────

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// ─── Demo Data ─────────────────────────────────────────────────────

function generateDemoData() {
    return {
        generated_at: new Date().toISOString(),
        total_relevant: 6,
        summary: { high_confidence: 3, medium_confidence: 2, low_confidence: 1, fallback: 0 },
        bids: [
            {
                bid_number: "GEM/2026/B/5847231",
                title: "Supply of Mobile Lighting Tower (Diesel Operated) for construction site illumination — 9 Meter Mast Height, 4x1000W Metal Halide Lamps",
                department: "Central Public Works Department (CPWD)",
                quantity: "15 Units",
                start_date: "15-Sep-2026",
                end_date: "30-Sep-2026",
                bid_value: "₹ 45,00,000",
                ai_confidence: "high",
                ai_reason: "Directly requesting mobile lighting towers for construction use — exact product match.",
                matched_product: "Mobile Light Tower",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5847231",
            },
            {
                bid_number: "GEM/2026/B/5923847",
                title: "Procurement of Inflatable Balloon Light Systems for Emergency Disaster Response — 1000W LED, 360° illumination coverage",
                department: "National Disaster Response Force (NDRF)",
                quantity: "25 Units",
                start_date: "18-Sep-2026",
                end_date: "05-Oct-2026",
                bid_value: "₹ 37,50,000",
                ai_confidence: "high",
                ai_reason: "Inflatable balloon light systems for disaster response — core product category.",
                matched_product: "Inflatable Light System",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5923847",
            },
            {
                bid_number: "GEM/2026/B/5789012",
                title: "Mobile Service Tower (MST) with integrated LED lighting system for telecom infrastructure maintenance",
                department: "Bharat Sanchar Nigam Limited (BSNL)",
                quantity: "10 Units",
                start_date: "10-Sep-2026",
                end_date: "28-Sep-2026",
                bid_value: "₹ 62,00,000",
                ai_confidence: "high",
                ai_reason: "MST with integrated LED lighting — directly within product portfolio.",
                matched_product: "MST Lighting System",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5789012",
            },
            {
                bid_number: "GEM/2026/B/5834567",
                title: "Solar Powered Portable Light Tower with Telescopic Mast for Border Outpost Illumination",
                department: "Border Security Force (BSF)",
                quantity: "20 Units",
                start_date: "20-Sep-2026",
                end_date: "10-Oct-2026",
                bid_value: "₹ 28,00,000",
                ai_confidence: "medium",
                ai_reason: "Solar-powered portable light tower — matches product range but solar variant may need verification.",
                matched_product: "Solar Light Tower",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5834567",
            },
            {
                bid_number: "GEM/2026/B/5901234",
                title: "LED Floodlight Tower for Sports Ground and Stadium Illumination — 12 Meter Height",
                department: "Sports Authority of India",
                quantity: "8 Units",
                start_date: "12-Sep-2026",
                end_date: "02-Oct-2026",
                bid_value: "₹ 18,40,000",
                ai_confidence: "medium",
                ai_reason: "LED floodlight tower for sports — related to lighting towers but fixed installation type.",
                matched_product: "LED Floodlight Tower",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5901234",
            },
            {
                bid_number: "GEM/2026/B/5867890",
                title: "Portable Area Lighting Equipment for Railway Track Maintenance — 500W LED, Tripod Mounted",
                department: "Indian Railways",
                quantity: "50 Units",
                start_date: "14-Sep-2026",
                end_date: "25-Sep-2026",
                bid_value: "₹ 15,00,000",
                ai_confidence: "low",
                ai_reason: "Portable area lighting — related but tripod-mounted, not a tower system.",
                matched_product: "Portable Lighting Equipment",
                detail_link: "https://bidplus.gem.gov.in/showbidDocument/GEM_2026_B_5867890",
            },
        ],
    };
}

// ─── Auto-load latest results ──────────────────────────────────────

(function init() {
    // Try to load latest_results.json from the backend output directory
    fetch('../backend/output/latest_results.json')
        .then(response => {
            if (!response.ok) throw new Error('No latest results file');
            return response.json();
        })
        .then(data => {
            loadData(data);
            document.getElementById('loadFileBtn').classList.add('file-selector__btn--active');
        })
        .catch(() => {
            // No auto-loaded data — user needs to load manually
            console.log('No latest results file found. Load manually or use demo data.');
        });
})();
