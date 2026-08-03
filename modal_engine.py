import modal
import re
from fastapi import Request, Security, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel


# --- KHAI BÁO CẤU TRÚC REQUEST ĐẦU VÀO ---
class GradingRequest(BaseModel):
    document_text: str


# 1. Khai báo App - Trái tim của toàn bộ hệ thống Serverless
app = modal.App("phase1-gatekeeper-2026")

# --- CƠ CHẾ BẢO MẬT API (BEARER TOKEN) ---
security = HTTPBearer()
SECRET_API_KEY = "satori_2026_secure_key"  # Mật khẩu để WebApp được quyền gọi API


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Hàm chặn cửa: Nếu API Key gửi lên không khớp, lập tức trả về lỗi 401"""
    if credentials.credentials != SECRET_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai API Key! Bạn không có quyền truy cập hệ thống chấm điểm.",
        )
    return credentials.credentials


# ------------------------------------------

# 2. Khởi tạo Volume (Ổ cứng đám mây) để lưu trữ vĩnh viễn trọng số mô hình
CACHE_DIR = "/root/.cache/huggingface"
hf_volume = modal.Volume.from_name("qwen-weights-cache", create_if_missing=True)

# 3. Định nghĩa Image (Môi trường Linux Backend trên Modal)
gatekeeper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.26.0",
        "huggingface_hub",
        "hf-transfer",
        "fastapi[standard]"
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "VLLM_USE_FLASHINFER_SAMPLER": "0",
        "VLLM_ATTENTION_BACKEND": "TRITON"  # Chốt chặn bắt buộc để T4 GPU chạy mượt
    })
    .add_local_file("schemas.py", remote_path="/root/schemas.py")
)

# 4. Viết hàm tải trọng số ngầm từ Hugging Face vào Volume
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-AWQ"

# Gatekeeper System Prompt
GATEKEEPER_PROMPT = """You are a STRICT structural parser (Gatekeeper).
Your ONLY task is to scan the provided document and detect the presence of 3 mandatory sections:
1. Factory Overview
2. Production Technology Process
3. Food Safety and Hygiene (VSATTP) Conditions

