/**
 * AI Limited Edition Product Tracker — Frontend Logic
 * Fetch-based API client with auto-refresh, toast notifications, and relative timestamps.
 */

const API_BASE = '/api';
const REFRESH_INTERVAL = 30_000; // 30 seconds

// ── State ─────────────────────────────────────────

let products = [];
let alerts = [];
let stats = {};

// ── DOM Elements ──────────────────────────────────

const dom = {
    form: document.getElementById('add-product-form'),
    urlInput: document.getElementById('product-url-input'),
    addBtn: document.getElementById('add-product-btn'),
    btnText: null,
    btnLoader: null,
    productsGrid: document.getElementById('products-grid'),
    emptyState: document.getElementById('empty-state'),
    alertsList: document.getElementById('alerts-list'),
    alertsEmpty: document.getElementById('alerts-empty-state'),
    productCount: document.getElementById('product-count'),
    statTotal: document.getElementById('stat-total-value'),
    statAlerts: document.getElementById('stat-alerts-value'),
    statActive: document.getElementById('stat-active-value'),
    toastContainer: document.getElementById('toast-container'),
};

// ── Init ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    dom.btnText = dom.addBtn.querySelector('.btn-text');
    dom.btnLoader = dom.addBtn.querySelector('.btn-loader');

    dom.form.addEventListener('submit', handleAddProduct);

    // Initial load
    refreshAll();

    // Auto-refresh
    setInterval(refreshAll, REFRESH_INTERVAL);
});


// ── API Client ────────────────────────────────────

