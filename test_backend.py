import json
import requests

def test_chat_stream():
    url = "http://localhost:8000/api/chat"
    payload = {
        "query": "Tóm tắt ngắn gọn tài liệu này.",
        "notebook_id": "default"
    }
    
    print("🚀 Gửi request tới /api/chat...")
    try:
        with requests.post(url, json=payload, stream=True) as response:
            if response.status_code != 200:
                print(f"❌ API trả về lỗi: {response.status_code}")
                print(response.text)
                return

            print("✅ Đã kết nối, đang nhận Stream...")
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "citations":
                                print("\n📚 Trích dẫn tìm được:")
                                for cit in data.get("citations", []):
                                    print(f" - {cit['marker']} [{cit['filename']}]")
                                print("\n🤖 Trả lời:")
                            elif data.get("type") == "chunk":
                                # In chữ ra không xuống dòng
                                print(data.get("text", ""), end="", flush=True)
                            elif data.get("type") == "done":
                                print("\n\n✅ Hoàn tất luồng!")
                        except json.JSONDecodeError:
                            pass
    except requests.exceptions.ConnectionError:
        print("❌ Không thể kết nối tới FastAPI. Hãy chạy lệnh: uvicorn src.api.api:app --reload")

if __name__ == "__main__":
    test_chat_stream()