RULES:
- DO NOT summarize the content.
- DO NOT evaluate the scientific accuracy of the text.
- DO NOT fix errors.
- You must ONLY output a valid JSON object matching the exact schema requested."""


@app.function(
    image=gatekeeper_image,
    volumes={CACHE_DIR: hf_volume},
    timeout=1800
)
def download_model_to_cache():
    from huggingface_hub import snapshot_download
    print(f"🚀 Bắt đầu tải trọng số {MODEL_NAME} vào Volume đám mây...")
    snapshot_download(
        repo_id=MODEL_NAME,
        local_dir=f"{CACHE_DIR}/{MODEL_NAME}",
        ignore_patterns=["*.pt", "*.bin"]
    )
    print("✅ Đã tải xong và lưu Cache thành công! Container sẵn sàng Scale-to-Zero.")


# Khai báo Class bọc Endpoint, ép chạy trên Lớp Tiết Kiệm T4 GPU
@app.cls(
    gpu="T4",
    image=gatekeeper_image,
    volumes={CACHE_DIR: hf_volume},
    max_containers=10,
    scaledown_window=900,
    min_containers=1
)
class GatekeeperEndpoint:
    @modal.enter()
    def load_model(self):
        # noinspection PyUnresolvedReferences
        from vllm import LLM
        print("⏳ Đang nạp Qwen2.5-7B từ Cache vào VRAM của T4 GPU...")
        self.llm = LLM(
            model=f"{CACHE_DIR}/{MODEL_NAME}",
            tensor_parallel_size=1,
            gpu_memory_utilization=0.9,
            max_model_len=8192
        )
        print("✅ Nạp mô hình thành công. Sẵn sàng nhận lệnh!")

    @modal.method()
    def parse_structure(self, document_text: str) -> str:
        # noinspection PyUnresolvedReferences
        from vllm import SamplingParams
        json_template = '''{
      "has_overview": true,
      "has_process": true,
      "has_safety": false
    }'''
        prompt = (
            f"<|im_start|>system\n{GATEKEEPER_PROMPT}\n"
            f"You MUST output JSON ONLY in the exact format of this example:\n{json_template}<|im_end|>\n"
            f"<|im_start|>user\n{document_text}<|im_end|>\n"
            f"<|im_start|>assistant\n{{"
        )
        sampling_params = SamplingParams(temperature=0.0, max_tokens=150)
        outputs = self.llm.generate([prompt], sampling_params)
        raw_output = outputs[0].outputs[0].text
        return "{" + raw_output


# =====================================================================
# GIAI ĐOẠN 2 & 3: HỘI ĐỒNG GIÁM KHẢO TỐI CAO (A100 GPU)
# =====================================================================

DEEPSEEK_CACHE_DIR = "/root/.cache/deepseek"
deepseek_volume = modal.Volume.from_name("deepseek-weights-cache", create_if_missing=True)
expert_image = gatekeeper_image
DEEPSEEK_MODEL_NAME = "casperhansen/deepseek-r1-distill-llama-70b-awq"


@app.function(
    image=expert_image,
    volumes={DEEPSEEK_CACHE_DIR: deepseek_volume},
    timeout=3600
)
def download_deepseek_to_cache():
    from huggingface_hub import snapshot_download
    print(f"🚀 Bắt đầu tải siêu mô hình {DEEPSEEK_MODEL_NAME} (~40GB) vào Volume đám mây...")
    snapshot_download(
        repo_id=DEEPSEEK_MODEL_NAME,
        local_dir=f"{DEEPSEEK_CACHE_DIR}/{DEEPSEEK_MODEL_NAME}",
        ignore_patterns=["*.pt", "*.bin"]
    )
    print("✅ Đã tải xong Siêu mô hình 70B! Vùng chứa đã tự động Scale-to-Zero.")


# ==========================================
# BỘ CÂU LỆNH MỒI (PROMPTS) ĐÃ ĐƯỢC VÁ LỖI
# ==========================================
PROMPT_ACADEMIC_REVIEWER = """You are the Academic Reviewer.
Your ONLY job is to evaluate the depth, technical density, and overall effort of this factory internship report.
CRITICAL RULES:
1. DO NOT search for or penalize scientific/HACCP errors. That is someone else's job.
2. Focus ONLY on the structure, detailed explanations, and presence of technical data.
3. List out the "Bright Spots" (Ưu điểm) of the report.

OUTPUT FORMAT (Strictly in Vietnamese):
[ĐIỂM SÁNG]
- (Liệt kê ưu điểm 1)
- (Liệt kê ưu điểm 2)

[ĐÁNH GIÁ CHIỀU SÂU]
(Viết 3-4 câu nhận xét về mức độ chi tiết và hàm lượng chất xám của bài làm)

[BASE SCORE]
(Chỉ ghi một con số duy nhất từ 0.0 đến 10.0)
"""

PROMPT_PROSECUTOR = """You are the Strict Prosecutor (Food Engineering & QA Expert).
Your ONLY job is to scan the report and find OBJECTIVE SCIENTIFIC ERRORS or HACCP VIOLATIONS.
CRITICAL RULES:
1. PENALTY RULE: You are FORBIDDEN to penalize for missing explanations, lack of economic ROI analysis, or optimization debates. 
2. ONLY penalize if a parameter is physically impossible (e.g., water boiling at 500°C, RO membrane 10cm) or clearly violates biological safety (e.g., unpurified water for final rinsing).

OUTPUT FORMAT (Strictly in Vietnamese). If no errors, output "KHÔNG CÓ LỖI". If errors exist, list them EXACTLY like this:
[LỖI]: (Tên lỗi)
[LÝ DO]: (Giải thích khoa học ngắn gọn)
[TRỪ DỰ KIẾN]: (Số điểm, ví dụ: 0.5 hoặc 1.0)
"""

PROMPT_DEFENDER = """You are the Defense Attorney.
You will receive a factory internship report and a Prosecution Report (Cáo trạng).
Your job is to defend the student by looking for context, modern automation logic, or inline sensors that might explain the "errors" found by the Prosecutor.

CRITICAL RULES FOR DEFENSE:
1. DO NOT INVENT FACTS. You must base your defense ONLY on the text provided or general engineering logic. If the text clearly states a dangerous practice (e.g., "tráng lần cuối bằng nước lã"), you MUST ACCEPT the error. Do not hallucinate that they treated it later if the text doesn't say so.

