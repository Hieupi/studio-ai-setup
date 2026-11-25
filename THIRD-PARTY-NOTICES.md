# Thông Báo Bên Thứ Ba (Third-Party Notices)

**Studio AI Setup** tự động tải trực tiếp các công cụ và thư viện nguồn mở chính thức từ danh sách dưới đây theo lựa chọn của người dùng. Toàn bộ thông tin phiên bản/commit được khóa trong `catalog-lock.json`.

| Lô | Thành phần | Phiên bản / Commit ghim | Giấy phép | Nguồn chính thức |
| :--- | :--- | :--- | :--- | :--- |
| Lô 0 · Nền tảng | Python 3.12 | `Python.Python.3.12` (>= 3.10) | PSF License | https://www.python.org/ |
| Lô 0 · Nền tảng | uv | `astral-sh.uv` | MIT / Apache-2.0 | https://github.com/astral-sh/uv |
| Lô 0 · Nền tảng | Node.js LTS | `OpenJS.NodeJS.LTS` (^22.23.4 / ^24.22.1 / >=26.12.1) | MIT | https://nodejs.org/ |
| Lô 0 · Nền tảng | Git for Windows | `Git.Git` | GPL-2.0 | https://git-scm.com/ |
| Lô 0 · Nền tảng | GitHub CLI (`gh`) | `GitHub.cli` | MIT | https://cli.github.com/ |
| Lô 1 · Content | Vietnamese Humanizer (chỉ lấy `humanizer-vi`, `translationese-cleaner-vi`, `lint.py`) | Commit `f6d54bdd627a` (v0.7.0+) | MIT | https://github.com/longhang2004/vietnamese-humanizer |
| Lô 1 · Content | Jsonschema & PyYAML | `jsonschema==4.23.0`, `PyYAML==6.0.2` | MIT | https://pypi.org/ |
| Lô 2 · Edit Video | FFmpeg & FFprobe | `Gyan.FFmpeg` | GPL / LGPL | https://ffmpeg.org/ |
| Lô 2 · Edit Video | Auto-Editor | `29.3.1` | Unlicense | https://github.com/WyattBlue/auto-editor |
| Lô 2 · Edit Video | FFmpeg Skill | `ffmpeg-skill@3.8.16` | MIT | https://github.com/kajisho5/ffmpeg-skill |
| Lô 2 · Edit Video | EditAtlas Skills (chỉ lấy `sound-design`, `media-picker`) | Commit `75cee479db21` | MIT | https://github.com/EditAtlas/skills |
| Lô 2 · Edit Video | REA Video | Commit `b08faf2eb536` | MIT | https://github.com/JuneYaooo/rea-video |
| Lô 2 · Edit Video | Thư viện Media Python (`numpy`, `pillow`, `opencv-python`, `soundfile`, `scipy`, `pyyaml`, `openpyxl`) | PyPI trong venv riêng | BSD / MIT / Apache-2.0 | https://pypi.org/ |
| Lô 2 · Tùy chọn | OpenMontage | Commit `2e003e65fa99` (tùy chọn, tắt mặc định) | AGPL-3.0 | https://github.com/calesthio/OpenMontage |
| Lô 2 · Tùy chọn | AssetFurnace 3D (`image-to-3dlab`) | Commit `a319975821a6` (tùy chọn, tắt mặc định, cần GPU NVIDIA) | Apache-2.0 | https://github.com/Bingeljell/image-to-3dlab |
| Lô 3 · Code | Superpowers Skills | Commit `22f0b463e7a5` | MIT | https://github.com/obra/superpowers |
| Lô 3 · Code | Andrej Karpathy Coding Guidelines | SHA-256 `6e22cc54cb02a5e98ae42d06d9d7292db0c1b43894831b32879beb0166b2aea7` | MIT | https://github.com/multica-ai/andrej-karpathy-skills |
| Lô 3 · Code | Modern Web Guidance | `modern-web-guidance@1.0.2` | Apache-2.0 | https://github.com/GoogleChrome/modern-web-guidance-src |
| Lô 3 · Code | Ruff & Pytest | `ruff==0.17.6`, `pytest==9.2.0` | MIT | https://pypi.org/ |
| Lô 4 · Cào & Nghiên cứu | Reverse Engineer Anything (`rea-agents`) | `rea-agents@6.10.1` | MIT | https://www.npmjs.com/package/rea-agents |
| Lô 4 · Cào & Nghiên cứu | yt-dlp | `2026.11.23` | Unlicense | https://github.com/yt-dlp/yt-dlp |
| Lô 4 · Cào & Nghiên cứu | Trendspyg | `1.9.0` | MIT | https://github.com/flack0x/trendspyg |
| Lô 4 · Cào & Nghiên cứu | MarkItDown | `0.1.9` | MIT | https://github.com/microsoft/markitdown |
| Lô 4 · Tùy chọn | Agent-Reach | Commit `8d9ecc1f5521` (tùy chọn, tắt mặc định) | MIT | https://github.com/Panniantong/Agent-Reach |
| Lô 5 · Phản biện (EGM) | Google Elephant-Goldfish Model (EGM) | Commit `63e239d8d4c3` (v0.1.1+egm-lite) | Apache-2.0 | https://github.com/google/elephant-goldfish-model |

---

## Ghi Nhận Bản Quyền Bắt Buộc (Upstream Attributions)

- **Elephant-Goldfish Model (EGM):** `Copyright 2026 Google LLC` — Licensed under the Apache License, Version 2.0 (tệp `LICENSE` gốc được giữ nguyên trong thư mục cài đặt plugin). *This is not an officially supported Google product.*
