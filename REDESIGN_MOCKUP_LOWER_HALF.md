# Factor Analysis Page - Lower Half Redesign Mockup

## Current Issues
1. **No visual rhythm** — all panels same size, equal weight
2. **Orange circle score** — looks unintentional
3. **Colored text headers** — blue, teal inconsistency
4. **Inline explainers** — "What are these zones?" feels like tutorial
5. **Watchlist buttons** — destructive (red) should be subtle
6. **Page structure** — no clear tab nav, everything scrolls

---

## New Layout Structure

### TOP SECTION (Already redesigned ✓)
```
┌─────────────────────────────────────────────────────┐
│ AAPL | $190.25 | +2.3% today                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ● Buy signal                                       │
│  Based on momentum, macro, and sentiment            │
│                                                     │
│  Signal strength: ████████░░ 52/100                 │
│                                                     │
│  Key metrics                                        │
│  ┌──────────┬──────────┬──────────┬──────────┐      │
│  │Factor    │Momentum  │RSI       │Sentiment │      │
│  │52/100    │+12.3%    │65        │Positive  │      │
│  │Momentum  │12-month  │Overbought│4 bullish │      │
│  └──────────┴──────────┴──────────┴──────────┘      │
│                                                     │
│  AI Analysis                                        │
│  ℹ️ AAPL is showing strong bullish signals...       │
│                                                     │
│  Recommendation                                     │
│  ✓ Buy signal: With a factor score of 52/100...    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### MIDDLE SECTION - Analysis Tabs (NEW)
```
┌─────────────────────────────────────────────────────┐
│ Analysis | Chart | Watchlist                        │
├─────────────────────────────────────────────────────┤
│ (Content changes based on selected tab)             │
└─────────────────────────────────────────────────────┘
```

**Benefits:**
- Clear navigation between Analysis / Chart / Watchlist
- No more scrolling through everything
- Users see what they need

---

## ANALYSIS TAB - "Deep Dive" Sections

### Visual Hierarchy Fix

**OLD:** All panels equal size
```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Factor      │ │ Macro       │ │ Sentiment   │
│ Score       │ │ Context     │ │             │
│ [Big 52]    │ │             │ │             │
└─────────────┘ └─────────────┘ └─────────────┘

┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Signal      │ │ Entry/Exit  │ │ Market      │
│ Timing      │ │ Zones       │ │ Correlation │
└─────────────┘ └─────────────┘ └─────────────┘
```

**NEW:** Clear visual hierarchy
```
┌───────────────────────────────────────────────────┐
│ FACTOR SCORE                                      │
│                                                   │
│ 52/100  (Momentum signal)                        │
│                                                   │
│ 12-month momentum: +12.3% ↗️                      │
│ This stock is outperforming the market.          │
│                                                   │
│ ─────────────────────────────────────────────── │
│                                                   │
│ PRIMARY INSIGHTS:                                │
│ • Strong technical momentum (RSI: 65)            │
│ • Positive recent news (4 bullish articles)      │
│ • Market conditions favorable (VIX: 18)          │
└───────────────────────────────────────────────────┘

┌────────────────────────┬────────────────────────┐
│ MACRO CONTEXT          │ MARKET SENTIMENT       │
├────────────────────────┼────────────────────────┤
│ VIX: 18 (Normal)       │ Bullish articles: 4    │
│ 10Y Yield: 4.2%        │ Bearish articles: 1    │
│ Sector: Tech           │ Overall: Positive      │
│                        │ Mixed news flow        │
└────────────────────────┴────────────────────────┘

┌─────────────────────────────────────────────────┐
│ ENTRY & EXIT ZONES                              │
│ (Technical price levels — removed explainers)   │
│                                                 │
│ Buy Zones (Support)          Sell Zones (Resist)│
│ ┌─────────────────────┐     ┌─────────────────┐│
│ │ $165 Conservative   │     │ $220 Conservative││
│ │ $172 Moderate       │     │ $235 Moderate    ││
│ │ $185 Aggressive     │     │ $250 Ambitious   ││
│ └─────────────────────┘     └─────────────────┘│
│                                                 │
│ Current price: $185                             │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ SIGNAL TIMING (Backtesting)                     │
│ If you'd bought at previous signal strengths:   │
│                                                 │
│ 1 day ago:   $183 → $190 (+3.8%) ✓              │
│ 1 week ago:  $180 → $190 (+5.6%) ✓              │
│ 1 month ago: $175 → $190 (+8.6%) ✓              │
│ 3 months ago: $168 → $190 (+13.1%) ✓            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ MARKET CORRELATION                              │
│ How this stock moves with indices:              │
│                                                 │
│ S&P 500:   R² = 0.87 (Tracks market closely)   │
│ Nasdaq:    R² = 0.92 (Tech correlation)        │
│ Tech ETF:  R² = 0.94 (Sector correlation)      │
│                                                 │
│ Interpretation: AAPL moves with tech sector.   │
│ When Nasdaq rises, AAPL usually rises too.     │
└─────────────────────────────────────────────────┘
```

---

## Specific Fixes Applied

### 1. Factor Score Section
**OLD:**
```html
<div class="score-display">
    <div class="score-circle" id="score-circle"></div>  ← Big orange blob
    <div class="score-info">...
