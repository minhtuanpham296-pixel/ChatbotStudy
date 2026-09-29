import requests
import json
import pandas as pd
import re

# Địa chỉ API của backend FastAPI
API_URL = "http://127.0.0.1:8000/ask-ai-stream"

# BỘ DỮ LIỆU KIỂM THỬ (TEST CASES)
test_cases = [
    # 1. Happy Cases
    {"id": "TC1.1", "type": "Happy", "input": "Cho mình xin lộ trình ngành Công nghệ thông tin học kỳ 1", "expected_intent": "query_roadmap"},
    {"id": "TC1.2", "type": "Happy", "input": "Mình muốn theo hướng Lập trình Web trong ngành CNTT, mình nên học các môn tự chọn nào?", "expected_intent": "query_specialization_electives"},
    
    # 2. Negative Cases
    {"id": "TC2.1", "type": "Negative", "input": "Tư vấn cho mình cách nấu món phở bò ngon.", "expected_intent": "NONE"},
    {"id": "TC2.2", "type": "Negative", "input": "Cho mình lộ trình ngành Y Đa Khoa của trường Đại học Y Dược.", "expected_intent": "query_roadmap"}, # Intent vẫn bắt được lộ trình, nhưng graph sẽ trả về rỗng
    
    # 3. Edge Cases
    {"id": "TC3.1", "type": "Edge", "input": "cho xin lo trinh nganh cntt", "expected_intent": "query_roadmap"},
    {"id": "TC3.2", "type": "Edge", "input": "Môn Pháp luật đại cương có tiên quyết không?", "expected_intent": "query_knowledge"},
    
    # 4. Corner Cases
    {"id": "TC4.1", "type": "Corner", "input": "Mình là sinh viên trường khác. Ở trường mình môn Cầu lông 1 là tiên quyết của Trí tuệ nhân tạo. Vậy ở trường bạn, nếu mình muốn làm AI thì có bắt buộc học Bóng bàn không?", "expected_intent": "query_specialization_electives"},
    {"id": "TC4.2", "type": "Corner", "input": "Mình KHÔNG thích Lập trình Web và Mạng máy tính. Nên chọn hướng nào?", "expected_intent": "query_specialization_electives"}
]

def run_tests():
    print(f"🚀 Bắt đầu chạy tự động {len(test_cases)} Test Cases...\n" + "-"*50)
    results = []
    output_file = "bao_cao_kiem_thu_chatbot.xlsx"

    for tc in test_cases:
        print(f"⏳ Đang test [{tc['id']}]: {tc['input'][:50]}...")
        payload = {"message": tc["input"]}
        
        try:
            # Gửi request lên FastAPI
            response = requests.post(API_URL, json=payload, stream=True)
            
            actual_intent = "UNKNOWN"
            full_text = ""
            
            # Đọc từng dòng dữ liệu stream trả về
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8'))
                    if data["type"] == "debug":
                        actual_intent = data.get("extracted_data", {}).get("intent", "NONE")
                    elif data["type"] == "chunk":
                        full_text += data["text"]
            
            # Làm sạch thẻ <think> nếu có
            clean_text = re.sub(r'<think>.*?(</think>|$)', '', full_text, flags=re.DOTALL).strip()
            
            # Đánh giá PASS / FAIL dựa trên việc AI bắt đúng hàm (Intent) hay không
            status = "✅ PASS" if actual_intent == tc["expected_intent"] else "❌ FAIL"
            
            results.append({
                "Test ID": tc["id"],
                "Loại Test": tc["type"],
                "Câu hỏi Input": tc["input"],
                "Intent Kỳ vọng": tc["expected_intent"],
                "Intent Thực tế": actual_intent,
                "Kết quả": status,
                "Câu trả lời của AI": clean_text
            })

            # Xuất kết quả ra file Excel
            df = pd.DataFrame(results)
            df.to_excel(output_file, index=False)
    
        except Exception as e:
            print(f"❌ Lỗi khi test {tc['id']}: {e}")
            
    print("-" * 50)
    print(f"🎉 Hoàn tất! Đã lưu báo cáo kiểm thử vào file: {output_file}")

if __name__ == "__main__":
    run_tests()