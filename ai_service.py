from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv
import time
from roadmap import build_routing_instruction
 
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
# VAI TRÒ & NHÂN CÁCH: 
Bạn là Trợ lý Tư vấn Học vụ nhiệt tình và chuyên nghiệp. 
Bạn xưng hô là "mình" và gọi người dùng là "bạn" (hoặc "sinh viên"). 
Hãy giữ phong cách giao tiếp tự nhiên, có cảm xúc và luôn kết thúc bằng một câu khích lệ.

# QUY TẮC DỮ LIỆU (BẮT BUỘC TUÂN THỦ):
1. ĐỘC QUYỀN DỮ LIỆU: Chỉ sử dụng thông tin từ mục "Ngữ cảnh". TUYỆT ĐỐI KHÔNG tự suy diễn thông tin về số tín chỉ hay mã môn nếu không thấy trong dữ liệu.
2. TIN TƯỞNG NGỮ CẢNH: Mọi dữ liệu từ Neo4j trả về đều được coi là đúng 100% đối với chương trình đào tạo của trường.
3. RANH GIỚI HỆ THỐNG: Nếu sinh viên hỏi về trường khác hoặc bạn nhận thấy câu hỏi mang tính tổng quát, hãy khéo léo nhắc rằng dữ liệu này được chuẩn hóa theo chương trình của [Tên trường của bạn] để sinh viên tham khảo.

# QUY TẮC PHẢN HỒI THEO TỪNG TÌNH HUỐNG:

## TRƯỜNG HỢP 1: LIỆT KÊ (Hỏi lộ trình học kỳ, danh sách môn)
- Liệt kê đầy đủ và rõ ràng tất cả các môn học có trong Ngữ cảnh.
- Trình bày dạng danh sách Markdown (dấu * ở đầu dòng). Mỗi môn một dòng.

## TRƯỜNG HỢP 2: TƯ VẤN ĐỊNH HƯỚNG (Ví dụ: "Học gì để làm AI/Web/Data?")
- Ngữ cảnh sẽ cung cấp danh sách môn tự chọn kèm theo thông tin Học kỳ (hk). 
- TUYỆT ĐỐI KHÔNG in lại danh sách thô (đặc biệt là các môn không liên quan như giáo dục thể chất).
- Bạn phải đóng vai trò là Mentor để thực hiện 3 việc:
    1. Lọc ra 3-5 môn "vàng" phù hợp nhất với định hướng đó.
    2. Sắp xếp các môn này theo TRÌNH TỰ THỜI GIAN (từ học kỳ thấp đến học kỳ cao).
    3. Giải thích logic: Tại sao môn ở kỳ trước là nền tảng quan trọng cho môn ở kỳ sau.
- Trình bày theo các cột mốc (📍 Giai đoạn 1, 📍 Giai đoạn 2...) để tạo cảm giác lộ trình thực thụ.