```

**NEW:**
```
52/100  (Momentum signal)

Text explanation of what it means, not a giant circle.
- Uses number + context
- Removes orange blob that looks unintentional
```

### 2. Section Headers
**OLD:**
```html
<div class="panel-title">📈 Factor Score</div>  ← Emoji + colored text
<div class="panel-title">🌍 Macro Context</div>
```

**NEW:**
```
FACTOR SCORE              ← White text, uppercase label
Entry & Exit Zones        ← White text, sentence case
Signal Timing             ← Consistent throughout
Market Correlation        ← No emojis, clean
```

### 3. Entry & Exit Zones
**OLD:**
```html
<p style="margin-bottom: 12px; padding: 12px; background: #F0FDF4; ...">
    <strong>What are these zones?</strong> Green zones = good price to buy...
</p>
```

**NEW:**
```
ENTRY & EXIT ZONES
Technical price levels — recommended buy/sell points

Buy Zones (Support)    |  Sell Zones (Resistance)
$165 Conservative      |  $220 Conservative
$172 Moderate          |  $235 Moderate
$185 Aggressive        |  $250 Ambitious

Current price: $185
```

**Why this is better:**
- Removed tutorial-style "What are these zones?"
- Put explanation in section subtitle: "Technical price levels..."
- Users understand immediately (implied: these are entry/exit targets)
- Cleaner, more professional

### 4. Watchlist Tab Buttons
**OLD:**
```html
<button id="add-to-watchlist" class="add-watchlist-btn">⭐ Add Current Ticker</button>
<button id="delete-watchlist-btn" style="background: #e74c3c;">🗑️ Delete</button>  ← Red
```

**NEW:**
```
Add to watchlist  ← Blue/primary button (constructive)
Remove            ← Ghost button, muted text (destructive)
```

**CSS:**
```css
.btn-remove {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

.btn-remove:hover {
    background: rgba(239, 68, 68, 0.05);
    border-color: var(--danger);
    color: var(--danger);
}
```

### 5. Tab Navigation (NEW)
**Add this below the header, before analysis panels:**
```html
<div class="tabs-nav">
    <button class="tab-link active" data-tab="analysis">Analysis</button>
    <button class="tab-link" data-tab="chart">Chart</button>
    <button class="tab-link" data-tab="watchlist">Watchlist</button>
</div>
```

**CSS:**
```css
.tabs-nav {
    display: flex;
    gap: 24px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 32px;
    padding-bottom: 16px;
}

.tab-link {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 1em;
    font-weight: 500;
    cursor: pointer;
    padding: 0;
    position: relative;
    transition: color 0.2s;
}

.tab-link:hover {
    color: var(--text-primary);
}

.tab-link.active {
    color: var(--primary-blue);
}

.tab-link.active::after {
    content: '';
    position: absolute;
    bottom: -16px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--primary-blue);
}
```

### 6. Grid Layout Hierarchy
**OLD:**
```css
.panels-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 24px;
}
```

**NEW:**
```css
.panels-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 32px;
}

/* Factor Score takes full width */
.panel:nth-child(1) {
    grid-column: 1;
}

/* Macro + Sentiment side-by-side */
.panel:nth-child(2),
.panel:nth-child(3) {
    display: inline-grid;
    width: 48%;
}

/* Entry/Exit & Correlation full width */
.panel:nth-child(5),
.panel:nth-child(6) {
    grid-column: 1;
}

/* Hide on mobile, show on desktop */
@media (max-width: 768px) {
    .panel {
        width: 100% !important;
    }
}
```

---

## Color / Typography Updates

### Section Headers
```css
.panel-title {
    font-size: 0.75em;           ← Small
    text-transform: uppercase;   ← UPPERCASE
    letter-spacing: 0.05em;
    color: var(--text-secondary); ← Gray, not blue
    font-weight: 600;
    margin-bottom: 16px;
}
```

### Panel Content
```css
.panel-content {
    font-size: 1em;
    color: var(--text-primary);
    line-height: 1.6;
}
```

### Value Display
```css
.value {
    font-size: 1.5em;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.value-detail {
    font-size: 0.85em;
    color: var(--text-secondary);
}
```

---

## Implementation Checklist

- [ ] Remove orange `score-circle` div, replace with text
- [ ] Remove emoji from all section headers
- [ ] Change colored headers to white text
- [ ] Remove inline "What are these zones?" explainers
- [ ] Add tab navigation above results
- [ ] Make Macro + Sentiment side-by-side on desktop
- [ ] Make Entry/Exit zones full-width
- [ ] Update watchlist delete button to ghost style
- [ ] Update grid breakpoints for mobile
- [ ] Test dark/light mode contrast
- [ ] Add subtle hover effects to cards

---

## Expected Result

**Visual improvement:**
- Clear hierarchy: Factor Score → Macro/Sentiment → Entry/Exit → Correlation
- Professional appearance: no emojis, consistent headers
- Better navigation: tabs instead of infinite scroll
- Cleaner watchlist: destructive actions subtle

**User experience:**
- Users see most important info first
- Secondary info in 2-column layout
- Deep dives available but not cluttering main flow
- Mobile-responsive and touch-friendly

