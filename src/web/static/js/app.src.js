import { WebHaptics } from "web-haptics";

const haptics = new WebHaptics({ debug: true });

const App = {
    haptics,

    socket: null,

    _subscribedServers: new Set(),
    _dayChangeHandlers: [],
    _dayChangeListenerInstalled: false,
    _hourChangeHandlers: [],
    _hourChangeListenerInstalled: false,

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
        this._installHourChangeListener();
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

    _installHourChangeListener() {
        if (!this.socket || this._hourChangeListenerInstalled) return;

        this.socket.on('hour_change', (data) => {
            // Hour ticks are more frequent than day ticks, so use a gentler haptic.
            if (data && (data.deaths?.length || data.births?.length || data.fights?.length)) {
                haptics.trigger('success');
            }
            for (const handler of this._hourChangeHandlers) {
                try {
                    handler(data);
                } catch (err) {
                    console.error('Hour change handler failed:', err);
                }
            }
        });

        this._hourChangeListenerInstalled = true;
    },

    /**
     * Subscribe the current socket to server rooms for receiving day-change
     * and hour-change events.
     *
     * @param {number[]} serverIds
     * @param {(data: any) => void} [onDayChange]
     * @param {(data: any) => void} [onHourChange]
     */
    subscribeToServers(serverIds, onDayChange, onHourChange) {
        if (!this.socket) return;

        if (typeof onDayChange === 'function') {
            this._dayChangeHandlers.push(onDayChange);
        }
        if (typeof onHourChange === 'function') {
            this._hourChangeHandlers.push(onHourChange);
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

        /**
         * Render a game message (which uses Discord-style **bold** and *italic*) as safe HTML.
         */
        richText(text) {
            return escapeHtml(text)
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.+?)\*/g, '<em>$1</em>');
        },

        /**
         * DaisyUI badge colour for an owner/server event severity (the bot's embed colours).
         */
        eventSeverityBadge(severity) {
            const badges = { moderate: 'badge-info', major: 'badge-warning', critical: 'badge-error' };
            return badges[String(severity || '').toLowerCase()] || 'badge-ghost';
        },

        /**
         * DaisyUI badge colour for an injury severity (trivial → catastrophic). Injuries have no rarity.
         */
        severityBadge(severity) {
            const v = String(severity || '').toLowerCase();
            if (v === 'trivial' || v === 'minor') return 'badge-info';
            if (v === 'moderate') return 'badge-warning';
            return 'badge-error';
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
//
// escapeHtml takes any value and returns a string that is safe to embed
// into an HTML attribute OR text node. We escape the five characters that
// can break out of either context: & < > " '
//
// Prefer element.textContent over this function when possible. This is
// only safe for well-formed attribute/text substitutions, not for
// constructing complex markup.
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Construct a DOM node safely from untrusted text. Use this instead of
// innerHTML when you only need to set text inside an element.
function makeTextNode(tag, text, className) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    el.textContent = text == null ? '' : String(text);
    return el;
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
window.makeTextNode = makeTextNode;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
