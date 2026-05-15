import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import fitz

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_SIZE_MB = 4
TARGET_SIZE_BYTES = TARGET_SIZE_MB * 1024 * 1024
MAX_UPLOAD_MB = 100
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def sanitize_filename(name: str) -> str:
    name = name.strip()

    if not name:
        name = "compressed"

    name = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w\u4e00-\u9fff\s\-.]", "", name)
    name = name[:80].strip()

    if not name:
        name = "compressed"

    return f"{name}.pdf"


def find_ghostscript() -> str:
    for command in ["gswin64c", "gswin32c", "gs"]:
        if shutil.which(command):
            return command

    raise RuntimeError("找不到 Ghostscript，請確認已安裝 gswin64c。")


def run_ghostscript(input_path: str, output_path: str, dpi: int, jpeg_quality: int):
    gs_command = find_ghostscript()

    command = [
        gs_command,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dSAFER",

        # PDF 清理與最佳化
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",
        "-dCompressPages=true",
        "-dUseFlateCompression=true",

        # 移除可能增加大小的互動內容
        "-dPreserveAnnots=false",
        "-dPreserveMarkedContent=false",

        # 彩色圖片降解析度
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={dpi}",
        f"-dColorImageDownsampleThreshold=1.0",

        # 灰階圖片降解析度
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={dpi}",
        f"-dGrayImageDownsampleThreshold=1.0",

        # 黑白圖片降解析度
        "-dDownsampleMonoImages=true",
        "-dMonoImageDownsampleType=/Subsample",
        f"-dMonoImageResolution={max(dpi, 150)}",
        "-dMonoImageDownsampleThreshold=1.0",

        # JPEG 品質
        f"-dJPEGQ={jpeg_quality}",

        f"-sOutputFile={output_path}",
        input_path,
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Ghostscript 壓縮失敗")





def rasterize_pdf_to_4mb(input_path: str, output_dir: str) -> tuple[str, int]:
    """
    終極壓縮：
    把每頁轉成圖片後重新組成 PDF。
    目標是找出低於 4MB 但畫質盡量高的版本。
    """
    attempts = [
        {"dpi": 150, "quality": 75},
        {"dpi": 135, "quality": 72},
        {"dpi": 120, "quality": 70},
        {"dpi": 110, "quality": 68},
        {"dpi": 100, "quality": 65},
        {"dpi": 90, "quality": 62},
        {"dpi": 80, "quality": 58},
        {"dpi": 72, "quality": 55},
        {"dpi": 65, "quality": 52},
        {"dpi": 60, "quality": 50},
        {"dpi": 55, "quality": 48},
        {"dpi": 50, "quality": 45},
        {"dpi": 45, "quality": 42},
        {"dpi": 40, "quality": 38},
        {"dpi": 35, "quality": 34},
        {"dpi": 30, "quality": 30},
        {"dpi": 25, "quality": 25},
        {"dpi": 20, "quality": 20},
    ]

    best_under_path = None
    best_under_size = None

    smallest_path = None
    smallest_size = None

    original_doc = fitz.open(input_path)

    try:
        for index, setting in enumerate(attempts):
            dpi = setting["dpi"]
            quality = setting["quality"]
            zoom = dpi / 72

            output_path = os.path.join(output_dir, f"rasterized_{index}.pdf")

            new_doc = fitz.open()

            for page in original_doc:
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                img_bytes = pix.tobytes("jpeg", jpg_quality=quality)

                new_page = new_doc.new_page(
                    width=page.rect.width,
                    height=page.rect.height,
                )

                new_page.insert_image(page.rect, stream=img_bytes)

            new_doc.save(
                output_path,
                garbage=4,
                deflate=True,
                clean=True,
            )

            new_doc.close()

            output_size = os.path.getsize(output_path)

            if smallest_size is None or output_size < smallest_size:
                smallest_path = output_path
                smallest_size = output_size

            # 低於 4MB 但盡量接近 4MB，通常代表畫質比較高
            if output_size <= TARGET_SIZE_BYTES:
                if best_under_size is None or output_size > best_under_size:
                    best_under_path = output_path
                    best_under_size = output_size

        if best_under_path and best_under_size:
            return best_under_path, best_under_size

        if smallest_path and smallest_size:
            return smallest_path, smallest_size

        raise HTTPException(status_code=500, detail="終極壓縮失敗。")

    finally:
        original_doc.close()


def compress_pdf_to_4mb(input_path: str, output_dir: str) -> tuple[str, int]:
    original_size = os.path.getsize(input_path)

    if original_size <= TARGET_SIZE_BYTES:
        return input_path, original_size

    # 第一階段：模仿 Adobe High compression
    # 重點：保留文字與向量，只壓縮圖片
    ghostscript_attempts = [
        {"dpi": 120, "quality": 75},
        {"dpi": 100, "quality": 70},
        {"dpi": 90, "quality": 65},
        {"dpi": 80, "quality": 60},
        {"dpi": 72, "quality": 55},
        {"dpi": 65, "quality": 50},
        {"dpi": 60, "quality": 45},
    ]

    best_under_path = None
    best_under_size = None

    smallest_gs_path = None
    smallest_gs_size = None

    for index, setting in enumerate(ghostscript_attempts):
        output_path = os.path.join(output_dir, f"gs_adobe_like_{index}.pdf")

        try:
            run_ghostscript(
                input_path=input_path,
                output_path=output_path,
                dpi=setting["dpi"],
                jpeg_quality=setting["quality"],
            )
        except RuntimeError:
            continue

        output_size = os.path.getsize(output_path)

        if smallest_gs_size is None or output_size < smallest_gs_size:
            smallest_gs_path = output_path
            smallest_gs_size = output_size

        if output_size <= TARGET_SIZE_BYTES:
            if best_under_size is None or output_size > best_under_size:
                best_under_path = output_path
                best_under_size = output_size

    # 如果 Ghostscript 已經能低於 4MB，就回傳最接近 4MB 的版本
    # 通常這會比整頁轉圖片清楚
    if best_under_path and best_under_size:
        return best_under_path, best_under_size

    # 第二階段：如果 Ghostscript 最小版本還是壓不下來，才用終極圖片化
    return rasterize_pdf_to_4mb(input_path, output_dir)


@app.get("/")
def home():
    return {"message": "SubmitFit backend is running"}


@app.post("/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    output_name: str = Form(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="目前只支援 PDF 檔案。")

    safe_output_name = sanitize_filename(output_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        input_path = temp_dir_path / f"{uuid.uuid4()}_input.pdf"

        total_size = 0

        with open(input_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"檔案太大，目前最大只支援 {MAX_UPLOAD_MB}MB。",
                    )

                buffer.write(chunk)

        try:
            compressed_path, compressed_size = compress_pdf_to_4mb(
                input_path=str(input_path),
                output_dir=temp_dir,
            )
        except RuntimeError as error:
            raise HTTPException(status_code=500, detail=str(error))

        final_path = temp_dir_path / safe_output_name
        shutil.copyfile(compressed_path, final_path)

        with open(final_path, "rb") as result_file:
            pdf_bytes = result_file.read()

        return Response(
    content=pdf_bytes,
    media_type="application/pdf",
    headers={
        "Content-Disposition": 'attachment; filename="compressed.pdf"',
        "X-Compressed-Size": str(compressed_size),
        "X-Original-Size": str(total_size),
    },
)