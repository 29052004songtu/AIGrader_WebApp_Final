import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Tải biến môi trường
load_dotenv()
OCR_API_URL = os.getenv("OCR_API_URL")
GRADING_API_URL = os.getenv("GRADING_API_URL")

st.set_page_config(page_title="Hệ Thống Chấm Điểm AI V2.0", layout="wide", page_icon="🎓")

# Quản lý trạng thái (Session State)
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "is_extracted" not in st.session_state:
    st.session_state.is_extracted = False
if "grading_result" not in st.session_state:
    st.session_state.grading_result = None

st.title("🎓 Hệ Thống Số Hóa & Kiểm Toán Chuyên Môn Tự Động")
st.markdown("Quy trình: **Nộp bài (PDF)** ➔ **AI Trích xuất Text** ➔ **Sinh viên Kiểm duyệt** ➔ **AI Chấm điểm**")

# BƯỚC 1: UPLOAD & TRÍCH XUẤT
st.header("1. Tải lên bài thu hoạch (PDF)")
uploaded_file = st.file_uploader("Kéo thả hoặc chọn file PDF chứa chữ viết máy xen kẽ viết tay", type=["pdf"])

if uploaded_file is not None and not st.session_state.is_extracted:
    if st.button("🚀 Bắt đầu trích xuất AI", type="primary", use_container_width=True):
        if not OCR_API_URL:
            st.error("Chưa cấu hình OCR_API_URL trong file .env")
        else:
            with st.spinner("🤖 Đang chạy Qwen2.5-VL bóc tách PDF (Có thể mất 30s - 1 phút)..."):
                try:
                    # Gọi API Modal Qwen2.5-VL
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(OCR_API_URL, files=files)

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.extracted_text = data.get("extracted_text", "")
                        st.session_state.is_extracted = True
                        st.rerun()
                    else:
                        st.error(f"Lỗi API: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"Lỗi kết nối: {str(e)}")

# BƯỚC 2: KIỂM DUYỆT & CHỈNH SỬA
if st.session_state.is_extracted:
    st.header("2. Trình Soạn Thảo Kiểm Duyệt (Human-in-the-loop)")
    st.info(
        "💡 Vui lòng rà soát và chỉnh sửa các lỗi chính tả (nếu có) do AI bóc tách từ chữ viết tay trước khi đưa vào chấm điểm.")

    # Giao diện Text Area rộng rãi để chỉnh sửa
    edited_text = st.text_area(
        "Nội dung văn bản (Có thể chỉnh sửa trực tiếp):",
        value=st.session_state.extracted_text,
        height=500
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Tải lại file khác", use_container_width=True):
            st.session_state.is_extracted = False
            st.session_state.extracted_text = ""
            st.session_state.grading_result = None
            st.rerun()

    with col2:
        if st.button("✅ Lưu & Tiến hành Chấm điểm", type="primary", use_container_width=True):
            if not GRADING_API_URL:
                st.error("Chưa cấu hình GRADING_API_URL trong file .env")
            else:
                with st.spinner("⚖️ Tổ Công Tố và Luật Sư đang kiểm toán dữ liệu (Vui lòng đợi 1 - 2 phút)..."):
                    try:
                        # Gọi API Chấm điểm (DeepSeek V2.0)
                        payload = {"report_text": edited_text}
                        grade_response = requests.post(GRADING_API_URL, json=payload)

                        if grade_response.status_code == 200:
                            st.session_state.grading_result = grade_response.json()
                        else:
                            st.error(f"Lỗi hệ thống chấm điểm: {grade_response.status_code} - {grade_response.text}")
                    except Exception as e:
                        st.error(f"Lỗi kết nối API chấm điểm: {str(e)}")

# BƯỚC 3: HIỂN THỊ KẾT QUẢ CHẤM ĐIỂM
if st.session_state.grading_result:
    st.markdown("---")
    st.header("3. Bảng Điểm & Kết Quả Kiểm Toán")

    res = st.session_state.grading_result

    # Hiển thị KPI bằng Metrics của Streamlit
    m1, m2, m3 = st.columns(3)
    m1.metric(label="📌 Điểm Nội Dung (Base Score)", value=f"{res.get('base_score', 0)} / 10")
    m2.metric(label="⚠️ Tổng Điểm Phạt", value=f"- {res.get('total_penalty', 0)}")
    m3.metric(label="🏆 ĐIỂM TỔNG KẾT", value=f"{res.get('final_score', 0)} / 10")

    # Hiển thị Điểm sáng
    with st.expander("✨ Điểm Sáng & Ưu Điểm Bài Làm", expanded=True):
        highlights = res.get("highlights", [])
        if highlights:
            for hl in highlights:
                st.markdown(f"- {hl}")
        else:
            st.write("Chưa ghi nhận điểm sáng nổi bật.")

    # Hiển thị Lỗi sai
    with st.expander("⚖️ Danh Sách Lỗi Phạm Quy & Án Phạt (Đã gộp & bảo vệ)", expanded=True):
        errors = res.get("errors", [])
        if errors:
            for err in errors:
                st.error(
                    f"**Lỗi:** {err.get('error_name')}  \n**Giải thích:** {err.get('reason')}  \n**Phạt:** -{err.get('penalty_score')} điểm")
        else:
            st.success("🎉 Bài làm hoàn hảo, không phát hiện lỗi khoa học hay vi phạm HACCP!")

    # Hiển thị Log không gian suy luận (Dành cho Giảng viên kiểm chứng)
    with st.expander("🧠 Xem Log Không Gian Suy Luận (Dành cho Giảng Viên)"):
        st.code(res.get("think_log", "Không có log suy luận."), language="markdown")