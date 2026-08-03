# 🎓 Hệ Thống Số Hóa PDF & Chấm Điểm Ứng Dụng AI (V2.0)

Dự án này tích hợp mô hình **Qwen2.5-VL-7B** (Vision-Language Model) để bóc tách thông tin từ PDF (bao gồm chữ viết máy xen lẫn viết tay), kết hợp với kiến trúc **Đa Tác Tử (Multi-Agent) sử dụng DeepSeek-70B** để chấm điểm bài thu hoạch/báo cáo tự động. Hệ thống cho phép người dùng kiểm duyệt dữ liệu (Human-in-the-loop) trước khi AI tiến hành kiểm toán.

## 🏗️ Kiến trúc Hệ thống
Dự án được thiết kế theo chuẩn Clean Architecture, tách biệt hoàn toàn Frontend và Backend:
* **Frontend:** Xây dựng bằng `Streamlit`, xử lý giao diện và quản lý Session.
* **Backend (Microservices):** Chạy Serverless trên hạ tầng đám mây `Modal.com`, sử dụng GPU A10G (cho OCR) và cụm GPU A100 (cho Đa Tác Tử chấm điểm).

---

## 🚀 Hướng Dẫn Cài Đặt & Triển Khai (Deployment)

### Bước 1: Clone kho lưu trữ và cài đặt môi trường
Bật Terminal / Command Prompt và chạy các lệnh sau:

    git clone https://github.com/29052004songtu/AIGrader_WebApp_Final.git

    cd AIGrader_WebApp_Final

# Tạo và kích hoạt môi trường ảo (Dành cho Windows)
python -m venv .venv
.venv\Scripts\activate

# Cài đặt toàn bộ thư viện cần thiết
    pip install -r requirements.txt


### Bước 2: Thiết lập tài khoản Đám mây Modal
Hệ thống AI nặng hàng chục GB không thể chạy trên máy cá nhân. Bạn cần có tài khoản tại Modal.com. Sau khi đăng ký, hãy xác thực Terminal của bạn với Modal bằng lệnh:
    
    modal token new


### Bước 3: Triển khai (Deploy) 2 Microservices Backend
Bạn cần đưa 2 bộ não AI lên đám mây. Chạy lần lượt 2 lệnh sau (quá trình này có thể mất vài phút cho lần đầu tiên do hệ thống cần tải mô hình AI vào ổ cứng đám mây):

1. **Deploy API Trích xuất OCR (Qwen2.5-VL):**

    modal deploy modal_qwen_extractor.py   

    *(Sau khi deploy thành công, Modal sẽ cấp cho bạn một đường link URL).*

2. **Deploy API Hội đồng Chấm điểm (DeepSeek-70B):**

    modal deploy modal_engine.py

    *(Modal sẽ cấp tiếp cho bạn một đường link URL thứ hai).*


### Bước 4: Cấu hình biến môi trường (Frontend)
Sao chép file `.env.example` thành `.env`:

    cp .env.example .env

Mở file `.env` lên và điền 2 đường link URL bạn vừa nhận được ở Bước 3 vào, đồng thời nhập API Key bảo mật. 

Ví dụ:

    OCR_API_URL=https://...modal.run
    GRADING_API_URL=https://...modal.run
    GRADING_API_KEY=satori_2026_secure_key


### Bước 5: Khởi chạy Giao diện WebApp
Cuối cùng, gõ lệnh sau để mở phần mềm:

    streamlit run app.py

Trình duyệt sẽ tự động mở hệ thống tại `http://localhost:8501`. Bạn có thể bắt đầu nộp file PDF và trải nghiệm!