async function api(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const defaultHeaders = { 'Content-Type': 'application/json' };

    try {
        const response = await fetch(url, {
            headers: { ...defaultHeaders, ...options.headers },
            ...options,
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (err) {
        if (err.name === 'TypeError' && err.message.includes('fetch')) {
            throw new Error('Cannot connect to server. Is it running?');
        }
        throw err;
    }
}


// ── Data Refresh ──────────────────────────────────

async function refreshAll() {
    try {
        const [productsData, statsData, alertsData] = await Promise.all([
            api('/products'),
            api('/stats'),
            api('/alerts'),
        ]);

        products = productsData;
        stats = statsData;
        alerts = alertsData;

        renderStats();
        renderProducts();
        renderAlerts();
    } catch (err) {
        console.error('Refresh failed:', err);
    }
}


// ── Add Product ───────────────────────────────────

async function handleAddProduct(e) {
    e.preventDefault();

    const url = dom.urlInput.value.trim();
    if (!url) return;

    setLoading(true);

    try {
        await api('/products', {
            method: 'POST',
            body: JSON.stringify({ url }),
        });

        dom.urlInput.value = '';
        showToast('Product added! Monitoring will begin shortly.', 'success');
        await refreshAll();
    } catch (err) {
        showToast(err.message || 'Failed to add product', 'error');
    } finally {
        setLoading(false);
    }
}


// ── Force Check ───────────────────────────────────

async function forceCheck(productId) {
    const btn = document.querySelector(`[data-check-id="${productId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳';
    }

    try {
        await api(`/products/${productId}/check`, { method: 'POST' });
        showToast('Product checked successfully!', 'success');
        await refreshAll();
    } catch (err) {
        showToast(`Check failed: ${err.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄';
        }
    }
}


// ── Delete Product ────────────────────────────────

async function deleteProduct(productId) {
    if (!confirm('Stop tracking this product? All history will be deleted.')) return;

    try {
        await api(`/products/${productId}`, { method: 'DELETE' });
        showToast('Product removed.', 'info');
        await refreshAll();
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, 'error');
    }
}


// ── Renderers ─────────────────────────────────────

function renderStats() {
    dom.statTotal.textContent = stats.total_products ?? 0;
    dom.statAlerts.textContent = stats.alerts_today ?? 0;
    dom.statActive.textContent = stats.active_monitors ?? 0;
}

function renderProducts() {
    const count = products.length;
    dom.productCount.textContent = `${count} product${count !== 1 ? 's' : ''}`;

    if (count === 0) {
        dom.productsGrid.innerHTML = '';
        dom.emptyState.classList.add('visible');
        return;
    }

    dom.emptyState.classList.remove('visible');
    dom.productsGrid.innerHTML = products.map(p => createProductCard(p)).join('');
}

function createProductCard(product) {
    const {
        id, product_name, site_name, current_price, previous_price,
        currency, stock_status, stock_text, last_checked, last_error, url
    } = product;

    const siteInitial = (site_name || '?')[0].toUpperCase();
    const priceDisplay = current_price != null ? `${currency}${current_price.toFixed(2)}` : 'N/A';
    const prevPriceDisplay = previous_price != null ? `${currency}${previous_price.toFixed(2)}` : '';

    // Price trend
    let trendHtml = '';
    if (current_price != null && previous_price != null) {
        if (current_price < previous_price) {
            const pct = (((previous_price - current_price) / previous_price) * 100).toFixed(1);
            trendHtml = `<span class="price-trend down">↓ ${pct}%</span>`;
        } else if (current_price > previous_price) {
            const pct = (((current_price - previous_price) / previous_price) * 100).toFixed(1);
            trendHtml = `<span class="price-trend up">↑ ${pct}%</span>`;
        } else {
            trendHtml = `<span class="price-trend stable">→ 0%</span>`;
        }
    }

    // Stock badge
    const stockClass = stock_status.replace('_', '-');
    const stockLabel = stock_status.replace('_', ' ').toUpperCase();

    // Last checked
    const checkedText = last_checked ? `Checked ${timeAgo(last_checked)}` : 'Not checked yet';

    // Error
    const errorHtml = last_error
        ? `<div class="product-error">⚠️ ${escapeHtml(last_error.substring(0, 80))}</div>`
        : '';

    return `
        <div class="product-card" id="product-card-${id}">
            <div class="product-card-header">
                <div class="site-favicon">${siteInitial}</div>
                <div class="product-info">
                    <a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="product-name" title="${escapeHtml(product_name)}">
                        ${escapeHtml(product_name)}
                    </a>
                    <div class="product-site">${escapeHtml(site_name)}</div>
                </div>
            </div>
            <div class="product-card-body">
                <div class="price-section">
                    <div class="current-price">${priceDisplay}</div>
                    ${prevPriceDisplay ? `<div class="previous-price">${prevPriceDisplay}</div>` : ''}
                    ${trendHtml}
                </div>
                <span class="stock-badge ${stockClass}">${stockLabel}</span>
            </div>
            ${errorHtml}
            <div class="product-card-footer">
                <span class="last-checked">${checkedText}</span>
                <div class="card-actions">
                    <button class="btn-icon" data-check-id="${id}" onclick="forceCheck(${id})" title="Force check">🔄</button>
                    <button class="btn-icon danger" onclick="deleteProduct(${id})" title="Remove product">🗑️</button>
                </div>
            </div>
        </div>
    `;
}

function renderAlerts() {
    if (alerts.length === 0) {
        dom.alertsList.innerHTML = '';
        dom.alertsEmpty.classList.add('visible');
        return;
    }

    dom.alertsEmpty.classList.remove('visible');
    dom.alertsList.innerHTML = alerts.map(a => {
        const icon = getAlertIcon(a.alert_type);
        const time = a.sent_at ? timeAgo(a.sent_at) : '';

        return `
            <div class="alert-item">
                <span class="alert-icon">${icon}</span>
                <div class="alert-content">
                    <div class="alert-message">${escapeHtml(a.message)}</div>
                    <div class="alert-time">${time}</div>
                </div>
            </div>
        `;
    }).join('');
}


// ── Helpers ───────────────────────────────────────

function getAlertIcon(type) {
    const icons = {
        price_drop: '💰',
        back_in_stock: '🔔',
        low_stock: '⚠️',
        price_increase: '📈',
    };
    return icons[type] || 'ℹ️';
}

function timeAgo(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 60) return 'just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return date.toLocaleDateString();
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function setLoading(loading) {
    dom.addBtn.disabled = loading;
    dom.btnText.hidden = loading;
    dom.btnLoader.hidden = !loading;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    toast.innerHTML = `<span>${icons[type] || ''}</span><span>${escapeHtml(message)}</span>`;

    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toast-out 0.3s ease-out forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
