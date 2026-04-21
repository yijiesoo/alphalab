/**
 * Phase 3B: ML Metrics Dashboard Widget
 * 
 * Displays latest ML backtest metrics on the dashboard.
 * Integrates with /api/latest-metrics endpoint (no yfinance calls).
 * 
 * Usage:
 *   1. Include this script in your HTML template
 *   2. Add a container element: <div id="ml-metrics-widget"></div>
 *   3. Call: initMLMetricsWidget()
 */

// =====================================================================
// ML Metrics Widget
// =====================================================================

async function initMLMetricsWidget() {
    // Initialize ML metrics widget on page load
    console.log("📊 Loading ML metrics widget...");
    
    const container = document.getElementById("ml-metrics-widget");
    if (!container) {
        console.warn("⚠️ ML metrics widget container not found");
        return;
    }
    
    // Show loading state
    container.innerHTML = `
        <div class="ml-widget-card">
            <div class="ml-widget-header">
                <h3>ML Model Performance</h3>
            </div>
            <div class="ml-widget-content" style="text-align: center; padding: 40px 20px;">
                <div class="loading-spinner" style="display: inline-block; font-size: 32px;">⟳</div>
                <p style="margin-top: 16px; color: var(--text-secondary);">Loading metrics...</p>
            </div>
        </div>
    `;
    
    try {
        // Fetch latest metrics from API
        const response = await fetch("/api/latest-metrics");
        const data = await response.json();
        
        if (data.status === "success") {
            renderMLMetrics(container, data);
        } else if (data.status === "no_data") {
            container.innerHTML = `
                <div class="ml-widget-card ml-widget-empty">
                    <div class="ml-widget-header">
                        <h3>🤖 ML Model Metrics</h3>
                    </div>
                    <div class="ml-widget-content">
                        <p>No backtest runs available yet</p>
                        <p class="ml-widget-help">Run the ML pipeline to generate metrics</p>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="ml-widget-card ml-widget-error">
                    <div class="ml-widget-header">
                        <h3>🤖 ML Model Metrics</h3>
                    </div>
                    <div class="ml-widget-content">
                        <p class="ml-widget-error-text">❌ ${data.message || "Error loading metrics"}</p>
                    </div>
                </div>
            `;
        }
        
        // Auto-refresh every 5 minutes
        setInterval(() => initMLMetricsWidget(), 5 * 60 * 1000);
        
    } catch (error) {
        console.error("❌ Error loading ML metrics:", error);
        container.innerHTML = `
            <div class="ml-widget-card ml-widget-error">
                <div class="ml-widget-header">
                    <h3>🤖 ML Model Metrics</h3>
                </div>
                <div class="ml-widget-content">
                    <p class="ml-widget-error-text">❌ ${error.message}</p>
                </div>
            </div>
        `;
    }
}

