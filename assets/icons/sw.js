// assets/sw.js

// 1. When a push message arrives, parse its JSON payload and show a notification.
self.addEventListener("push", event => {
  if (!event.data) {
    return;
  }
  const payload = event.data.json();  // e.g. { title: "...", body: "..." }
  
  // Show a system-level notification
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/assets/icons/icon-128.png" // or any icon path
    })
  );
});

// 2. When the user clicks on the notification, close it and optionally open your app.
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(
    // e.g., open your Dash app's home page
    clients.openWindow("/")
  );
});
