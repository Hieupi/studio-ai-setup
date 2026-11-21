# Chỉ Dẫn Lô 2 · Edit Video (Cắt Ghép, Âm Thanh, Mổ Xẻ Video Mẫu)

Tài liệu này giúp bạn dùng các công cụ dựng phim và xử lý âm thanh tự động **ngay cả khi bạn chưa từng viết lệnh FFmpeg hay dựng video bằng code**.

---

## 1. Trong Lô 2 Đã Cài Sẵn Cho Bạn Những Gì?

### Nhóm Cốt Lõi (Chạy mượt trên mọi máy)
- **`FFmpeg` & `FFprobe`:** Bộ công cụ nền tảng chuyên cắt ghép video, tách tiếng, ghép phụ đề, đổi định dạng và đo chuẩn âm lượng phát hành YouTube.
- **`Auto-Editor` (`29.3.1`):** Tự động tìm và cắt bỏ các đoạn im lặng, khoảng nghỉ dài hoặc lỗi ngập ngừng trong video quay nói chuyện / hướng dẫn màn hình.
- **`rea-video`:** Trình mổ xẻ video mẫu chuyên sâu — nhìn vào một video bạn đưa, công cụ tách từng cảnh (shot), kiểm tra cảnh nào quay thật / dùng AI / dựng bằng code, phân tích lớp chữ, nhạc nền, hiệu ứng tiếng động và xuất báo cáo `report.html`.
- **`FFmpeg Skill` (`3.8.16`):** Kỹ năng giúp AI viết chính xác lệnh ghép video/âm thanh mà không bị lỗi cú pháp filter phức tạp.
- **`EditAtlas Sound Design` & `Media Picker`:** Hai kỹ năng giúp AI lên danh sách hiệu ứng âm thanh (whoosh, impact, ambient...) và chọn tư liệu hình ảnh khớp nhịp dựng.
- **Môi trường Media Python (`venvs\media`):** Đã cài sẵn `numpy`, `pillow`, `opencv-python`, `soundfile`, `scipy`, `pyyaml`, `openpyxl` để bạn chạy mượt các bộ kit xử lý ảnh/video/âm thanh bằng Python.

### Nhóm Tùy Chọn Nâng Cao (Chỉ cài nếu bạn tự tích chọn)
- **`OpenMontage`:** Hệ thống dựng video agentic lấy nguồn footage mở *(nặng và cần cấu hình API ngoài)*.
- **`AssetFurnace 3D`:** Tạo nhân vật 3D có xương chuyển động cục bộ *(chỉ chạy được trên máy có card đồ họa NVIDIA RTX dòng 20 trở lên và dung lượng ổ trống lớn)*.

---

## 2. Quy Trình 5 Bước Làm Video Với AI Cho Người Mới

1. **Bước 1 — Mổ xẻ video mẫu để học cách dựng (`rea-video`):**  
   Khi có 1 video tham khảo hay (`mau.mp4`), bạn mở thư mục chứa video và bảo AI:  
   > *"Dùng `rea-video` phân tích cấu trúc video `mau.mp4`, xuất báo cáo để tôi xem cách họ chia cảnh, nhịp cắt và dùng chữ trên màn hình."*
2. **Bước 2 — Cắt bỏ khoảng lặng thừa (`auto-editor`):**  
   Với video bạn tự quay hoặc đọc hướng dẫn, bạn có thể cắt bớt đoạn im lặng nhanh chóng:  
   > *"Dùng `auto-editor` cắt bỏ các đoạn im lặng trên video `tho.mp4` thành file `da-cat.mp4`, giữ lại khoảng đệm tự nhiên 0.2 giây."*
3. **Bước 3 — Chuẩn bị tư liệu & thiết kế âm thanh:**  
   Dùng kỹ năng `sound-design` và `media-picker` để AI gợi ý đúng các điểm cần chèn tiếng động (lúc chữ nảy ra, lúc chuyển cảnh) thay vì rải tiếng động bừa bãi.
4. **Bước 4 — Dựng & xuất video bằng FFmpeg (hoặc bộ kit Remotion của dự án):**  
   Bạn chỉ cần mô tả kích thước (`16:9` ngang cho YouTube hoặc `9:16` dọc cho Shorts/Reels), AI tự tạo lệnh FFmpeg chuẩn.
5. **Bước 5 — Kiểm tra âm lượng chuẩn YouTube (`-14 LUFS`) trước khi đăng:**  
   Video quá nhỏ hoặc quá rè sẽ làm người xem thoát sớm. Luôn bảo AI:  
   > *"Kiểm tra giúp tôi file `thanh-pham.mp4` đã đạt chuẩn âm lượng khoảng -14 LUFS và đỉnh âm không vượt -1 dBTP chưa."*

---

## 3. Lệnh Tham Khảo Nhanh (Nếu Cần Gõ Tay Trong PowerShell)

```powershell
# Kiểm tra FFmpeg đã hoạt động chưa
ffmpeg -version

# Cắt tự động khoảng lặng bằng auto-editor (trong môi trường media đã cài)
& "$env:LocalAppData\StudioAISetup\venvs\media\Scripts\auto-editor.exe" video-goc.mp4 -o video-sach.mp4

# Phân tích video mẫu bằng rea-video
& "$env:LocalAppData\StudioAISetup\venvs\media\Scripts\rea-video.exe" survey mau.mp4 -o out/mau
```
