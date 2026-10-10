import streamlit as st
import requests
import json
import re # Thêm thư viện re để xử lý chuỗi
import os

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(page_title="Trợ lý Học vụ AI", page_icon="🎓")
st.title("🎓 Trợ lý Tư vấn Học vụ Đa Ngành")
with st.sidebar:
    st.markdown("### ℹ️ Thông tin hệ thống")
    st.info(
        "**Nguồn dữ liệu:**\n"
        "Toàn bộ thông tin môn học, tín chỉ và lộ trình được trích xuất từ Chương trình đào tạo chính thức của trường Đại học Sài Gòn cập nhật năm 2025-2026."
    )
    st.warning(
        "**⚠️ Lưu ý (Disclaimer):**\n"
        "EduChatbot là trợ lý AI mang tính chất tư vấn và tham khảo nhanh."
        "Sinh viên vui lòng luôn đối chiếu lại với Cổng thông tin đào tạo hoặc liên hệ trực tiếp Phòng Giáo vụ tại chính trường bản thân theo học để có quyết định chính thức."
    )
# --- KẾT THÚC PHẦN DISCLAIMER ---

st.caption(
    "💡 **Nguồn dữ liệu:** Cập nhật từ Chương trình đào tạo chính thức của trường Đại học Sài Gòn cập nhật năm 2025-2026.\n"
    "*(Lưu ý: Edu-Mentor là AI tư vấn, thông tin chỉ mang tính tham khảo. Vui lòng đối chiếu với Phòng Giáo vụ trước khi đăng ký môn học).* "
)

# 2. Khởi tạo lịch sử chat và Lời chào đầu tiên
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """
👋 Chào bạn! Mình là **Edu-Mentor**, trợ lý học vụ thông minh được xây dựng bằng công nghệ **Đồ thị Tri thức (Knowledge Graph)** kết hợp với AI.

Mình có thể giúp bạn giải đáp các thông tin về chương trình đào tạo của trường Đại học, bao gồm:
* 📚 **Chương trình đào tạo:** Môn học của từng học kỳ, môn tiên quyết, môn song hành.
* ⏱️ **Tín chỉ:** Tổng số tín chỉ của ngành, số tín chỉ từng môn học.
* 🧩 **Phân loại môn học:** Khối kiến thức (Đại cương, Cơ sở ngành...), Loại học phần (Bắt buộc, Tự chọn).

Bạn cần tư vấn về ngành học nào và mình có thể giúp gì cho bạn hôm nay?
"""
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Nhập câu hỏi của bạn vào đây..."):
    with st.chat_message("user"):
        st.markdown(prompt)
        # ---------------------------------------------------------
    # 🧠 ÁP DỤNG SLIDING WINDOW (CỬA SỔ TRƯỢT)
    # ---------------------------------------------------------
    WINDOW_SIZE = 4  # Chỉ nhớ 4 tin nhắn gần nhất (tương đương 2 lượt hỏi-đáp)
    
    # Cắt lấy N tin nhắn cuối cùng trong lịch sử chat
    recent_history = st.session_state.messages[-WINDOW_SIZE:]
    
    history_text = ""
    for msg in recent_history:
        # Lọc bỏ các thẻ <think> trong lịch sử để tiết kiệm Token
        clean_content = re.sub(r'<think>.*?</think>', '', msg['content'], flags=re.DOTALL).strip()
        role_name = "Sinh viên" if msg["role"] == "user" else "Trợ lý"
        history_text += f"- {role_name}: {clean_content}\n"

    # Đóng gói lịch sử và câu hỏi hiện tại thành một Prompt siêu cấp
    enhanced_prompt = (
        f"LỊCH SỬ TRÒ CHUYỆN GẦN NHẤT:\n{history_text}\n\n"
        f"CÂU HỎI MỚI CỦA SINH VIÊN: {prompt}\n"
        f"(Lưu ý: Dựa vào lịch sử trên để tự hiểu ngữ cảnh nếu sinh viên nói vắn tắt)"
    )
    # ---------------------------------------------------------
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        try:
            res = requests.post(
            f"{API_BASE_URL}/ask-ai-stream",
            json={"message": enhanced_prompt},
            stream=True,
            timeout=(15, 180),
        )
            
            if res.status_code == 200:
                placeholder = st.empty()
                full_answer = ""
                debug_data = None
                
                for line in res.iter_lines():
                    if line:
                        data = json.loads(line.decode('utf-8'))
                        if data["type"] == "debug":
                            debug_data = data 
                        elif data["type"] == "chunk":
                            full_answer += data["text"]
                            
                            # LỌC THẺ <think>: Ẩn mọi thứ từ <think> đến </think>
                            # Nếu đang stream dở chưa có </think>, thì ẩn đến cuối chuỗi ($)
                            display_text = re.sub(r'<think>.*?(</think>|$)', '', full_answer, flags=re.DOTALL).strip()
                            
                            # Chỉ in ra màn hình phần text đã lọc
                            placeholder.markdown(display_text + " ▌") 
                
                # Cập nhật lần cuối: Xóa con trỏ nhấp nháy
                final_display = re.sub(r'<think>.*?(</think>|$)', '', full_answer, flags=re.DOTALL).strip()
                placeholder.markdown(final_display) 
                          
                # Lưu vào lịch sử chat (chỉ lưu phần final_display để các câu chat sau không bị rác)
                st.session_state.messages.append({"role": "assistant", "content": final_display})
            else:
                st.error(f"Lỗi FastAPI — HTTP {res.status_code}")
                st.code(res.text[:2000], language="text")             
        except requests.exceptions.ConnectionError:
            st.error("🔌 Mất kết nối! Bạn đã bật server `main.py` chưa?")
        except requests.exceptions.Timeout:
            st.error("Máy chủ phản hồi quá lâu. Bạn vui lòng thử lại.")
        except requests.exceptions.RequestException:
            st.error("Có lỗi khi gửi yêu cầu đến máy chủ.")        