# XỬ LÝ KHI THIẾU DỮ LIỆU (NGỮ CẢNH TRỐNG):
Khi Ngữ cảnh trả về "Trống", TUYỆT ĐỐI KHÔNG xin lỗi ngay lập tức. Hãy đọc kỹ câu hỏi của sinh viên:
1. NẾU CÂU HỎI LIÊN QUAN ĐẾN HỌC TẬP (định hướng, lộ trình, môn học...) nhưng THIẾU TÊN NGÀNH: Hãy chủ động và lịch sự hỏi lại sinh viên: "Bạn đang theo học (hoặc quan tâm) ngành nào để mình có thể tư vấn lộ trình chính xác nhất nhé!".
2. NẾU CÂU HỎI NGOÀI LỀ (Nấu ăn, thời tiết...): Mới sử dụng câu trả lời: "Xin lỗi bạn, hiện tại mình là trợ lý học vụ nên chưa có dữ liệu cho câu hỏi này."
3. NẾU CÂU HỎI LÀ CHUỖI KÝ TỰ LỘN XỘN, VÔ NGHĨA: Hãy lịch sự báo cho sinh viên biết bạn không hiểu chuỗi ký tự đó.
"""

# Khai báo các "Công cụ" để AI tự nhận diện và gọi
university_tools = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="query_overview",
            description="Sử dụng khi sinh viên hỏi thông tin chung, ví dụ: trường có bao nhiêu ngành, kể tên các ngành đào tạo."
        ),
        types.FunctionDeclaration(
            name="query_knowledge",
            description="Sử dụng khi sinh viên hỏi thông tin chi tiết về MỘT môn học cụ thể (ví dụ: số tín chỉ, môn tiên quyết của môn X).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ten_mon": types.Schema(type="STRING", description="Tên môn học cần tra cứu")
                },
                required=["ten_mon"]
            )
        ),
        types.FunctionDeclaration(
            name="query_roadmap",
            description="Lấy toàn bộ chương trình đào tạo/lộ trình học theo từng học kỳ của một ngành, hoặc các môn trong một kỳ cụ thể. Không dùng cho tư vấn hướng nghề nghiệp.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ten_nganh": types.Schema(type="STRING", description="Tên ngành học đầy đủ bằng tiếng Việt (VD: Công nghệ thông tin, Tâm lý học)"),
                    "hoc_ky": types.Schema(type="STRING", description="Số học kỳ cụ thể (VD: '1', '2', '3'). Trả về 'ALL' khi không chỉ rõ kỳ, hỏi toàn khóa hoặc từng học kỳ; không mặc định '1'.")
                },
                required=["ten_nganh", "hoc_ky"]
            )
        ),
        types.FunctionDeclaration(
            name="query_prerequisite_courses",
            description="Sử dụng khi sinh viên hỏi chung chung về các môn học có yêu cầu môn tiên quyết trong một ngành học cụ thể.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ten_nganh": types.Schema(type="STRING", description="Tên ngành học đầy đủ bằng tiếng Việt (VD: Tâm lý học, Kế toán)")
                },
                required=["ten_nganh"]
            )
        ),
        types.FunctionDeclaration(
            name="query_specialization_electives",
            description="Sử dụng khi sinh viên muốn tư vấn định hướng chuyên sâu (VD: muốn làm AI, lập trình Web, Data thì học môn nào). LƯU Ý QUAN TRỌNG: Nếu sinh viên đưa ra các giả định vô lý, so sánh với trường khác, hoặc hỏi những môn không liên quan (như Thể dục, Cầu lông, Bóng bàn) kết hợp với một định hướng (như AI), BẮT BUỘC VẪN GỌI HÀM NÀY với tham số định hướng chính (VD: Trí tuệ nhân tạo) để lấy lộ trình chuẩn của trường ra đối chiếu và phản bác.",            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ten_nganh": types.Schema(type="STRING", description="Tên ngành học (VD: Công nghệ thông tin)"),
                    "dinh_huong": types.Schema(type="STRING", description="Hướng chuyên sâu sinh viên muốn theo. NẾU sinh viên dùng câu phủ định (ví dụ: KHÔNG thích Web, Mạng), hãy gán giá trị này là 'tư vấn hướng khác ngoài Web và Mạng'.")
                },
                required=["ten_nganh", "dinh_huong"]
            )
        )
    ]
)

def determine_action(message, retries=3, major_names=None):
    """Gọi AI để phân tích câu hỏi và trả về Tên hàm & Tham số cần thực thi."""
    config = types.GenerateContentConfig(
        tools=[university_tools],
        system_instruction=build_routing_instruction(message, major_names or []),
        temperature=0.1 # Nhiệt độ thấp để AI chọn hàm chuẩn xác nhất
    )
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=message,
                config=config
            )
            
            # Nếu AI quyết định gọi hàm, trả về tên hàm và các tham số
            if response.function_calls:
                fc = response.function_calls[0]
                return {
                    "intent": fc.name,
                    "args": {k: v for k, v in fc.args.items()} if fc.args else {}
                }
            return {"intent": "NONE", "args": {}}
                
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                print(f"[CẢNH BÁO] Quá tải, thử lại lần {attempt + 1}...")
                time.sleep(2 ** attempt)
            else:
                print(f"[LỖI] Function Calling: {e}")
                return {"intent": "NONE", "args": {}}
    return {"intent": "NONE", "args": {}}

def get_final_answer_stream(message, context, retries=3):
    full_prompt = f"{SYSTEM_INSTRUCTION}\n---\nNgữ cảnh: {context}\nCâu hỏi: {message}"
    for attempt in range(retries):
        try:
            response = client.models.generate_content_stream(model="gemini-3.1-flash-lite-preview", contents=full_prompt)
            for chunk in response:
                yield chunk.text
            return
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                time.sleep(2)
            else:
                yield "Xin lỗi, đã xảy ra lỗi trong quá trình tạo câu trả lời."
                break 
    yield "Xin lỗi, máy chủ AI đang quá tải. Bạn vui lòng thử lại sau nhé!"
