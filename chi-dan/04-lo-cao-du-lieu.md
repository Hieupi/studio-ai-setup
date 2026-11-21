# Chỉ Dẫn Lô 4 · Cào Dữ Liệu, Nghiên Cứu Ngách & Phân Tích Đối Thủ

Tài liệu này giúp bạn khai thác bộ công cụ nghiên cứu thị trường, đọc tài liệu và phân tích phần mềm/video một cách **nhanh, tiết kiệm token và an toàn**.

---

## 1. Trong Lô 4 Đã Cài Sẵn Cho Bạn Những Gì?
- **`REA 6.10.1` (`rea-agents` MCP):** Công cụ mạnh mẽ chuyên phân tích cấu trúc ứng dụng, web bundle, tệp đóng gói Desktop/Android/SQLite ngay trong khung chat AI.
- **`yt-dlp` (`2026.10.26`):** Lấy thông tin chi tiết, phụ đề, danh sách video công khai để nghiên cứu chủ đề và từ khóa.
- **`Trendspyg` (`1.9.0`):** Đo xu hướng tìm kiếm theo thời gian trên Google Search và YouTube Search (`--gprop youtube`).
- **`MarkItDown` (`0.1.9`):** Chuyển đổi nhanh các tệp văn bản phức tạp (`.pdf`, `.docx`, `.xlsx`, `.pptx`, trang web HTML) sang Markdown sạch để AI đọc hiểu chính xác 100% mà không tốn dung lượng.

---

## 2. Cách Dùng Từng Công Cụ Đúng Cách (Copy Mẫu Chat Để Dùng Ngay)

### A. Đọc tài liệu PDF / Word / Excel dày hàng trăm trang (`MarkItDown`)
Nếu bạn có file PDF nghiên cứu hoặc file Excel số liệu, hãy bảo AI hoặc chạy lệnh:
```powershell
& "$env:LocalAppData\StudioAISetup\venvs\data\Scripts\markitdown.exe" tai-lieu.pdf -o tai-lieu.md
```
Sau đó gửi tệp `.md` đó cho AI đọc — vừa nhanh vừa ít bị sót số liệu hơn mở trực tiếp file PDF nặng.

### B. Đo xu hướng từ khóa trên YouTube trước khi làm video (`Trendspyg`)
Bảo AI viết 1 đoạn script ngắn dùng `trendspyg` trong `venvs\data` để kiểm tra mức độ quan tâm 12 tháng qua cho 3–5 từ khóa ngách bạn đang cân nhắc.
> *Lưu ý tốc độ:* Không gửi hàng chục yêu cầu liên tục trong vài phút để tránh bị Google tạm giới hạn IP (`429 Rate Limit`). Mỗi lần chỉ kiểm tra một nhóm nhỏ 3–5 từ khóa và lưu kết quả lại.

### C. Lấy phụ đề / thông tin video tham khảo (`yt-dlp`)
```powershell
# Chỉ tải phụ đề tự động và thông tin video (không tốn dung lượng tải cả video)
& "$env:LocalAppData\StudioAISetup\venvs\data\Scripts\yt-dlp.exe" --skip-download --write-auto-subs --sub-lang en,vi "https://www.youtube.com/watch?v=VIDEO_ID"
```
> *Lưu ý:* Nếu bộ kit riêng của bạn (có ghi trong `CLAUDE.md`) yêu cầu dùng một cổng hoặc công cụ cào riêng của dự án đó, hãy tuân thủ quy định trong `CLAUDE.md`.

### D. Phân tích cấu trúc App / Web Bundle với `REA`
Trình cài đã tự động đăng ký máy chủ MCP **`rea`** vào các trợ lý AI tìm thấy trên máy (Antigravity, Claude Code, Codex, VS Code).  
Khi muốn kiểm tra một phần mềm hoặc web bundle:
> *"Hãy dùng công cụ REA kiểm tra tóm tắt cấu trúc file này theo chế độ summary trước, không cần đọc tràn lan."*  
Việc bắt đầu bằng `summary` giúp tiết kiệm tới 80–90% bộ nhớ ngữ cảnh của cuộc trò chuyện.

---

## 3. Nguyên Tắc An Toàn Khi Nghiên Cứu & Thu Thập Dữ Liệu
1. Chỉ thu thập dữ liệu công khai hoặc phục vụ học tập/nghiên cứu hợp lệ, tuân thủ điều khoản của từng nền tảng.
2. **Không bao giờ** chia sẻ tệp cookie trình duyệt cá nhân hay khóa API lên mạng hoặc đưa vào các công cụ không rõ nguồn gốc.
3. Khi tải bất kỳ mã nguồn lạ nào từ GitHub về máy để chạy thử, luôn đọc kỹ tệp `README.md`, danh sách thư viện (`package.json` / `requirements.txt`) và kiểm tra virus trước khi chạy.