#         # 1. Khởi tạo biến lưu tóm tắt nếu chưa có
# if "chat_summary" not in st.session_state:
#     st.session_state.chat_summary = ""

# # 2. Hàm nhờ AI tóm tắt (Bạn có thể gọi một API riêng hoặc dùng chính hàm hiện tại)
# def summarize_context(old_messages):
#     if not old_messages:
#         return st.session_state.chat_summary
    
#     # Tạo prompt yêu cầu AI tóm tắt ngắn gọn
#     history_to_compress = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])
#     summarize_prompt = (
#         f"Hãy tóm tắt nội dung chính của cuộc đối thoại sau đây trong tối đa 2 câu. "
#         f"Chỉ tập trung vào: Tên ngành, định hướng sở thích, hoặc các lưu ý đặc biệt của sinh viên. "
#         f"Nội dung cũ: {st.session_state.chat_summary}\n"
#         f"Nội dung mới cần thêm vào: {history_to_compress}"
#     )
    
#     try:
#         # Gọi API (Dùng mode không stream để lấy kết quả nhanh)
#         res = requests.post("http://127.0.0.1:8000/ask-ai-stream", json={"message": summarize_prompt})
#         # Ở đây bạn có thể tối ưu bằng cách tạo một Endpoint riêng cho tóm tắt ở FastAPI
#         # Nhưng để nhanh, ta có thể dùng kết quả từ AI trả về.
#         return res.text # Giả định lấy được chuỗi tóm tắt
#     except:
#         return st.session_state.chat_summary

# # 3. Logic xử lý trong Chat Input
# if prompt := st.chat_input("Nhập câu hỏi..."):
#     # ... (phần hiển thị user message giữ nguyên) ...

#     # KIỂM TRA ĐỘ DÀI LỊCH SỬ ĐỂ NÉN
#     THRESHOLD = 6 # Nếu quá 6 tin nhắn thì bắt đầu nén các tin nhắn cũ nhất
#     if len(st.session_state.messages) > THRESHOLD:
#         # Lấy các tin nhắn cũ (trừ 4 tin nhắn cuối cùng ra)
#         to_compress = st.session_state.messages[:-4]
#         # Cập nhật tóm tắt mới
#         st.session_state.chat_summary = summarize_context(to_compress)
#         # (Tùy chọn) Có thể xóa bớt messages cũ để nhẹ session_state
#         # st.session_state.messages = st.session_state.messages[-4:]

#     # ĐÓNG GÓI PROMPT GỬI ĐI
#     recent_history = st.session_state.messages[-4:]
#     history_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent_history])
    
#     enhanced_prompt = (
#         f"TÓM TẮT BỐI CẢNH TRƯỚC ĐÓ: {st.session_state.chat_summary}\n\n"
#         f"CHI TIẾT GẦN NHẤT:\n{history_text}\n"
#         f"CÂU HỎI MỚI: {prompt}"
#     )