OUTPUT FORMAT (Strictly in Vietnamese):
[LỖI BỊ CÁO BUỘC]: (Tên lỗi)
[PHÁN QUYẾT]: (BẢO VỆ THÀNH CÔNG / BẤT LỰC CHẤP NHẬN LỖI)
[LẬP LUẬN]: (Lý do bảo vệ hoặc lý do đồng ý với Công tố)
"""

PROMPT_JUDGE = """You are the Supreme Judge.
You will receive the Prosecutor's Cáo trạng and the Defender's Lập luận.
Your job is to make the FINAL decision on which errors are valid and which are dismissed.
If there are duplicated errors from multiple Prosecutors, combine them into one single penalty.

CRITICAL RULES:
1. Align your final output with your reasoning. If your reasoning concludes the student is innocent, you MUST output KHONG_CO_LOI. Do not copy the prosecutor's list just to fill the format.

CRITICAL OUTPUT FORMAT (You MUST wrap your final verdict exactly between the tags FINAL_ERRORS_BEGIN and FINAL_ERRORS_END).
If there are no valid errors (defense succeeded), format it EXACTLY like this:
FINAL_ERRORS_BEGIN
KHONG_CO_LOI
FINAL_ERRORS_END

If there are valid errors, format EACH error on a new line like this:
- Lỗi: (Tên lỗi) || Lý do: (Giải thích) || Phạt: (0.5 hoặc 1.0)

