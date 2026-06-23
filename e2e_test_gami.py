import requests
import time

BASE_URL = "http://127.0.0.1:8000"
TEST_NOTEBOOK = "test_gami_notebook"

print("1. Tạo sổ tay test...")
requests.post(f"{BASE_URL}/api/notebooks", data={"title": "Test Gamification"})
# We assume test_gami_notebook might not be created exactly with that ID, 
# let's fetch all notebooks and use the first one
nbs = requests.get(f"{BASE_URL}/api/notebooks").json()
if not nbs:
    print("Failed to get notebooks")
    exit(1)
nb_id = nbs[0]["id"]
print(f"Sử dụng notebook: {nb_id}")

print("2. Lấy trạng thái Gamification ban đầu...")
res = requests.get(f"{BASE_URL}/api/notebooks/{nb_id}/gamification").json()
print("Trạng thái:", res)

print("3. Thêm 150 EXP (Kỳ vọng: Lên cấp 2, SP=1, dư 50 EXP)...")
res = requests.post(f"{BASE_URL}/api/notebooks/{nb_id}/add-exp", json={"amount": 150}).json()
print("Kết quả:", res)
assert res["level"] == 2
assert res["exp"] == 50
assert res["sp"] == 1

print("4. Test Leaderboard (Có bot ảo)...")
lb = requests.get(f"{BASE_URL}/api/leaderboard").json()
for u in lb:
    print(f"Hạng {u.get('rank')}: {u['title']} - Lv {u['level']} - {u['exp']} EXP")

print("5. Mua kỹ năng (Bình Máu Phụ - cost 1)...")
res = requests.post(f"{BASE_URL}/api/notebooks/{nb_id}/unlock-skill", json={"skill_id": "hp_up", "cost": 1})
print("Mua:", res.json())

print("6. Kiểm tra lại kỹ năng đã mua...")
skills = requests.get(f"{BASE_URL}/api/notebooks/{nb_id}/skills").json()
print("Skills:", skills)
assert skills.get("hp_up", 0) >= 1

print("✅ Tất cả bài test Gamification Giai đoạn 2 đã pass!")
