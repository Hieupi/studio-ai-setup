# Bắt Đầu Nhanh Trong 1 Phút — Studio AI Setup

Chào mừng bạn đến với **Studio AI Setup v2.0.0**. Nếu bạn mới làm quen với AI, làm YouTube, dựng video hay chạy các bộ kit/repo trên GitHub, bạn chỉ cần làm đúng **4 việc đơn giản** dưới đây.

---

## 1. Xem Tóm Tắt Doctor & Mở Lại Trợ Lý AI Sau Khi Cài Xong
- Ngay trên **màn hình hoàn tất**, trình cài đặt sẽ tự chạy bước kiểm tra sức khỏe (**Doctor**) để báo rõ từng Lô đã sẵn sàng chưa, trạng thái cài plugin **EGM** trên Antigravity / Claude Code / Codex và thông báo nếu có tệp quy tắc cũ được giữ nguyên an toàn.
- Sau khi trình cài báo **Cài xong rồi!**, hãy **đóng và mở lại** trình biên tập AI bạn đang dùng (*Antigravity, Claude Code, Codex hoặc VS Code*) để phần mềm nhận đầy đủ kỹ năng mới, plugin và bộ điều phối tự động.

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

## 3. Bạn Đang Làm Việc Gì Thì Đọc Tệp Chỉ Dẫn Đó (5 Lô)

| Việc bạn muốn làm | Mở tệp chỉ dẫn này | Công cụ chính đã cài sẵn |
| :--- | :--- | :--- |
| **Viết kịch bản, bài viết, lọc câu bị "mùi AI"** | [`01-lo-content.md`](01-lo-content.md) | `humanizer-vi`, `translationese-cleaner-vi`, `lint.py` |
| **Edit video, cắt khoảng lặng, âm thanh, soi video mẫu** | [`02-lo-edit-video.md`](02-lo-edit-video.md) | `ffmpeg`, `auto-editor`, `ffmpeg-skill`, `rea-video`, `sound-design`, `media-picker` |
| **Tải repo/kit từ GitHub, cài thư viện, sửa lỗi code** | [`03-lo-code.md`](03-lo-code.md) | `git`, `gh`, `uv`, `superpowers` (15 kỹ năng), `karpathy-guidelines`, `modern-web-guidance`, `ruff`, `pytest` |
| **Nghiên cứu ngách, đo xu hướng, đọc PDF/DOCX, phân tích app** | [`04-lo-cao-du-lieu.md`](04-lo-cao-du-lieu.md) | `REA 6.10.1 MCP`, `yt-dlp`, `trendspyg`, `markitdown` |
| **Phản biện mù thiết kế, rà lỗi ngầm, soát kịch bản trọng điểm** | [`05-lo-phan-bien-egm.md`](05-lo-phan-bien-egm.md) | `EGM` (8 kỹ năng gồm `/egm:egm-lite`, `/egm:egm-review`, `/egm:egm-review-loop`, 10 chuyên gia Goldfish) |

---

## 4. Nguyên Tắc Vàng Khi Làm Việc Với Bất Kỳ Bộ Kit Nào
1. **Không cần nhớ tên lệnh phức tạp:** Bộ luật điều phối tự động 5 Lô đã được cài sẵn. Bạn chỉ cần **mở đúng thư mục dự án** trong trợ lý AI và nói yêu cầu bằng tiếng Việt bình thường — AI sẽ tự đọc tệp `CLAUDE.md` (nếu dự án có) và chọn đúng bộ kỹ năng phù hợp.
2. **Thấy dự án có tệp `CLAUDE.md`:** Đó là bộ nội quy riêng của dự án đó. Trợ lý AI sẽ luôn ưu tiên làm theo tệp này trước.
3. **Gặp lỗi khó hiểu:** Copy nguyên dòng báo lỗi dán vào khung chat và nói: *"Kiểm tra giúp tôi lỗi này và giải thích dễ hiểu nguyên nhân."*

---

## Sao Lưu & Chuyển Cấu Hình Sang Máy Mới (Khóa SHA-256)

Khi bạn muốn lưu lại các quy tắc AI cá nhân hóa (`AGENTS.md`, `GEMINI.md` của Antigravity / Claude Code) và trạng thái các Lô đã cài (`state.json`) để phòng rủi ro hoặc chuyển sang máy tính mới:

