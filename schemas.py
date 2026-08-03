from pydantic import BaseModel, Field
from typing import List

# ==========================================
# SCHEMA GIAI ĐOẠN 1: KIỂM DUYỆT CẤU TRÚC
# ==========================================
class StructuralValidation(BaseModel):
    has_overview: bool = Field(
        description="Văn bản có chứa phần Giới thiệu tổng quan nhà máy không? (True/False)"
    )
    has_process: bool = Field(
        description="Văn bản có chứa phần Thuyết minh quy trình công nghệ sản xuất không? (True/False)"
    )
    has_safety: bool = Field(
        description="Văn bản có chứa phần Đánh giá thực trạng điều kiện đảm bảo VSATTP không? (True/False)"
    )

# ==========================================
# SCHEMA GIAI ĐOẠN CUỐI: PYTHON TRẢ VỀ WEBAPP
# ==========================================
class LoiChuyenMon(BaseModel):
    phan_muc: str = Field(description="Tên phân mục chứa lỗi")
    loi_sai: str = Field(description="Tóm tắt lỗi sai chuyên môn")
    giai_thich_ngan_gon: str = Field(description="Giải thích nguyên lý khoa học/kỹ thuật")
    diem_tru: float = Field(description="Số điểm trừ cho lỗi này (Số dương)")

class BaoCaoKiemToan(BaseModel):
    diem_noi_dung: float = Field(description="Điểm nội dung cơ bản (Base Score) trên thang 10")
    danh_gia_chieu_sau: str = Field(description="Nhận xét đánh giá chiều sâu của bài làm")
    diem_sang: List[str] = Field(default_factory=list, description="Các ưu điểm nổi bật của bài báo cáo")
    cac_loi_sai: List[LoiChuyenMon] = Field(default_factory=list, description="Danh sách các lỗi sai chuyên môn (nếu có)")
    diem_tong_ket: float = Field(description="Điểm tổng kết cuối cùng (Python tự làm toán)")
    lich_su_think: str = Field(default="", description="Lưu lại tư duy của Tác tử Học thuật")
    bien_ban_hoi_dong: str = Field(default="", description="Lưu lại phiên tòa: Công tố -> Luật sư -> Thẩm phán")