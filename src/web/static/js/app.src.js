import { WebHaptics } from "web-haptics";

const haptics = new WebHaptics({ debug: true });

const App = {
    haptics,

    socket: null,

    _subscribedServers: new Set(),
    _dayChangeHandlers: [],
    _dayChangeListenerInstalled: false,

    init() {
        this.initSocket();
        this.initTheme();
        this.checkPendingNotification();
    },

    queueNotification(message, type = 'info') {
        const hapticMap = { success: 'success', error: 'error', warning: 'warning' };
        if (hapticMap[type]) haptics.trigger(hapticMap[type]);
        sessionStorage.setItem('pending_notification', JSON.stringify({ message, type }));
    },

    checkPendingNotification() {
        const raw = sessionStorage.getItem('pending_notification');
        if (!raw) return;
        sessionStorage.removeItem('pending_notification');
        try {
            const { message, type } = JSON.parse(raw);
            this.showNotification(message, type, true);
        } catch {}
    },

    rumble() {
        haptics.trigger([100, 30, 150, 50, 200, 30, 80, 40, 250]);
    },

    initTheme() {
        const saved = localStorage.getItem('theme') || 'dark';
        const radios = document.querySelectorAll('input[name="theme-picker"].theme-controller');
        if (!radios.length) return;

        radios.forEach(radio => {
            if (radio.value === saved) radio.checked = true;
            radio.addEventListener('change', () => {
                if (radio.checked) {
                    document.documentElement.setAttribute('data-theme', radio.value);
                    localStorage.setItem('theme', radio.value);
                }
            });
        });
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
            haptics.trigger('warning');
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

    showNotification(message, type = 'info', skipHaptics = false) {
        if (!skipHaptics) {
            const hapticMap = { success: 'success', error: 'error', warning: 'warning' };
            if (hapticMap[type]) haptics.trigger(hapticMap[type]);
        }

        const container = document.getElementById('notification-container');
        if (!container) return;

        const alertClass = { info: 'alert-info', success: 'alert-success', error: 'alert-error', warning: 'alert-warning' }[type] || 'alert-info';

        const notification = document.createElement('div');
        notification.role = 'alert';
        notification.className = `alert ${alertClass} shadow-lg max-w-sm text-sm`;
        notification.textContent = message;

        container.appendChild(notification);

        setTimeout(() => {
            notification.style.transition = 'opacity 0.3s ease';
            notification.style.opacity = '0';
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

        /**
         * Breeding status label for a pooch's `breeding_status` key, matching the bot's labels.
         */
        breedingStatus(status) {
            const labels = { in_heat: 'In Heat', heating_up: 'Heating Up', cooled: 'Cooled' };
            return labels[status] || '—';
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
    return div.innerHTML.replace(/'/g, '&quot;');
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
    }).format(amount);
}

// Expose globals for inline template scripts
window.App = App;
window.escapeHtml = escapeHtml;
window.formatCurrency = formatCurrency;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
