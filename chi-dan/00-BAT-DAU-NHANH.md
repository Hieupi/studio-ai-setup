# Bắt Đầu Nhanh Trong 1 Phút — Studio AI Setup

Chào mừng bạn đến với **Studio AI Setup**. Nếu bạn mới làm quen với AI, làm YouTube, dựng video hay chạy các bộ kit/repo trên GitHub, bạn chỉ cần làm đúng **4 việc đơn giản** dưới đây.

---

## 1. Mở Lại Trợ Lý AI Sau Khi Cài Xong
Sau khi trình cài báo **Cài xong rồi!**, hãy **đóng và mở lại** trình biên tập AI bạn đang dùng (*Antigravity, Claude Code, Codex hoặc VS Code*) để phần mềm nhận đầy đủ kỹ năng mới và bộ điều phối tự động.

---

## 2. Đăng Nhập GitHub (Chỉ làm 1 lần duy nhất)
Nếu bạn cần tải các bộ kit hoặc repo từ GitHub về máy:
- Tại màn hình hoàn tất của trình cài, bấm nút **`Đăng nhập GitHub (Tải Kit)`**.
- Trình duyệt web sẽ mở ra và hiện một mã 8 ký tự — bạn dán mã đó rồi bấm **Authorize** để xác nhận.
- Nếu muốn mở bằng tay sau này, mở **PowerShell** (nhấn phím Windows → gõ `PowerShell` → Enter) và gõ:
  ```powershell
  gh auth login
  ```

---

## 3. Bạn Đang Làm Việc Gì Thì Đọc Tệp Chỉ Dẫn Đó

| Việc bạn muốn làm | Mở tệp chỉ dẫn này | Công cụ chính đã cài sẵn |
| :--- | :--- | :--- |
| **Viết kịch bản, bài viết, lọc câu bị "mùi AI"** | [`01-lo-content.md`](01-lo-content.md) | `humanizer-vi`, `translationese-cleaner-vi`, `lint.py` |
| **Edit video, cắt khoảng lặng, âm thanh, soi video mẫu** | [`02-lo-edit-video.md`](02-lo-edit-video.md) | `ffmpeg`, `auto-editor`, `ffmpeg-skill`, `rea-video`, `sound-design`, `media-picker` |
| **Tải repo/kit từ GitHub, cài thư viện, sửa lỗi code** | [`03-lo-code.md`](03-lo-code.md) | `git`, `gh`, `uv`, `superpowers` (15 kỹ năng), `karpathy-guidelines`, `ruff`, `pytest` |
| **Nghiên cứu ngách, đo xu hướng, đọc PDF/DOCX, phân tích app** | [`04-lo-cao-du-lieu.md`](04-lo-cao-du-lieu.md) | `REA 6.10.1 MCP`, `yt-dlp`, `trendspyg`, `markitdown` |

---

## 4. Nguyên Tắc Vàng Khi Làm Việc Với Bất Kỳ Bộ Kit Nào
1. **Không cần nhớ tên lệnh phức tạp:** Bộ luật điều phối tự động đã được cài sẵn. Bạn chỉ cần **mở đúng thư mục dự án** trong trợ lý AI và nói yêu cầu bằng tiếng Việt bình thường — AI sẽ tự đọc tệp `CLAUDE.md` (nếu dự án có) và chọn đúng bộ kỹ năng phù hợp.
2. **Thấy dự án có tệp `CLAUDE.md`:** Đó là bộ nội quy riêng của dự án đó. Trợ lý AI sẽ luôn ưu tiên làm theo tệp này trước.
3. **Gặp lỗi khó hiểu:** Copy nguyên dòng báo lỗi dán vào khung chat và nói: *"Kiểm tra giúp tôi lỗi này và giải thích dễ hiểu nguyên nhân."*

---

## Câu Hỏi Thường Gặp (FAQ)

- **Tôi lỡ tắt nhầm giữa lúc cài đặt thì sao?**  
  Chỉ cần nhấp đúp lại biểu tượng **Studio AI Setup** trên màn hình nền (hoặc chạy lại `cai-dat.bat`). Trình cài tự bỏ qua những phần đã cài xong và cài tiếp phần còn thiếu.
- **Công cụ Python cài ở đâu? Có làm hỏng máy tôi không?**  
  Mọi công cụ Python của từng Lô được tách gọn vào môi trường ảo riêng tại `%LocalAppData%\StudioAISetup\venvs\`, không trộn lẫn vào hệ thống và có thể xóa sạch bất cứ lúc nào.
- **Tôi có phải trả phí bản quyền cho bộ cài này không?**  
  Không. Bộ cài hoàn toàn miễn phí theo giấy phép MIT và tải trực tiếp các gói nguồn mở về máy bạn. Các dịch vụ AI bên ngoài (như API trả phí nếu bạn tự dùng trong dự án riêng) do tài khoản cá nhân của bạn tự quản lý.
