# Chỉ Dẫn Lô 3 · Code & Chạy Bộ Kit (Dành Cho Người Mới Giấy Trắng)

Bạn không cần phải biết lập trình sâu vẫn có thể tải các bộ kit/repo trên Web về máy, chạy ứng dụng và nhờ AI sửa theo ý mình một cách an toàn.

---

## 1. Trong Lô 3 Đã Cài Sẵn Cho Bạn Những Gì?
- **`Git` & `GitHub CLI (gh)`:** Hai công cụ giúp tải code từ GitHub về máy chỉ với 1 dòng lệnh đơn giản, tự động đăng nhập qua trình duyệt web.
- **`Python` + `uv` + `Node.js LTS`:** Bộ nền tảng để chạy gần như toàn bộ các công cụ Python, giao diện web React/Next.js và công cụ dựng video Remotion.
- **`Superpowers` (15 kỹ năng chuẩn):** Dạy AI thói quen làm việc bài bản: thảo luận rõ ý tưởng trước (`brainstorming`) → viết kế hoạch ngắn (`writing-plans`) → sửa lỗi có hệ thống (`systematic-debugging`) → kiểm tra chạy thật trước khi báo xong (`verification-before-completion`).
- **4 Nguyên tắc Karpathy (`karpathy-guidelines`):** Giữ cho AI viết code gọn gàng, không tự ý đẻ ra tính năng thừa làm hỏng các phần đang chạy tốt.
- **`Modern Web Guidance` (`1.0.2`, Chrome/Edge/Firefox/MDN):** Giúp AI tự tra cứu hơn 250 tính năng nền tảng web hiện đại khi bạn làm website, tránh viết code JavaScript/CSS cũ rườm rà.
- **`Ruff` & `Pytest`:** Công cụ kiểm tra lỗi cú pháp và chạy test tự động cho các dự án Python.

---

## 2. Cách Lấy Một Bộ Kit / Repo Từ GitHub Về Máy Chạy Ngay

Nếu bạn chưa quen dùng PowerShell, cứ làm chậm từng bước dưới đây (chỉ cần làm lần đầu):

### Bước 1: Đăng nhập GitHub (chỉ làm 1 lần)
1. Nếu ở màn hình cài xong bạn đã bấm **`Đăng nhập GitHub (Tải Kit)`**, hãy bỏ qua bước này.
2. Nếu chưa, mở **PowerShell** và gõ:
   ```powershell
   gh auth login
   ```
   Chọn lần lượt: `GitHub.com` → `HTTPS` → `Yes` → `Login with a web browser`, nhấn **Enter** rồi dán mã hiện trên màn hình vào trình duyệt để xác nhận.
3. Khai tên cho Git (để sau này lưu thay đổi không báo lỗi):
   ```powershell
   git config --global user.name "Ten Cua Ban"
   git config --global user.email "email-github-cua-ban@example.com"
   ```

### Bước 2: Tải bộ kit về máy
Mở PowerShell tại ổ đĩa bạn muốn lưu (ví dụ `D:\DuAn\`), gõ:
```powershell
gh repo clone <link-hoac-ten-repo>
```
Sau đó mở chính thư mục vừa tải về bằng trình biên tập AI (*Antigravity / Claude Code / VS Code*).

---

## 3. Cách Nói Chuyện Với AI Để Code Không Bị Rối Hoặc Lỗi Vòng Lặp

1. **Bước 0 — Để AI đọc hướng dẫn dự án trước:**  
   Khi mới mở thư mục vừa tải về, câu đầu tiên hãy nhắn:
   > *"Hãy đọc `README.md` và `CLAUDE.md` (nếu có) của dự án này, rồi hướng dẫn tôi cách chạy thử trên máy."*
2. **Với tính năng mới hoặc yêu cầu lớn:**  
   Dùng lệnh `/plan` hoặc nói rõ ràng trước khi sửa:
   > *"Tôi muốn thêm chức năng [X]. Hãy lên kế hoạch ngắn gọn gồm các tệp sẽ sửa trước, chờ tôi đồng ý rồi mới viết code."*
3. **Khi gặp lỗi đỏ trên màn hình:**  
   Đừng vội bảo *"Sửa lại đi"*. Hãy copy nguyên đoạn báo lỗi (hoặc chụp ảnh màn hình) gửi vào khung chat:
   > *"Khi chạy lệnh [X], máy báo lỗi này. Hãy tìm đúng nguyên nhân gốc, sửa gọn rồi chạy lại kiểm tra giúp tôi."*
4. **Luôn giữ bản sao an toàn:**  
   Trước khi sửa lớn một tính năng đang chạy tốt, hãy bảo AI tạo một nhánh Git mới hoặc sao lưu trước.

---

## 4. Phối Hợp Nhịp Nhàng: Karpathy → Superpowers → EGM

Để vừa code chắc tay vừa không tốn quota thừa, bộ quy tắc đã nối sẵn 3 tầng kiểm soát chất lượng:
- **Sửa nhỏ 1–2 tệp:** Chỉ dùng `karpathy-guidelines` để sửa gọn, không gọi thêm tác nhân phụ.
- **Tính năng thường / sửa lỗi / viết test:** Để `superpowers` dẫn dắt từ lập kế hoạch đến kiểm thử thật.
- **Thiết kế lớn, bảo mật, đổi cấu trúc dữ liệu hoặc cần mắt nhìn khách quan rà lỗ hổng:** Chuyển lên **Lô 5 · EGM** — bắt đầu bằng `/egm:egm-lite` (nhanh, tiết kiệm) hoặc `/egm:egm-review <file>` (5 vòng chuyên sâu). Xem hướng dẫn đầy đủ tại [`05-lo-phan-bien-egm.md`](05-lo-phan-bien-egm.md).

---

## 5. Lưu Ý An Toàn Tài Khoản & API Key
- **Tuyệt đối không** dán API Key, mật khẩu, cookie trình duyệt trực tiếp vào các tệp code rồi đẩy lên GitHub công khai.
- Các thông tin bí mật luôn đặt trong tệp `.env` (tệp này thường đã được `.gitignore` ẩn đi).
