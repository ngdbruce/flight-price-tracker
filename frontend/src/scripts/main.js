/**
 * Flight Price Tracker - Main JavaScript Module
 * 
 * Handles form validation, API communication, UI interactions, and
 * progressive enhancement for the flight tracking application.
 */

// API Configuration
const API_CONFIG = {
    baseUrl: window.location.origin.includes('localhost') 
        ? 'http://localhost:8000'
        : window.location.origin,
    endpoints: {
        trackingRequests: '/api/v1/tracking',
        flightSearch: '/api/v1/flights/search',
        health: '/api/v1/health'
    },
    timeout: 30000 // 30 seconds
};

// Validation patterns and rules
const VALIDATION_RULES = {
    iataCode: {
        pattern: /^[A-Z]{3}$/,
        message: 'Please enter a valid 3-letter airport code (e.g., JFK)'
    },
    telegramChatId: {
        pattern: /^-?\d+$/,
        message: 'Please enter a valid Telegram Chat ID (numbers only)'
    },
    maxPrice: {
        min: 1,
        max: 50000,
        message: 'Price must be between $1 and $50,000'
    },
    dateRange: {
        maxDays: 365,
        message: 'Travel dates must be within the next year'
    }
};

// Common IATA airport codes for suggestions
const COMMON_AIRPORTS = {
    'JFK': 'John F. Kennedy International Airport - New York',
    'LAX': 'Los Angeles International Airport - California',
    'LHR': 'London Heathrow Airport - United Kingdom',
    'CDG': 'Charles de Gaulle Airport - Paris',
    'DXB': 'Dubai International Airport - UAE',
    'NRT': 'Narita International Airport - Tokyo',
    'SIN': 'Singapore Changi Airport - Singapore',
    'FRA': 'Frankfurt Airport - Germany',
    'AMS': 'Amsterdam Airport Schiphol - Netherlands',
    'ICN': 'Incheon International Airport - Seoul'
};

/**
 * Main Application Class
 */
