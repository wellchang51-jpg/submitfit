"use client";

import { useEffect, useRef, useState } from "react";

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [outputName, setOutputName] = useState("");
  const [message, setMessage] = useState("");
  const [isCompressing, setIsCompressing] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [estimatedSecondsLeft, setEstimatedSecondsLeft] = useState<
    number | null
  >(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  function removePdfExtension(filename: string) {
    return filename.replace(/\.pdf$/i, "");
  }

  function estimateProcessingSeconds(file: File) {
    const fileSizeMB = file.size / 1024 / 1024;

    if (fileSizeMB <= 4) return 30;
    if (fileSizeMB <= 10) return 90;
    if (fileSizeMB <= 20) return 180;
    if (fileSizeMB <= 40) return 300;

    return 420;
  }

  useEffect(() => {
    function checkScreenSize() {
      setIsMobile(window.innerWidth <= 768);
    }

    checkScreenSize();

    window.addEventListener("resize", checkScreenSize);

    return () => {
      window.removeEventListener("resize", checkScreenSize);
    };
  }, []);

  useEffect(() => {
    if (!isCompressing || estimatedSecondsLeft === null) return;

    const timer = window.setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
      setEstimatedSecondsLeft((prev) => {
        if (prev === null) return null;
        return Math.max(prev - 1, 0);
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isCompressing, estimatedSecondsLeft]);

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    setMessage("");

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("請上傳 PDF 檔案");

      setSelectedFile(null);
      setOutputName("");

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      return;
    }

    setSelectedFile(file);
    setOutputName(removePdfExtension(file.name));
  }

  function clearName() {
    setOutputName("");
    setMessage("");
  }

  function removeFile() {
    setSelectedFile(null);
    setOutputName("");
    setMessage("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function chooseAnotherFile() {
    fileInputRef.current?.click();
  }

  async function handleCompress() {
    setMessage("");

    if (!selectedFile) {
      setMessage("請先上傳 PDF 檔案。");
      return;
    }

    if (!outputName.trim()) {
      setMessage("請輸入壓縮後的檔名。");
      return;
    }

    const estimatedSeconds = estimateProcessingSeconds(selectedFile);

    setIsCompressing(true);
    setEstimatedSecondsLeft(estimatedSeconds);
    setElapsedSeconds(0);
    setMessage("正在為你的學習歷程檔案壓縮到 4MB 以下，請不要關閉頁面。");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("output_name", outputName);

    try {
      const response = await fetch(
        "https://submitfit-backend.onrender.com/compress",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        setMessage(errorData?.detail || "壓縮失敗，請稍後再試。");
        return;
      }

      const blob = await response.blob();

      const finalFileName = outputName.toLowerCase().endsWith(".pdf")
        ? outputName
        : `${outputName}.pdf`;

      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = downloadUrl;
      link.download = finalFileName;

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(downloadUrl);

      const originalSize = response.headers.get("X-Original-Size");
      const compressedSize = response.headers.get("X-Compressed-Size");

      if (originalSize && compressedSize) {
        const originalMB = (Number(originalSize) / 1024 / 1024).toFixed(2);
        const compressedMB = (Number(compressedSize) / 1024 / 1024).toFixed(2);

        if (Number(compressedSize) <= 4 * 1024 * 1024) {
          setMessage(
            `壓縮完成：${originalMB} MB → ${compressedMB} MB，已符合學習歷程 4MB 限制，檔案已下載。`
          );
        } else {
          setMessage(
            `已盡力壓縮：${originalMB} MB → ${compressedMB} MB，但仍超過 4MB。為了保留圖片與版面完整，建議拆分 PDF 或降低原始圖片解析度。`
          );
        }
      } else {
        setMessage("壓縮完成，檔案已下載。");
      }
    } catch (error) {
      setMessage("前端連不到後端，請確認後端服務目前是否啟動。");
    } finally {
      setIsCompressing(false);
      setEstimatedSecondsLeft(null);
      setElapsedSeconds(0);
    }
  }

  return (
    <main
      style={{
        ...styles.page,
        ...(isMobile ? styles.pageMobile : {}),
      }}
    >
      <section
        style={{
          ...styles.card,
          ...(isMobile ? styles.cardMobile : {}),
        }}
      >
        <p style={styles.logo}>Drago&apos;s project</p>

        <h1
          style={{
            ...styles.title,
            ...(isMobile ? styles.titleMobile : {}),
          }}
        >
          幫助學習歷程壓縮器
        </h1>

        <p
          style={{
            ...styles.subtitle,
            ...(isMobile ? styles.subtitleMobile : {}),
          }}
        >
          專為高中生上傳學習歷程設計。上傳 PDF 後，系統會自動壓縮到
          4MB 以下，並盡量保留文字與圖片清晰度。
        </p>

        <div
          style={{
            ...styles.mobileNotice,
            ...(isMobile ? styles.mobileNoticeMobile : {}),
          }}
        >
          <p style={styles.mobileNoticeTitle}>手機使用提醒</p>
          <p style={styles.mobileNoticeText}>
            建議用 Safari，再用 Chrome。下載完可以到分享傳去檔案，或是在下載裡面找。
          </p>
        </div>

        <div
          style={{
            ...styles.grid,
            ...(isMobile ? styles.gridMobile : {}),
          }}
        >
          <div>
            <label style={styles.label}>上傳 PDF</label>

            <div style={styles.uploadArea}>
              <div
                style={{
                  ...styles.uploadBox,
                  ...(isMobile ? styles.uploadBoxMobile : {}),
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={handleFileChange}
                  style={{ display: "none" }}
                />

                {selectedFile ? (
                  <div>
                    <p style={styles.fileName}>{selectedFile.name}</p>
                    <p style={styles.fileInfo}>
                      原始大小：{(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                ) : (
                  <div>
                    <p style={styles.uploadTitle}>點擊選擇 PDF</p>
                    <p style={styles.uploadHint}>專為學習歷程 4MB 限制設計</p>
                  </div>
                )}
              </div>

              {selectedFile && (
                <div
                  style={{
                    ...styles.fileButtonRow,
                    ...(isMobile ? styles.fileButtonRowMobile : {}),
                  }}
                >
                  <button onClick={removeFile} style={styles.removeFileButton}>
                    移除檔案
                  </button>

                  <button
                    onClick={chooseAnotherFile}
                    style={styles.chooseFileButton}
                  >
                    選擇其他檔案
                  </button>
                </div>
              )}
            </div>
          </div>

          <div
            style={{
              ...(isMobile ? styles.nameSectionMobile : {}),
            }}
          >
            <label style={styles.label}>壓縮後檔名</label>

            <div
              style={{
                ...styles.nameRow,
                ...(isMobile ? styles.nameRowMobile : {}),
              }}
            >
              <input
                value={outputName}
                onChange={(event) => setOutputName(event.target.value)}
                placeholder="請輸入檔名"
                style={{
                  ...styles.input,
                  ...(isMobile ? styles.inputMobile : {}),
                }}
              />

              <button
                onClick={clearName}
                style={{
                  ...styles.clearButton,
                  ...(isMobile ? styles.clearButtonMobile : {}),
                }}
              >
                清除
              </button>
            </div>

            <p style={styles.hint}>不用輸入 .pdf，下載時會自動加上。</p>

            <div style={styles.infoBox}>
              <p style={styles.infoTitle}>壓縮目標</p>
              <p style={styles.infoText}>
                系統會自動壓縮到 4MB 以下，適合上傳學習歷程檔案。
                線上版會優先保留圖片與版面完整，大檔案可能需要數分鐘。
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={handleCompress}
          style={{
            ...styles.primaryButton,
            ...(isMobile ? styles.primaryButtonMobile : {}),
            ...(isCompressing ? styles.primaryButtonDisabled : {}),
          }}
          disabled={isCompressing}
        >
          {isCompressing ? "正在處理檔案……" : "開始壓縮到 4MB 以下"}
        </button>

        {isCompressing && estimatedSecondsLeft !== null && (
          <div style={styles.progressBox}>
            <p style={styles.progressTitle}>正在壓縮中</p>

            <p style={styles.progressText}>
              預估處理時間：線上版通常需要 1～4 分鐘，大檔案可能更久
            </p>

            <p style={styles.progressHint}>
              已處理約 {elapsedSeconds} 秒。系統會優先保留圖片與版面完整；
              30MB 以上的 PDF 可能需要數分鐘，請不要重新整理或關閉頁面。
            </p>
          </div>
        )}

        {message && <p style={styles.message}>{message}</p>}
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f4f6fb",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "40px 20px",
    fontFamily: "Arial, sans-serif",
    boxSizing: "border-box",
  },
  pageMobile: {
    alignItems: "flex-start",
    padding: "18px 12px",
  },
  card: {
    width: "100%",
    maxWidth: "920px",
    background: "white",
    borderRadius: "24px",
    padding: "36px",
    boxShadow: "0 20px 60px rgba(15, 23, 42, 0.08)",
    boxSizing: "border-box",
  },
  cardMobile: {
    maxWidth: "100%",
    padding: "20px",
    borderRadius: "18px",
  },
  logo: {
    margin: "0 0 8px",
    fontSize: "14px",
    fontWeight: 800,
    color: "#4f46e5",
    letterSpacing: "0.08em",
  },
  title: {
    margin: 0,
    fontSize: "36px",
    lineHeight: 1.2,
    color: "#111827",
    wordBreak: "break-word",
  },
  titleMobile: {
    fontSize: "29px",
    lineHeight: 1.25,
  },
  subtitle: {
    marginTop: "14px",
    marginBottom: "20px",
    color: "#64748b",
    fontSize: "16px",
    lineHeight: 1.7,
  },
  subtitleMobile: {
    fontSize: "15px",
    lineHeight: 1.65,
    marginBottom: "16px",
  },
  mobileNotice: {
    marginBottom: "28px",
    padding: "14px 16px",
    borderRadius: "14px",
    background: "#fff7ed",
    border: "1px solid #fed7aa",
  },
  mobileNoticeMobile: {
    padding: "13px",
    marginBottom: "22px",
  },
  mobileNoticeTitle: {
    margin: 0,
    color: "#9a3412",
    fontWeight: 800,
    fontSize: "14px",
  },
  mobileNoticeText: {
    margin: "6px 0 0",
    color: "#9a3412",
    fontSize: "14px",
    lineHeight: 1.7,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "24px",
  },
  gridMobile: {
    gridTemplateColumns: "1fr",
    gap: "26px",
  },
  label: {
    display: "block",
    marginBottom: "10px",
    fontWeight: 700,
    color: "#111827",
  },
  uploadArea: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  uploadBox: {
    minHeight: "170px",
    border: "2px dashed #cbd5e1",
    borderRadius: "18px",
    background: "#f8fafc",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    padding: "20px",
    boxSizing: "border-box",
  },
  uploadBoxMobile: {
    minHeight: "150px",
    padding: "18px",
  },
  uploadTitle: {
    margin: 0,
    fontSize: "18px",
    fontWeight: 800,
    textAlign: "center",
    color: "#111827",
  },
  uploadHint: {
    marginTop: "8px",
    color: "#64748b",
    textAlign: "center",
  },
  fileName: {
    margin: 0,
    fontSize: "16px",
    fontWeight: 800,
    color: "#111827",
    textAlign: "center",
    wordBreak: "break-all",
  },
  fileInfo: {
    marginTop: "8px",
    color: "#64748b",
    textAlign: "center",
  },
  fileButtonRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "10px",
  },
  fileButtonRowMobile: {
    gridTemplateColumns: "1fr",
  },
  removeFileButton: {
    height: "42px",
    border: "none",
    borderRadius: "12px",
    background: "#fee2e2",
    color: "#991b1b",
    fontWeight: 800,
    cursor: "pointer",
  },
  chooseFileButton: {
    height: "42px",
    border: "none",
    borderRadius: "12px",
    background: "#e0e7ff",
    color: "#3730a3",
    fontWeight: 800,
    cursor: "pointer",
  },
  nameSectionMobile: {
    paddingTop: "4px",
  },
  nameRow: {
    display: "flex",
    gap: "10px",
  },
  nameRowMobile: {
    flexDirection: "column",
    gap: "12px",
  },
  input: {
    flex: 1,
    width: "100%",
    height: "48px",
    border: "1px solid #cbd5e1",
    borderRadius: "12px",
    padding: "0 14px",
    fontSize: "16px",
    outline: "none",
    color: "#111827",
    background: "white",
    fontWeight: 700,
    boxSizing: "border-box",
  },
  inputMobile: {
    height: "54px",
    fontSize: "17px",
    padding: "0 16px",
  },
  clearButton: {
    height: "48px",
    border: "none",
    borderRadius: "12px",
    padding: "0 16px",
    background: "#e2e8f0",
    color: "#1e293b",
    fontWeight: 800,
    cursor: "pointer",
  },
  clearButtonMobile: {
    width: "100%",
    height: "48px",
  },
  hint: {
    marginTop: "10px",
    color: "#64748b",
    fontSize: "14px",
  },
  infoBox: {
    marginTop: "24px",
    padding: "16px",
    borderRadius: "14px",
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
  },
  infoTitle: {
    margin: 0,
    fontWeight: 800,
    color: "#111827",
  },
  infoText: {
    margin: "8px 0 0",
    color: "#64748b",
    lineHeight: 1.6,
  },
  primaryButton: {
    marginTop: "30px",
    width: "100%",
    height: "54px",
    border: "none",
    borderRadius: "14px",
    background: "#4f46e5",
    color: "white",
    fontSize: "17px",
    fontWeight: 800,
    cursor: "pointer",
  },
  primaryButtonMobile: {
    height: "52px",
    fontSize: "16px",
    marginTop: "24px",
  },
  primaryButtonDisabled: {
    background: "#94a3b8",
    cursor: "not-allowed",
  },
  progressBox: {
    marginTop: "16px",
    padding: "16px",
    borderRadius: "14px",
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
  },
  progressTitle: {
    margin: 0,
    fontWeight: 800,
    color: "#111827",
  },
  progressText: {
    margin: "8px 0 0",
    color: "#3730a3",
    fontWeight: 800,
    lineHeight: 1.6,
  },
  progressHint: {
    margin: "8px 0 0",
    color: "#64748b",
    fontSize: "14px",
    lineHeight: 1.6,
  },
  message: {
    marginTop: "16px",
    padding: "14px 16px",
    borderRadius: "12px",
    background: "#eef2ff",
    color: "#3730a3",
    fontWeight: 700,
    lineHeight: 1.6,
    wordBreak: "break-word",
  },
};