CRITICAL INSTRUCTION: After you output FINAL_ERRORS_END, you MUST STOP GENERATING IMMEDIATELY. Do not add any explanations, notes, or repeated tags.
"""


@app.cls(
    gpu="A100-80GB",
    image=expert_image,
    volumes={DEEPSEEK_CACHE_DIR: deepseek_volume},
    max_containers=2,
    timeout=1200,
    scaledown_window=900
)
class SupremeCouncilEndpoint:
    @modal.enter()
    def load_super_model(self):
        # noinspection PyUnresolvedReferences
        from vllm import LLM
        print("⏳ Đang nạp Hội đồng DeepSeek-70B AWQ vào VRAM A100...")
        self.llm = LLM(
            model=f"{DEEPSEEK_CACHE_DIR}/{DEEPSEEK_MODEL_NAME}",
            tokenizer="deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            tensor_parallel_size=1,
            gpu_memory_utilization=0.95,
            max_model_len=8192
        )
        print("✅ Hội đồng 70B đã vào vị trí!")

    def _generate_response(self, system_prompt: str, user_content: str, temperature: float = 0.6) -> str:
        # noinspection PyUnresolvedReferences
        from vllm import SamplingParams
        tokenizer = self.llm.get_tokenizer()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        prompt += "<think>\n"

        sampling_params = SamplingParams(temperature=temperature, max_tokens=1500,
                                         stop=["<|eot_id|>", "<|end_of_text|>"])
        outputs = self.llm.generate([prompt], sampling_params)
        return "<think>\n" + outputs[0].outputs[0].text

    @modal.method()
    def evaluate_base_score(self, document_text: str) -> str:
        return self._generate_response(PROMPT_ACADEMIC_REVIEWER, document_text, temperature=0.5)

    @modal.method()
    def prosecute(self, document_text: str) -> str:
        return self._generate_response(PROMPT_PROSECUTOR, document_text, temperature=0.1)

    @modal.method()
    def defend(self, document_text: str, prosecution_report: str) -> str:
        user_content = f"--- BÁO CÁO CỦA SINH VIÊN ---\n{document_text}\n\n--- TỔNG HỢP CÁO TRẠNG TỪ TỔ CÔNG TỐ ---\n{prosecution_report}"
        return self._generate_response(PROMPT_DEFENDER, user_content, temperature=0.3)

    @modal.method()
    def judge(self, prosecution_report: str, defense_report: str) -> str:
        user_content = f"--- CÁO TRẠNG ---\n{prosecution_report}\n\n--- LUẬT SƯ BÀO CHỮA ---\n{defense_report}"
        return self._generate_response(PROMPT_JUDGE, user_content, temperature=0.1)


# =====================================================================
# GIAI ĐOẠN 4: NHẠC TRƯỞNG ĐÁM MÂY & WEBHOOK API
# =====================================================================

@app.function(
    image=gatekeeper_image,
    timeout=1800
)
@modal.fastapi_endpoint(method="POST")
def grade_report_api(request: GradingRequest, token: str = Depends(verify_token)):
    print(f"🚀 [API Nhận Lệnh] Đang xử lý báo cáo với độ dài: {len(request.document_text.split())} từ.")

    print("🔍 [Phase 1] Kích hoạt Gatekeeper kiểm tra cấu trúc...")
    gatekeeper = GatekeeperEndpoint()
    json_structure_str = gatekeeper.parse_structure.remote(request.document_text)

    from schemas import StructuralValidation, BaoCaoKiemToan, LoiChuyenMon

    try:
        validated_data = StructuralValidation.model_validate_json(json_structure_str)
    except Exception as e:
        validated_data = StructuralValidation(has_overview=True, has_process=True, has_safety=True)

    danh_sach_loi_cuoi_cung = []

    if not validated_data.has_safety:
        print("⚠️ [Penalty] Gatekeeper phát hiện thiếu mục VSATTP!")
        danh_sach_loi_cuoi_cung.append(
            LoiChuyenMon(
                phan_muc="Cấu trúc bài làm",
                loi_sai="Thiếu hoàn toàn mục Đánh giá VSATTP.",
                giai_thich_ngan_gon="Báo cáo không tuân thủ cấu trúc bắt buộc.",
                diem_tru=2.0
            )
        )

    print("🧠 [Phase 2A] Kích hoạt 3 Tác tử Học thuật chạy SONG SONG để lấy trung bình Base Score...")
    expert = SupremeCouncilEndpoint()
    base_score_reports = list(expert.evaluate_base_score.map([request.document_text] * 3))

    base_scores = []
    diem_sang_list = []
    danh_gia_chieu_sau = ""
    lich_su_think = ""

    for idx, rep in enumerate(base_score_reports):
        # 1. Bóc tách phần Suy luận (Think) và Phần trả lời (Clean Text)
        think_match = re.search(r'<think>(.*?)</think>', rep, re.DOTALL)
        clean_rep = re.sub(r'<think>.*?</think>', '', rep, flags=re.DOTALL).strip()

        # BẢO HIỂM: Nếu model quên đóng tag </think>, ta dùng toàn bộ text (cắt bỏ chữ <think> mở đầu)
        if not clean_rep:
            clean_rep = rep.replace('<think>', '').strip()

        # 2. Tìm Base Score bằng Regex linh hoạt (chấp nhận có hoặc không có ngoặc vuông, khoảng trắng thừa)
        match = re.search(r'\[?BASE SCORE\]?\s*[:\-]*\s*([\d\.]+)', clean_rep, re.IGNORECASE)
        if match:
            base_scores.append(float(match.group(1)))

        if idx == 0:
            lich_su_think = think_match.group(
                1).strip() if think_match else "Không có dữ liệu suy luận (hoặc model quên đóng tag)."

            # 3. Tìm Điểm Sáng
            ds_match = re.search(r'\[?ĐIỂM SÁNG\]?(.*?)\[?ĐÁNH GIÁ CHIỀU SÂU\]?', clean_rep, re.DOTALL | re.IGNORECASE)
            if ds_match:
                lines = ds_match.group(1).strip().split('\n')
                diem_sang_list = [line.strip('- *') for line in lines if line.strip()]

            # 4. Tìm Đánh Giá Chiều Sâu
            dg_match = re.search(r'\[?ĐÁNH GIÁ CHIỀU SÂU\]?(.*?)\[?BASE SCORE\]?', clean_rep, re.DOTALL | re.IGNORECASE)
            if dg_match:
                danh_gia_chieu_sau = dg_match.group(1).strip()

    avg_base_score = round(sum(base_scores) / len(base_scores), 1) if base_scores else 7.0
    print(f"📊 [Toán học] Các Base Score AI cho: {base_scores} -> Trung bình chốt: {avg_base_score}")

    # ---------------------------------------------------------
    # PHASE 2B & 3: TỔ CÔNG TỐ & PHIÊN TÒA ĐỐI KHÁNG
    # ---------------------------------------------------------
    print("⚖️ [Phase 2B] Kích hoạt Tổ Công Tố (3 Tác tử) rà soát độc lập...")

    # Kích hoạt 3 Công tố viên chạy song song để tránh việc "bỏ lọt tội phạm"
    prosecution_reports = list(expert.prosecute.map([request.document_text] * 3))

    bien_ban_cong_to = ""
    has_error = False

    # Gom kết quả của 3 Công tố viên
    for idx, pros in enumerate(prosecution_reports):
        # Lọc bỏ phần <think> để tránh bị nhiễu từ khóa "KHÔNG CÓ LỖI" lọt vào suy nghĩ
        pros_no_think = re.sub(r"<think>.*?</think>", "", pros, flags=re.DOTALL).strip()

        # Nếu có bất kỳ Công tố viên nào tìm thấy lỗi, ghi nhận vào Siêu Cáo Trạng
        if "KHÔNG CÓ LỖI" not in pros_no_think.upper() and "[LỖI" in pros_no_think.upper():
            has_error = True
            bien_ban_cong_to += f"\n--- LỜI BUỘC TỘI TỪ CÔNG TỐ VIÊN SỐ {idx + 1} ---\n{pros_no_think}\n"

    bien_ban = ""
    # Mở phiên tòa nếu Tổ Công Tố tìm thấy ít nhất 1 lỗi
    if has_error:
        print("🛡️ [Phase 3A] Tổ Công Tố phát hiện lỗi. Gọi Luật sư biện hộ...")
        defense = expert.defend.remote(request.document_text, bien_ban_cong_to)

        print("👨‍⚖️ [Phase 3B] Gọi Thẩm phán chốt án và gộp lỗi (Deduplication)...")
        judge_verdict = expert.judge.remote(bien_ban_cong_to, defense)

        bien_ban = f"=== TỔNG HỢP CÁO TRẠNG (3 CÔNG TỐ) ===\n{bien_ban_cong_to}\n\n=== LUẬT SƯ PHẢN BIỆN ===\n{defense}\n\n=== PHÁN QUYẾT TỐI CAO ===\n{judge_verdict}"

        # Python trích xuất án phạt bằng Regex từ Template của Thẩm phán
        verdict_match = re.search(r'FINAL_ERRORS_BEGIN(.*?)FINAL_ERRORS_END', judge_verdict, re.DOTALL)
        if verdict_match:
            lines = verdict_match.group(1).strip().split('\n')
            for line in lines:
                if '||' in line:
                    parts = line.split('||')
                    if len(parts) >= 3:
                        try:
                            loi = parts[0].replace('- Lỗi:', '').strip()
                            ly_do = parts[1].replace('Lý do:', '').strip()
                            phat_str = parts[2].replace('Phạt:', '').strip()
                            phat = float(phat_str)
                            danh_sach_loi_cuoi_cung.append(
                                LoiChuyenMon(
                                    phan_muc="Nhận định từ Hội Đồng",
                                    loi_sai=loi,
                                    giai_thich_ngan_gon=ly_do,
                                    diem_tru=phat
                                )
                            )
                        except Exception as e:
                            print(f"Lỗi parse Regex Thẩm phán: {e}")
    else:
        bien_ban = "=== TỔNG HỢP CÁO TRẠNG ===\n(Tổ Công Tố 3 thành viên không tìm thấy lỗi khoa học nào. Phiên tòa không diễn ra.)"

    # ---------------------------------------------------------
    # PHASE 4: PYTHON TÍNH TOÁN (ĐỘ CHÍNH XÁC TUYỆT ĐỐI 100%)
    # ---------------------------------------------------------
    print("🧮 [Phase 4] Python đang làm phép toán trừ...")
    tong_diem_phat = sum(err.diem_tru for err in danh_sach_loi_cuoi_cung)
    diem_tong_ket = max(0.0, avg_base_score - tong_diem_phat)
    diem_tong_ket = round(diem_tong_ket, 1)

    final_data = BaoCaoKiemToan(
        diem_noi_dung=avg_base_score,
        danh_gia_chieu_sau=danh_gia_chieu_sau,
        diem_sang=diem_sang_list,
        cac_loi_sai=danh_sach_loi_cuoi_cung,
        diem_tong_ket=diem_tong_ket,
        lich_su_think=lich_su_think,
        bien_ban_hoi_dong=bien_ban
    )

    print(f"✅ [Hoàn Thành] Trả JSON về WebApp: {diem_tong_ket}/10")
    return final_data.model_dump()