function renderMLMetrics(container, data) {
    // Render ML metrics into the widget
    const metrics = data.metrics || {};
    const portfolio = data.portfolio || {};
    const coverage = data.coverage || {};
    
    const ic = metrics.ic !== undefined ? metrics.ic.toFixed(4) : "N/A";
    const hitRate = metrics.hit_rate !== undefined ? (metrics.hit_rate * 100).toFixed(1) : "N/A";
    const sharpe = metrics.sharpe !== undefined ? metrics.sharpe.toFixed(2) : "N/A";
    const maxDD = metrics.max_drawdown !== undefined ? (metrics.max_drawdown * 100).toFixed(1) : "N/A";
    const turnover = metrics.turnover !== undefined ? (metrics.turnover * 100).toFixed(1) : "N/A";
    
    const longExp = portfolio.long_exposure !== undefined ? (portfolio.long_exposure * 100).toFixed(1) : "N/A";
    const shortExp = portfolio.short_exposure !== undefined ? (portfolio.short_exposure * 100).toFixed(1) : "N/A";
    const grossLev = portfolio.gross_leverage !== undefined ? (portfolio.gross_leverage * 100).toFixed(1) : "N/A";
    
    const universeSize = coverage.universe_size || 0;
    const validScores = coverage.valid_scores || 0;
    const coverage_pct = universeSize > 0 ? ((validScores / universeSize) * 100).toFixed(1) : "N/A";
    
    // Status indicators for KPIs
    const getStatusDot = (value, target, isHigherBetter = true) => {
        if (value === "N/A" || target === undefined) return '<span class="ml-status-none">—</span>';
        const numValue = parseFloat(value);
        const passed = isHigherBetter ? numValue >= target : numValue <= target;
        if (passed) return '<span class="ml-status ml-status-good">●</span>';
        if (isHigherBetter) {
            return numValue > (target * 0.8) ? '<span class="ml-status ml-status-neutral">●</span>' : '<span class="ml-status ml-status-bad">●</span>';
        }
        return '<span class="ml-status ml-status-bad">●</span>';
    };
    
    const icStatus = getStatusDot(ic, 0.05, true);
    const hitRateStatus = getStatusDot(hitRate.replace('%', ''), 55, true);
    const sharpeStatus = getStatusDot(sharpe, 1.0, true);
    const maxDDStatus = getStatusDot(maxDD.replace('%', ''), -15, false);
    
    const warningHtml = data.warning 
        ? `<div class="ml-widget-warning">⚠️ ${data.warning}</div>` 
        : "";
    
    const html = `
        <div class="ml-widget-card">
            <div class="ml-widget-header">
                <h3>ML Model Performance</h3>
                <div class="ml-widget-meta">
                    <span class="ml-widget-version">v${data.model_version}</span>
                    <span class="ml-widget-date">${data.as_of_date}</span>
                </div>
            </div>
            
            ${warningHtml}
            
            <div class="ml-widget-content">
                <!-- Key Performance Indicators (Primary) -->
                <div class="ml-kpi-section">
                    <div class="ml-kpi-grid">
                        <div class="ml-kpi-card">
                            <div class="ml-kpi-header">
                                <span class="ml-kpi-label">Information coefficient</span>
                                ${icStatus}
                            </div>
                            <div class="ml-kpi-value">${ic}</div>
                            <div class="ml-kpi-target">Target: &gt; 0.05</div>
                        </div>
                        
                        <div class="ml-kpi-card">
                            <div class="ml-kpi-header">
                                <span class="ml-kpi-label">Hit rate</span>
                                ${hitRateStatus}
                            </div>
                            <div class="ml-kpi-value">${hitRate}%</div>
                            <div class="ml-kpi-target">Target: &gt; 55%</div>
                        </div>
                        
                        <div class="ml-kpi-card">
                            <div class="ml-kpi-header">
                                <span class="ml-kpi-label">Sharpe ratio</span>
                                ${sharpeStatus}
                            </div>
                            <div class="ml-kpi-value">${sharpe}</div>
                            <div class="ml-kpi-target">Target: &gt; 1.00</div>
                        </div>
                        
                        <div class="ml-kpi-card">
                            <div class="ml-kpi-header">
                                <span class="ml-kpi-label">Max drawdown</span>
                                ${maxDDStatus}
                            </div>
                            <div class="ml-kpi-value">${maxDD}%</div>
                            <div class="ml-kpi-target">Worst: ${maxDD}%</div>
                        </div>
                    </div>
                </div>
                
                <!-- Portfolio Exposure (Secondary) -->
                <div class="ml-secondary-section">
                    <div class="ml-section-title">Portfolio exposure</div>
                    <div class="ml-exposure-grid">
                        <div class="ml-exposure-item">
                            <div class="ml-exposure-label">Long</div>
                            <div class="ml-exposure-value positive">${longExp}%</div>
                        </div>
                        <div class="ml-exposure-item">
                            <div class="ml-exposure-label">Short</div>
                            <div class="ml-exposure-value negative">${shortExp}%</div>
                        </div>
                        <div class="ml-exposure-item">
                            <div class="ml-exposure-label">Gross leverage</div>
                            <div class="ml-exposure-value">${grossLev}%</div>
                        </div>
                        <div class="ml-exposure-item">
                            <div class="ml-exposure-label">Avg turnover</div>
                            <div class="ml-exposure-value">${turnover}%</div>
                        </div>
                    </div>
                </div>
                
                <!-- Coverage (Tertiary) -->
                <div class="ml-tertiary-section">
                    <div class="ml-section-title">Universe coverage</div>
                    <div class="ml-coverage-stat">
                        <div class="ml-coverage-label">Stocks scored</div>
                        <div class="ml-coverage-value">${validScores} / ${universeSize} (${coverage_pct}%)</div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="ml-widget-actions">
                    <button class="btn btn-secondary" onclick="showMLMetricsHistory()">View history</button>
                    <button class="btn btn-secondary" onclick="downloadMLMetrics()">Export</button>
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

async function showMLMetricsHistory() {
    // Show historical ML metrics in a modal
    console.log("📊 Loading ML metrics history...");
    
    try {
        const response = await fetch("/api/all-backtests?limit=50");
        const data = await response.json();
        
        if (data.status !== "success" || !data.backtests) {
            alert("Failed to load history");
            return;
        }
        
        // Create modal
        const modal = document.createElement("div");
        modal.className = "ml-modal";
        modal.style.display = "flex";
        
        let html = `
            <div class="ml-modal-content">
                <div class="ml-modal-header">
                    <h2>Model performance history</h2>
                    <button class="ml-modal-close" onclick="this.parentElement.parentElement.remove()">✕</button>
                </div>
                <div class="ml-modal-body">
                    <table class="ml-history-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Model</th>
                                <th>IC</th>
                                <th>Hit Rate</th>
                                <th>Sharpe</th>
                                <th>Max DD</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        data.backtests.forEach(run => {
            const metrics = run.metrics || {};
            const ic = metrics.ic !== undefined ? metrics.ic.toFixed(4) : "N/A";
            const hitRate = metrics.hit_rate !== undefined ? (metrics.hit_rate * 100).toFixed(1) : "N/A";
            const sharpe = metrics.sharpe !== undefined ? metrics.sharpe.toFixed(2) : "N/A";
            const maxDD = metrics.max_drawdown !== undefined ? (metrics.max_drawdown * 100).toFixed(1) : "N/A";
            
            html += `
                <tr>
                    <td>${run.rebalance_date}</td>
                    <td>v${run.model_version}</td>
                    <td>${ic}</td>
                    <td>${hitRate}%</td>
                    <td>${sharpe}</td>
                    <td>${maxDD}%</td>
                </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        modal.innerHTML = html;
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener("click", (e) => {
            if (e.target === modal) modal.remove();
        });
        
    } catch (error) {
        console.error("❌ Error loading history:", error);
        alert("Error loading history: " + error.message);
    }
}

function downloadMLMetrics() {
    // Download latest metrics as JSON
    console.log("📥 Downloading ML metrics...");
    
    fetch("/api/latest-metrics")
        .then(r => r.json())
        .then(data => {
            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `ml_metrics_${data.as_of_date}.json`;
            a.click();
            URL.revokeObjectURL(url);
        })
        .catch(e => {
            console.error("❌ Download failed:", e);
            alert("Failed to download metrics");
        });
}

// =====================================================================
// CSS Styles (embedded)
// =====================================================================

const ML_WIDGET_CSS = `
/* ML Metrics Widget Container */
.ml-widget-card {
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.ml-widget-card.ml-widget-empty,
.ml-widget-card.ml-widget-error {
    background: var(--light-bg);
    border-color: var(--border-color);
}

.ml-widget-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 0;
}

.ml-widget-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}

.ml-widget-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
}

.ml-widget-version {
    background: rgba(59, 130, 246, 0.2);
    color: var(--primary-blue);
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
}

.ml-widget-date {
    color: var(--text-secondary);
    padding: 4px 8px;
}

.loading-spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* KPI Section (Primary Metrics with Hierarchy) */
.ml-kpi-section {
    margin-bottom: 32px;
}

.ml-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
}

