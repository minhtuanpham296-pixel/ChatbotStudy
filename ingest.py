import glob
import pandas as pd
import re
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# 1. Load cấu hình từ file .env
load_dotenv()

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "12345678")

MAJOR_MAPPING = {
    "CNTT": "Công nghệ thông tin",
    "CONGNGHEKYTHUATDIENTUVIENTHONG": "Công nghệ kỹ thuật điện tử viễn thông",
    "CONGNGHEKYTHUATDIENTU": "Công nghệ kỹ thuật điện tử",
    "KETOAN": "Kế toán",
    "KHOAHOCDULIEU": "Khoa học dữ liệu",
    "KHOAHOCMOITRUONG": "Khoa học môi trường",
    "KIEMTOAN": "Kiểm toán",
    "KINHDOANHQUOCTE": "Kinh doanh quốc tế",
    "KYTHUATPHANMEM": "Kỹ thuật phần mềm",
    "LUAT": "Luật",
    "NGONNGUANH": "Ngôn ngữ Anh",
    "QUANLYGIAODUC": "Quản lý giáo dục",
    "QUANTRIKINHDOANH": "Quản trị kinh doanh",
    "QUANTRIVANPHONG": "Quản trị văn phòng",
    "QUOCTEHOC": "Quốc tế học",
    "TAICHINHNGANHANG": "Tài chính ngân hàng",
    "TAMLYHOC": "Tâm lý học",
    "THONGTINTHUVIEN": "Thông tin thư viện",
    "TOANUNGDUNG": "Toán ứng dụng",
    "TRITUENHANTAO": "Trí tuệ nhân tạo",
    "VIETNAMHOC": "Việt Nam học",
    "CONGNGHEKYTHUATMOITRUONG": "Công nghệ kỹ thuật môi trường",
    "DULICH": "Du lịch",
    "GIAODUCCHINHTRI": "Giáo dục chính trị",
    "GIAODUCMAMNON": "Giáo dục mầm non",
    "GIAODUCTIEUHOC": "Giáo dục tiểu học",
    "KYTHUATDIEN": "Kỹ thuật điện",
    "KYTHUATDIENTUVIENTHONG(THIETKEVIMACH)": "Kỹ thuật điện tử viễn thông(thiết kế vi mạch)",
    "QUANTRINHAHANGVADICHVUANUONG": "Quản trị nhà hàng và dịch vụ ăn uống",
    "SUPHAMTOANHOC": "Sư phạm toán học",
    "SUPHAMVATLY": "Sư phạm vật lý",
    "DIALYHOC": "Địa lý học",
    "LICHSUHOC": "Lịch sử học",
    "SUPHAMAMNHAC": "Sư phạm âm nhạc",
    "SUPHAMKHOAHOCTUNHIEN(GIAOVIENTHCS)": "Sư phạm khoa học tự nhiên(dành cho giáo viên THCS)",
    "SUPHAMLICHSUDIALY(GIAOVIENTHCS)": "Sư phạm lịch sử địa lý(dành cho giáo viên THCS)",
    "SUPHAMLICHSU": "Sư phạm lịch sử",
    "SUPHAMMYTHUAT": "Sư phạm mỹ thuật",
    "SUPHAMNGUVAN": "Sư phạm ngữ văn",
    "SUPHAMSINHHOC": "Sư phạm sinh học",
    "SUPHAMTIENGANH": "Sư phạm tiếng Anh",
}

