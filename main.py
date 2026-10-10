from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from database import db
from ai_service import determine_action, get_final_answer_stream
import uvicorn
import json
from roadmap import normalize_semester, resolve_major, roadmap_chunks

app = FastAPI()
@app.get("/health")
def health():
    return {"status": "ok"}

class ChatMessage(BaseModel):
    message: str

@app.post("/ask-ai-stream")
async def ask_ai_stream(payload: ChatMessage):
    # 1. Để AI TỰ ĐỘNG quyết định hàm cần gọi (Function Calling)
    overview = db.query_overview()
    major_names = overview[0].get("danh_sach_nganh", []) if overview else []
    action = determine_action(payload.message, major_names=major_names)
    intent = action.get("intent", "NONE")
    args = action.get("args", {})
    
    knowledge = []

    if intent == "query_roadmap":
        requested = str(args.get("ten_nganh") or "").strip()
        matches = resolve_major(requested, major_names)
        courses = []
        semester = None
        if not requested:
            answer = "Bạn muốn xem lộ trình học của ngành nào?"
        elif not matches:
            answer = f"Mình chưa tìm thấy ngành '{requested}' trong dữ liệu. Bạn kiểm tra lại tên ngành nhé."
        elif len(matches) > 1:
            answer = "Bạn muốn xem ngành nào trong các ngành sau?\n\n" + "\n".join(f"- {name}" for name in matches)
        else:
            try:
                semester = normalize_semester(args.get("hoc_ky"))
            except ValueError:
                answer = "Bạn muốn xem toàn khóa hay học kỳ cụ thể nào? Vui lòng nhập số học kỳ."
            else:
                courses = db.query_roadmap(matches[0], semester)
                answer = "Mình chưa có dữ liệu môn học cho ngành/học kỳ bạn yêu cầu."

        def event_stream_roadmap():
            yield json.dumps({"type": "debug", "extracted_data": action, "source": courses}, ensure_ascii=False) + "\n"
            chunks = roadmap_chunks(matches[0], courses, semester) if courses else [answer]
            for chunk in chunks:
                yield json.dumps({"type": "chunk", "text": chunk}, ensure_ascii=False) + "\n"

        return StreamingResponse(event_stream_roadmap(), media_type="application/x-ndjson")
    
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