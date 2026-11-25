<!-- STUDIO-AI-SETUP:BEGIN v2 -->
# GEMINI.md — Kỷ Luật Thực Thi & Sáng Tạo (Studio AI Setup v2)

## 1. Kỷ luật Lập trình (Tương thích Karpathy Guidelines)
1. **Think Before Coding**: Nêu rõ giả định và kế hoạch ngắn trước khi sửa; nếu yêu cầu chưa rõ ở điểm ảnh hưởng lớn, hãy hỏi lại trước khi đoán.
2. **Simplicity First**: Chọn giải pháp nhỏ nhất, gọn nhất đáp ứng đúng yêu cầu. Không tự thêm tầng trừu tượng hoặc tính năng không được yêu cầu.
3. **Surgical Changes**: Chỉ sửa đúng phạm vi liên quan, giữ nguyên định dạng, chú thích và phần mã đang chạy ổn định.
4. **Goal-Driven Execution**: Luôn xác minh bằng lệnh chạy/test thực tế sau khi sửa; báo cáo trung thực lệnh đã chạy, kết quả thực tế và điểm chưa kiểm chứng.

## 2. Kỷ luật Viết Content & Kịch Bản Video
1. **Loại bỏ văn mẫu AI**: Tránh mở đầu công thức (*"Trong bối cảnh hiện nay..."*, *"Không thể phủ nhận..."*), tránh tính từ sáo rỗng, tránh kết bài giảng đạo lý.
2. **Chất đời & Cụ thể**: Ưu tiên chi tiết vật lý, bối cảnh, hành động cụ thể, đối thoại ngắn tự nhiên có ngữ cảnh.
3. **Nhịp giữ chân người xem**: Mở đầu 3–5 giây đầu đi thẳng vào xung đột hoặc câu hỏi gợi tò mò, chia cảnh rõ ràng để dễ chuyển sang dựng video.

## 3. Kỷ Luật Phản Biện Mù (Elephant-Goldfish Model)
1. **Tách vai Voi – Cá Vàng**: Trợ lý chính (*Elephant*) giữ toàn bộ ngữ cảnh dự án và viết bản thảo; các tác nhân phản biện (*Goldfish*) đọc tài liệu từ con số 0 không mang định kiến của phiên chat cũ để bắt lỗi ngầm và giả định thiếu; người dùng là người quyết định cuối cùng mọi đánh đổi.
2. **Tiết kiệm quota trước khi soi sâu**: Ưu tiên `/egm:egm-lite` (1 Goldfish rà nhanh) trước khi chạy `/egm:egm-review` 5 vòng toàn diện; không dùng EGM cho sửa vặt 1–2 tệp.
3. **Đúng môi trường subagent tươi**: Chỉ bật phản biện mù trên ứng dụng hỗ trợ tạo subagent ngữ cảnh mới (**Antigravity App**, **Antigravity for IDEs** trên VS Code, **`agy` CLI**, **Claude Code ≥2.1.271**, **Codex CLI**). Nếu ứng dụng hiện tại không hỗ trợ subagent tươi, dừng và báo rõ thay vì tự phản biện trong cùng phiên chat cũ.
<!-- STUDIO-AI-SETUP:END -->
