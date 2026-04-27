// ========================================
// GLOBAL DARK MODE SYSTEM
// Shared across all pages
// ========================================

function initThemeToggle() {
    const darkModeBtn = document.getElementById('dark-mode-btn');
    const lightModeBtn = document.getElementById('light-mode-btn');
    const html = document.documentElement;
    
    if (!darkModeBtn || !lightModeBtn) {
        console.warn('⚠️ Theme toggle buttons not found');
        return;
    }
    
    // Load saved preference or default to light mode
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        html.classList.add('dark-mode');
        darkModeBtn.classList.add('active');
        lightModeBtn.classList.remove('active');
    }
    
    darkModeBtn.addEventListener('click', () => {
        html.classList.add('dark-mode');
        darkModeBtn.classList.add('active');
        lightModeBtn.classList.remove('active');
        localStorage.setItem('theme', 'dark');
        
        // Re-render any charts if they exist
        if (typeof renderPortfolioChart === 'function') {
            setTimeout(() => renderPortfolioChart(), 100);
        }
        
        console.log('🌙 Dark mode enabled');
    });
    
    lightModeBtn.addEventListener('click', () => {
        html.classList.remove('dark-mode');
        lightModeBtn.classList.add('active');
        darkModeBtn.classList.remove('active');
        localStorage.setItem('theme', 'light');
        
        // Re-render any charts if they exist
        if (typeof renderPortfolioChart === 'function') {
            setTimeout(() => renderPortfolioChart(), 100);
        }
        
        console.log('☀️ Light mode enabled');
    });
}

// Initialize theme when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeToggle);
} else {
    initThemeToggle();
}

// Also initialize on window load
window.addEventListener('load', initThemeToggle);
