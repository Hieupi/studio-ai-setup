# Chỉ Dẫn Lô 5 · Phản Biện Mù & Kiểm Chứng (EGM — Elephant-Goldfish Model)

Tài liệu này giúp bạn dùng bộ công cụ phản biện mù **EGM** để bắt lỗi ngầm trong bản thiết kế phần mềm, kiểm tra tài liệu lệch code, và soát chất lượng **kịch bản video, bài viết dài hoặc đề xuất kinh doanh** trước khi bắt tay vào làm thật.

---

## 1. EGM Là Gì? (Hiểu Trong 30 Giây)

Khi bạn trao đổi với một trợ lý AI suốt hàng chục lượt, AI thường bị **thiên kiến theo câu chuyện cũ** — nó dễ đồng tình với bạn và bỏ sót những lỗ hổng hiển nhiên với người ngoài.

**Elephant-Goldfish Model (EGM)** giải quyết vấn đề đó bằng cách tách rạch ròi 3 vai trò:
- **Voi (*Elephant*):** Trợ lý chính đang chat cùng bạn — giữ trọn trí nhớ dự án, hiểu bối cảnh và đứng ra viết bản thảo.
- **Cá Vàng (*Goldfish*):** Các tác nhân phản biện mới tinh được gọi lên từ **con số 0** — hoàn toàn không biết lịch sử tranh luận trước đó, chỉ đọc đúng bản thảo và tài liệu nguồn để vạch ra giả định thiếu, mâu thuẫn và rủi ro ngầm.
- **Bạn:** Người cầm cân nảy mực — xem các phát hiện của Cá Vàng rồi quyết định sửa gì, đánh đổi gì trước khi triển khai.

> *Nguồn mở chính thức:* Gói plugin **Elephant-Goldfish Model (EGM)** được tải trực tiếp từ `google/elephant-goldfish-model` (giấy phép Apache-2.0, gồm đầy đủ **8 kỹ năng**, **10 chuyên gia phản biện Goldfish** và **5 chuẩn tài liệu** — đây không phải sản phẩm được Google hỗ trợ chính thức).

---

## 2. Bảng 8 Lệnh EGM & Cách Gọi Đúng

> **Lưu ý cách gõ lệnh:**
> - Trên **Antigravity** (App, VS Code ext, `agy` CLI) và **Claude Code**: gõ kèm tiền tố **`/egm:`** (ví dụ `/egm:egm-lite`).
> - Trên **Codex CLI**: mở danh sách chọn kỹ năng (*skill picker*) và chọn đúng tên kỹ năng EGM tương ứng.

| Lệnh EGM | Tác dụng chính | Khi nào nên dùng |
| :--- | :--- | :--- |
| **`/egm:egm-lite`** *(Khuyên dùng đầu tiên)* | Gọi **1 Goldfish** đọc mù rà nhanh lỗi ngầm, giả định hở và điểm mù. | **Nhanh & tiết kiệm quota nhất** — dùng cho bản kế hoạch vừa, rà diff code hoặc soát nháp ban đầu. |
| **`/egm:egm-brainstorm`** | Mổ xẻ ý tưởng, để Goldfish chất vấn rồi chốt thành tệp `concepts_brief.md`. | Khi bắt đầu tính năng lớn hoặc ý tưởng sản phẩm còn nhiều phương án đánh đổi. |
| **`/egm:egm-draft`** | Chuyển `concepts_brief.md` (hoặc ghi chú có sẵn) thành `design_draft.md`, dừng hỏi bạn từng phần. | Khi cần biến ý tưởng đã thống nhất thành bản thiết kế chi tiết trước lúc code. |
| **`/egm:egm-review <file>`** | Phản biện mù **5 vòng toàn diện** (thiết kế, độ rõ, độ khớp code thật, kế hoạch triển khai). | Chỉ dùng cho kiến trúc lớn, bảo mật, đổi database schema hoặc bản thiết kế trọng điểm. |
| **`/egm:egm-resolve`** | Đi lần lượt từng phát hiện sau vòng phản biện để chốt mục nào sửa, mục nào giữ nguyên. | Ngay sau `/egm:egm-review` hoặc `/egm:egm-lite` khi có nhiều góp ý cần quyết định. |
| **`/egm:egm-review-loop`** | Chạy vòng phản biện mù với **tiêu chí và vai phản biện do bạn tự chọn**. | **Dùng được cho cả kịch bản video, bài viết dài, đề xuất kinh doanh** — không giới hạn trong code! |
| **`/egm:egm-bootstrap`** | Tự đọc mã nguồn dự án có sẵn để dựng bộ tài liệu kiến trúc chuẩn. | Khi mới tải một repo/kit cũ về máy mà tài liệu thiếu hoặc quá sơ sài. |
| **`/egm:egm-drift-report`** | Soi đối chiếu tài liệu thiết kế/`README`/`CLAUDE.md` hiện có với mã nguồn thực tế. | Khi dự án đã sửa qua nhiều vòng và bạn nghi tài liệu đang nói sai so với code thật. |

### Ví dụ copy-dán dùng ngay
- **Rà nhanh kế hoạch code trước khi sửa (tiết kiệm quota):**
  > `/egm:egm-lite` Rà giúp tôi bản kế hoạch trong `plan.md`, tập trung tìm lỗ hổng xử lý lỗi và các giả định chưa kiểm chứng.
