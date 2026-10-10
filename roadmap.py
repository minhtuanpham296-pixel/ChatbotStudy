"""Dynamic intent examples and complete, database-backed roadmap formatting."""

import json
import re
import unicodedata
from collections import defaultdict


def normalize_name(value):
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).replace("đ", "d").split())


def resolve_major(requested, names):
    """Prefer an exact match; never silently combine ambiguous majors."""
    key = normalize_name(requested)
    if not key:
        return []
    exact = [name for name in names if normalize_name(name) == key]
    return exact or [name for name in names if key in normalize_name(name)]


def build_roadmap_examples(message, names, limit=3):
    """Select relevant real majors, then instantiate question/tool-call pairs."""
    text = normalize_name(message)
    words = set(re.findall(r"\w+", text))
    names = sorted(set(name for name in names if name))
    ranked = sorted(names, key=lambda name: (
        -int(normalize_name(name) in text),
        -len(words & set(normalize_name(name).split())), name,
    ))
    examples = []
    for major in ranked[:limit]:
        for question, semester in (
            (f"Lộ trình học ngành {major}", "ALL"),
            (f"Tất cả môn học ngành {major} theo từng học kỳ", "ALL"),
            (f"Ngành {major} học kỳ 2 có những môn nào?", "2"),
        ):
            examples.append({"question": question, "function_call": {
                "name": "query_roadmap",
                "args": {"ten_nganh": major, "hoc_ky": semester},
            }})
    return examples


def build_routing_instruction(message, names):
    examples = build_roadmap_examples(message, names)
    return (
        "Chọn công cụ dựa trên CÂU HỎI MỚI, dùng lịch sử chỉ để hiểu ngành đang nói đến. "
        "Hỏi lộ trình/chương trình đào tạo/danh sách môn theo kỳ: query_roadmap. "
        "Không chỉ rõ kỳ hoặc hỏi toàn khóa/từng kỳ: hoc_ky='ALL'; không mặc định kỳ 1. "
        "Hỏi một kỳ cụ thể: hoc_ky là số kỳ dưới dạng chuỗi. "
        "Thiếu ngành trong cả câu hỏi lẫn lịch sử: ten_nganh=''. "
        "Không chọn đại một ngành. Tên ngành phải lấy từ danh sách nếu xác định được. "
        "Hỏi hướng nghề nghiệp AI/Web/Data: query_specialization_electives, "
        "không nhầm với yêu cầu liệt kê toàn bộ chương trình đào tạo.\n"
        "Danh sách ngành hiện có:\n" + json.dumps(names, ensure_ascii=False)
        + "\nVí dụ few-shot được tạo theo ngành liên quan đến câu hỏi hiện tại "
        "(chỉ minh họa cách gọi hàm, không phải dữ liệu môn học):\n"
        + json.dumps(examples, ensure_ascii=False)
    )


def normalize_semester(value):
    text = str(value or "").strip()
    if not text or text.casefold() in {"all", "tất cả", "toàn khóa"}:
        return None
    if re.fullmatch(r"[0-9]+(?:\.0)?", text) and int(float(text)) > 0:
        return str(int(float(text)))
    raise ValueError("Học kỳ phải là số nguyên dương hoặc ALL.")


def _semester_key(value):
    text = str(value or "").strip()
    if re.fullmatch(r"[0-9]+(?:\.0)?", text):
        return (0, int(float(text)), "")
    return (1, 0, text)


def _display(value):
    text = str(value if value is not None else "").strip()
    if not text or text.casefold() in {"nan", "none", "null"}:
        return "Chưa có dữ liệu"
    # Keep Markdown table cells on one line, without corrupting course codes.
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def roadmap_chunks(major, courses, semester=None):
    """Render all returned rows without a second LLM call or output-token limit."""
    scope = f"học kỳ {semester}" if semester else "theo từng học kỳ"
    yield f"Lộ trình học ngành **{_display(major)}** — {scope}.\n\n"
    groups = defaultdict(list)
    for course in courses:
        raw = course.get("hk")
        label = str(raw or "").strip()
        if label.casefold() in {"", "nan", "none", "null"}:
            label = "Chưa xác định"
        elif re.fullmatch(r"[0-9]+(?:\.0)?", label):
            label = str(int(float(label)))
        groups[label].append(course)
    for label in sorted(groups, key=_semester_key):
        title = "Môn chưa xác định học kỳ" if label == "Chưa xác định" else f"Học kỳ {label}"
        yield f"### {title}\n\n| Mã môn | Tên môn | Tín chỉ | Loại học phần |\n|---|---|---|---|\n"
        for course in sorted(groups[label], key=lambda c: (str(c.get("name") or ""), str(c.get("code") or ""))):
            cells = [_display(course.get(key)) for key in ("code", "name", "tc", "loai_mon")]
            yield "| " + " | ".join(cells) + " |\n"
        yield "\n"
    yield (
        "Danh sách gồm các môn có trong dữ liệu, bao gồm môn tự chọn nếu có; "
        "không có nghĩa bạn phải đăng ký tất cả môn tự chọn. "
        "Hãy đối chiếu chương trình đào tạo chính thức trước khi đăng ký."
    )
