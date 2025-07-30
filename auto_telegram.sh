while true; do
  echo "Starting Telegram notifications"
  python3 notif_telegram.py
  echo "Το script σταμάτησε με κωδικό εξόδου $?. Επανεκκίνηση σε 10 δευτερόλεπτα..."
  sleep 10
done
