/**
 * Curavit — Browser Notification Service
 * Handles Notification API permissions, delivery, lead-time checking, and limitation transparency.
 */

const NOTIFIED_KEY = 'curavit_notified_doses';

export const notificationService = {
  /**
   * Checks whether the Web Notification API is supported by the current browser environment.
   */
  isSupported() {
    return typeof window !== 'undefined' && 'Notification' in window;
  },

  /**
   * Returns current permission status: 'granted' | 'denied' | 'default' | 'unsupported'.
   */
  getPermissionStatus() {
    if (!this.isSupported()) {
      return 'unsupported';
    }
    return Notification.permission;
  },

  /**
   * Explicitly requests notification permission from the user.
   */
  async requestPermission() {
    if (!this.isSupported()) {
      return 'unsupported';
    }
    try {
      const permission = await Notification.requestPermission();
      return permission;
    } catch (err) {
      console.warn('Error requesting notification permission:', err);
      return Notification.permission;
    }
  },

  /**
   * Sends an immediate browser notification if permitted.
   */
  notify(title, options = {}) {
    if (!this.isSupported()) {
      return false;
    }
    if (Notification.permission !== 'granted') {
      return false;
    }

    try {
      const notif = new Notification(title, {
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        tag: options.tag || 'curavit-medication-alert',
        renotify: Boolean(options.renotify),
        body: options.body || '',
        ...options,
      });

      notif.onclick = () => {
        window.focus();
        notif.close();
      };

      return true;
    } catch (err) {
      console.warn('Failed to display browser notification:', err);
      return false;
    }
  },

  /**
   * Dispatches a test notification for user verification.
   */
  sendTestNotification() {
    return this.notify('Curavit — Test Medication Reminder', {
      body: 'Notifications are working properly! You will receive scheduled dose alerts.',
      tag: 'test-notification-' + Date.now(),
    });
  },

  /**
   * Inspects today's schedule and triggers lead-time reminders for upcoming doses.
   * Prevents duplicate alerts by persisting notified log IDs in sessionStorage.
   */
  checkAndNotifyUpcomingDoses(schedule = [], settings = {}) {
    if (!this.isSupported() || Notification.permission !== 'granted') {
      return;
    }
    if (settings.notifications_enabled === 'false') {
      return;
    }

    const leadMinutes = parseInt(settings.reminder_lead_time, 10) || 5;
    const now = new Date();
    const leadThreshold = new Date(now.getTime() + leadMinutes * 60 * 1000);

    // Retrieve already notified IDs
    let notifiedSet = new Set();
    try {
      const stored = sessionStorage.getItem(NOTIFIED_KEY);
      if (stored) {
        notifiedSet = new Set(JSON.parse(stored));
      }
    } catch {
      // Ignore storage read error
    }

    let newlyNotified = false;

    schedule.forEach((dose) => {
      if (dose.status !== 'pending' || !dose.scheduled_time) {
        return;
      }
      if (notifiedSet.has(dose.id)) {
        return;
      }

      // Parse scheduled timestamp
      const schedDt = new Date(dose.scheduled_time.replace(' ', 'T'));
      if (isNaN(schedDt.getTime())) {
        return;
      }

      // Check if scheduled time is between now - 1 minute and now + leadMinutes
      const pastWindow = new Date(now.getTime() - 60 * 1000);
      if (schedDt >= pastWindow && schedDt <= leadThreshold) {
        const timeStr = dose.scheduled_time.split(' ')[1] || '';
        const bodyText = `Time for ${dose.medicine_name} (${dose.dosage}) scheduled at ${timeStr}.` +
          (dose.instructions ? ` Note: ${dose.instructions}` : '');

        const success = this.notify(`Reminder: ${dose.medicine_name}`, {
          body: bodyText,
          tag: `dose-${dose.id}`,
          renotify: true,
        });

        if (success) {
          notifiedSet.add(dose.id);
          newlyNotified = true;
        }
      }
    });

    if (newlyNotified) {
      try {
        sessionStorage.setItem(NOTIFIED_KEY, JSON.stringify([...notifiedSet]));
      } catch {
        // Ignore storage write error
      }
    }
  },

  /**
   * Detailed explanation of browser and device notification limitations.
   */
  getLimitationsNotice() {
    return {
      title: 'Browser Notification Considerations',
      points: [
        'Notifications display only while the browser or application tab remains open in the background.',
        'Operating system "Do Not Disturb", Focus Assist, or Battery Saver modes may suppress banners.',
        'Mobile browsers (such as iOS Safari) require web applications to be added to the Home Screen (PWA) to display notifications.',
        'For reliable alerts across all conditions, ensure notification permissions remain allowed in your browser address bar settings.',
      ],
    };
  },
};

export default notificationService;
