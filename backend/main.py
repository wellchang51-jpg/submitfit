import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_SIZE = 4 * 1024 * 1024
MAX_INPUT_SIZE = 50 * 1024 * 1024


@app.get("/")
def root():
    return {"message": "SubmitFit backend is running"}


def file_size(path: str) -> int:
    return os.path.getsize(path)


def find_ghostscript() -> Optional[str]:
    candidates = [
        "gs",
        "gswin64c",
        "gswin32c",
        r"C:\Program Files\gs\gs10.07.0\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe",
        r"C:\Program Files\gs\gs10.05.0\bin\gswin64c.exe",
    ]

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

        if os.path.exists(candidate):
            return candidate

    return None


def count_pages(path: str) -> int:
    doc = fitz.open(path)
    pages = len(doc)
    doc.close()
    return pages


def is_pdf_visually_valid(path: str, expected_pages: int) -> bool:
    """
    安全檢查：
    1. PDF 要能打開
    2. 頁數不能變少
    3. 每頁都要能渲染
    """
    try:
        doc = fitz.open(path)

        if len(doc) != expected_pages:
            doc.close()
            return False

        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)

            if pix.width <= 0 or pix.height <= 0 or len(pix.samples) == 0:
                doc.close()
                return False

        doc.close()
        return True

    except Exception:
        return False


def ghostscript_compress(input_path: str, output_path: str, setting: str):
    """
    Ghostscript 壓縮：
    優點：盡量保留文字、向量與原始 PDF 結構。
    缺點：不一定能壓到 4MB 以下。
    """
    gs = find_ghostscript()

    if not gs:
        raise RuntimeError("找不到 Ghostscript")

    command = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{setting}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dMonoImageDownsampleType=/Subsample",
        "-dColorImageResolution=120",
        "-dGrayImageResolution=120",
        "-dMonoImageResolution=300",
        f"-sOutputFile={output_path}",
        input_path,
    ]

    subprocess.run(command, check=True)


def rasterize_pdf_preserve_layout(
    input_path: str,
    output_path: str,
    dpi: int,
    jpeg_quality: int,
):
    """
    安全 fallback：
    把每一頁完整渲染成圖片，再重新組成 PDF。

    重點：
    - 不抽文字
    - 不抽圖片
    - 不重建版面
    - 保留整頁視覺結果

    這樣可以避免圖片消失或版面跑掉。
    """
    source_pdf = fitz.open(input_path)
    output_pdf = fitz.open()

    zoom = dpi / 72

    try:
        for page in source_pdf:
            rect = page.rect
            matrix = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=matrix, alpha=False)

            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            image_bytes = io.BytesIO()
            image.save(
                image_bytes,
                format="JPEG",
                quality=jpeg_quality,
                optimize=True,
                progressive=True,
            )
            image_bytes.seek(0)

            new_page = output_pdf.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=image_bytes.getvalue())

        output_pdf.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
        )

    finally:
        output_pdf.close()
        source_pdf.close()


def compress_pdf_to_target(input_path: str, final_output_path: str):
    original_size = file_size(input_path)
    expected_pages = count_pages(input_path)

    candidates: list[tuple[str, int, str]] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # 第一階段：Ghostscript，盡量保留 PDF 原結構
        gs_settings = ["ebook", "screen"]

        for setting in gs_settings:
            output_path = temp_dir_path / f"ghostscript_{setting}.pdf"

            try:
                ghostscript_compress(input_path, str(output_path), setting)

                if output_path.exists() and is_pdf_visually_valid(
                    str(output_path), expected_pages
                ):
                    size = file_size(str(output_path))
                    candidates.append(
                        (str(output_path), size, f"ghostscript-{setting}")
                    )

                    if size <= TARGET_SIZE:
                        shutil.copyfile(output_path, final_output_path)
                        return {
                            "method": f"ghostscript-{setting}",
                            "original_size": original_size,
                            "compressed_size": size,
                            "under_target": True,
                        }

            except Exception:
                pass

        # 第二階段：整頁視覺保留壓縮
        # Render 免費版 CPU 很弱，所以只跑 2 組，避免處理太久。
        raster_settings = [
            (100, 45),
            (80, 35),
        ]

        for dpi, quality in raster_settings:
            output_path = temp_dir_path / f"raster_{dpi}_{quality}.pdf"

            try:
                rasterize_pdf_preserve_layout(
                    input_path=input_path,
                    output_path=str(output_path),
                    dpi=dpi,
                    jpeg_quality=quality,
                )

                if output_path.exists() and is_pdf_visually_valid(
                    str(output_path), expected_pages
                ):
                    size = file_size(str(output_path))
                    candidates.append(
                        (str(output_path), size, f"raster-{dpi}-{quality}")
                    )

                    if size <= TARGET_SIZE:
                        shutil.copyfile(output_path, final_output_path)
                        return {
                            "method": f"raster-{dpi}-{quality}",
                            "original_size": original_size,
                            "compressed_size": size,
                            "under_target": True,
                        }

            except Exception:
                pass

        if not candidates:
            raise RuntimeError("壓縮失敗，沒有產生可用 PDF")

        # 如果都壓不到 4MB，就回傳最小但視覺有效的版本。
        # 原則：內容完整優先，不刪圖片、不刪頁面。
        best_path, best_size, best_method = min(candidates, key=lambda item: item[1])
        shutil.copyfile(best_path, final_output_path)

        return {
            "method": best_method,
            "original_size": original_size,
            "compressed_size": best_size,
            "under_target": best_size <= TARGET_SIZE,
        }


@app.post("/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    output_name: str = Form(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="請上傳 PDF 檔案。")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        input_path = temp_dir_path / "input.pdf"
        output_path = temp_dir_path / "compressed.pdf"

        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if file_size(str(input_path)) > MAX_INPUT_SIZE:
            raise HTTPException(
                status_code=400,
                detail="這份 PDF 超過 50MB。為了保留圖片與版面完整，請先拆分 PDF 或降低原始圖片解析度後再上傳。",
            )

        try:
            result = compress_pdf_to_target(str(input_path), str(output_path))

            if not output_path.exists():
                raise HTTPException(status_code=500, detail="壓縮失敗，沒有輸出檔案。")

            with open(output_path, "rb") as compressed_file:
                pdf_bytes = compressed_file.read()

            headers = {
                "Content-Disposition": 'attachment; filename="compressed.pdf"',
                "X-Original-Size": str(result["original_size"]),
                "X-Compressed-Size": str(result["compressed_size"]),
                "X-Compression-Method": result["method"],
                "X-Under-Target": str(result["under_target"]),
            }

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers=headers,
            )

        except HTTPException:
            raise

        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=f"壓縮失敗：{str(error)}",
            )