# Studio AI Setup v2.0.0

Bộ cài đặt giao diện trực quan (Windows 10/11) giúp bạn thiết lập đầy đủ môi trường làm **Content · Edit Video · Code · Cào Dữ Liệu & Nghiên Cứu · Phản Biện & Kiểm Chứng (EGM)** trên máy tính mới chỉ trong vài phút — kể cả khi bạn chưa từng lập trình trước đây.

- **Miễn phí · Mã nguồn mở (MIT)** — Không gắn khóa bản quyền, không thu phí, không theo dõi người dùng.
- **Tải trực tiếp từ nguồn chính thức (Xác thực 2 lớp)** — Máy tính của bạn tự tải trực tiếp qua `HTTPS` kèm kiểm tra mã `SHA-256` và chữ ký số **Authenticode** (cho bộ cài `.exe` Windows như Python, Git) từ trang chủ chính thức (Python, Node.js, Git, GitHub CLI, FFmpeg — không cần Winget hay quyền Admin bắt buộc, chỉ dùng Winget làm phương án hỗ trợ nếu tải trực tiếp gặp trục trặc) cùng các gói nguồn mở trên `PyPI`, `npm`, `GitHub` sau khi bạn chọn và xác nhận.
- **An toàn, Tách biệt & Nâng cấp v1 → v2 không mất dữ liệu** — Công cụ Python tách gọn trong `%LOCALAPPDATA%\StudioAISetup\venvs\`; quy tắc `AGENTS.md` / `GEMINI.md` dùng khối thẻ đánh dấu quản lý (`<!-- STUDIO-AI-SETUP:BEGIN v2 -->`) nên khi nâng cấp từ v1.0.0 lên v2.0.0 mọi dòng tùy chỉnh riêng của bạn luôn được giữ nguyên và bản cũ được sao lưu an toàn vào `%LOCALAPPDATA%\StudioAISetup\backups\`.
- **Kiểm tra sức khỏe Doctor tích hợp** — Ngay trên màn hình hoàn tất, trình cài tự rà soát trạng thái cả 5 Lô, số kỹ năng/chuyên gia phản biện của **EGM**, trạng thái đăng ký cho Antigravity / Claude Code / Codex và thông báo rõ nếu có tệp tùy chỉnh được bảo toàn.

---

## Cài đặt nhanh trong 3 bước (Dành cho người mới)

1. **Giải nén toàn bộ file ZIP** ra một thư mục trên máy (ví dụ `D:\Studio-AI-Setup\`).  
   *(Không nhấp đúp chạy trực tiếp khi file vẫn còn nằm bên trong cửa sổ `.zip`.)*
2. **Nhấp đúp vào file `cai-dat.bat`**.  
   Cửa sổ giao diện **Studio AI Setup** sẽ hiện ra (không hiện màn hình dòng lệnh khó nhìn).
3. **Nhập tên của bạn**, giữ mặc định **5 Lô** khuyên dùng và bấm **`Bắt đầu cài đặt tự động`**.  
   Nếu Windows hiện bảng hỏi quyền cài đặt (*User Account Control*), bạn bấm **Yes (Có)** để máy tự hoàn tất và xem bảng kết quả **Doctor** ở màn hình cuối.

> **Đang dùng v1.0.0 muốn nâng cấp lên v2.0.0?** Chỉ cần giải nén bản mới và chạy lại `cai-dat.bat`. Bộ cài tự nhận diện tên cũ và các Lô đã cài qua `%LOCALAPPDATA%\StudioAISetup\state.json`, sao lưu quy tắc cũ vào `%LOCALAPPDATA%\StudioAISetup\backups\`, không ghi đè tệp bạn tự chỉnh sửa tay và chỉ cài bổ sung phần mới (như Lô 5 · EGM).

---

## 5 Lô Công Cụ & Chỉ Dẫn Đi Kèm

Sau khi cài xong, toàn bộ tài liệu hướng dẫn dễ hiểu sẽ nằm sẵn trong `Documents\Studio AI Setup\Chi-Dan\` (và ngay trong thư mục `chi-dan\` tại đây):

| Lô | Dành cho việc gì? | Tài liệu hướng dẫn chi tiết |
| :--- | :--- | :--- |
| **Tổng quan 1 phút** | Xem bảng Doctor, mở lại trợ lý AI, nối GitHub và câu hỏi thường gặp | [`chi-dan/00-BAT-DAU-NHANH.md`](chi-dan/00-BAT-DAU-NHANH.md) |
| **Lô 1 · Content** | Viết kịch bản, kể chuyện tự nhiên, lọc câu chữ "mùi AI" & dịch máy | [`chi-dan/01-lo-content.md`](chi-dan/01-lo-content.md) |
| **Lô 2 · Edit Video** | Cắt khoảng lặng tự động, chuẩn hóa âm lượng `-14 LUFS`, dựng FFmpeg/Remotion, mổ xẻ video mẫu | [`chi-dan/02-lo-edit-video.md`](chi-dan/02-lo-edit-video.md) |
| **Lô 3 · Code** | Đăng nhập GitHub lấy repo/kit, quy trình AI lập kế hoạch → test → kiểm tra (`superpowers`, `karpathy`, `modern-web-guidance`) | [`chi-dan/03-lo-code.md`](chi-dan/03-lo-code.md) |
| **Lô 4 · Cào Dữ Liệu** | Đo xu hướng Google/YouTube, đọc PDF/DOCX sang Markdown, phân tích đối thủ với REA | [`chi-dan/04-lo-cao-du-lieu.md`](chi-dan/04-lo-cao-du-lieu.md) |
| **Lô 5 · Phản Biện (EGM)** | Phản biện mù kiểu Voi – Cá Vàng (**8 kỹ năng**, **10 chuyên gia Goldfish**) giúp bắt lỗi ngầm trong thiết kế code lẫn kịch bản/bài viết (`/egm:egm-lite`, `/egm:egm-review`, `/egm:egm-review-loop`) | [`chi-dan/05-lo-phan-bien-egm.md`](chi-dan/05-lo-phan-bien-egm.md) |

---

## Sao lưu & Chuyển sang máy mới (Khóa SHA-256)

- **1 chạm trên giao diện:** Tại màn hình hoàn tất, bấm nút **`Sao lưu cấu hình (Chuyển máy)`** để đóng gói `state.json` cùng các quy tắc `AGENTS.md` / `GEMINI.md` thành tệp `.zip` có danh mục khóa `SHA-256` tại `%LOCALAPPDATA%\StudioAISetup\snapshots\`.
- **Lệnh dòng lệnh (CLI):** Chạy `python -B engine\setup_engine.py` với `--backup` (tạo bản sao lưu), `--list-backups` (xem danh sách bản đã lưu), `--restore latest --dry-run` (xác thực `SHA-256` và xem trước, không ghi ổ cứng) hoặc `--restore latest` (khôi phục nguyên tử, tự sao lưu bản cũ trước khi thay thế).
- **An toàn khi chuyển máy:** Chép tệp `studio-ai-snapshot-*.zip` vào `%LOCALAPPDATA%\StudioAISetup\snapshots\` trên máy mới rồi chạy lệnh khôi phục; mọi tệp sai mã `SHA-256` đều bị chặn trước khi ghi đĩa. Xem hướng dẫn từng bước tại [`chi-dan/00-BAT-DAU-NHANH.md`](chi-dan/00-BAT-DAU-NHANH.md).

---

## Yêu cầu hệ thống tối thiểu

- **Hệ điều hành:** Windows 10 hoặc Windows 11 (64-bit).
- **RAM:** Khuyên dùng từ 8 GB trở lên.
- **Ổ cứng trống:** Tối thiểu 5–10 GB cho phần cốt lõi (nếu bật thêm tùy chọn nâng cao như dựng 3D cục bộ cần card đồ họa NVIDIA RTX và thêm 15–30 GB trống).
- **Kết nối mạng:** Cần internet ổn định trong lúc tải bộ cài từ nguồn chính thức.

---

## Giấy phép & Miễn trừ trách nhiệm

Phát hành theo giấy phép **MIT** (`LICENSE`). Xem thông báo miễn trừ trách nhiệm tại [`DISCLAIMER.md`](DISCLAIMER.md) và danh sách nguồn bên thứ ba (bao gồm thông báo Apache-2.0 cho EGM) tại [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
