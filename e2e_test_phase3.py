import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

nbs = requests.get(f"{BASE_URL}/api/notebooks").json()
if not nbs:
    print("No notebooks found.")
    exit(1)
nb_id = nbs[0]["id"]
print(f"Testing on notebook: {nb_id}")

print("1. Testing Escape Room Eval (Without HP/Mages, just syntax check)")
# Since we don't have chat history, it might fail or pass but shouldn't crash
res = requests.post(f"{BASE_URL}/api/notebooks/{nb_id}/gamification/eval-escape", json={"answer": "I have no idea"})
print(res.status_code, res.json())

print("2. Checking Gamification Skills fetch")
res = requests.get(f"{BASE_URL}/api/notebooks/{nb_id}/gamification").json()
print("Gamification:", res)

print("✅ Phase 3 APIs are alive!")
