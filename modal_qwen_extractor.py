import modal
import io
import base64
import gc
import asyncio
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse


def download_model_to_image():
    import huggingface_hub
    print("📥 Đang nén model Qwen2.5-VL-AWQ vào Container Image...")
    huggingface_hub.snapshot_download(
        "Qwen/Qwen2.5-VL-7B-Instruct-AWQ",
        ignore_patterns=["*.pt", "*.bin"]
    )


image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "vllm",
        "PyMuPDF",
        "Pillow",
        "fastapi",
        "python-multipart",
        "opencv-python-headless",
        "numpy",
        "huggingface_hub",
        "hf_transfer"
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "VLLM_USE_FLASHINFER_SAMPLER": "0"
    })
    .run_function(download_model_to_image)
)

app = modal.App("qwen-pdf-ocr-api")


@app.cls(gpu="A10G", scaledown_window=300, min_containers=1, image=image)
class QwenPDFExtractor:
    @modal.enter()
    def load_model(self):
        # noinspection PyUnresolvedReferences
        from vllm import LLM
        print("⏳ Đang tải mô hình Qwen2.5-VL-7B-AWQ vào GPU A10G...")
        self.llm = LLM(
            model="Qwen/Qwen2.5-VL-7B-Instruct-AWQ",
            max_model_len=8192,  # 🚀 NÂNG CẤP: Tăng gấp đôi độ dài ngữ cảnh để chứa ảnh lớn
            gpu_memory_utilization=0.9,
            enforce_eager=True
        )
        print("✅ Tải mô hình hoàn tất!")

    def _extract_sequential_elements(self, pdf_bytes: bytes) -> list:
        import fitz
        from PIL import Image

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        sequential_elements = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_elements = []

            text_blocks = page.get_text("blocks")
            for x0, y0, x1, y1, text, block_no, block_type in text_blocks:
                if block_type == 0 and text.strip():
                    page_elements.append(
                        {"type": "machine_text", "content": text.strip(), "y_coord": y0, "x_coord": x0})

            dict_blocks = page.get_text("dict")["blocks"]
            for block in dict_blocks:
                if block["type"] == 1:
                    try:
                        bbox = block["bbox"]
                        image_bytes = block["image"]
                        pil_img = Image.open(io.BytesIO(image_bytes))

                        if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
                            background = Image.new('RGB', pil_img.size, (255, 255, 255))
                            background.paste(pil_img, mask=pil_img.convert('RGBA').split()[3])
                            pil_img = background
                        else:
                            pil_img = pil_img.convert("RGB")

                        if pil_img.width > 30 and pil_img.height > 30:
                            page_elements.append(
                                {"type": "handwritten_image", "content": pil_img, "y_coord": bbox[1],
                                 "x_coord": bbox[0]}
                            )
                    except Exception as e:
                        pass

            page_elements.sort(key=lambda e: (e["y_coord"], e["x_coord"]))
            sequential_elements.extend(page_elements)

        return sequential_elements

    @modal.fastapi_endpoint(method="POST")
    async def process_pdf(self, file: UploadFile = File(...)):
        # noinspection PyUnresolvedReferences
        from vllm import SamplingParams
        from PIL import Image
        import re  # Thêm thư viện Regex

        pdf_bytes = await file.read()
        elements = self._extract_sequential_elements(pdf_bytes)

        sampling_params = SamplingParams(temperature=0.01, max_tokens=2000)

        # 🚀 CẬP NHẬT 1: Ra lệnh ép AI trả về "EMPTY" nếu ảnh không có chữ
        vlm_prompt = (
            "Bạn là hệ thống OCR tự động. Hãy trích xuất chính xác văn bản tiếng Việt trong ảnh. "
            "TUYỆT ĐỐI KHÔNG thêm bình luận hay câu mào đầu. KHÔNG dùng markdown. "
            "Nếu bức ảnh KHÔNG có chữ (chỉ là logo hoặc nền trống), hãy trả về duy nhất chữ: EMPTY"
        )

        def pil_to_base64(img):
            max_edge = 1536
            if max(img.size) > max_edge:
                ratio = max_edge / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            buffered = io.BytesIO()
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(buffered, format="JPEG", quality=85)
            return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

        async def generate():
            yield "Khởi động AI thành công! Đang tiến hành đọc luồng dữ liệu...\n\n"
            await asyncio.sleep(0.5)

            for elem in elements:
                if elem["type"] == "machine_text":
                    yield elem["content"] + "\n\n"
                    await asyncio.sleep(0.01)

                elif elem["type"] == "handwritten_image":
                    raw_img = elem["content"]
                    b64_url = pil_to_base64(raw_img)

                    messages = [
                        {"role": "user", "content": [
                            {"type": "text", "text": vlm_prompt},
                            {"type": "image_url", "image_url": {"url": b64_url}}
                        ]}
                    ]

                    try:
                        outputs = await asyncio.to_thread(
                            self.llm.chat, messages, sampling_params=sampling_params
                        )
                        ocr_text = outputs[0].outputs[0].text.strip()

                        # 🚀 CẬP NHẬT 2: Tiêu diệt ảnh rác và các câu chào hỏi thừa thãi
                        if "EMPTY" in ocr_text.upper() or len(ocr_text) < 3:
                            continue  # Bỏ qua luôn ảnh này

                        # Cạo sạch các câu mào đầu kiểu "Chương trình OCR đã..."
                        ocr_text = re.sub(r'(?i)^(.*?trích xuất.*?:|.*?như sau:)\s*', '', ocr_text)
                        ocr_text = ocr_text.replace('```markdown', '').replace('```', '').strip()

                        if ocr_text:
                            yield ocr_text + "\n\n"
                            await asyncio.sleep(0.01)
                    except Exception as e:
                        yield f"[Lỗi trích xuất ảnh: {str(e)}]\n\n"

                    del raw_img
                    gc.collect()

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")