class FlightTracker {
    constructor() {
        this.form = null;
        this.loadingOverlay = null;
        this.submitButton = null;
        this.currentRequest = null;
        
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
            this.initializeForm();
            this.setupAccessibility();
            console.log('Flight Tracker initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Flight Tracker:', error);
            this.showMessage('Application failed to initialize. Please refresh the page.', 'error');
        }
    }

    /**
     * Cache DOM elements for better performance
     */
    cacheElements() {
        this.form = document.getElementById('tracking-form');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.submitButton = document.getElementById('submit-btn');
        this.messagesContainer = document.getElementById('system-messages');
        
        // Form fields
        this.fields = {
            tripType: document.getElementsByName('tripType'),
            origin: document.getElementById('origin'),
            destination: document.getElementById('destination'),
            departureDate: document.getElementById('departure-date'),
            returnDate: document.getElementById('return-date'),
            passengers: document.getElementById('passengers'),
            cabinClass: document.getElementById('cabin-class'),
            maxPrice: document.getElementById('max-price'),
            telegramChatId: document.getElementById('telegram-chat-id'),
            trackingDuration: document.getElementById('tracking-duration'),
            priceAlerts: document.getElementById('price-alerts'),
            expiryAlerts: document.getElementById('expiry-alerts')
        };

        // Validation elements
        this.errorElements = {
            origin: document.getElementById('origin-error'),
            destination: document.getElementById('destination-error'),
            departureDate: document.getElementById('departure-date-error'),
            returnDate: document.getElementById('return-date-error'),
            passengers: document.getElementById('passengers-error'),
            maxPrice: document.getElementById('max-price-error'),
            telegramChatId: document.getElementById('telegram-error')
        };

        // Other UI elements
        this.swapButton = document.querySelector('.swap-button');
        this.returnDateGroup = document.getElementById('return-date-group');
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        
        // Form reset
        this.form.addEventListener('reset', (e) => this.handleFormReset(e));

        // Trip type change
        this.fields.tripType.forEach(radio => {
            radio.addEventListener('change', (e) => this.handleTripTypeChange(e));
        });

        // Airport swap
        this.swapButton.addEventListener('click', (e) => this.handleAirportSwap(e));

        // Real-time validation
        this.setupRealTimeValidation();

        // Date validation
        this.fields.departureDate.addEventListener('change', (e) => this.validateDates());
        this.fields.returnDate.addEventListener('change', (e) => this.validateDates());

        // Airport code formatting
        this.fields.origin.addEventListener('input', (e) => this.formatAirportCode(e));
        this.fields.destination.addEventListener('input', (e) => this.formatAirportCode(e));

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Window events
        window.addEventListener('beforeunload', (e) => this.handleBeforeUnload(e));
        
        // Network status
        window.addEventListener('online', () => this.handleNetworkChange(true));
        window.addEventListener('offline', () => this.handleNetworkChange(false));
    }

    /**
     * Initialize form with default values and constraints
     */
    initializeForm() {
        // Set minimum dates
        const today = new Date().toISOString().split('T')[0];
        this.fields.departureDate.setAttribute('min', today);
        this.fields.returnDate.setAttribute('min', today);

        // Set maximum dates (1 year from now)
        const maxDate = new Date();
        maxDate.setFullYear(maxDate.getFullYear() + 1);
        const maxDateString = maxDate.toISOString().split('T')[0];
        this.fields.departureDate.setAttribute('max', maxDateString);
        this.fields.returnDate.setAttribute('max', maxDateString);

        // Set default passenger count
        if (!this.fields.passengers.value) {
            this.fields.passengers.value = '1';
        }

        // Initialize trip type state
        this.handleTripTypeChange();
    }

    /**
     * Set up accessibility enhancements
     */
    setupAccessibility() {
        // Announce form errors to screen readers
        this.form.setAttribute('novalidate', 'true');
        
        // Add ARIA live regions for dynamic content
        this.messagesContainer.setAttribute('aria-live', 'polite');
        this.messagesContainer.setAttribute('aria-atomic', 'true');

        // Enhanced focus management
        this.setupFocusManagement();
    }

    /**
     * Set up real-time field validation
     */
    setupRealTimeValidation() {
        Object.keys(this.fields).forEach(fieldName => {
            const field = this.fields[fieldName];
            if (field && field.addEventListener) {
                field.addEventListener('blur', () => this.validateField(fieldName));
                field.addEventListener('input', () => this.clearFieldError(fieldName));
            }
        });
    }

    /**
     * Handle form submission
     */
    async handleFormSubmit(event) {
        event.preventDefault();
        
        try {
            // Prevent double submission
            if (this.currentRequest) {
                return;
            }

            // Validate form
            if (!this.validateForm()) {
                this.announceValidationErrors();
                return;
            }

            // Show loading state
            this.setLoadingState(true);
            
            // Collect form data
            const formData = this.collectFormData();
            
            // Submit to API
            const result = await this.submitTrackingRequest(formData);
            
            // Handle success
            this.handleSubmissionSuccess(result);
            
        } catch (error) {
            console.error('Form submission error:', error);
            this.handleSubmissionError(error);
        } finally {
            this.setLoadingState(false);
        }
    }

    /**
     * Collect and format form data
     */
    collectFormData() {
        const tripType = document.querySelector('input[name="tripType"]:checked')?.value || 'round-trip';
        
        const data = {
            origin: this.fields.origin.value.toUpperCase().trim(),
            destination: this.fields.destination.value.toUpperCase().trim(),
            departure_date: this.fields.departureDate.value,
            passengers: parseInt(this.fields.passengers.value) || 1,
            cabin_class: this.fields.cabinClass.value || 'ECONOMY',
            telegram_chat_id: parseInt(this.fields.telegramChatId.value),
            is_active: true,
            notifications: {
                price_alerts: this.fields.priceAlerts.checked,
                expiry_alerts: this.fields.expiryAlerts.checked
            }
        };

        // Add return date for round trips
        if (tripType === 'round-trip' && this.fields.returnDate.value) {
            data.return_date = this.fields.returnDate.value;
        }

        // Add max price if specified
        if (this.fields.maxPrice.value) {
            data.max_price = parseFloat(this.fields.maxPrice.value);
        }

        // Calculate expiry date based on tracking duration
        const trackingDays = parseInt(this.fields.trackingDuration.value) || 30;
        const expiryDate = new Date();
        expiryDate.setDate(expiryDate.getDate() + trackingDays);
        data.expires_at = expiryDate.toISOString();

        return data;
    }

    /**
     * Submit tracking request to API
     */
    async submitTrackingRequest(data) {
        const response = await this.makeApiRequest('POST', API_CONFIG.endpoints.trackingRequests, data);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }

    /**
     * Make API request with proper error handling
     */
    async makeApiRequest(method, endpoint, data = null) {
        const url = `${API_CONFIG.baseUrl}${endpoint}`;
        
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            signal: AbortSignal.timeout(API_CONFIG.timeout)
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        this.currentRequest = fetch(url, options);
        
        try {
            const response = await this.currentRequest;
            return response;
        } finally {
            this.currentRequest = null;
        }
    }

    /**
     * Handle successful form submission
     */
    handleSubmissionSuccess(result) {
        // Show success message
        this.showMessage(
            `🎉 Flight tracking started! Your tracking ID is: ${result.id}. You'll receive notifications when prices change.`,
            'success'
        );

        // Reset form
        this.form.reset();
        this.initializeForm();

        // Focus on first field for new request
        this.fields.origin.focus();

        // Track analytics event
        this.trackEvent('tracking_request_created', {
            origin: result.origin,
            destination: result.destination,
            passengers: result.passengers
        });
    }

    /**
     * Handle form submission error
     */
    handleSubmissionError(error) {
        let message = 'Failed to create tracking request. Please try again.';
        
        if (error.name === 'AbortError') {
            message = 'Request timed out. Please check your connection and try again.';
        } else if (error.message.includes('400')) {
            message = 'Please check your input data and try again.';
        } else if (error.message.includes('429')) {
            message = 'Too many requests. Please wait a moment before trying again.';
        } else if (error.message.includes('500')) {
            message = 'Server error. Our team has been notified. Please try again later.';
        }

        this.showMessage(message, 'error');
    }

    /**
     * Validate entire form
     */
    validateForm() {
        let isValid = true;
        const fieldsToValidate = ['origin', 'destination', 'departureDate', 'passengers', 'telegramChatId'];
        
        // Add return date validation for round trips
        const tripType = document.querySelector('input[name="tripType"]:checked')?.value;
        if (tripType === 'round-trip') {
            fieldsToValidate.push('returnDate');
        }

        // Add max price validation if provided
        if (this.fields.maxPrice.value) {
            fieldsToValidate.push('maxPrice');
        }

        // Validate each field
        fieldsToValidate.forEach(fieldName => {
            if (!this.validateField(fieldName)) {
                isValid = false;
            }
        });

        // Additional cross-field validation
        if (isValid) {
            isValid = this.validateDates() && this.validateAirports();
        }

        return isValid;
    }

    /**
     * Validate individual field
     */
    validateField(fieldName) {
        const field = this.fields[fieldName];
        const errorElement = this.errorElements[fieldName];
        
        if (!field || !errorElement) {
            return true;
        }

        let isValid = true;
        let errorMessage = '';

        // Clear previous error state
        this.clearFieldError(fieldName);

        // Required field validation
        if (field.hasAttribute('required') && !field.value.trim()) {
            isValid = false;
            errorMessage = 'This field is required.';
        }

        // Field-specific validation
        if (isValid && field.value.trim()) {
            switch (fieldName) {
                case 'origin':
                case 'destination':
                    if (!VALIDATION_RULES.iataCode.pattern.test(field.value.toUpperCase().trim())) {
                        isValid = false;
                        errorMessage = VALIDATION_RULES.iataCode.message;
                    }
                    break;

                case 'telegramChatId':
                    if (!VALIDATION_RULES.telegramChatId.pattern.test(field.value.trim())) {
                        isValid = false;
                        errorMessage = VALIDATION_RULES.telegramChatId.message;
                    }
                    break;

                case 'maxPrice':
                    const price = parseFloat(field.value);
                    if (isNaN(price) || price < VALIDATION_RULES.maxPrice.min || price > VALIDATION_RULES.maxPrice.max) {
                        isValid = false;
                        errorMessage = VALIDATION_RULES.maxPrice.message;
                    }
                    break;

                case 'departureDate':
                case 'returnDate':
                    const date = new Date(field.value);
                    const today = new Date();
                    const maxDate = new Date();
                    maxDate.setFullYear(maxDate.getFullYear() + 1);
                    
                    if (date < today || date > maxDate) {
                        isValid = false;
                        errorMessage = 'Please select a date between today and one year from now.';
                    }
                    break;
            }
        }

        // Show error if validation failed
        if (!isValid) {
            this.showFieldError(fieldName, errorMessage);
        }

        return isValid;
    }

    /**
     * Validate date relationships
     */
    validateDates() {
        const departureDate = new Date(this.fields.departureDate.value);
        const returnDate = new Date(this.fields.returnDate.value);
        const tripType = document.querySelector('input[name="tripType"]:checked')?.value;
        
        // Only validate return date for round trips
        if (tripType === 'round-trip' && this.fields.returnDate.value) {
            if (returnDate <= departureDate) {
                this.showFieldError('returnDate', 'Return date must be after departure date.');
                return false;
            }
        }

        return true;
    }

    /**
     * Validate airport codes are different
     */
    validateAirports() {
        const origin = this.fields.origin.value.toUpperCase().trim();
        const destination = this.fields.destination.value.toUpperCase().trim();
        
        if (origin && destination && origin === destination) {
            this.showFieldError('destination', 'Destination must be different from origin.');
            return false;
        }

        return true;
    }

    /**
     * Show field error
     */
    showFieldError(fieldName, message) {
        const field = this.fields[fieldName];
        const errorElement = this.errorElements[fieldName];
        
        if (field && errorElement) {
            field.classList.add('error');
            field.setAttribute('aria-invalid', 'true');
            errorElement.textContent = message;
            errorElement.classList.add('visible');
        }
    }

    /**
     * Clear field error
     */
    clearFieldError(fieldName) {
        const field = this.fields[fieldName];
        const errorElement = this.errorElements[fieldName];
        
        if (field && errorElement) {
            field.classList.remove('error', 'success');
            field.removeAttribute('aria-invalid');
            errorElement.textContent = '';
            errorElement.classList.remove('visible');
        }
    }

    /**
     * Format airport code input
     */
    formatAirportCode(event) {
        const field = event.target;
        let value = field.value.toUpperCase().replace(/[^A-Z]/g, '');
        
        if (value.length > 3) {
            value = value.substring(0, 3);
        }
        
        field.value = value;

        // Show suggestion if it's a common airport
        if (value.length === 3 && COMMON_AIRPORTS[value]) {
            this.showAirportSuggestion(field, COMMON_AIRPORTS[value]);
        }
    }

    /**
     * Show airport code suggestion
     */
    showAirportSuggestion(field, suggestion) {
        // Remove existing suggestions
        this.clearAirportSuggestions(field);
        
        // Create suggestion element
        const suggestionEl = document.createElement('div');
        suggestionEl.className = 'airport-suggestion';
        suggestionEl.textContent = suggestion;
        suggestionEl.setAttribute('role', 'status');
        suggestionEl.setAttribute('aria-live', 'polite');
        
        // Insert after the field
        field.parentNode.insertBefore(suggestionEl, field.nextSibling);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (suggestionEl.parentNode) {
                suggestionEl.parentNode.removeChild(suggestionEl);
            }
        }, 3000);
    }

    /**
     * Clear airport suggestions
     */
    clearAirportSuggestions(field) {
        const suggestions = field.parentNode.querySelectorAll('.airport-suggestion');
        suggestions.forEach(el => el.remove());
    }

    /**
     * Handle trip type change
     */
    handleTripTypeChange() {
        const tripType = document.querySelector('input[name="tripType"]:checked')?.value;
        const returnDateGroup = document.getElementById('return-date-group');
        const returnDateField = this.fields.returnDate;
        
        if (tripType === 'one-way') {
            returnDateGroup.style.display = 'none';
            returnDateField.removeAttribute('required');
            returnDateField.value = '';
            this.clearFieldError('returnDate');
        } else {
            returnDateGroup.style.display = 'block';
            returnDateField.setAttribute('required', 'true');
        }
    }

    /**
     * Handle airport swap
     */
    handleAirportSwap() {
        const originValue = this.fields.origin.value;
        const destinationValue = this.fields.destination.value;
        
        // Swap values
        this.fields.origin.value = destinationValue;
        this.fields.destination.value = originValue;
        
        // Clear any errors
        this.clearFieldError('origin');
        this.clearFieldError('destination');
        
        // Validate swapped values
        setTimeout(() => {
            this.validateField('origin');
            this.validateField('destination');
        }, 100);

        // Announce to screen readers
        this.announceToScreenReader('Airport codes swapped');
    }

    /**
     * Handle form reset
     */
    handleFormReset() {
        // Clear all field errors
        Object.keys(this.errorElements).forEach(fieldName => {
            this.clearFieldError(fieldName);
        });

        // Clear messages
        this.clearMessages();

        // Reinitialize form
        setTimeout(() => {
            this.initializeForm();
        }, 100);
    }

    /**
     * Set loading state
     */
    setLoadingState(isLoading) {
        if (isLoading) {
            this.submitButton.classList.add('btn--loading');
            this.submitButton.disabled = true;
            this.loadingOverlay.classList.add('visible');
            this.loadingOverlay.setAttribute('aria-hidden', 'false');
            
            // Prevent form interactions
            this.form.style.pointerEvents = 'none';
        } else {
            this.submitButton.classList.remove('btn--loading');
            this.submitButton.disabled = false;
            this.loadingOverlay.classList.remove('visible');
            this.loadingOverlay.setAttribute('aria-hidden', 'true');
            
            // Restore form interactions
            this.form.style.pointerEvents = '';
        }
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
     * Clear all messages
     */
    clearMessages() {
        this.messagesContainer.innerHTML = '';
    }

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        // Escape key - close loading overlay or clear messages
        if (event.key === 'Escape') {
            if (this.loadingOverlay.classList.contains('visible')) {
                this.setLoadingState(false);
            } else {
                this.clearMessages();
            }
        }

        // Ctrl/Cmd + Enter - submit form
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            this.form.dispatchEvent(new Event('submit'));
        }
    }

    /**
     * Handle network status changes
     */
    handleNetworkChange(isOnline) {
        if (isOnline) {
            this.showMessage('Connection restored.', 'success');
        } else {
            this.showMessage('You are currently offline. Please check your internet connection.', 'warning');
        }
    }

    /**
     * Handle before page unload
     */
    handleBeforeUnload(event) {
        // Warn if form has data and request is in progress
        if (this.currentRequest) {
            event.preventDefault();
            event.returnValue = 'A request is in progress. Are you sure you want to leave?';
            return event.returnValue;
        }
    }

    /**
     * Set up focus management for better accessibility
     */
    setupFocusManagement() {
        // Focus first invalid field on validation error
        this.form.addEventListener('invalid', (event) => {
            event.target.focus();
        }, true);

        // Focus management for loading states
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Tab' && this.loadingOverlay.classList.contains('visible')) {
                event.preventDefault();
            }
        });
    }

    /**
     * Announce validation errors to screen readers
     */
    announceValidationErrors() {
        const errorCount = document.querySelectorAll('.form-error.visible').length;
        if (errorCount > 0) {
            this.announceToScreenReader(`Form has ${errorCount} error${errorCount > 1 ? 's' : ''}. Please review and correct.`);
        }
    }

    /**
     * Announce message to screen readers
     */
    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'assertive');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.style.position = 'absolute';
        announcement.style.left = '-10000px';
        announcement.style.width = '1px';
        announcement.style.height = '1px';
        announcement.style.overflow = 'hidden';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }

    /**
     * Track analytics events
     */
    trackEvent(eventName, properties = {}) {
        // Placeholder for analytics tracking
        console.log('Analytics Event:', eventName, properties);
        
        // Could integrate with Google Analytics, Mixpanel, etc.
        if (typeof gtag !== 'undefined') {
            gtag('event', eventName, properties);
        }
    }
}

