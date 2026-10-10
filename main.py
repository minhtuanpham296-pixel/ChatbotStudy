from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database import db
from ai_service import determine_action, get_final_answer_stream
import uvicorn
import json

app = FastAPI()
@app.get("/health")
def health():
    return {"status": "ok"}

class ChatMessage(BaseModel):
    message: str

@app.post("/ask-ai-stream")
async def ask_ai_stream(payload: ChatMessage):
    # 1. Để AI TỰ ĐỘNG quyết định hàm cần gọi (Function Calling)
    action = determine_action(payload.message)
    intent = action.get("intent", "NONE")
    args = action.get("args", {})
    
    knowledge = []
    
    # === NHÁNH 1: TRẢ LỜI TRỰC TIẾP (BYPASS AI) ===
    if intent == "query_overview":
        knowledge = db.query_overview()
        def event_stream_direct():
            yield json.dumps({"type": "debug", "extracted_data": action, "source": knowledge}, ensure_ascii=False) + "\n"
            if knowledge:
                tong_so = knowledge[0]['tong_so_nganh']
                danh_sach = knowledge[0]['danh_sach_nganh']
                danh_sach_str = "\n".join([f"- {nganh}" for nganh in danh_sach])
                direct_answer = f"Hiện tại, trường có tổng cộng **{tong_so} ngành đào tạo**.\n\nDanh sách chi tiết:\n{danh_sach_str}"
                yield json.dumps({"type": "chunk", "text": direct_answer}, ensure_ascii=False) + "\n"
            else:
                yield json.dumps({"type": "chunk", "text": "Xin lỗi, hiện tại hệ thống chưa có dữ liệu."}, ensure_ascii=False) + "\n"
        return StreamingResponse(event_stream_direct(), media_type="application/x-ndjson")

    # === NHÁNH 2: GỌI HÀM DATABASE THEO YÊU CẦU CỦA AI ===
    if intent == "query_knowledge":
        knowledge = db.query_knowledge(args.get("ten_mon", ""))
    elif intent == "query_roadmap":
        knowledge = db.query_roadmap(args.get("ten_nganh", ""), args.get("hoc_ky", "1"))
    elif intent == "query_prerequisite_courses":
        knowledge = db.query_prerequisite_courses_by_major(args.get("ten_nganh", ""))
    elif intent == "query_specialization_electives":
        # Lấy toàn bộ môn tự chọn từ Database
        elective_courses = db.query_elective_courses(args.get("ten_nganh", "Công nghệ thông tin"))
        dinh_huong = args.get("dinh_huong", "")
        # Đóng gói ngữ cảnh đặc biệt để AI hiểu nhiệm vụ
        knowledge = {
            "nhiem_vu": f"Sinh viên muốn theo hướng: {dinh_huong}. Hãy lọc và đề xuất môn phù hợp từ danh sách dưới đây.",
            "danh_sach_mon_tu_chon": elective_courses
        }
    # =========================================================
    # THÊM ĐOẠN NÀY ĐỂ IN LOG RA TERMINAL
    # =========================================================
    print("\n" + "="*50)
    print("🔍 QUÁ TRÌNH HỆ THỐNG XỬ LÝ:")
    print("1. Dữ liệu AI bóc tách (JSON):")
    print(json.dumps(action, indent=2, ensure_ascii=False))
    print("\n2. Dữ liệu Neo4j trả về:")
    print(json.dumps(knowledge, indent=2, ensure_ascii=False))
    print("="*50 + "\n")
    # =========================================================
    
    # Chuẩn hóa ngữ cảnh thành chuỗi JSON để AI tiếp thu tốt nhất
    if knowledge:
        json_data = json.dumps(knowledge, ensure_ascii=False)
        # Gắn nhãn khẳng định 100% dữ liệu này là đúng trọng tâm để AI hết sợ
        context = f"Dữ liệu hệ thống ĐÃ XÁC NHẬN thuộc về ngành/môn mà sinh viên đang hỏi. Hãy đọc bảng sau: {json_data}"
    else:
        context = "Ngữ cảnh trống."
    
    def event_stream():
        # Dữ liệu debug lúc này sẽ hiển thị tên hàm và các tham số mà AI tự động bắt được
        yield json.dumps({
            "type": "debug", 
            "extracted_data": action, 
            "source": knowledge
        }, ensure_ascii=False) + "\n"
        
        for chunk in get_final_answer_stream(payload.message, context):
            yield json.dumps({
                "type": "chunk", 
                "text": chunk.replace('.0', '')
            }, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)