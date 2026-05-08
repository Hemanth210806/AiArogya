// reminder.js — Browser notification reminders for medicines
function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
}

function scheduleReminder(medicineName, dosage, timeStr) {
  const [hours, minutes] = timeStr.split(':').map(Number);
  const now = new Date();
  const target = new Date();
  target.setHours(hours, minutes, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  const delay = target - now;
  setTimeout(() => {
    if (Notification.permission === 'granted') {
      new Notification('💊 Medicine Reminder — ArogyaAI', {
        body: `Time to take ${medicineName} (${dosage})`,
        icon: '/static/images/logo.png',
        vibrate: [200, 100, 200]
      });
    }
    if ('vibrate' in navigator) navigator.vibrate([200, 100, 200]);
  }, delay);
}

document.addEventListener('DOMContentLoaded', requestNotificationPermission);
