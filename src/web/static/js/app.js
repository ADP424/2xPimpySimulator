const App = {
    socket: null,

    _subscribedServers: new Set(),
    _dayChangeHandlers: [],
    _dayChangeListenerInstalled: false,

    init() {
        this.initSocket();
    },

    initSocket() {
        if (typeof io === 'undefined') return;

        this.socket = io();

        this.socket.on('connect', () => {
            console.log('WebSocket connected');
        });

        this.socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
        });

        this.socket.on('connected', (data) => {
            console.log('Connection confirmed:', data);
        });

        this._installDayChangeListener();
    },

    _installDayChangeListener() {
        if (!this.socket || this._dayChangeListenerInstalled) return;

        this.socket.on('day_change', (data) => {
            for (const handler of this._dayChangeHandlers) {
                try {
                    handler(data);
                } catch (err) {
                    console.error('Day change handler failed:', err);
                }
            }
        });

        this._dayChangeListenerInstalled = true;
    },

    /**
     * Subscribe the current socket to server rooms for receiving day-change events.
     *
     * @param {number[]} serverIds
     * @param {(data: any) => void} [onDayChange]
     */
    subscribeToServers(serverIds, onDayChange) {
        if (!this.socket) return;

        if (typeof onDayChange === 'function') {
            this._dayChangeHandlers.push(onDayChange);
        }

        const ids = (serverIds || [])
            .map((v) => Number(v))
            .filter((v) => Number.isFinite(v) && v > 0);

        const newIds = [];
        for (const id of ids) {
            if (!this._subscribedServers.has(id)) {
                this._subscribedServers.add(id);
                newIds.push(id);
            }
        }

        if (newIds.length > 0) {
            this.socket.emit('subscribe_servers', { server_ids: newIds });
        }
    },

    showNotification(message, type = 'info') {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    },

    format: {
        /**
         * Mirror the bot's enum formatting: underscores to spaces + capitalize first letter.
         */
        enumLabel(value) {
            if (value === null || value === undefined) return '—';
            const str = String(value).replaceAll('_', ' ');
            if (!str) return '—';
            return str.charAt(0).toUpperCase() + str.slice(1);
        },
    },

    /**
     * Group mutation health impacts to match existing UI styling.
     */
    healthImpactGroup(impact) {
        const v = String(impact || '').toLowerCase();

        const negative = new Set([
            'instant_death',
            'fatal',
            'brutal',
            'severe',
            'unhealthy',
            'harmful',
        ]);

        const positive = new Set([
            'helpful',
            'healthy',
            'great',
            'fantastic',
            'brilliant',
            'immortality',
        ]);

        if (negative.has(v)) return 'negative';
        if (positive.has(v)) return 'positive';
        return 'neutral';
    },
};

// Utility functions
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
    }).format(amount);
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
