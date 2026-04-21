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
                <h3>🤖 ML Model Metrics</h3>
                <span class="loading-spinner">⟳</span>
            </div>
            <div class="ml-widget-content">Loading...</div>
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
    
    // Color coding for metrics
    const icColor = ic > 0.05 ? "good" : ic > 0 ? "neutral" : ic < 0 ? "bad" : "neutral";
    const hitRateColor = hitRate > 55 ? "good" : hitRate > 50 ? "neutral" : "bad";
    const sharpeColor = sharpe > 1.0 ? "good" : sharpe > 0.5 ? "neutral" : "bad";
    
    const warningHtml = data.warning 
        ? `<div class="ml-widget-warning">⚠️ ${data.warning}</div>` 
        : "";
    
    const html = `
        <div class="ml-widget-card">
            <div class="ml-widget-header">
                <h3>🤖 ML Model Metrics</h3>
                <div class="ml-widget-meta">
                    <span class="ml-widget-version">v${data.model_version}</span>
                    <span class="ml-widget-date">${data.as_of_date}</span>
                </div>
            </div>
            
            ${warningHtml}
            
            <div class="ml-widget-content">
                <!-- Performance Metrics -->
                <div class="ml-metrics-grid">
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">IC (Rank Correlation)</div>
                        <div class="ml-metric-value ${icColor}">${ic}</div>
                        <div class="ml-metric-hint">Target: > 0.05</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Hit Rate</div>
                        <div class="ml-metric-value ${hitRateColor}">${hitRate}%</div>
                        <div class="ml-metric-hint">Target: > 55%</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Sharpe Ratio</div>
                        <div class="ml-metric-value ${sharpeColor}">${sharpe}</div>
                        <div class="ml-metric-hint">Annualized</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Max Drawdown</div>
                        <div class="ml-metric-value">${maxDD}%</div>
                        <div class="ml-metric-hint">Worst period</div>
                    </div>
                </div>
                
                <!-- Portfolio Exposure -->
                <div class="ml-section-title">Portfolio Exposure</div>
                <div class="ml-metrics-grid">
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Long Exposure</div>
                        <div class="ml-metric-value positive">${longExp}%</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Short Exposure</div>
                        <div class="ml-metric-value negative">${shortExp}%</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Gross Leverage</div>
                        <div class="ml-metric-value">${grossLev}%</div>
                    </div>
                    
                    <div class="ml-metric-card">
                        <div class="ml-metric-label">Avg Turnover</div>
                        <div class="ml-metric-value">${turnover}%</div>
                        <div class="ml-metric-hint">Per rebalance</div>
                    </div>
                </div>
                
                <!-- Coverage -->
                <div class="ml-section-title">Coverage</div>
                <div class="ml-metric-card">
                    <div class="ml-metric-label">Stocks Scored</div>
                    <div class="ml-metric-value">${validScores} / ${universeSize}</div>
                    <div class="ml-metric-hint">${coverage_pct}% of universe</div>
                </div>
                
                <!-- Action Buttons -->
                <div class="ml-widget-actions">
                    <button class="btn btn-secondary" onclick="showMLMetricsHistory()">
                        📈 View History
                    </button>
                    <button class="btn btn-secondary" onclick="downloadMLMetrics()">
                        📥 Download
                    </button>
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
                    <h2>📊 ML Backtest History</h2>
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
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--border-color);
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

/* Metrics Grid */
.ml-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}

.ml-metric-card {
    background: var(--light-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 12px;
    text-align: center;
}

.ml-metric-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: none;
    margin-bottom: 8px;
}

.ml-metric-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.ml-metric-value.good {
    color: var(--success);
}

.ml-metric-value.neutral {
    color: var(--warning);
}

.ml-metric-value.bad {
    color: var(--danger);
}

.ml-metric-value.positive {
    color: var(--success);
}

.ml-metric-value.negative {
    color: var(--danger);
}

.ml-metric-hint {
    font-size: 10px;
    color: var(--text-secondary);
    opacity: 0.7;
}

.ml-section-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-secondary);
    text-transform: none;
    margin: 20px 0 12px 0;
    padding: 8px 0;
    border-bottom: 2px solid var(--border-color);
    letter-spacing: 0.3px;
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
    .ml-metrics-grid {
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
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
