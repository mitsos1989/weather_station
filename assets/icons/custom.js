<script>
// Convert a base64-URL string to a Uint8Array (needed for pushManager.subscribe)
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

// The main function to register the service worker, request permission, and subscribe to push
async function registerAndSubscribePush() {
  // If the browser doesn't support service workers or notifications, bail out
  if (!("serviceWorker" in navigator)) {
    console.warn("Service workers not supported in this browser.");
    return;
  }
  if (!("Notification" in window)) {
    console.warn("Notifications not supported in this browser.");
    return;
  }

  try {
    // 1) Register the service worker (make sure sw.js is in /assets/sw.js)
    const reg = await navigator.serviceWorker.register("/assets/sw.js");
    console.log("Service Worker registered:", reg);

    // 2) Request Notification permission
    const permission = await Notification.requestPermission();
    console.log("Notification permission:", permission);
    if (permission !== "granted") {
      alert("Notifications not granted!");
      return;
    }

    // 3) Subscribe to push using your VAPID public key
    if (!("PushManager" in window)) {
      console.warn("PushManager not supported.");
      return;
    }

    // Replace this with your actual base64-URL public key
    const VAPID_PUBLIC_KEY = "BJNBtL_G3JAn73y9WbBCwJ-u4EbiguQ7L1yfz8-tK2V-lbSB_x-vWWDdQ-RKG2xRIxzuDAbMIp-MW0YynqzrCLI";

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
    });
    console.log("Push subscription:", subscription);

    // 4) Send subscription to your server to store it
    await fetch("/store_subscription", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(subscription)
    });
    alert("Subscribed to push notifications!");
  } catch (err) {
    console.error("Push subscription failed:", err);
  }
}

// Optional: call the function automatically on page load
document.addEventListener("DOMContentLoaded", () => {
  // You can also trigger this via a button click or Dash clientside callback
  registerAndSubscribePush();
});
</script>