- **Cách 1 — Bấm 1 chạm trên màn hình hoàn tất:**  
  Bấm nút **`Sao lưu cấu hình (Chuyển máy)`** ở màn hình cuối của trình cài. Hệ thống tự tạo tệp `studio-ai-snapshot-<ngày-giờ>.zip` kèm danh mục mã `SHA-256` (`manifest.json`) lưu tại `%LOCALAPPDATA%\StudioAISetup\snapshots\`.
- **Cách 2 — Chạy lệnh nhanh trong PowerShell:**  
  Mở **PowerShell** ngay trong thư mục giải nén **Studio AI Setup** (ví dụ `D:\Studio-AI-Setup`) và chạy các lệnh tương ứng:
  ```powershell
  # 1. Tạo bản sao lưu cấu hình mới
  python -B engine\setup_engine.py --backup

  # 2. Xem danh sách bản sao lưu và mở thư mục chứa tệp .zip
  python -B engine\setup_engine.py --list-backups
  explorer "$env:LocalAppData\StudioAISetup\snapshots"

  # 3. Trên máy mới: chép tệp .zip vào "$env:LocalAppData\StudioAISetup\snapshots" rồi kiểm tra thử (không ghi đĩa)
  python -B engine\setup_engine.py --restore latest --dry-run

  # 4. Nếu kết quả kiểm tra SHA-256 hợp lệ, khôi phục cấu hình thật
  python -B engine\setup_engine.py --restore latest
  ```
  *(Bạn cũng có thể chỉ định trực tiếp đường dẫn tệp `.zip` thay cho `latest`, ví dụ `python -B engine\setup_engine.py --restore "$env:LocalAppData\StudioAISetup\snapshots\studio-ai-snapshot-20261125T120000Z.zip"`.)*
- **Bảo vệ toàn vẹn 2 bước:** Trước khi ghi bất kỳ tệp nào, lệnh khôi phục luôn kiểm tra đủ mã `SHA-256` của từng tệp theo `manifest.json` — nếu tệp bị lỗi hoặc bị chỉnh sửa dù chỉ 1 byte, hệ thống dừng ngay và không thay đổi dữ liệu hiện có. Khi khôi phục thật, cấu hình cũ trên máy vẫn được sao lưu tự động sang `%LOCALAPPDATA%\StudioAISetup\backups\` trước khi thay thế.

---

## Câu Hỏi Thường Gặp (FAQ)

- **Làm sao tôi biết các bộ cài tải về là hàng chính chủ, không bị sửa đổi giữa đường?**  
  Mọi công cụ nền tảng đều được tải trực tiếp qua `HTTPS` từ trang chủ chính thức và đi qua **2 lớp xác thực tự động** trước khi chạy: (1) kiểm tra đúng mã băm `SHA-256` khóa sẵn trong `catalog-lock.json`, và (2) xác thực chữ ký số **Authenticode** của Windows cho các bộ cài `.exe` (như Python, Git). Nếu tệp lỗi tải, sai mã `SHA-256` hoặc không có chữ ký số hợp lệ, trình cài tự xóa tệp tạm và dừng an toàn.

- **Tôi đang dùng bản v1.0.0 nâng cấp lên v2.0.0 thì có bị mất quy tắc riêng không?**  
  Không. Bộ cài v2.0.0 tự động sao lưu tệp cũ sang `%LOCALAPPDATA%\StudioAISetup\backups\`. Nếu tệp `AGENTS.md` / `GEMINI.md` còn nguyên bản v1, bộ cài tự nâng cấp gọn lên v2 với cặp thẻ quản lý riêng; nếu bạn đã tự chỉnh sửa tay, bộ cài **giữ nguyên tệp đang dùng** và chỉ đặt bản mẫu v2 tham khảo trong thư mục `backups\`.
- **Tôi lỡ tắt nhầm giữa lúc cài đặt hoặc muốn cài bổ sung riêng Lô 5 thì sao?**  
  Chỉ cần nhấp đúp lại biểu tượng **Studio AI Setup** trên màn hình nền (hoặc chạy lại `cai-dat.bat`). Trình cài tự bỏ qua những phần đã cài xong, ghi nhớ các Lô trước đó và chỉ cài thêm phần còn thiếu.
- **Công cụ Python cài ở đâu? Có làm hỏng máy tôi không?**  
  Mọi công cụ Python của từng Lô được tách gọn vào môi trường ảo riêng tại `%LOCALAPPDATA%\StudioAISetup\venvs\`, không trộn lẫn vào hệ thống và có thể xóa sạch bất cứ lúc nào.
- **Tôi có phải trả phí bản quyền cho bộ cài này không?**  
  Không. Bộ cài hoàn toàn miễn phí theo giấy phép MIT và tải trực tiếp các gói nguồn mở về máy bạn. Các dịch vụ AI bên ngoài (như API trả phí nếu bạn tự dùng trong dự án riêng) do tài khoản cá nhân của bạn tự quản lý.
