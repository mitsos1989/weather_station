while true; do
  echo "Starting lightning_detector2.py"
  python3 lightning_detector2.py
  echo "Το script σταμάτησε με κωδικό εξόδου $?. Επανεκκίνηση σε 5 δευτερόλεπτα..."
  sleep 5
done
