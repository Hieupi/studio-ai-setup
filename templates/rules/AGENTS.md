<!-- STUDIO-AI-SETUP:BEGIN v2 -->
# AGENTS.md — Quy Tắc Điều Phối Tự Động (Studio AI Setup v2)

- **Người dùng**: **{{USER_NAME}}**. Xưng hô lịch sự, tự nhiên, nghiêm túc, ngắn gọn và đi thẳng vào giải pháp.
- **Quy tắc Thứ Tự Ưu Tiên Tuyệt Đối *(Local-First)***: Khi mở bất kỳ thư mục dự án nào có tệp `CLAUDE.md` (hoặc `.agent/rules/` riêng), **luôn đọc `CLAUDE.md` của dự án đó trước ở Bước 0**. Mọi quy tắc, vùng cấm, bước tốn phí và lệnh kiểm "xong" của dự án luôn được ưu tiên cao hơn quy tắc chung này.
- **Chất lượng đầu ra**: Không cắt cụt mã nguồn (`// ...rest`, `/* TODO */`), không trả lời vòng vo hay thuyết giáo thừa, không tự bịa số liệu hoặc kết quả kiểm thử chưa chạy.

## Tự Động Chọn Đúng Công Cụ Theo 5 Lô (Người dùng không cần nhớ tên lệnh)

| Ngữ cảnh công việc | Lô tương ứng | Kỹ năng & công cụ tự động áp dụng |
| :--- | :--- | :--- |
| **Viết kịch bản, bài viết, lời thoại, lọc văn phong AI** | **Lô 1 · Content** | Tự đọc `humanizer-vi` và `translationese-cleaner-vi` (nếu có); áp dụng lối viết giàu hình ảnh cụ thể, chất đời tự nhiên, bỏ câu mở đầu sáo rỗng và lời dịch máy. Nếu là kịch bản tài liệu/sự kiện thật, tuân thủ tuyệt đối nguồn gốc dữ liệu trong dự án. |
| **Dựng video, xử lý âm thanh, cắt ghép, mổ xẻ video mẫu** | **Lô 2 · Edit Video** | Kết hợp `rea-video` (bóc cấu trúc từng cảnh), `ffmpeg-skill` (cắt ghép, đo chuẩn âm lượng `-14 LUFS`), `auto-editor` (cắt khoảng lặng), `sound-design` & `media-picker`. Ưu tiên xem xét bố cục Remotion/FFmpeg rõ ràng trước khi xuất bản. |
| **Lập trình ứng dụng, sửa lỗi, chạy repo/kit từ GitHub** | **Lô 3 · Code** | Áp dụng 4 nguyên tắc Karpathy (`Think Before Coding → Simplicity First → Surgical Changes → Goal-Driven Execution`) cùng bộ kỹ năng `superpowers` (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`) và `modern-web-guidance` (tra cứu 250+ tính năng web hiện đại Chrome/MDN khi làm web). |
| **Nghiên cứu ngách, cào dữ liệu web, đọc PDF/DOCX, phân tích app/web** | **Lô 4 · Cào & Nghiên cứu** | Dùng công cụ `rea` MCP theo chiến thuật *Summary-First* (`open` → phân tích tóm tắt → `close`), dùng `markitdown` chuyển tài liệu sang Markdown sạch, dùng `trendspyg` kiểm tra xu hướng YouTube có kiểm soát tốc độ, tôn trọng điều khoản nguồn dữ liệu và không lưu/lộ cookie hay API key. |
| **Phản biện mù thiết kế, rà lỗi ngầm, soát kịch bản trọng điểm, soi lệch tài liệu** | **Lô 5 · Phản Biện & Kiểm Chứng (EGM)** | Chỉ gợi ý đúng thang leo bậc tiết kiệm quota bên dưới bằng nhóm lệnh `/egm:*` (`/egm:egm-lite`, `/egm:egm-brainstorm`, `/egm:egm-draft`, `/egm:egm-review`, `/egm:egm-resolve`, `/egm:egm-review-loop`, `/egm:egm-drift-report`, `/egm:egm-bootstrap`). |

## Thang Leo Bậc Tiết Kiệm Quota (Karpathy → Superpowers → EGM)

1. **Sửa nhỏ / 1–2 tệp / hỏi nhanh** → chỉ dùng `karpathy-guidelines` (0 subagent, 0 tốn quota thêm).
2. **Tính năng thường / sửa lỗi / TDD** → dùng `superpowers` (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`).
3. **Sửa vừa / rà diff / tinh chỉnh spec** → gợi ý 1 dòng `/egm:egm-lite` (1 Goldfish đọc mù, nhanh & tiết kiệm quota).
4. **Kiến trúc lớn / bảo mật / schema / kịch bản trọng điểm** → gợi ý 1 dòng `/egm:egm-brainstorm`, `/egm:egm-review <file>`, hoặc `/egm:egm-review-loop` (chọn tiêu chí riêng cho kịch bản video/bài viết); nếu phát hiện **tài liệu lệch so với code thật** → gợi ý `/egm:egm-drift-report` hoặc `/egm:egm-bootstrap`. **Tuyệt đối không tự gọi EGM cho sửa vặt.**

- *Lưu ý tương thích EGM:* EGM cần ứng dụng hỗ trợ subagent ngữ cảnh tươi (**Antigravity App**, **Antigravity for IDEs** trên VS Code, **`agy` CLI**, **Claude Code ≥2.1.271**, **Codex CLI**; **Antigravity IDE độc lập** hiện không tạo được subagent).

## Tự Động Đề Xuất Lệnh Hệ Thống Đúng Lúc
- Yêu cầu mới hoặc phức tạp cần chốt kiến trúc trước khi làm → gợi ý người dùng gõ `/plan` hoặc `/grill-me`.
- Công việc nhiều bước cần chạy tự động dài hơi → gợi ý `/goal`.
- Cuộc trò chuyện đã quá dài → gợi ý `/compact` để làm nhẹ bộ nhớ.
<!-- STUDIO-AI-SETUP:END -->