// Additional utility functions

/**
 * Debounce function for performance
 */
function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Format currency for display
 */
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

/**
 * Format date for display
 */
function formatDate(dateString, options = {}) {
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...options
    };
    
    return new Date(dateString).toLocaleDateString('en-US', defaultOptions);
}

/**
 * Check if browser supports required features
 */
function checkBrowserSupport() {
    const requiredFeatures = [
        'fetch',
        'Promise',
        'AbortController',
        'IntersectionObserver'
    ];
    
    const unsupported = requiredFeatures.filter(feature => !(feature in window));
    
    if (unsupported.length > 0) {
        console.warn('Unsupported browser features:', unsupported);
        // Could show a message to user about browser compatibility
    }
    
    return unsupported.length === 0;
}

// Initialize the application
const flightTracker = new FlightTracker();

// Add airport suggestion styles
const suggestionStyles = document.createElement('style');
suggestionStyles.textContent = `
    .airport-suggestion {
        font-size: 0.75rem;
        color: var(--color-text-muted);
        background-color: var(--color-bg-tertiary);
        padding: 0.25rem 0.5rem;
        border-radius: var(--radius-sm);
        margin-top: 0.25rem;
        border: 1px solid var(--color-border-light);
        animation: fadeIn 0.3s ease-in-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(suggestionStyles);

// Check browser support on load
checkBrowserSupport();

// Export for potential testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FlightTracker, formatCurrency, formatDate };
}