- **Soát mù kịch bản video / bài viết bằng tiêu chí riêng:**
  > `/egm:egm-review-loop` Đọc tệp `kich-ban-tap-05.md` với 2 vai phản biện: (1) khán giả khó tính xem 15 giây đầu có muốn bấm bỏ qua không, (2) biên tập viên kiểm tra đoạn nào lê thê hoặc thiếu dẫn chứng.
- **Soi tài liệu bị lệch so với code thật:**
  > `/egm:egm-drift-report` Đối chiếu thư mục `docs/` với mã nguồn hiện tại và liệt kê những chỗ mô tả không còn khớp.

---

## 3. Khi Nào NÊN và KHÔNG NÊN Dùng (Quy Tắc Tiết Kiệm Quota)

Phản biện mù tạo các tác nhân phụ đọc tài liệu độc lập nên sẽ tốn nhiều lượt sử dụng (*quota/token*) hơn chat thông thường. Hãy đi theo đúng **4 bậc** sau:

1. **Sửa vặt 1–2 tệp, đổi câu chữ, hỏi đáp nhanh → KHÔNG dùng EGM.**  
   Chỉ cần quy tắc `karpathy-guidelines` đã cài sẵn (0 subagent, 0 tốn quota thêm).
2. **Làm tính năng thường, sửa lỗi, viết test → Dùng `superpowers` (Lô 3).**  
   Đủ chặt chẽ cho công việc hằng ngày mà không cần gọi dàn phản biện mù.
3. **Sửa vừa, rà diff trước khi chốt, soát bản nháp → Bắt đầu bằng `/egm:egm-lite`.**  
   Chỉ gọi 1 Goldfish nên rất gọn, đủ bắt phần lớn lỗi ngầm quan trọng.
4. **Kiến trúc lớn, bảo mật, đổi cấu trúc dữ liệu, hoặc kịch bản tập chủ lực → Dùng `/egm:egm-brainstorm`, `/egm:egm-review <file>`, hoặc `/egm:egm-review-loop`.**  
   Luôn chốt rõ phạm vi tệp cần đọc để tránh đốt quota vào những thư mục không liên quan.

---

## 4. Bảng Tương Thích Ứng Dụng

Để Cá Vàng thực sự "đọc mù" không dính trí nhớ phiên chat cũ, ứng dụng AI phải hỗ trợ tạo **subagent ngữ cảnh tươi** (*fresh-context subagent*):

| Ứng dụng AI | Mức hỗ trợ EGM | Ghi chú sử dụng |
| :--- | :--- | :--- |
| **Antigravity App** | Hỗ trợ đầy đủ | Đã cài sẵn plugin, gõ lệnh tiền tố `/egm:...`. |
| **Antigravity for IDEs** *(tiện ích trên VS Code)* | Hỗ trợ đầy đủ | Dùng chung thư mục plugin Antigravity, gõ `/egm:...`. |
| **`agy` CLI** *(Antigravity CLI)* | Hỗ trợ đầy đủ | Gõ `/egm:...` trực tiếp trong phiên CLI. |
| **Claude Code** *(≥2.1.271)* | Hỗ trợ đầy đủ | Trình cài tự đăng ký nếu máy có sẵn lệnh `claude`; gõ `/egm:...`. |
| **Codex CLI** | Hỗ trợ đầy đủ | Trình cài tự đăng ký nếu máy có sẵn lệnh `codex`; chọn kỹ năng EGM trong danh sách skill. |
| **Antigravity IDE** *(bản độc lập / standalone)* | **Không hỗ trợ phản biện mù** | Dù IDE thấy tên plugin, bản độc lập hiện **không có công cụ tạo subagent tươi** nên lệnh phản biện Goldfish sẽ tự dừng lại thay vì chạy giả trong cùng ngữ cảnh cũ. Hãy chuyển sang một trong 5 ứng dụng phía trên khi cần dùng EGM. |

---

## 5. Vị Trí Cài Đặt & Lệnh Đăng Ký Thủ Công Dự Phòng

Studio AI Setup v2.0.0 đã cài sẵn toàn bộ plugin EGM nguyên vẹn tại 2 thư mục sạch:
- **Cho hệ sinh thái Antigravity:** `%USERPROFILE%\.gemini\config\plugins\egm\`
- **Gói nguồn cục bộ cho Claude Code & Codex CLI:** `%LOCALAPPDATA%\StudioAISetup\plugins\egm\`

Nếu bạn cài đặt **Claude Code** hoặc **Codex CLI** *sau* khi chạy Studio AI Setup (hoặc màn hình kiểm tra Doctor nhắc cần đăng ký bổ sung), hãy mở **PowerShell** và chạy đúng 2 lệnh tương ứng:

- **Đăng ký cho Claude Code:**
  ```powershell
  claude plugin marketplace add "$env:LocalAppData\StudioAISetup\plugins\egm"
  claude plugin install egm@egm
  ```
- **Đăng ký cho Codex CLI:**
  ```powershell
  codex plugin marketplace add "$env:LocalAppData\StudioAISetup\plugins\egm"
  codex plugin add egm@egm
  ```

Sau đó **đóng và mở lại** phiên làm việc mới để ứng dụng nạp plugin.

> **Cảnh báo quan trọng — KHÔNG copy lẻ thư mục `skills/`:**  
> Tuyệt đối không tự chép riêng các thư mục bên trong `skills/` sang `~/.claude/skills` hay `~/.codex/skills`. Khi hoạt động, kỹ năng EGM bắt buộc phải đọc đồng thời thư mục `agents/` (10 chuyên gia Goldfish) và `resources/` (5 chuẩn tài liệu) nằm cùng gốc plugin; chép lẻ sẽ làm lệnh phản biện bị lỗi.