.ml-kpi-card {
    background: var(--light-bg);
    border: 2px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    transition: all 0.2s ease;
}

.ml-kpi-card:hover {
    border-color: var(--primary-blue);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.ml-kpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.ml-kpi-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: none;
    letter-spacing: 0.3px;
}

.ml-kpi-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 8px;
    line-height: 1;
}

.ml-kpi-target {
    font-size: 11px;
    color: var(--text-secondary);
    opacity: 0.8;
}

/* Status Indicators */
.ml-status {
    font-size: 12px;
    font-weight: bold;
}

.ml-status-good {
    color: var(--success);
}

.ml-status-neutral {
    color: var(--warning);
}

.ml-status-bad {
    color: var(--danger);
}

.ml-status-none {
    color: var(--border-color);
}

/* Secondary Section - Portfolio Exposure */
.ml-secondary-section {
    margin-bottom: 28px;
    padding: 16px;
    background: var(--light-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.ml-section-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
    text-transform: none;
    margin: 0 0 12px 0;
    padding: 0;
    letter-spacing: 0.3px;
}

.ml-exposure-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
}

.ml-exposure-item {
    text-align: center;
}

.ml-exposure-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: none;
    margin-bottom: 4px;
}

.ml-exposure-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
}

.ml-exposure-value.positive {
    color: var(--success);
}

