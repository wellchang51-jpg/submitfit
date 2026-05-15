import json
from pathlib import Path

from adobe.pdfservices.operation.auth.service_principal_credentials import (
    ServicePrincipalCredentials,
)
from adobe.pdfservices.operation.exception.exceptions import (
    ServiceApiException,
    ServiceUsageException,
    SdkException,
)
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdfjobs.jobs.compress_pdf_job import CompressPDFJob
from adobe.pdfservices.operation.pdfjobs.params.compress_pdf.compress_pdf_params import (
    CompressPDFParams,
)
from adobe.pdfservices.operation.pdfjobs.params.compress_pdf.compression_level import (
    CompressionLevel,
)
from adobe.pdfservices.operation.pdfjobs.result.compress_pdf_result import (
    CompressPDFResult,
)


BASE_DIR = Path(__file__).parent
CREDENTIALS_PATH = BASE_DIR / "pdfservices-api-credentials.json"
INPUT_PATH = BASE_DIR / "test.pdf"
OUTPUT_PATH = BASE_DIR / "adobe_output.pdf"


def load_credentials():
    with open(CREDENTIALS_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    client_id = data.get("client_credentials", {}).get("client_id")
    client_secret = data.get("client_credentials", {}).get("client_secret")

    if not client_id or not client_secret:
        raise RuntimeError("credentials JSON 裡找不到 client_id 或 client_secret")

    return ServicePrincipalCredentials(
        client_id=client_id,
        client_secret=client_secret,
    )


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError("找不到 test.pdf，請把測試 PDF 放到 backend 並改名為 test.pdf")

    credentials = load_credentials()
    pdf_services = PDFServices(credentials=credentials)

    with open(INPUT_PATH, "rb") as file:
        input_stream = file.read()

    input_asset = pdf_services.upload(
        input_stream=input_stream,
        mime_type=PDFServicesMediaType.PDF,
    )

    compress_params = CompressPDFParams(compression_level=CompressionLevel.HIGH)
    compress_job = CompressPDFJob(input_asset=input_asset, compress_pdf_params=compress_params)

    location = pdf_services.submit(compress_job)
    pdf_services_response = pdf_services.get_job_result(location, CompressPDFResult)

    result_asset: CloudAsset = pdf_services_response.get_result().get_asset()
    stream_asset: StreamAsset = pdf_services.get_content(result_asset)

    with open(OUTPUT_PATH, "wb") as file:
        file.write(stream_asset.get_input_stream())

    original_mb = INPUT_PATH.stat().st_size / 1024 / 1024
    output_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024

    print("Adobe 壓縮完成")
    print(f"原始大小：{original_mb:.2f} MB")
    print(f"壓縮後：{output_mb:.2f} MB")
    print(f"輸出檔案：{OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (ServiceApiException, ServiceUsageException, SdkException) as error:
        print("Adobe API 發生錯誤：")
        print(error)
    except Exception as error:
        print("發生錯誤：")
        print(error)