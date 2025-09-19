/**
 * Flight Price Tracker - Tracking Page JavaScript Module
 * 
 * Handles loading, displaying, and managing flight tracking requests
 * with price history visualization and interactive controls.
 */

// API Configuration
const API_CONFIG = {
    baseUrl: window.location.origin.includes('localhost') 
        ? 'http://localhost:8000'
        : window.location.origin,
    endpoints: {
        trackingRequests: '/api/v1/tracking',
        priceHistory: '/api/v1/tracking/{id}/history'
    },
    timeout: 30000
};

/**
 * Main Tracking Page Application Class
 */
class TrackingApp {
    constructor() {
        this.currentChatId = null;
        this.trackingRequests = [];
        this.filteredRequests = [];
        this.currentChart = null;
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    /**
     * Initialize the application
     */
    init() {
        try {
            this.cacheElements();
            this.setupEventListeners();
            this.loadChatIdFromStorage();
            console.log('Tracking App initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Tracking App:', error);
            this.showMessage('Application failed to initialize. Please refresh the page.', 'error');
        }
    }

    /**
     * Cache DOM elements for better performance
     */
    cacheElements() {
        // Input elements
        this.chatIdInput = document.getElementById('chat-id-input');
        this.loadTrackingBtn = document.getElementById('load-tracking-btn');
        this.statusFilter = document.getElementById('status-filter');
        this.sortSelect = document.getElementById('sort-select');
        this.refreshBtn = document.getElementById('refresh-btn');

        // Display elements
        this.messagesContainer = document.getElementById('system-messages');
        this.trackingOverview = document.getElementById('tracking-overview');
        this.trackingControls = document.getElementById('tracking-controls');
        this.trackingList = document.getElementById('tracking-list');
        this.requestsGrid = document.getElementById('tracking-requests');
        this.emptyState = document.getElementById('empty-state');
        this.loadingState = document.getElementById('loading-state');

        // Statistics elements
        this.activeCount = document.getElementById('active-count');
        this.expiredCount = document.getElementById('expired-count');
        this.alertsCount = document.getElementById('alerts-count');

        // Modal elements
        this.priceHistoryModal = document.getElementById('price-history-modal');
        this.deleteModal = document.getElementById('delete-modal');
        this.priceChart = document.getElementById('price-chart');
        this.priceStats = document.getElementById('price-stats');
        this.deleteRequestDetails = document.getElementById('delete-request-details');
        this.confirmDeleteBtn = document.getElementById('confirm-delete-btn');

        // Template
        this.cardTemplate = document.getElementById('tracking-card-template');

        // Error elements
        this.chatIdError = document.getElementById('chat-id-error');
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Chat ID input and loading
        this.chatIdInput.addEventListener('input', () => this.validateChatId());
        this.chatIdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.loadTrackingRequests();
            }
        });
        this.loadTrackingBtn.addEventListener('click', () => this.loadTrackingRequests());

        // Filters and controls
        this.statusFilter.addEventListener('change', () => this.applyFilters());
        this.sortSelect.addEventListener('change', () => this.applyFilters());
        this.refreshBtn.addEventListener('click', () => this.refreshData());

        // Modal events
        this.setupModalEventListeners();

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    /**
     * Set up modal event listeners
     */
    setupModalEventListeners() {
        // Price history modal
        const priceModalCloseButtons = this.priceHistoryModal.querySelectorAll('.modal__close, .modal-close');
        priceModalCloseButtons.forEach(btn => {
            btn.addEventListener('click', () => this.closePriceHistoryModal());
        });

        // Delete modal  
        const deleteModalCloseButtons = this.deleteModal.querySelectorAll('.modal__close, .modal-close');
        deleteModalCloseButtons.forEach(btn => {
            btn.addEventListener('click', () => this.closeDeleteModal());
        });

        this.confirmDeleteBtn.addEventListener('click', () => this.confirmDelete());

        // Click outside to close modals
        [this.priceHistoryModal, this.deleteModal].forEach(modal => {
            modal.querySelector('.modal__overlay').addEventListener('click', () => {
                if (modal === this.priceHistoryModal) {
                    this.closePriceHistoryModal();
                } else {
                    this.closeDeleteModal();
                }
            });
        });

        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closePriceHistoryModal();
                this.closeDeleteModal();
            }
        });
    }

    /**
     * Load chat ID from localStorage
     */
    loadChatIdFromStorage() {
        const storedChatId = localStorage.getItem('flight-tracker-chat-id');
        if (storedChatId) {
            this.chatIdInput.value = storedChatId;
            this.validateChatId();
        }
    }

    /**
     * Validate chat ID input
     */
    validateChatId() {
        const chatId = this.chatIdInput.value.trim();
        const isValid = /^-?\d+$/.test(chatId);

        this.clearFieldError('chat-id');

        if (chatId && !isValid) {
            this.showFieldError('chat-id', 'Please enter a valid Telegram Chat ID (numbers only)');
            this.loadTrackingBtn.disabled = true;
            return false;
        }

        this.loadTrackingBtn.disabled = !chatId;
        return isValid || !chatId;
    }

    /**
     * Load tracking requests for the current chat ID
     */
    async loadTrackingRequests() {
        if (!this.validateChatId()) {
            return;
        }

        const chatId = this.chatIdInput.value.trim();
        
        try {
            this.setLoadingState(true);
            this.currentChatId = chatId;
            
            // Store chat ID for future use
            localStorage.setItem('flight-tracker-chat-id', chatId);

            // Fetch tracking requests
            const requests = await this.fetchTrackingRequests(chatId);
            this.trackingRequests = requests;
            this.applyFilters();
            this.updateOverview();
            this.showTrackingContent();
            
            this.showMessage(`Loaded ${requests.length} tracking request${requests.length !== 1 ? 's' : ''}`, 'success');

        } catch (error) {
            console.error('Failed to load tracking requests:', error);
            this.handleApiError(error);
        } finally {
            this.setLoadingState(false);
        }
    }

    /**
     * Fetch tracking requests from API
     */
    async fetchTrackingRequests(chatId) {
        const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.trackingRequests}?telegram_chat_id=${encodeURIComponent(chatId)}`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            },
            signal: AbortSignal.timeout(API_CONFIG.timeout)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data.requests || [];
    }

    /**
     * Apply filters and sorting to requests
     */
    applyFilters() {
        let filtered = [...this.trackingRequests];

        // Apply status filter
        const statusFilter = this.statusFilter.value;
        if (statusFilter !== 'all') {
            const now = new Date();
            filtered = filtered.filter(request => {
                const isExpired = new Date(request.expires_at) < now;
                if (statusFilter === 'active') {
                    return request.is_active && !isExpired;
                } else if (statusFilter === 'expired') {
                    return !request.is_active || isExpired;
                }
                return true;
            });
        }

        // Apply sorting
        const sortBy = this.sortSelect.value;
        filtered.sort((a, b) => {
            switch (sortBy) {
                case 'created_desc':
                    return new Date(b.created_at) - new Date(a.created_at);
                case 'created_asc':
                    return new Date(a.created_at) - new Date(b.created_at);
                case 'departure_asc':
                    return new Date(a.departure_date) - new Date(b.departure_date);
                case 'price_desc':
                    const priceA = this.getCurrentPrice(a);
                    const priceB = this.getCurrentPrice(b);
                    return priceA - priceB;
                default:
                    return 0;
            }
        });

        this.filteredRequests = filtered;
        this.renderTrackingRequests();
    }

    /**
     * Get current price for a tracking request
     */
    getCurrentPrice(request) {
        if (request.price_history && request.price_history.length > 0) {
            const latest = request.price_history[request.price_history.length - 1];
            return latest.price || Infinity;
        }
        return Infinity;
    }

    /**
     * Update overview statistics
     */
    updateOverview() {
        const now = new Date();
        const activeCount = this.trackingRequests.filter(r => 
            r.is_active && new Date(r.expires_at) >= now
        ).length;
        const expiredCount = this.trackingRequests.filter(r => 
            !r.is_active || new Date(r.expires_at) < now
        ).length;
        const totalAlerts = this.trackingRequests.reduce((sum, r) => 
            sum + (r.notification_count || 0), 0
        );

        this.activeCount.textContent = activeCount;
        this.expiredCount.textContent = expiredCount;
        this.alertsCount.textContent = totalAlerts;
    }

    /**
     * Show tracking content sections
     */
    showTrackingContent() {
        this.trackingOverview.classList.remove('hidden');
        this.trackingControls.classList.remove('hidden');
        this.trackingList.classList.remove('hidden');
    }

    /**
     * Render tracking request cards
     */
    renderTrackingRequests() {
        this.requestsGrid.innerHTML = '';

        if (this.filteredRequests.length === 0) {
            this.emptyState.classList.remove('hidden');
            return;
        }

        this.emptyState.classList.add('hidden');

        this.filteredRequests.forEach(request => {
            const card = this.createTrackingCard(request);
            this.requestsGrid.appendChild(card);
        });
    }

    /**
     * Create a tracking request card
     */
    createTrackingCard(request) {
        const template = this.cardTemplate.content.cloneNode(true);
        const card = template.querySelector('.tracking-card');
        
        // Set request ID
        card.setAttribute('data-request-id', request.id);

        // Fill in basic information
        card.querySelector('.origin').textContent = request.origin;
        card.querySelector('.destination').textContent = request.destination;
        card.querySelector('.departure-date').textContent = this.formatDate(request.departure_date);
        card.querySelector('.passengers').textContent = `${request.passengers} ${request.passengers === 1 ? 'passenger' : 'passengers'}`;
        card.querySelector('.cabin-class').textContent = this.formatCabinClass(request.cabin_class);
        card.querySelector('.expires-at').textContent = this.formatDate(request.expires_at);

        // Route type
        const routeType = request.return_date ? 'Round Trip' : 'One Way';
        card.querySelector('.route-type').textContent = routeType;

        // Return date (only for round trips)
        const returnDateRow = card.querySelector('.return-date-row');
        if (request.return_date) {
            card.querySelector('.return-date').textContent = this.formatDate(request.return_date);
        } else {
            returnDateRow.style.display = 'none';
        }

        // Max price (only if set)
        const maxPriceRow = card.querySelector('.max-price-row');
        if (request.max_price) {
            card.querySelector('.max-price').textContent = this.formatCurrency(request.max_price);
        } else {
            maxPriceRow.style.display = 'none';
        }

        // Status badge
        const statusBadge = card.querySelector('.status-badge');
        const now = new Date();
        const isExpired = new Date(request.expires_at) < now;
        
        if (request.is_active && !isExpired) {
            statusBadge.textContent = 'Active';
            statusBadge.className = 'status-badge status-badge--active';
        } else if (isExpired) {
            statusBadge.textContent = 'Expired';
            statusBadge.className = 'status-badge status-badge--expired';
        } else {
            statusBadge.textContent = 'Inactive';
            statusBadge.className = 'status-badge status-badge--inactive';
        }

        // Price information
        this.updatePriceDisplay(card, request);

        // Event listeners for actions
        const viewHistoryBtn = card.querySelector('.view-history-btn');
        const deleteBtn = card.querySelector('.delete-btn');

        viewHistoryBtn.addEventListener('click', () => this.showPriceHistory(request));
        deleteBtn.addEventListener('click', () => this.showDeleteConfirmation(request));

        return card;
    }

    /**
     * Update price display for a card
     */
    updatePriceDisplay(card, request) {
        const priceAmount = card.querySelector('.price-amount');
        const priceTrend = card.querySelector('.price-trend');
        const updateTime = card.querySelector('.update-time');

        if (request.price_history && request.price_history.length > 0) {
            const sortedHistory = [...request.price_history].sort((a, b) => 
                new Date(a.checked_at) - new Date(b.checked_at)
            );
            const latest = sortedHistory[sortedHistory.length - 1];
            
            priceAmount.textContent = this.formatCurrency(latest.price);
            updateTime.textContent = this.formatRelativeTime(latest.checked_at);

            // Show price trend
            if (sortedHistory.length > 1) {
                const previous = sortedHistory[sortedHistory.length - 2];
                const change = latest.price - previous.price;
                
                if (change > 0) {
                    priceTrend.textContent = '↗️';
                    priceTrend.className = 'price-trend price-trend--up';
                    priceTrend.setAttribute('title', `+${this.formatCurrency(change)}`);
                } else if (change < 0) {
                    priceTrend.textContent = '↘️';
                    priceTrend.className = 'price-trend price-trend--down';
                    priceTrend.setAttribute('title', `${this.formatCurrency(change)}`);
                } else {
                    priceTrend.textContent = '→';
                    priceTrend.className = 'price-trend price-trend--same';
                    priceTrend.setAttribute('title', 'No change');
                }
            }
        } else {
            priceAmount.textContent = 'No data';
            updateTime.textContent = 'Never';
        }
    }

    /**
     * Show price history modal
     */
    async showPriceHistory(request) {
        try {
            this.setModalLoadingState(this.priceHistoryModal, true);
            
            // Update modal title
            document.getElementById('modal-title').textContent = 
                `Price History: ${request.origin} → ${request.destination}`;

            // Show modal
            this.priceHistoryModal.classList.add('visible');
            this.priceHistoryModal.setAttribute('aria-hidden', 'false');

            // Load detailed price history
            const priceHistory = await this.fetchPriceHistory(request.id);
            
            // Render chart and statistics
            this.renderPriceChart(priceHistory, request);
            this.renderPriceStatistics(priceHistory);

        } catch (error) {
            console.error('Failed to load price history:', error);
            this.showMessage('Failed to load price history. Please try again.', 'error');
            this.closePriceHistoryModal();
        } finally {
            this.setModalLoadingState(this.priceHistoryModal, false);
        }
    }

    /**
     * Fetch detailed price history
     */
    async fetchPriceHistory(requestId) {
        const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.priceHistory.replace('{id}', requestId)}`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            },
            signal: AbortSignal.timeout(API_CONFIG.timeout)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data.price_history || [];
    }

    /**
     * Render price chart using Chart.js
     */
    renderPriceChart(priceHistory, request) {
        const ctx = this.priceChart.getContext('2d');

        // Destroy existing chart
        if (this.currentChart) {
            this.currentChart.destroy();
        }

        // Prepare data
        const sortedHistory = [...priceHistory].sort((a, b) => 
            new Date(a.checked_at) - new Date(b.checked_at)
        );

        const labels = sortedHistory.map(item => 
            new Date(item.checked_at).toLocaleDateString()
        );
        const prices = sortedHistory.map(item => item.price);

        // Create chart
        this.currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Price (USD)',
                    data: prices,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointBackgroundColor: '#2563eb',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: `${request.origin} → ${request.destination} Price History`
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    }
                },
                elements: {
                    point: {
                        hoverRadius: 8
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }

    /**
     * Render price statistics
     */
    renderPriceStatistics(priceHistory) {
        if (priceHistory.length === 0) {
            this.priceStats.innerHTML = '<p>No price data available.</p>';
            return;
        }

        const prices = priceHistory.map(item => item.price);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        const avgPrice = prices.reduce((sum, price) => sum + price, 0) / prices.length;
        const currentPrice = prices[prices.length - 1];

        const stats = [
            { label: 'Current Price', value: this.formatCurrency(currentPrice) },
            { label: 'Lowest Price', value: this.formatCurrency(minPrice) },
            { label: 'Highest Price', value: this.formatCurrency(maxPrice) },
            { label: 'Average Price', value: this.formatCurrency(avgPrice) },
            { label: 'Price Checks', value: priceHistory.length.toString() }
        ];

        this.priceStats.innerHTML = stats.map(stat => `
            <div class="price-stat">
                <div class="price-stat__value">${stat.value}</div>
                <div class="price-stat__label">${stat.label}</div>
            </div>
        `).join('');
    }

    /**
     * Show delete confirmation modal
     */
    showDeleteConfirmation(request) {
        // Update modal content
        this.deleteRequestDetails.innerHTML = `
            <div class="delete-details__route">
                ${request.origin} → ${request.destination}
            </div>
            <div class="delete-details__dates">
                ${this.formatDate(request.departure_date)}${request.return_date ? ` - ${this.formatDate(request.return_date)}` : ''}
            </div>
        `;

        // Store request for deletion
        this.requestToDelete = request;

        // Show modal
        this.deleteModal.classList.add('visible');
        this.deleteModal.setAttribute('aria-hidden', 'false');
    }

    /**
     * Confirm and execute deletion
     */
    async confirmDelete() {
        if (!this.requestToDelete) {
            return;
        }

        try {
            this.setModalLoadingState(this.deleteModal, true);

            await this.deleteTrackingRequest(this.requestToDelete.id);
            
            // Remove from local data
            this.trackingRequests = this.trackingRequests.filter(
                r => r.id !== this.requestToDelete.id
            );
            
            // Update display
            this.applyFilters();
            this.updateOverview();
            
            this.showMessage('Tracking request deleted successfully.', 'success');
            this.closeDeleteModal();

        } catch (error) {
            console.error('Failed to delete tracking request:', error);
            this.showMessage('Failed to delete tracking request. Please try again.', 'error');
        } finally {
            this.setModalLoadingState(this.deleteModal, false);
        }
    }

    /**
     * Delete tracking request via API
     */
    async deleteTrackingRequest(requestId) {
        const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.trackingRequests}/${requestId}`;
        
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            },
            signal: AbortSignal.timeout(API_CONFIG.timeout)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
    }

    /**
     * Close price history modal
     */
    closePriceHistoryModal() {
        this.priceHistoryModal.classList.remove('visible');
        this.priceHistoryModal.setAttribute('aria-hidden', 'true');
        
        // Destroy chart to prevent memory leaks
        if (this.currentChart) {
            this.currentChart.destroy();
            this.currentChart = null;
        }
    }

    /**
     * Close delete confirmation modal
     */
    closeDeleteModal() {
        this.deleteModal.classList.remove('visible');
        this.deleteModal.setAttribute('aria-hidden', 'true');
        this.requestToDelete = null;
    }

    /**
     * Refresh data
     */
    async refreshData() {
        if (this.currentChatId) {
            this.refreshBtn.disabled = true;
            this.refreshBtn.querySelector('.btn__icon').style.animation = 'spin 1s linear infinite';
            
            try {
                await this.loadTrackingRequests();
            } finally {
                this.refreshBtn.disabled = false;
                this.refreshBtn.querySelector('.btn__icon').style.animation = '';
            }
        }
    }

    /**
     * Set loading state for the main content
     */
    setLoadingState(isLoading) {
        if (isLoading) {
            this.loadingState.classList.remove('hidden');
            this.loadTrackingBtn.disabled = true;
            this.loadTrackingBtn.classList.add('btn--loading');
        } else {
            this.loadingState.classList.add('hidden');
            this.loadTrackingBtn.disabled = false;
            this.loadTrackingBtn.classList.remove('btn--loading');
        }
    }

    /**
     * Set loading state for modals
     */
    setModalLoadingState(modal, isLoading) {
        const body = modal.querySelector('.modal__body');
        const footer = modal.querySelector('.modal__footer');
        
        if (isLoading) {
            body.style.opacity = '0.5';
            footer.style.pointerEvents = 'none';
        } else {
            body.style.opacity = '';
            footer.style.pointerEvents = '';
        }
    }

    /**
     * Handle API errors
     */
    handleApiError(error) {
        let message = 'An error occurred. Please try again.';
        
        if (error.message.includes('404')) {
            message = 'No tracking requests found for this Chat ID.';
        } else if (error.message.includes('400')) {
            message = 'Invalid Chat ID format. Please check and try again.';
        } else if (error.message.includes('429')) {
            message = 'Too many requests. Please wait a moment before trying again.';
        } else if (error.message.includes('500')) {
            message = 'Server error. Please try again later.';
        } else if (error.name === 'AbortError') {
            message = 'Request timed out. Please check your connection and try again.';
        }

        this.showMessage(message, 'error');
    }

    /**
     * Show system message
     */
    showMessage(text, type = 'info') {
        const messageEl = document.createElement('div');
        messageEl.className = `message message--${type}`;
        messageEl.textContent = text;
        messageEl.setAttribute('role', 'alert');
        
        this.messagesContainer.appendChild(messageEl);
        
        // Auto-remove success and info messages
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.remove();
                }
            }, 8000);
        }

        // Scroll to message
        messageEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Show field error
     */
    showFieldError(fieldName, message) {
        const errorElement = document.getElementById(`${fieldName}-error`);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.add('visible');
        }
    }

    /**
     * Clear field error
     */
    clearFieldError(fieldName) {
        const errorElement = document.getElementById(`${fieldName}-error`);
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.classList.remove('visible');
        }
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + R - refresh data
        if ((event.ctrlKey || event.metaKey) && event.key === 'r' && this.currentChatId) {
            event.preventDefault();
            this.refreshData();
        }
    }

    // Utility methods for formatting
    
    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    formatRelativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) {
            return 'Just now';
        } else if (diffMins < 60) {
            return `${diffMins}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else {
            return `${diffDays}d ago`;
        }
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }

    formatCabinClass(cabinClass) {
        const classMap = {
            'ECONOMY': 'Economy',
            'PREMIUM_ECONOMY': 'Premium Economy',
            'BUSINESS': 'Business',
            'FIRST': 'First Class'
        };
        return classMap[cabinClass] || cabinClass;
    }
}

// Initialize the tracking application
const trackingApp = new TrackingApp();

// Export for potential testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TrackingApp;
}