.ml-exposure-value.negative {
    color: var(--danger);
}

/* Tertiary Section - Coverage */
.ml-tertiary-section {
    padding: 12px;
    background: transparent;
}

.ml-coverage-stat {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.ml-coverage-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
}

.ml-coverage-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
}

.ml-widget-warning {
    background: rgba(245, 158, 11, 0.1);
    border-left: 4px solid var(--warning);
    color: var(--warning);
    padding: 12px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 13px;
}

.ml-widget-empty .ml-widget-content,
.ml-widget-error .ml-widget-content {
    text-align: center;
    padding: 20px;
    color: var(--text-secondary);
}

.ml-widget-help {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 8px;
    opacity: 0.8;
}

.ml-widget-error-text {
    color: var(--danger);
    font-weight: 600;
}

/* Action Buttons */
.ml-widget-actions {
    display: flex;
    gap: 8px;
    margin-top: 20px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
}

.btn {
    flex: 1;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--card-bg);
    color: var(--text-primary);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn:hover {
    background: var(--light-bg);
    border-color: var(--primary-blue);
    color: var(--primary-blue);
}

.btn.btn-secondary {
    background: var(--light-bg);
    border-color: var(--border-color);
    color: var(--text-primary);
}

/* Modal */
.ml-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.ml-modal-content {
    background: var(--card-bg);
    border-radius: 8px;
    max-width: 900px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 20px 25px rgba(0, 0, 0, 0.15);
    border: 1px solid var(--border-color);
}

.ml-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    background: var(--card-bg);
}

.ml-modal-header h2 {
    margin: 0;
    font-size: 18px;
    color: var(--text-primary);
}

.ml-modal-close {
    background: none;
    border: none;
    font-size: 24px;
    color: var(--text-secondary);
    cursor: pointer;
}

.ml-modal-close:hover {
    color: var(--text-primary);
}

.ml-modal-body {
    padding: 20px;
}

.ml-history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.ml-history-table thead {
    background: var(--light-bg);
    border-bottom: 2px solid var(--border-color);
}

.ml-history-table th {
    padding: 12px;
    text-align: left;
    font-weight: 600;
    color: var(--text-primary);
    text-transform: none;
    font-size: 11px;
}

.ml-history-table td {
    padding: 12px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-primary);
}

.ml-history-table tbody tr:hover {
    background: var(--light-bg);
}

/* Responsive */
@media (max-width: 768px) {
    .ml-kpi-grid {
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }
    
    .ml-exposure-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .ml-kpi-value {
        font-size: 22px;
    }
    
    .ml-widget-header {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .ml-widget-meta {
        margin-top: 12px;
        width: 100%;
    }
    
    .ml-modal-content {
        width: 95%;
    }
}`;

// Inject CSS on page load
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        const style = document.createElement("style");
        style.textContent = ML_WIDGET_CSS;
        document.head.appendChild(style);
    });
} else {
    const style = document.createElement("style");
    style.textContent = ML_WIDGET_CSS;
    document.head.appendChild(style);
}
