# Studio AI Setup v1.0.0

Bộ cài đặt giao diện trực quan (Windows 10/11) giúp bạn thiết lập đầy đủ môi trường làm **Content · Edit Video · Code · Cào Dữ Liệu & Nghiên Cứu** trên máy tính mới chỉ trong vài phút — kể cả khi bạn chưa từng lập trình trước đây.

- **Miễn phí · Mã nguồn mở (MIT)** — Không gắn khóa bản quyền, không thu phí, không theo dõi người dùng.
- **Tải trực tiếp từ nguồn chính thức** — Máy tính của bạn tự tải trực tiếp qua `HTTPS` kèm kiểm tra mã `SHA-256` từ trang chủ chính thức (Python, Node.js, Git, GitHub CLI, FFmpeg — không cần Winget, chỉ dùng Winget làm phương án hỗ trợ nếu máy có sẵn) cùng các gói nguồn mở trên `PyPI`, `npm`, `GitHub` sau khi bạn chọn và xác nhận.
- **An toàn & Tách biệt** — Các công cụ Python được cài gọn trong môi trường ảo riêng tại `%LocalAppData%\StudioAISetup\venvs\`, không làm rối hệ thống.

---

## Cài đặt nhanh trong 3 bước (Dành cho người mới)

1. **Giải nén toàn bộ file ZIP** ra một thư mục trên máy (ví dụ `D:\Studio-AI-Setup\`).  
   *(Không nhấp đúp chạy trực tiếp khi file vẫn còn nằm bên trong cửa sổ `.zip`.)*
2. **Nhấp đúp vào file `cai-dat.bat`**.  
   Cửa sổ giao diện **Studio AI Setup** sẽ hiện ra (không hiện màn hình dòng lệnh khó nhìn).
3. **Nhập tên của bạn**, giữ mặc định 4 Lô khuyên dùng và bấm **`Bắt đầu cài đặt tự động`**.  
   Nếu Windows hiện bảng hỏi quyền cài đặt (*User Account Control*), bạn bấm **Yes (Có)** để máy tự hoàn tất.

> **Cần cập nhật lại sau này?** Bạn chỉ cần giải nén bản mới và chạy lại `cai-dat.bat`. Bộ cài tự nhận biết những gì đã có sẵn, giữ nguyên cấu hình của bạn và chỉ cập nhật phần mới.

---

## 4 Lô Công Cụ & Chỉ Dẫn Đi Kèm

Sau khi cài xong, toàn bộ tài liệu hướng dẫn dễ hiểu sẽ nằm sẵn trong `Documents\Studio AI Setup\Chi-Dan\` (và ngay trong thư mục `chi-dan\` tại đây):

| Lô | Dành cho việc gì? | Tài liệu hướng dẫn chi tiết |
| :--- | :--- | :--- |
| **Tổng quan 1 phút** | Xem cách mở ứng dụng, nối GitHub và câu hỏi thường gặp | [`chi-dan/00-BAT-DAU-NHANH.md`](chi-dan/00-BAT-DAU-NHANH.md) |
| **Lô 1 · Content** | Viết kịch bản, kể chuyện tự nhiên, lọc câu chữ "mùi AI" & dịch máy | [`chi-dan/01-lo-content.md`](chi-dan/01-lo-content.md) |
| **Lô 2 · Edit Video** | Cắt khoảng lặng tự động, chuẩn hóa âm lượng `-14 LUFS`, dựng FFmpeg/Remotion, mổ xẻ video mẫu | [`chi-dan/02-lo-edit-video.md`](chi-dan/02-lo-edit-video.md) |
| **Lô 3 · Code** | Đăng nhập GitHub lấy repo/kit, quy trình AI lập kế hoạch -> test -> kiểm tra | [`chi-dan/03-lo-code.md`](chi-dan/03-lo-code.md) |
| **Lô 4 · Cào Dữ Liệu** | Đo xu hướng Google/YouTube, đọc PDF/DOCX sang Markdown, phân tích đối thủ với REA | [`chi-dan/04-lo-cao-du-lieu.md`](chi-dan/04-lo-cao-du-lieu.md) |

---

## Yêu cầu hệ thống tối thiểu

- **Hệ điều hành:** Windows 10 hoặc Windows 11 (64-bit).
- **RAM:** Khuyên dùng từ 8 GB trở lên.
- **Ổ cứng trống:** Tối thiểu 5–10 GB cho phần cốt lõi (nếu bật thêm tùy chọn nâng cao như dựng 3D cục bộ cần card đồ họa NVIDIA RTX và thêm 15–30 GB trống).
- **Kết nối mạng:** Cần internet ổn định trong lúc tải bộ cài từ nguồn chính thức.

---

## Giấy phép & Miễn trừ trách nhiệm

Phát hành theo giấy phép **MIT** (`LICENSE`). Xem thông báo miễn trừ trách nhiệm tại [`DISCLAIMER.md`](DISCLAIMER.md) và danh sách nguồn bên thứ ba tại [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