def load_data_to_neo4j():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    file_list = glob.glob("data/*.xlsx")
    
    if not file_list: return

    # Gom tất cả dữ liệu từ 21 file vào 1 danh sách duy nhất để xử lý cực nhanh
    all_courses = []
    all_prerequisites = []

    print(f"📂 Đang đọc {len(file_list)} file Excel...")
    for file_name in file_list:
        # Lấy tên ngành từ tên file (Ví dụ: 'data/cntt_ekg.xlsx' -> 'CNTT')
        base_name = os.path.basename(file_name) 
        raw_major = base_name.replace('_ekg.xlsx', '').replace('.xlsx', '').upper()
        major_name = MAJOR_MAPPING.get(raw_major, raw_major)

        df = pd.read_excel(file_name)
        df = df.dropna(subset=['Mã HP', 'Tên học phần'], how='all')
        
        for _, row in df.iterrows():
            code = str(row['Mã HP']).replace('.0', '').strip()
            all_courses.append({
                "code": code,
                "name": str(row['Tên học phần']).strip(),
                "credits": str(row['Số TC']).replace('.0', '').strip(),
                "semester": str(row['Học kỳ']).replace('.0', '').strip(),
                "kb": str(row.get('Khối kiến thức', '')).strip(),
                "type": str(row.get('Loại học phần', '')).strip(),
                "major": major_name # THÊM DÒNG NÀY: Lưu tên ngành vào danh sách
            })
            
            # Gom quan hệ tiên quyết
            pre_raw = str(row['Mã HP học trước']).strip()
            if pre_raw and pre_raw.lower() != 'nan':
                for p_code in [c.replace('.0', '').strip() for c in re.split(',|;', pre_raw)]:
                    if p_code:
                        all_prerequisites.append({"code": code, "p_code": p_code})

    # NẠP VÀO NEO4J BẰNG BATCH (CỰC NHANH)
    with driver.session() as session:
        print("🚀 Đang đẩy dữ liệu vào Graph Database...")
        
        # Nạp Node môn học bằng UNWIND 
        session.run("""
            UNWIND $rows AS row
            MERGE (c:Course {code: row.code})
            SET c.name = row.name, 
                c.credits = row.credits, 
                c.semester = row.semester
        """, rows=all_courses)

        # Nạp quan hệ tiên quyết bằng UNWIND
        session.run("""
            UNWIND $rows AS row
            MATCH (c:Course {code: row.code})
            MERGE (p:Course {code: row.p_code})
            MERGE (c)-[:TIEN_QUYET]->(p)
        """, rows=all_prerequisites)
        
        # THÊM ĐOẠN NÀY: Nạp quan hệ phân loại (Bắt buộc/Tự chọn)
        session.run("""
            UNWIND $rows AS row
            WITH row WHERE row.type <> "" AND row.type <> "nan"
            MATCH (c:Course {code: row.code})
            MERGE (t:CourseType {name: row.type}) // Tạo nút loại môn (Tự chọn/Bắt buộc)
            MERGE (c)-[:THUOC_LOAI]->(t)         // Kéo mũi tên quan hệ
        """, rows=all_courses)

        # THÊM ĐOẠN NÀY: Nạp quan hệ Khối kiến thức (Đại cương/Chuyên ngành)
        session.run("""
            UNWIND $rows AS row
            WITH row WHERE row.kb <> "" AND row.kb <> "nan"
            MATCH (c:Course {code: row.code})
            MERGE (k:KnowledgeBlock {name: row.kb}) // Tạo nút khối kiến thức
            MERGE (c)-[:THUOC_KHOI]->(k)            // Kéo mũi tên quan hệ
        """, rows=all_courses)
        
        # THÊM ĐOẠN NÀY: Nạp quan hệ Ngành học
        session.run("""
            UNWIND $rows AS row
            WITH row WHERE row.major <> ""
            MATCH (c:Course {code: row.code})
            MERGE (m:Major {name: row.major}) // Tạo nút Ngành
            MERGE (c)-[:THUOC_NGANH]->(m)     // Kéo mũi tên quan hệ
        """, rows=all_courses)

    print(f"✅ Xong! Đã nạp {len(all_courses)} nút và {len(all_prerequisites)} quan hệ.")
    driver.close()

if __name__ == "__main__":
    # Chỉ chạy khi bạn thực thi trực tiếp file này: python ingest.py
    load_data_to_neo4j()