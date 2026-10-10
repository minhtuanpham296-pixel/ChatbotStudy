from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class Neo4jManager:
    def __init__(self):
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]

        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
    )   

    def close(self):
        self.driver.close()

    def query_knowledge(self, input_text):
        with self.driver.session() as session:
            # Xử lý từ khóa để tìm kiếm mờ (Fuzzy Search)
            # Ví dụ: "triet hoc" -> "triet~ hoc~" (Cho phép gõ sai/thiếu dấu)
            words = input_text.split()
            search_query = " ".join([f"{word}~" for word in words])
            
            # Sử dụng Full-Text Search thay cho CONTAINS
            cypher = """
            CALL db.index.fulltext.queryNodes("course_search", $search_query) YIELD node AS c, score
            
            // Lọc bớt các kết quả có điểm (score) quá thấp để tránh lạc đề râu ông nọ cắm cằm bà kia
            WHERE score > 0.5 
            
            OPTIONAL MATCH (c)-[:TIEN_QUYET]->(pre)
            OPTIONAL MATCH (c)-[:THUOC_LOAI]->(type:CourseType)
            OPTIONAL MATCH (c)-[:THUOC_KHOI]->(kb:KnowledgeBlock)
            
            RETURN c.name AS name, 
                   c.code AS code, 
                   c.credits AS tc, 
                   c.semester AS hk,
                   type.name AS loai_mon,
                   kb.name AS khoi_kien_thuc,
                   collect(DISTINCT pre.name) AS pres,
                   score // Trả về cả điểm tin cậy
            ORDER BY score DESC // Sắp xếp kết quả chính xác nhất lên đầu
            LIMIT 3
            """
            results = session.run(cypher, search_query=search_query)
            return [dict(r) for r in results]

    def query_roadmap(self, nganh, hoc_ky=None):
        with self.driver.session() as session:
            # The caller resolves one canonical major; no mixing similar names.
            cypher = """
            MATCH (c:Course)-[r:THUOC_NGANH]->(m:Major)
            WHERE m.name = $nganh
              AND ($hk IS NULL OR
                   toInteger(coalesce(r.semester, c.semester)) = toInteger($hk))
            RETURN DISTINCT c.code AS code, c.name AS name,
                   coalesce(r.credits, c.credits) AS tc,
                   coalesce(r.semester, c.semester) AS hk,
                   r.course_type AS loai_mon
            ORDER BY toInteger(hk), name, code
            """
            results = session.run(cypher, nganh=nganh, hk=hoc_ky)
            return [dict(r) for r in results]
        
    def query_overview(self):
        with self.driver.session() as session:
            # Lệnh Cypher đếm tổng số Node Major và gom tên chúng lại thành 1 danh sách
            cypher = """
            MATCH (m:Major)
            RETURN count(m) AS tong_so_nganh, collect(m.name) AS danh_sach_nganh
            """
            results = session.run(cypher)
            return [dict(r) for r in results]
    def query_prerequisite_courses_by_major(self, nganh):
        with self.driver.session() as session:
            # Tìm các môn thuộc ngành X CÓ mũi tên chỉ sang môn tiên quyết
            cypher = """
            MATCH (c:Course)-[:THUOC_NGANH]->(m:Major)
            WHERE toLower(m.name) CONTAINS toLower($nganh)
            MATCH (c)-[:TIEN_QUYET]->(pre:Course)
            RETURN c.name AS mon_hoc, c.semester AS hk, collect(pre.name) AS cac_mon_tien_quyet
            LIMIT 10
            """
            results = session.run(cypher, nganh=nganh)
            return [dict(r) for r in results]
        
    def query_elective_courses(self, nganh):
        with self.driver.session() as session:
            # Truy vấn tìm các môn thuộc ngành X và có loại là "Tự chọn"
            cypher = """
            MATCH (c:Course)-[:THUOC_NGANH]->(m:Major)
            WHERE toLower(m.name) CONTAINS toLower($nganh)
            MATCH (c)-[:THUOC_LOAI]->(t:CourseType)
            WHERE toLower(t.name) CONTAINS 'tự chọn' OR toLower(t.name) CONTAINS 'tu chon'
            RETURN c.name AS mon_hoc, c.credits AS tc, c.semester AS hk
            ORDER BY c.semester ASC
            """
            results = session.run(cypher, nganh=nganh)
            return [dict(r) for r in results]
# Khởi tạo db
db = Neo4jManager()
