# Chỉ Dẫn Lô 1 · Content (Viết Kịch Bản, Kể Chuyện & Lọc Văn "Mùi AI")

Tài liệu này giúp người mới làm YouTube, Shorts, hoặc viết bài nội dung biết cách điều khiển AI viết **tự nhiên như người thật nói**, tránh tình trạng văn sáo rỗng, dài dòng hoặc giống văn dịch máy.

---

## 1. Trong Lô 1 Đã Cài Sẵn Cho Bạn Những Gì?
- **Kỹ năng lọc văn tiếng Việt (`humanizer-vi` & `translationese-cleaner-vi`):** Giúp AI tự phát hiện và sửa các câu mang cấu trúc dịch từ tiếng Anh sang tiếng Việt (*"Trong bối cảnh hiện nay..."*, *"Không thể phủ nhận rằng..."*, lạm dụng bị động *"được thực hiện bởi..."*).
- **Công cụ kiểm tra kịch bản (`viet-writing-lint`):** Cài gọn trong `%LocalAppData%\StudioAISetup\venvs\content\` để kiểm tra nhanh tệp văn bản xem có bị lặp mẫu AI không.
- **Bộ kỷ luật viết Content chất đời (`GEMINI.md`):** Nhắc AI viết cụ thể vào chi tiết đời sống, cảnh vật, hành động, giữ nhịp cuốn ngay 3–5 giây đầu.

---

## 2. Quy Trình 4 Bước Để Viết Kịch Bản Không Bị "Giống AI"

1. **Bước 1 — Chốt dàn ý trước, chưa vội viết lời:**  
   Đừng bảo AI *"Viết cho tôi kịch bản 15 phút về..."* ngay lập tức, vì AI sẽ viết rất nhạt và bịa thông tin. Hãy yêu cầu AI lập dàn ý gồm **Mở đầu (Hook 5 giây) → 3–4 điểm chính → Cao trào → Kết** để bạn duyệt trước.
2. **Bước 2 — Đưa chất liệu thật của bạn:**  
   Nếu video dựa trên bài báo, tài liệu hoặc câu chuyện có thật, hãy gửi kèm nguồn dữ liệu đó cho AI và dặn: *"Chỉ viết dựa trên dữ liệu tôi cung cấp, chỗ nào thiếu thì hỏi lại, không tự bịa."*
3. **Bước 3 — Viết từng phần & Giữ giọng nói tự nhiên:**  
   Yêu cầu AI viết từng đoạn (mỗi đoạn khoảng 400–600 chữ) theo văn phong nói chuyện gần gũi, câu ngắn vừa nhịp thở người đọc voice-over.
4. **Bước 4 — Chạy lượt lọc "tẩy mùi AI" trước khi thu âm:**  
   Bảo AI đọc lại toàn bộ kịch bản bằng kỹ năng `humanizer-vi` và `translationese-cleaner-vi` để thay thế các cụm từ sáo rỗng và câu dịch cứng.

---

## 3. Các Câu Lệnh Mẫu (Bạn Chỉ Cần Copy Dán Vào Khung Chat AI)

- **Lên ý tưởng & Hook mở đầu:**
  > *"Tôi muốn làm video dài 12 phút chủ đề [tên chủ đề] cho khán giả [mô tả người xem]. Hãy đề xuất cho tôi 3 cách mở đầu trong 5 giây đầu tạo tò mò ngay, kèm dàn ý 4 phần. Chưa cần viết lời chi tiết."*
- **Viết nháp theo kiểu kể chuyện đời thường:**
  > *"Dựa theo dàn ý đã chốt, hãy viết phần 1 (khoảng 500 chữ) bằng văn phong kể chuyện đời thường, ưu tiên chi tiết cụ thể (ánh sáng, âm thanh, hành động), câu ngắn dễ đọc thành tiếng. Không dùng lời mở đầu kiểu sáo rỗng."*
- **Nhờ AI tự sửa câu chữ cứng, giống văn dịch:**
  > *"Hãy rà soát lại đoạn kịch bản vừa rồi theo chuẩn `humanizer-vi` và `translationese-cleaner-vi`: chỉ ra những câu bị sáo rỗng hoặc giống văn dịch máy, rồi viết lại cho mượt như người Việt nói chuyện ngoài đời."*
- **Kiểm tra kịch bản bằng công cụ dòng lệnh (nếu cần):**
  ```powershell
  & "$env:LocalAppData\StudioAISetup\venvs\content\Scripts\viet-writing-lint.exe" kich-ban.md
  ```

---

## 4. Lưu Ý Quan Trọng Khi Làm Nội Dung
- **Tách rạch ròi kênh hư cấu và kênh tài liệu thật:** Nếu bạn làm video kể chuyện hư cấu có thể dùng trí tưởng tượng, nhưng nếu làm chủ đề lịch sử, kiến thức, pháp luật hoặc tin tức thật thì bắt buộc phải kiểm chứng từng con số và tên riêng từ nguồn gốc.
- **Tổ chức thư mục gọn gàng:** Mỗi tập video nên để trong 1 thư mục riêng gồm 3 phần rõ ràng: `01-tai-lieu-goc/`, `02-kich-ban/`, `03-xuat-ban/` (tiêu đề, mô tả, ảnh bìa).
