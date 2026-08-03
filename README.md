# 🎓 Hệ Thống Chấm Điểm & Số Hóa PDF Ứng Dụng AI (V2.0)

Dự án này tích hợp mô hình **Qwen2.5-VL-7B** để bóc tách thông tin từ PDF (bao gồm chữ viết máy và viết tay), kết hợp với kiến trúc **Đa Tác Tử (DeepSeek V2.0)** để chấm điểm bài thu hoạch kiến tập tự động. Hệ thống cho phép người dùng kiểm duyệt dữ liệu (Human-in-the-loop) trước khi AI tiến hành kiểm toán.

## 🚀 Hướng Dẫn Cài Đặt

**Bước 1: Clone kho lưu trữ về máy**
git clone https://github.com/your-username/AIGrader_WebApp_Final.git
cd AIGrader_WebApp_Final

**Bước 2: Tạo môi trường ảo và cài đặt thư viện**
python -m venv .venv

# Kích hoạt môi trường (Windows)
.venv\Scripts\activate

# Cài đặt thư viện
pip install -r requirements.txt

**Bước 3: Cấu hình biến môi trường**
Sao chép file `.env.example` thành `.env`:
cp .env.example .env

Mở file `.env` và điền URL của 2 API (OCR và Chấm điểm) đã được deploy trên Modal.com.

**Bước 4: Khởi chạy hệ thống**
streamlit run app.py

Hệ thống sẽ tự động mở trên trình duyệt tại địa chỉ `http://localhost:8501`.