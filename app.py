import streamlit as st
import requests
import re
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
            # Tạo một vùng trống để hiển thị chữ chạy real-time
            status_text = st.info("🤖 Đang kết nối với Qwen2.5-VL trên đám mây...")
            stream_placeholder = st.empty()

            try:
                # Gọi API Modal Qwen2.5-VL với chế độ stream=True
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(OCR_API_URL, files=files, stream=True, timeout=600)

                if response.status_code == 200:
                    status_text.success("✅ Kết nối thành công! Đang tiến hành đọc dữ liệu luồng...")
                    full_text = ""

                    # Vòng lặp hứng dữ liệu liên tục từ API trả về
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            full_text += chunk
                            # 🚀 CẬP NHẬT 1: Ẩn dòng chữ Ping đi để giao diện trông chuyên nghiệp
                            display_text = full_text.replace(
                                "Khởi động AI thành công! Đang tiến hành đọc luồng dữ liệu...\n\n", "")
                            stream_placeholder.markdown(display_text + " ▌")

                    # 🚀 CẬP NHẬT 2: KÍCH HOẠT BỘ LỌC RÁC STUDOCU TRƯỚC KHI LƯU
                    final_text = full_text.replace("Khởi động AI thành công! Đang tiến hành đọc luồng dữ liệu...\n\n",
                                                   "")
                    final_text = re.sub(r'Downloaded by .*?\n', '', final_text)  # Xóa tên người tải
                    final_text = re.sub(r'lOMoARcPSD\|.*?\n', '', final_text)  # Xóa mã tài liệu chìm
                    final_text = final_text.strip()

                    # Lưu kết quả cuối cùng đã được làm sạch
                    st.session_state.extracted_text = final_text
                    st.session_state.is_extracted = True
                    st.rerun()
                else:
                    status_text.error(f"Lỗi API: {response.status_code} - {response.text}")
            except requests.exceptions.ReadTimeout:
                st.error("Lỗi Timeout: Dữ liệu quá lớn, hệ thống mạng đã ngắt kết nối giữa chừng.")
            except Exception as e:
                st.error(f"Lỗi kết nối: {str(e)}")

# BƯỚC 2: KIỂM DUYỆT & CHỈNH SỬA
if st.session_state.is_extracted:
    st.header("2. Trình Soạn Thảo Kiểm Duyệt (Human-in-the-loop)")
    st.info(
        "💡 Vui lòng rà soát và chỉnh sửa các lỗi chính tả (nếu có) do AI bóc tách từ chữ viết tay trước khi đưa vào chấm điểm."
    )

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
                        # 1. LẤY CHÌA KHÓA TỪ FILE .ENV
                        api_key = os.getenv("GRADING_API_KEY", "")

                        # 2. ĐÓNG GÓI CHÌA KHÓA VÀO HEADERS THEO CHUẨN BEARER TOKEN
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        }

                        payload = {"document_text": edited_text}

                        # 3. GỬI KÈM HEADERS VÀO REQUEST
                        grade_response = requests.post(
                            GRADING_API_URL,
                            json=payload,
                            headers=headers,  # Nâng cấp mấu chốt nằm ở đây
                            timeout=600
                        )

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

    # 🚀 CẬP NHẬT: Đồng bộ Key tiếng Việt từ API trả về
    diem_noi_dung = res.get('diem_noi_dung', 0)
    diem_tong_ket = res.get('diem_tong_ket', 0)
    tong_diem_phat = round(diem_noi_dung - diem_tong_ket, 1)

    # Hiển thị KPI bằng Metrics của Streamlit
    m1, m2, m3 = st.columns(3)
    m1.metric(label="📌 Điểm Nội Dung (Base Score)", value=f"{diem_noi_dung} / 10")
    m2.metric(label="⚠️ Tổng Điểm Phạt", value=f"- {tong_diem_phat}")
    m3.metric(label="🏆 ĐIỂM TỔNG KẾT", value=f"{diem_tong_ket} / 10")

    # Hiển thị Điểm sáng & Đánh giá chiều sâu
    with st.expander("✨ Điểm Sáng & Ưu Điểm Bài Làm", expanded=True):
        danh_gia = res.get("danh_gia_chieu_sau", "")
        if danh_gia:
            st.markdown(f"**Đánh giá tổng quan:** {danh_gia}")

        highlights = res.get("diem_sang", [])
        if highlights:
            for hl in highlights:
                st.markdown(f"- {hl}")
        else:
            st.write("Chưa ghi nhận điểm sáng nổi bật.")

    # Hiển thị Lỗi sai
    with st.expander("⚖️ Danh Sách Lỗi Phạm Quy & Án Phạt (Đã gộp & bảo vệ)", expanded=True):
        errors = res.get("cac_loi_sai", [])
        if errors:
            for err in errors:
                st.error(
                    f"**Lỗi:** {err.get('loi_sai')}  \n**Giải thích:** {err.get('giai_thich_ngan_gon')}  \n**Phạt:** -{err.get('diem_tru')} điểm"
                )
        else:
            st.success("🎉 Bài làm hoàn hảo, không phát hiện lỗi khoa học hay vi phạm HACCP!")

    # Hiển thị Log không gian suy luận & Biên bản
    with st.expander("🧠 Xem Log Không Gian Suy Luận & Biên Bản (Dành cho Giảng Viên)"):
        bien_ban = res.get("bien_ban_hoi_dong", "")
        if bien_ban:
            st.markdown("**Biên bản đối kháng:**")
            st.code(bien_ban, language="markdown")

        think_log = res.get("lich_su_think", "Không có log suy luận.")
        st.markdown("**Suy luận của AI (Think Log):**")
        st.code(think_log, language="markdown")