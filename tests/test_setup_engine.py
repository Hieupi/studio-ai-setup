"""Regression, migration, multi-harness, and security tests for Studio AI Setup v2.0.0."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import setup_engine as eng


def _load_build_release():
    spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts" / "build-release.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BUILD_MOD = _load_build_release()

# Exact canonical v1.0.0 rule templates (matching embedded V1_*_CANONICAL_SHA256 in setup_engine.py)
V1_AGENTS_TEMPLATE = (
    "# AGENTS.md — Quy Tắc Điều Phối Tự Động (Studio AI Setup)\n"
    "\n"
    "- **Người dùng**: **{{USER_NAME}}**. Xưng hô lịch sự, tự nhiên, nghiêm túc, ngắn gọn và đi thẳng vào giải pháp.\n"
    "- **Quy tắc Thứ Tự Ưu Tiên Tuyệt Đối *(Local-First)***: Khi mở bất kỳ thư mục dự án nào có tệp `CLAUDE.md` (hoặc `.agent/rules/` riêng), **luôn đọc `CLAUDE.md` của dự án đó trước ở Bước 0**. Mọi quy tắc, vùng cấm, bước tốn phí và lệnh kiểm \"xong\" của dự án luôn được ưu tiên cao hơn quy tắc chung này.\n"
    "- **Chất lượng đầu ra**: Không cắt cụt mã nguồn (`// ...rest`, `/* TODO */`), không trả lời vòng vo hay thuyết giáo thừa, không tự bịa số liệu hoặc kết quả kiểm thử chưa chạy.\n"
    "\n"
    "## Tự Động Chọn Đúng Công Cụ Theo 4 Lô (Người dùng không cần nhớ tên lệnh)\n"
    "\n"
    "| Ngữ cảnh công việc | Lô tương ứng | Kỹ năng & công cụ tự động áp dụng |\n"
    "| :--- | :--- | :--- |\n"
    "| **Viết kịch bản, bài viết, lời thoại, lọc văn phong AI** | **Lô 1 · Content** | Tự đọc `humanizer-vi` và `translationese-cleaner-vi` (nếu có); áp dụng lối viết giàu hình ảnh cụ thể, chất đời tự nhiên, bỏ câu mở đầu sáo rỗng và lời dịch máy. Nếu là kịch bản tài liệu/sự kiện thật, tuân thủ tuyệt đối nguồn gốc dữ liệu trong dự án. |\n"
    "| **Dựng video, xử lý âm thanh, cắt ghép, mổ xẻ video mẫu** | **Lô 2 · Edit Video** | Kết hợp `rea-video` (bóc cấu trúc từng cảnh), `ffmpeg-skill` (cắt ghép, đo chuẩn âm lượng `-14 LUFS`), `auto-editor` (cắt khoảng lặng), `sound-design` & `media-picker`. Ưu tiên xem xét bố cục Remotion/FFmpeg rõ ràng trước khi xuất bản. |\n"
    "| **Lập trình ứng dụng, sửa lỗi, chạy repo/kit từ GitHub** | **Lô 3 · Code** | Áp dụng 4 nguyên tắc Karpathy (`Think Before Coding → Simplicity First → Surgical Changes → Goal-Driven Execution`) cùng bộ kỹ năng `superpowers` (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`) và `modern-web-guidance` (tra cứu 250+ tính năng web hiện đại Chrome/MDN khi làm web). |\n"
    "| **Nghiên cứu ngách, cào dữ liệu web, đọc PDF/DOCX, phân tích app/web** | **Lô 4 · Cào & Nghiên cứu** | Dùng công cụ `rea` MCP theo chiến thuật *Summary-First* (`open` -> phân tích tóm tắt -> `close`), dùng `markitdown` chuyển tài liệu sang Markdown sạch, dùng `trendspyg` kiểm tra xu hướng YouTube có kiểm soát tốc độ, tôn trọng điều khoản nguồn dữ liệu và không lưu/lộ cookie hay API key. |\n"
    "\n"
    "## Tự Động Đề Xuất Lệnh Hệ Thống Đúng Lúc\n"
    "- Yêu cầu mới hoặc phức tạp cần chốt kiến trúc trước khi làm $\\rightarrow$ gợi ý người dùng gõ `/plan` hoặc `/grill-me`.\n"
    "- Công việc nhiều bước cần chạy tự động dài hơi $\\rightarrow$ gợi ý `/goal`.\n"
    "- Cuộc trò chuyện đã quá dài $\\rightarrow$ gợi ý `/compact` để làm nhẹ bộ nhớ.\n"
)

V1_GEMINI_TEMPLATE = (
    "# GEMINI.md — Kỷ Luật Thực Thi & Sáng Tạo (Studio AI Setup)\n"
    "\n"
    "## 1. Kỷ luật Lập trình (Tương thích Karpathy Guidelines)\n"
    "1. **Think Before Coding**: Nêu rõ giả định và kế hoạch ngắn trước khi sửa; nếu yêu cầu chưa rõ ở điểm ảnh hưởng lớn, hãy hỏi lại trước khi đoán.\n"
    "2. **Simplicity First**: Chọn giải pháp nhỏ nhất, gọn nhất đáp ứng đúng yêu cầu. Không tự thêm tầng trừu tượng hoặc tính năng không được yêu cầu.\n"
    "3. **Surgical Changes**: Chỉ sửa đúng phạm vi liên quan, giữ nguyên định dạng, chú thích và phần mã đang chạy ổn định.\n"
    "4. **Goal-Driven Execution**: Luôn xác minh bằng lệnh chạy/test thực tế sau khi sửa; báo cáo trung thực lệnh đã chạy, kết quả thực tế và điểm chưa kiểm chứng.\n"
    "\n"
    "## 2. Kỷ luật Viết Content & Kịch Bản Video\n"
    "1. **Loại bỏ văn mẫu AI**: Tránh mở đầu công thức (*\"Trong bối cảnh hiện nay...\"*, *\"Không thể phủ nhận...\"*), tránh tính từ sáo rỗng, tránh kết bài giảng đạo lý.\n"
    "2. **Chất đời & Cụ thể**: Ưu tiên chi tiết vật lý, bối cảnh, hành động cụ thể, đối thoại ngắn tự nhiên có ngữ cảnh.\n"
    "3. **Nhịp giữ chân người xem**: Mở đầu 3–5 giây đầu đi thẳng vào xung đột hoặc câu hỏi gợi tò mò, chia cảnh rõ ràng để dễ chuyển sang dựng video.\n"
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_mock_egm_source(src_root: Path, egm_entry: dict) -> None:
    """Create a synthetic EGM repository tree with allowlisted files and excluded noise."""
    _write_text(src_root / "plugin.json", json.dumps({"name": "egm", "version": "0.1.1"}))
    _write_text(src_root / "LICENSE", "Apache License 2.0\nCopyright 2026 Google LLC\n")
    _write_text(src_root / "README.md", "# Elephant-Goldfish Model\n")
    _write_text(src_root / "assets" / "logo.svg", "<svg/>")
    _write_text(src_root / "resources" / "overview.md", "# Overview\n")
    _write_text(src_root / "docs" / "index.md", "# Docs\n")

    for i in range(1, int(egm_entry["required_agent_count"]) + 1):
        _write_text(src_root / "agents" / f"goldfish-{i:02d}.md", f"# Reviewer {i}\n")

    for i in range(1, int(egm_entry["required_standard_count"]) + 1):
        _write_text(src_root / "resources" / "document_standards" / f"standard-{i:02d}.md", f"# Standard {i}\n")

    for skill in egm_entry["required_skills"]:
        _write_text(src_root / "skills" / skill / "SKILL.md", f"---\nname: {skill}\n---\n")
        _write_text(src_root / "skills" / skill / "agents" / "openai.yaml", "name: egm\n")
        _write_text(src_root / "skills" / skill / "references" / "rubric.md", "# Rubric\n")

    # Unified multi-harness extras (Claude Code + Codex)
    _write_text(src_root / ".claude-plugin" / "plugin.json", json.dumps({"name": "egm", "version": "0.1.1"}))
    _write_text(src_root / ".claude-plugin" / "marketplace.json", json.dumps({"name": "egm"}))
    (src_root / ".claude-plugin" / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    _write_text(src_root / ".claude-plugin" / "agents" / "goldfish-01.md", "# Claude Agent\n")
    _write_text(src_root / ".codex-plugin" / "plugin.json", json.dumps({"name": "egm", "version": "0.1.1"}))
    _write_text(src_root / ".agents" / "plugins" / "marketplace.json", json.dumps({"name": "egm"}))

    # Non-allowlisted noise & deeper-depth paths that exact-depth Path.glob() must exclude
    _write_text(src_root / "site" / "index.html", "<html>docs site</html>")
    _write_text(src_root / "tests" / "test_egm.py", "def test_ok(): pass\n")
    _write_text(src_root / ".github" / "workflows" / "ci.yml", "name: ci\n")
    _write_text(src_root / "TEST.md", "# Internal test notes\n")
    _write_text(src_root / "agents" / "nested" / "deep.md", "# Too deep for agents/*.md\n")
    _write_text(src_root / "skills" / "egm-lite" / "nested" / "SKILL.md", "# Too deep\n")


class CatalogLockTests(unittest.TestCase):
    def test_catalog_v2_pins_all_five_lots_and_integrity_hashes(self) -> None:
        cat = eng.load_catalog(ROOT / "catalog-lock.json")
        self.assertEqual(cat["schema_version"], 2)
        self.assertEqual(cat["app_name"], "Studio AI Setup")
        self.assertEqual(cat["app_version"], "2.0.0")
        for key in ("lot0_core", "lot1_content", "lot2_video", "lot3_code", "lot4_data", "lot5_review"):
            self.assertIn(key, cat)

        # Selective safe bumps & pins
        self.assertEqual(cat["lot1_content"]["vietnamese_humanizer"]["commit"], "f6d54bdd627a167e2539558037b860c18f485513")
        self.assertEqual(cat["lot3_code"]["modern_web_guidance"]["npm_spec"], "modern-web-guidance@1.0.2")
        self.assertEqual(cat["lot3_code"]["modern_web_guidance"]["version"], "1.0.2")
        self.assertEqual(cat["lot4_data"]["yt_dlp"]["pypi_spec"], "yt-dlp==2026.11.23")
        self.assertEqual(cat["lot4_data"]["rea_agents"]["version"], "6.10.1")

        # Optional heavy repos: off by default + full 40-char lowercase hex commit SHAs
        optional_entries = (
            cat["lot2_video"]["optional_openmontage"],
            cat["lot2_video"]["optional_assetfurnace"],
            cat["lot4_data"]["optional_agent_reach"],
        )
        for opt in optional_entries:
            self.assertFalse(opt["default_enabled"])
            self.assertRegex(opt["commit"], r"^[0-9a-f]{40}$")

        # Lot 5 EGM fields
        egm = cat["lot5_review"]["egm"]
        self.assertEqual(egm["commit"], "63e239d8d4c3ddc6774faf533b4997405f78c549")
        self.assertEqual(egm["license"], "Apache-2.0")
        self.assertEqual(egm["disclaimer"], "This is not an officially supported Google product.")
        self.assertEqual(len(egm["required_skills"]), 8)
        self.assertIn("egm-lite", egm["required_skills"])
        self.assertEqual(egm["required_agent_count"], 10)
        self.assertEqual(egm["required_standard_count"], 5)

        # Direct binary downloads
        direct_entries = [cat["lot0_core"][k] for k in ("python", "uv", "node", "git", "gh")] + [cat["lot2_video"]["ffmpeg"]]
        for entry in direct_entries:
            self.assertTrue(entry["direct_url"].startswith("https://"))
            self.assertRegex(entry["direct_sha256"], r"^[0-9a-f]{64}$")

        # All 5 GitHub codeload entries have valid 64-lowercase-hex tree_sha256
        codeload_entries = (
            cat["lot1_content"]["vietnamese_humanizer"],
            cat["lot2_video"]["editatlas_skills"],
            cat["lot2_video"]["rea_video"],
            cat["lot3_code"]["superpowers"],
            cat["lot5_review"]["egm"],
        )
        for entry in codeload_entries:
            self.assertTrue(entry["archive_url"].startswith("https://codeload.github.com/"))
            self.assertRegex(entry["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(entry["tree_sha256"], r"^[0-9a-f]{64}$")

        raw_text = (ROOT / "catalog-lock.json").read_text(encoding="utf-8")
        self.assertNotIn("@latest", raw_text)

    def test_load_catalog_accepts_schema_v1_and_v2_and_rejects_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "v1.json"
            p1.write_text(json.dumps({"schema_version": 1, "app_version": "1.0.0"}), encoding="utf-8")
            self.assertEqual(eng.load_catalog(p1)["schema_version"], 1)
            self.assertEqual(eng.get_app_version(catalog_path=p1), "1.0.0")

            p_bad = Path(tmp) / "v99.json"
            p_bad.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
            with self.assertRaises(eng.SetupError):
                eng.load_catalog(p_bad)


class SetupEngineUnitTests(unittest.TestCase):
    def test_sanitize_user_name_and_node_boundaries(self) -> None:
        self.assertEqual(eng.sanitize_user_name(None), "bạn")
        self.assertEqual(eng.sanitize_user_name("   \n\t "), "bạn")
        self.assertEqual(eng.sanitize_user_name("Anh Minh"), "Anh Minh")
        self.assertEqual(eng.sanitize_user_name("Lan<>`$\x01\x02"), "Lan")
        self.assertEqual(len(eng.sanitize_user_name("A" * 80)), 48)

        self.assertFalse(eng.node_supported("22.23.3"))
        self.assertTrue(eng.node_supported("v22.23.4"))
        self.assertFalse(eng.node_supported("24.22.0"))
        self.assertTrue(eng.node_supported("24.22.1"))
        self.assertFalse(eng.node_supported("26.12.0"))
        self.assertTrue(eng.node_supported("26.12.1"))
        self.assertTrue(eng.node_supported("v27.0.0"))

    def test_render_rules_preserves_local_first_modern_web_guidance_and_egm(self) -> None:
        rendered = eng.render_rules("Anh Nam")
        self.assertIn("Anh Nam", rendered["AGENTS.md"])
        self.assertNotIn("{{USER_NAME}}", rendered["AGENTS.md"])
        self.assertIn("CLAUDE.md", rendered["AGENTS.md"])
        self.assertIn("modern-web-guidance", rendered["AGENTS.md"])
        self.assertIn("/egm:egm-lite", rendered["AGENTS.md"])
        self.assertIn(eng.RULE_MARKER_BEGIN, rendered["AGENTS.md"])
        self.assertIn(eng.RULE_MARKER_END, rendered["AGENTS.md"])
        self.assertIn("Think Before Coding", rendered["GEMINI.md"])
        self.assertIn("Elephant-Goldfish Model", rendered["GEMINI.md"])
        self.assertIn(eng.RULE_MARKER_BEGIN, rendered["GEMINI.md"])
        self.assertIn(eng.RULE_MARKER_END, rendered["GEMINI.md"])

    def test_selective_allowlist_for_vietnamese_humanizer_editatlas_and_mwg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 1. Mock vietnamese-humanizer tree with forbidden folders
            vh_src = tmp_path / "vh_src"
            for rel in (
                "skills/humanizer-vi/SKILL.md",
                "skills/translationese-cleaner-vi/SKILL.md",
                "skills/style-guide-vi/SKILL.md",
                "src/vietnamese_writing_skills/cli/lint.py",
                "patterns/humanizer.yml",
                "pyproject.toml",
                ".agents/skills/impeccable/SKILL.md",
                "web/backend/app.py",
            ):
                _write_text(vh_src / rel, "demo")

            skill_target = tmp_path / "target_skills"
            tools_dest = tmp_path / "vh_tools"
            eng.deploy_vietnamese_humanizer_from_tree(vh_src, tools_dest, [skill_target])
            self.assertTrue((skill_target / "humanizer-vi" / "SKILL.md").is_file())
            self.assertTrue((skill_target / "translationese-cleaner-vi" / "SKILL.md").is_file())
            self.assertFalse((skill_target / "impeccable").exists())
            self.assertFalse((skill_target / "style-guide-vi").exists())
            self.assertFalse((tools_dest / ".agents").exists())
            self.assertFalse((tools_dest / "web").exists())

            # 2. Mock EditAtlas tree with forbidden evals and extra skills
            ea_src = tmp_path / "ea_src"
            for rel in (
                "skills/sound-design/SKILL.md",
                "skills/sound-design/evals/prompt.json",
                "skills/media-picker/SKILL.md",
                "skills/video-breakdown/SKILL.md",
                "skills/editable-export/SKILL.md",
            ):
                _write_text(ea_src / rel, "demo")
            eng.deploy_editatlas_from_tree(ea_src, [skill_target])
            self.assertTrue((skill_target / "sound-design" / "SKILL.md").is_file())
            self.assertTrue((skill_target / "media-picker" / "SKILL.md").is_file())
            self.assertFalse((skill_target / "sound-design" / "evals").exists())
            self.assertFalse((skill_target / "video-breakdown").exists())
            self.assertFalse((skill_target / "editable-export").exists())

            # 3. Mock modern-web-guidance tarball tree
            mwg_src = tmp_path / "mwg_src"
            _write_text(mwg_src / "skills" / "modern-web-guidance" / "SKILL.md", "---\nname: modern-web-guidance\n---\n")
            _write_text(mwg_src / "skills" / "modern-web-guidance" / "modern-web.mjs", "console.log('ok');\n")
            eng.deploy_modern_web_guidance_from_tree(mwg_src, [skill_target])
            self.assertTrue((skill_target / "modern-web-guidance" / "SKILL.md").is_file())
            self.assertTrue((skill_target / "modern-web-guidance" / "modern-web.mjs").is_file())

    def test_preflight_cli_returns_valid_json(self) -> None:
        res = subprocess.run(
            [sys.executable, "-B", str(ROOT / "engine" / "setup_engine.py"), "--preflight-json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(data["app_version"], "2.0.0")
        for key in ("os", "arch", "is_64bit", "nvidia_gpu", "tools", "ides"):
            self.assertIn(key, data)
        self.assertIn("plugins_dir", data["ides"]["antigravity"])


class EgmMultiHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cat = eng.load_catalog(ROOT / "catalog-lock.json")
        self.egm_entry = self.cat["lot5_review"]["egm"]

    def test_egm_allowlist_exact_depth_filters_noise_and_never_copies_flat_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_root = tmp_path / "egm_src"
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            _build_mock_egm_source(src_root, self.egm_entry)

            # Simulate existing IDE directories for all harnesses
            for d in (".gemini", ".claude", ".codex", ".agents"):
                (home / d).mkdir(parents=True, exist_ok=True)
            ides = eng.detect_ides(home=home)

            with mock.patch.object(eng.shutil, "which", return_value=None):
                res = eng.deploy_egm_from_tree(src_root, self.egm_entry, ides, app_root, home=home)

            ag_egm = home / ".gemini" / "config" / "plugins" / "egm"
            unified_egm = app_root / "plugins" / "egm"

            self.assertEqual(res["skills_count"], 8)
            self.assertEqual(res["agents_count"], 10)
            self.assertEqual(res["standards_count"], 5)
            self.assertTrue((ag_egm / "plugin.json").is_file())
            self.assertTrue((ag_egm / "LICENSE").is_file())
            for sk in self.egm_entry["required_skills"]:
                self.assertTrue((ag_egm / "skills" / sk / "SKILL.md").is_file())
            self.assertEqual(len(list((ag_egm / "agents").glob("*.md"))), 10)
            self.assertEqual(len(list((ag_egm / "resources" / "document_standards").glob("*.md"))), 5)

            # Noise & deeper nested files strictly excluded
            for forbidden in ("site", "tests", ".github", "TEST.md", "agents/nested", "skills/egm-lite/nested"):
                self.assertFalse((ag_egm / forbidden).exists(), f"Should not exist in Antigravity bundle: {forbidden}")
                self.assertFalse((unified_egm / forbidden).exists(), f"Should not exist in unified bundle: {forbidden}")
            self.assertFalse((ag_egm / ".claude-plugin").exists())
            self.assertTrue((unified_egm / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((unified_egm / ".codex-plugin" / "plugin.json").is_file())
            self.assertTrue((unified_egm / ".agents" / "plugins" / "marketplace.json").is_file())

            # NEVER flatten EGM skills into flat skills/ folders
            for flat_dir in (
                home / ".gemini" / "config" / "skills",
                home / ".claude" / "skills",
                home / ".codex" / "skills",
                home / ".agents" / "skills",
            ):
                for sk in self.egm_entry["required_skills"]:
                    self.assertFalse((flat_dir / sk).exists(), f"Flat skill copy forbidden: {flat_dir / sk}")

    def test_egm_rejects_tampered_manifests_and_missing_required_components(self) -> None:
        for bad_key in ("hooks", "mcpServers", "mcp", "apps"):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                src = tmp_path / "src"
                _build_mock_egm_source(src, self.egm_entry)
                _write_text(src / "plugin.json", json.dumps({"name": "egm", bad_key: {"bad": True}}))
                ides = eng.detect_ides(home=tmp_path / "home")
                with self.assertRaises(eng.SetupError):
                    eng.deploy_egm_from_tree(src, self.egm_entry, ides, tmp_path / "app", home=tmp_path / "home")

        # Forbidden key hidden in extensions or .claude-plugin/.codex-plugin manifests
        for target_manifest, payload in (
            ("plugin.json", {"name": "egm", "extensions": {"com.openai": {"mcp": {"x": 1}}}}),
            (".claude-plugin/plugin.json", {"name": "egm", "hooks": []}),
            (".codex-plugin/plugin.json", {"name": "egm", "apps": {}}),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                src = tmp_path / "src"
                _build_mock_egm_source(src, self.egm_entry)
                _write_text(src / target_manifest, json.dumps(payload))
                ides = eng.detect_ides(home=tmp_path / "home")
                with self.assertRaises(eng.SetupError):
                    eng.deploy_egm_from_tree(src, self.egm_entry, ides, tmp_path / "app", home=tmp_path / "home")

        # Missing LICENSE / skill / agent / standard
        for to_delete in (
            "LICENSE",
            "skills/egm-lite/SKILL.md",
            "agents/goldfish-10.md",
            "resources/document_standards/standard-05.md",
        ):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                src = tmp_path / "src"
                _build_mock_egm_source(src, self.egm_entry)
                (src / to_delete).unlink()
                ides = eng.detect_ides(home=tmp_path / "home")
                with self.assertRaises(eng.SetupError):
                    eng.deploy_egm_from_tree(src, self.egm_entry, ides, tmp_path / "app", home=tmp_path / "home")

    def test_clean_machine_antigravity_always_stages_superpowers_and_egm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            clean_home = tmp_path / "clean_home"
            clean_home.mkdir()
            app_root = tmp_path / "app"

            ides = eng.detect_ides(home=clean_home)
            self.assertFalse(ides["antigravity"]["detected"])
            _, _, _, ag_plugins_root = eng._target_skill_and_rule_dirs(ides)
            self.assertEqual(ag_plugins_root, clean_home / ".gemini" / "config" / "plugins")

            # Stage superpowers on clean machine
            sp_src = tmp_path / "sp_src"
            _write_text(sp_src / ".antigravity-plugin" / "plugin.json", json.dumps({"name": "superpowers"}))
            _write_text(sp_src / "skills" / "brainstorming" / "SKILL.md", "# Brainstorming\n")
            eng.deploy_superpowers_from_tree(sp_src, [], ag_plugins_root / "superpowers")
            self.assertTrue((clean_home / ".gemini" / "config" / "plugins" / "superpowers" / ".antigravity-plugin" / "plugin.json").is_file())

            # Stage EGM on clean machine
            egm_src = tmp_path / "egm_src"
            _build_mock_egm_source(egm_src, self.egm_entry)
            with mock.patch.object(eng.shutil, "which", return_value=None):
                eng.deploy_egm_from_tree(egm_src, self.egm_entry, ides, app_root, home=clean_home)
            self.assertTrue((clean_home / ".gemini" / "config" / "plugins" / "egm" / "plugin.json").is_file())
            self.assertTrue((clean_home / ".gemini" / "config" / "plugins" / "egm" / "skills" / "egm-lite" / "SKILL.md").is_file())

    def test_claude_cli_registration_non_clobber_and_no_redundant_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            (home / ".claude" / "plugins").mkdir(parents=True)
            unified_dir = tmp_path / "app" / "plugins" / "egm"
            unified_dir.mkdir(parents=True)
            ides = eng.detect_ides(home=home)

            # Case 1: Already installed -> skip without running CLI
            _write_text(home / ".claude" / "plugins" / "installed_plugins.json", json.dumps({"plugins": {"egm@egm": {"version": "0.1.1"}}}))
            calls: list[list[str]] = []

            def fake_runner(argv, **_kwargs):
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "/bin/claude" if c == "claude" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["claude_code"]["status"], "already_installed")
            self.assertEqual(calls, [])

            # Case 2: Existing marketplace pointing elsewhere -> do NOT overwrite marketplace
            (home / ".claude" / "plugins" / "installed_plugins.json").unlink()
            _write_text(
                home / ".claude" / "plugins" / "known_marketplaces.json",
                json.dumps({"egm": {"installLocation": str(tmp_path / "user_custom_egm")}}),
            )
            calls.clear()
            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "/bin/claude" if c == "claude" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["claude_code"]["status"], "installed")
            self.assertTrue(h["claude_code"].get("marketplace_preserved"))
            self.assertEqual(calls, [["/bin/claude", "plugin", "install", "egm@egm"]])

            # Case 3: Fresh registration -> runs marketplace add + install, NEVER redundant enable
            (home / ".claude" / "plugins" / "known_marketplaces.json").unlink()
            calls.clear()
            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "/bin/claude" if c == "claude" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["claude_code"]["status"], "installed")
            self.assertEqual(
                calls,
                [
                    ["/bin/claude", "plugin", "marketplace", "add", str(unified_dir)],
                    ["/bin/claude", "plugin", "install", "egm@egm"],
                ],
            )
            self.assertFalse(any("enable" in cmd for cmd in calls))

            # Case 4: Missing CLI -> non-fatal manual fallback
            with mock.patch.object(eng.shutil, "which", return_value=None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["claude_code"]["status"], "cli_not_found")
            self.assertEqual(len(h["claude_code"]["manual_commands"]), 2)

            # Case 5: Failing CLI -> non-fatal manual_required
            def failing_runner(argv, **_kwargs):
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="cli error")

            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "/bin/claude" if c == "claude" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=failing_runner)
            self.assertEqual(h["claude_code"]["status"], "manual_required")
            self.assertEqual(len(h["claude_code"]["manual_commands"]), 2)

    def test_codex_cli_registration_toml_section_regex_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            (home / ".codex").mkdir(parents=True)
            unified_dir = tmp_path / "app" / "plugins" / "egm"
            unified_dir.mkdir(parents=True)
            ides = eng.detect_ides(home=home)

            calls: list[list[str]] = []

            def fake_runner(argv, **_kwargs):
                calls.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

            # Case 1: Active TOML section -> skip
            _write_text(home / ".codex" / "config.toml", '[plugins."egm@local"]\nenabled = true\n')
            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "C:/codex.CMD" if c == "codex" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["codex"]["status"], "already_installed")
            self.assertEqual(calls, [])

            # Case 2: Commented-out line or other plugin does NOT match -> runs marketplace add + add
            _write_text(home / ".codex" / "config.toml", '# [plugins."egm@egm"]\n[plugins."other@other"]\nenabled = true\n')
            calls.clear()
            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "C:/codex.CMD" if c == "codex" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["codex"]["status"], "installed")
            self.assertEqual(
                calls,
                [
                    ["C:/codex.CMD", "plugin", "marketplace", "add", str(unified_dir)],
                    ["C:/codex.CMD", "plugin", "add", "egm@egm"],
                ],
            )

            # Case 3: Missing CLI -> non-fatal manual fallback
            with mock.patch.object(eng.shutil, "which", return_value=None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=fake_runner)
            self.assertEqual(h["codex"]["status"], "cli_not_found")
            self.assertEqual(len(h["codex"]["manual_commands"]), 2)

            # Case 4: Failing CLI -> non-fatal manual_required
            def failing_runner(argv, **_kwargs):
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="codex error")

            with mock.patch.object(eng.shutil, "which", side_effect=lambda c: "C:/codex.CMD" if c == "codex" else None):
                h = eng.register_harness_plugin("egm", unified_dir, ides, home=home, runner=failing_runner)
            self.assertEqual(h["codex"]["status"], "manual_required")
            self.assertEqual(len(h["codex"]["manual_commands"]), 2)


class MigrationAndUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cat = eng.load_catalog(ROOT / "catalog-lock.json")

    def test_v1_unmodified_rules_upgrade_cleanly_with_offdir_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            rules_dir = home / ".gemini" / "config" / "rules"
            (home / "Documents").mkdir(parents=True)

            v1_agents = V1_AGENTS_TEMPLATE.replace("{{USER_NAME}}", "Minh Anh")
            _write_text(rules_dir / "AGENTS.md", v1_agents)
            _write_text(rules_dir / "GEMINI.md", V1_GEMINI_TEMPLATE)

            res = eng.finalize_setup(
                self.cat,
                user_name="Minh Anh",
                installed_lots=["lot1", "lot5"],
                home=home,
                app_root=app_root,
            )
            self.assertEqual(res["rules_status"]["AGENTS.md"], "upgraded_v1")
            self.assertEqual(res["rules_status"]["GEMINI.md"], "upgraded_v1")

            new_agents = (rules_dir / "AGENTS.md").read_text(encoding="utf-8")
            new_gemini = (rules_dir / "GEMINI.md").read_text(encoding="utf-8")
            self.assertIn(eng.RULE_MARKER_BEGIN, new_agents)
            self.assertIn(eng.RULE_MARKER_END, new_agents)
            self.assertIn("Minh Anh", new_agents)
            self.assertIn("Lô 5", new_agents)
            self.assertIn(eng.RULE_MARKER_BEGIN, new_gemini)
            self.assertIn("Elephant-Goldfish Model", new_gemini)

            # Zero .bak files inside rules/, backups stored strictly under app_root/backups/
            self.assertEqual(list(rules_dir.glob("*.bak*")), [])
            backup_files = list((app_root / "backups").rglob("*.md"))
            backup_names = {p.name for p in backup_files}
            self.assertIn("AGENTS.md", backup_names)
            self.assertIn("GEMINI.md", backup_names)

    def test_user_customized_markerless_agents_stays_untouched_and_reference_saved_in_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rules_dir = tmp_path / "rules"
            backup_root = tmp_path / "backups" / "20261125"
            custom_text = "# My Custom AGENTS\n- Always write in Haiku.\n"
            dst = rules_dir / "AGENTS.md"
            _write_text(dst, custom_text)

            rendered = eng.render_rules("Lan")["AGENTS.md"]
            res = eng.sync_rule_file(
                dst,
                rendered,
                backup_root,
                {eng.V1_AGENTS_CANONICAL_SHA256},
                normalize_user_line=True,
            )
            self.assertEqual(res["status"], "preserved_user_custom")
            self.assertEqual(dst.read_text(encoding="utf-8"), custom_text)
            self.assertEqual(list(rules_dir.iterdir()), [dst])
            ref_path = Path(res["reference"])
            self.assertTrue(ref_path.is_file())
            self.assertEqual(ref_path.parent, backup_root)
            self.assertIn(".v2-reference.md", ref_path.name)
            self.assertIn(eng.RULE_MARKER_BEGIN, ref_path.read_text(encoding="utf-8"))

    def test_marker_wrapped_rule_preserves_custom_lines_before_and_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rules_dir = tmp_path / "rules"
            backup_root = tmp_path / "backups" / "20261125"
            dst = rules_dir / "AGENTS.md"
            prefix = "# User Personal Header\n- Keep my top rule.\n\n"
            suffix = "\n\n## User Personal Footer\n- Keep my bottom rule.\n"
            initial = f"{prefix}{eng.RULE_MARKER_BEGIN}\nOLD MANAGED CONTENT\n{eng.RULE_MARKER_END}{suffix}"
            _write_text(dst, initial)

            rendered = eng.render_rules("Huy")["AGENTS.md"]
            res = eng.sync_rule_file(dst, rendered, backup_root, {eng.V1_AGENTS_CANONICAL_SHA256}, normalize_user_line=True)
            self.assertEqual(res["status"], "updated_markers")
            updated = dst.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith(prefix))
            self.assertTrue(updated.endswith(suffix))
            self.assertIn("Huy", updated)
            self.assertNotIn("OLD MANAGED CONTENT", updated)
            self.assertEqual(list(rules_dir.glob("*.bak*")), [])
            self.assertTrue(Path(res["backup"]).is_file())

    def test_atomic_replace_dir_prunes_stale_files_and_rolls_back_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dst = tmp_path / "plugin_dir"
            _write_text(dst / "stale_v1.txt", "stale")
            _write_text(dst / "keep.txt", "v1")

            def _build_v2(stage: Path) -> None:
                _write_text(stage / "keep.txt", "v2")
                _write_text(stage / "fresh_v2.txt", "fresh")

            eng.atomic_replace_dir(_build_v2, dst)
            self.assertFalse((dst / "stale_v1.txt").exists())
            self.assertEqual((dst / "keep.txt").read_text(encoding="utf-8"), "v2")
            self.assertEqual((dst / "fresh_v2.txt").read_text(encoding="utf-8"), "fresh")
            self.assertEqual(list(tmp_path.glob(".*.stage-*")), [])
            self.assertEqual(list(tmp_path.glob(".*.old-*")), [])

            # Simulate error on second os.replace (stage -> dst); verify automatic rollback
            real_replace = os.replace
            call_count = {"n": 0}

            def flaky_replace(src, target):
                call_count["n"] += 1
                if call_count["n"] == 2:
                    raise OSError("Simulated swap failure")
                return real_replace(src, target)

            with mock.patch.object(eng.os, "replace", side_effect=flaky_replace), self.assertRaises(OSError):
                eng.atomic_replace_dir(lambda s: _write_text(s / "broken.txt", "x"), dst)

            self.assertEqual((dst / "keep.txt").read_text(encoding="utf-8"), "v2")
            self.assertFalse((dst / "broken.txt").exists())
            self.assertEqual(list(tmp_path.glob(".*.stage-*")), [])
            self.assertEqual(list(tmp_path.glob(".*.old-*")), [])

    def test_decoupled_rules_and_state_json_merges_partial_lots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            (home / "Documents").mkdir(parents=True)

            # 1. Finalize deploys rules even when lot3 is NOT selected
            r1 = eng.finalize_setup(
                self.cat,
                user_name="Thu",
                installed_lots=["lot1", "lot2", "lot4"],
                home=home,
                app_root=app_root,
            )
            self.assertTrue((home / ".gemini" / "config" / "rules" / "AGENTS.md").is_file())
            self.assertTrue((home / ".gemini" / "config" / "rules" / "GEMINI.md").is_file())
            self.assertEqual(r1["installed_lots"], ["lot1", "lot2", "lot4"])

            # 2. Partial --lots lot5 merges into existing installed_lots without erasing lot1,2,4
            r2 = eng.finalize_setup(
                self.cat,
                user_name=None,
                installed_lots=["lot5"],
                home=home,
                app_root=app_root,
            )
            self.assertEqual(r2["user_name"], "Thu")
            self.assertEqual(r2["installed_lots"], ["lot1", "lot2", "lot4", "lot5"])

            # 3. Omitting --lots (installed_lots=None) preserves existing installed_lots
            r3 = eng.finalize_setup(
                self.cat,
                user_name="Thu",
                installed_lots=None,
                home=home,
                app_root=app_root,
            )
            self.assertEqual(r3["installed_lots"], ["lot1", "lot2", "lot4", "lot5"])
            persisted = eng.load_state(app_root)
            self.assertEqual(persisted["installed_lots"], ["lot1", "lot2", "lot4", "lot5"])
            self.assertEqual(persisted["app_version"], "2.0.0")


class SecurityAndWindowsEdgeCaseTests(unittest.TestCase):
    def test_download_bytes_blocks_https_to_http_redirect_downgrade_and_retries_5xx(self) -> None:
        # 1. Reject plain HTTP upfront
        with self.assertRaises(eng.SetupError):
            eng.download_bytes("http://example.com/file.zip")

        # 2. _HttpsOnlyRedirectHandler blocks HTTPS -> HTTP downgrade
        handler = eng._HttpsOnlyRedirectHandler()
        req = urllib.request.Request("https://example.com/start")
        with self.assertRaises(eng.SetupError):
            handler.redirect_request(req, None, 302, "Found", {}, "http://evil.example.com/payload")

        # 3. Retries transient 503 and succeeds on 3rd attempt
        payload = b"clean-payload-v2"
        expected_sha = hashlib.sha256(payload).hexdigest()
        attempts = {"count": 0}

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self) -> str:
                return "https://example.com/final"

            def read(self) -> bytes:
                return payload

        class _FakeOpener:
            def open(self, _req, timeout=120):
                del timeout
                attempts["count"] += 1
                if attempts["count"] < 3:
                    raise urllib.error.HTTPError("https://example.com/file", 503, "Service Unavailable", {}, None)
                return _FakeResp()

        with (
            mock.patch.object(eng.urllib.request, "build_opener", return_value=_FakeOpener()),
            mock.patch.object(eng.time, "sleep") as sleep_mock,
        ):
            data = eng.download_bytes("https://example.com/file", expected_sha256=expected_sha, retries=3)
        self.assertEqual(data, payload)
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(sleep_mock.call_count, 2)

        # 4. SHA-256 mismatch fails cleanly
        attempts["count"] = 2
        with mock.patch.object(eng.urllib.request, "build_opener", return_value=_FakeOpener()), self.assertRaises(eng.SetupError):
            eng.download_bytes("https://example.com/file", expected_sha256="0" * 64, retries=1)

    def test_compute_tree_sha256_detects_tampering_and_ignores_zip_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            z1 = tmp_path / "z1.zip"
            z2 = tmp_path / "z2.zip"

            with zipfile.ZipFile(z1, "w", compression=zipfile.ZIP_STORED) as zf:
                zi1 = zipfile.ZipInfo("repo/a.txt", date_time=(2020, 1, 1, 0, 0, 0))
                zi2 = zipfile.ZipInfo("repo/sub/b.txt", date_time=(2020, 1, 1, 0, 0, 0))
                zf.writestr(zi1, b"alpha")
                zf.writestr(zi2, b"bravo")

            with zipfile.ZipFile(z2, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                zi1 = zipfile.ZipInfo("repo/a.txt", date_time=(2026, 11, 25, 12, 34, 56))
                zi2 = zipfile.ZipInfo("repo/sub/b.txt", date_time=(2026, 11, 25, 12, 34, 56))
                zf.writestr(zi1, b"alpha")
                zf.writestr(zi2, b"bravo")

            self.assertNotEqual(hashlib.sha256(z1.read_bytes()).hexdigest(), hashlib.sha256(z2.read_bytes()).hexdigest())
            d1 = eng.safe_extract_zip(z1, tmp_path / "out1")
            d2 = eng.safe_extract_zip(z2, tmp_path / "out2")
            h1 = eng.compute_tree_sha256(d1)
            h2 = eng.compute_tree_sha256(d2)
            self.assertEqual(h1, h2)

            # 1-byte tampering changes tree_sha256
            (d2 / "sub" / "b.txt").write_bytes(b"bravO")
            self.assertNotEqual(h1, eng.compute_tree_sha256(d2))

    def test_safe_extract_zip_2pass_blocks_attacks_with_zero_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Good archive sanity
            good_zip = tmp_path / "good.zip"
            with zipfile.ZipFile(good_zip, "w") as zf:
                zf.writestr("pkg/hello.txt", "xin chao")
            root_out = eng.safe_extract_zip(good_zip, tmp_path / "out_good")
            self.assertEqual((root_out / "hello.txt").read_text(encoding="utf-8"), "xin chao")

            # Attack cases: benign entry FIRST + malicious entry SECOND -> must write 0 files!
            def _assert_blocked(name: str, builder, **kwargs) -> None:
                zpath = tmp_path / f"{name}.zip"
                dest = tmp_path / f"out_{name}"
                with zipfile.ZipFile(zpath, "w") as zf:
                    zf.writestr("pkg/benign.txt", "safe")
                    builder(zf)
                with self.assertRaises(eng.SetupError, msg=f"ZIP case {name} should fail"):
                    eng.safe_extract_zip(zpath, dest, **kwargs)
                self.assertFalse(dest.exists(), f"ZIP case {name} left partial files on disk")

            _assert_blocked("backslash_traversal", lambda zf: zf.writestr("..\\evil.txt", "bad"))
            _assert_blocked("dotdot_traversal", lambda zf: zf.writestr("../escape.txt", "bad"))
            _assert_blocked("reserved_con", lambda zf: zf.writestr("pkg/CON.txt", "bad"))
            _assert_blocked("reserved_nul", lambda zf: zf.writestr("pkg/sub/NUL", "bad"))
            _assert_blocked(
                "case_collision",
                lambda zf: (zf.writestr("pkg/SKILL.md", "A"), zf.writestr("pkg/skill.md", "B")),
            )

            def _add_symlink(zf: zipfile.ZipFile) -> None:
                zi = zipfile.ZipInfo("pkg/link.txt")
                zi.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(zi, "/etc/passwd")

            _assert_blocked("symlink", _add_symlink)
            _assert_blocked("entry_cap", lambda zf: (zf.writestr("pkg/2.txt", "2"), zf.writestr("pkg/3.txt", "3")), max_entries=2)
            _assert_blocked("byte_cap", lambda zf: zf.writestr("pkg/big.bin", b"A" * 64), max_bytes=32)

    def test_safe_extract_tar_2pass_blocks_attacks_with_zero_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def _add_bytes(tf: tarfile.TarFile, name: str, data: bytes) -> None:
                ti = tarfile.TarInfo(name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))

            # Good tarball sanity
            good_tgz = tmp_path / "good.tgz"
            with tarfile.open(good_tgz, "w:gz") as tf:
                _add_bytes(tf, "package/hello.txt", b"xin chao tar")
            pkg_out = eng.safe_extract_tar(good_tgz, tmp_path / "out_good_tar")
            self.assertEqual((pkg_out / "hello.txt").read_text(encoding="utf-8"), "xin chao tar")

            def _assert_tar_blocked(name: str, builder, **kwargs) -> None:
                tpath = tmp_path / f"{name}.tgz"
                dest = tmp_path / f"out_tar_{name}"
                with tarfile.open(tpath, "w:gz") as tf:
                    _add_bytes(tf, "package/benign.txt", b"safe")
                    builder(tf)
                with self.assertRaises(eng.SetupError, msg=f"TAR case {name} should fail"):
                    eng.safe_extract_tar(tpath, dest, **kwargs)
                self.assertFalse(dest.exists(), f"TAR case {name} left partial files on disk")

            _assert_tar_blocked("backslash_traversal", lambda tf: _add_bytes(tf, "..\\evil.txt", b"bad"))
            _assert_tar_blocked("reserved_con", lambda tf: _add_bytes(tf, "package/CON.txt", b"bad"))
            _assert_tar_blocked("reserved_nul", lambda tf: _add_bytes(tf, "package/sub/NUL", b"bad"))
            _assert_tar_blocked(
                "case_collision",
                lambda tf: (_add_bytes(tf, "package/SKILL.md", b"A"), _add_bytes(tf, "package/skill.md", b"B")),
            )

            def _add_tar_symlink(tf: tarfile.TarFile) -> None:
                ti = tarfile.TarInfo("package/link")
                ti.type = tarfile.SYMTYPE
                ti.linkname = "../secret"
                tf.addfile(ti)

            def _add_tar_hardlink(tf: tarfile.TarFile) -> None:
                ti = tarfile.TarInfo("package/hlink")
                ti.type = tarfile.LNKTYPE
                ti.linkname = "package/benign.txt"
                tf.addfile(ti)

            _assert_tar_blocked("symlink", _add_tar_symlink)
            _assert_tar_blocked("hardlink", _add_tar_hardlink)
            _assert_tar_blocked(
                "entry_cap",
                lambda tf: (_add_bytes(tf, "package/2.txt", b"2"), _add_bytes(tf, "package/3.txt", b"3")),
                max_entries=2,
            )
            _assert_tar_blocked("byte_cap", lambda tf: _add_bytes(tf, "package/big.bin", b"B" * 64), max_bytes=32)

    def test_reject_links_allows_onedrive_cloudfiles_and_rejects_symlinks_junctions_and_wci(self) -> None:
        ancestor = Path("C:/MockHome/OneDrive/Documents")
        leaf = ancestor / "Studio AI Setup" / "Chi-Dan" / "guide.md"

        def _fake_stat(is_dir: bool, tag: int = 0, is_symlink_mode: bool = False):
            mode = stat.S_IFLNK if is_symlink_mode else (stat.S_IFDIR if is_dir else stat.S_IFREG)
            attrs = eng.FILE_ATTRIBUTE_REPARSE_POINT if tag != 0 else 0
            return types.SimpleNamespace(st_mode=mode, st_reparse_tag=tag, st_file_attributes=attrs)

        # Allowed OneDrive CloudFiles tags on BOTH ancestors and leaf
        for allowed_tag in (0x9000001A, 0x9000101A, 0x80000021):
            def _lstat_allow(p, t=allowed_tag):
                p_obj = Path(p)
                if p_obj == leaf:
                    return _fake_stat(is_dir=False, tag=t)
                if p_obj == ancestor:
                    return _fake_stat(is_dir=True, tag=t)
                return _fake_stat(is_dir=True, tag=0)

            with mock.patch.object(eng.os, "lstat", side_effect=_lstat_allow):
                eng.reject_links(leaf)  # Must NOT raise

        # Rejected tags on ancestor or leaf: symlink, junction, WCI (0x90001018)
        for bad_tag in (0xA000000C, 0xA0000003, 0x90001018):
            for fail_on_leaf in (False, True):
                def _lstat_deny(p, t=bad_tag, on_leaf=fail_on_leaf):
                    p_obj = Path(p)
                    if on_leaf and p_obj == leaf:
                        return _fake_stat(is_dir=False, tag=t)
                    if (not on_leaf) and p_obj == ancestor:
                        return _fake_stat(is_dir=True, tag=t)
                    return _fake_stat(is_dir=(p_obj != leaf), tag=0)

                with (
                    mock.patch.object(eng.os, "lstat", side_effect=_lstat_deny),
                    self.assertRaises(eng.SetupError, msg=f"Tag 0x{bad_tag:08X} (leaf={fail_on_leaf}) must be rejected"),
                ):
                    eng.reject_links(leaf)


class DoctorVerifyTests(unittest.TestCase):
    def test_collect_verify_checks_all_5_lots_and_distinguishes_ok_not_selected_failed(self) -> None:
        cat = eng.load_catalog(ROOT / "catalog-lock.json")
        egm_entry = cat["lot5_review"]["egm"]
        fake_preflight = {
            "tools": {
                "python": {"installed": True, "version": "3.12.10", "path": "python"},
                "uv": {"installed": True, "version": "0.13.9", "path": "uv"},
                "node": {"installed": True, "supported": True, "version": "24.22.3", "path": "node"},
                "git": {"installed": True, "version": "2.56.1", "path": "git"},
                "gh": {"installed": True, "version": "2.105.0", "path": "gh"},
                "ffmpeg": {"installed": True, "version": "9.1", "path": "ffmpeg"},
                "rea": {"installed": True, "version": "6.10.1", "path": "rea"},
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            (home / "Documents").mkdir(parents=True)
            ag_skills = home / ".gemini" / "config" / "skills"
            ag_plugins = home / ".gemini" / "config" / "plugins"
            ag_rules = home / ".gemini" / "config" / "rules"
            scripts_sub = "Scripts" if os.name == "nt" else "bin"
            ext = ".exe" if os.name == "nt" else ""

            # Populate Lot 3 (with .antigravity-plugin/plugin.json — B3!)
            for bin_name in ("python", "ruff", "pytest"):
                _write_text(app_root / "venvs" / "dev" / scripts_sub / f"{bin_name}{ext}", "bin")
            _write_text(ag_plugins / "superpowers" / ".antigravity-plugin" / "plugin.json", '{"name":"superpowers"}')
            _write_text(ag_plugins / "superpowers" / "skills" / "tdd" / "SKILL.md", "# TDD\n")
            _write_text(ag_skills / "karpathy-guidelines" / "SKILL.md", "# Karpathy\n")
            _write_text(ag_skills / "modern-web-guidance" / "SKILL.md", "# MWG\n")

            # Populate Lot 5 EGM (8 skills, 10 agents, 5 standards, LICENSE, plugin.json)
            egm_dir = ag_plugins / "egm"
            _write_text(egm_dir / "plugin.json", '{"name":"egm"}')
            _write_text(egm_dir / "LICENSE", "Apache-2.0")
            for sk in egm_entry["required_skills"]:
                _write_text(egm_dir / "skills" / sk / "SKILL.md", f"# {sk}\n")
            for i in range(1, 11):
                _write_text(egm_dir / "agents" / f"a{i:02d}.md", f"# A{i}\n")
            for i in range(1, 6):
                _write_text(egm_dir / "resources" / "document_standards" / f"s{i:02d}.md", f"# S{i}\n")

            # Rules & guides + state selecting only lot3 & lot5
            _write_text(ag_rules / "AGENTS.md", "# AGENTS\n")
            _write_text(ag_rules / "GEMINI.md", "# GEMINI\n")
            _write_text(home / "Documents" / "Studio AI Setup" / "Chi-Dan" / "00-BAT-DAU-NHANH.md", "# Guide\n")
            eng.save_state({"schema_version": 2, "app_version": "2.0.0", "installed_lots": ["lot3", "lot5"]}, app_root)

            with mock.patch.object(eng, "collect_preflight", return_value=fake_preflight):
                v1 = eng.collect_verify(cat, home=home, app_root=app_root)

            self.assertTrue(v1["ok"])
            self.assertEqual(v1["lots"]["lot3"]["status"], "ok")
            self.assertEqual(v1["lots"]["lot5"]["status"], "ok")
            self.assertEqual(v1["lots"]["lot5"]["skills_count"], 8)
            self.assertEqual(v1["lots"]["lot5"]["agents_count"], 10)
            self.assertEqual(v1["lots"]["lot5"]["standards_count"], 5)
            self.assertEqual(v1["lots"]["lot1"]["status"], "not_selected")
            self.assertEqual(v1["lots"]["lot2"]["status"], "not_selected")
            self.assertEqual(v1["lots"]["lot4"]["status"], "not_selected")
            self.assertTrue(v1["guides_ready"])
            self.assertTrue(v1["rules_ready"])

            # Mark lot1 as selected without files + break lot5 agent count -> both become 'failed'
            (egm_dir / "agents" / "a10.md").unlink()
            eng.save_state({"schema_version": 2, "app_version": "2.0.0", "installed_lots": ["lot1", "lot3", "lot5"]}, app_root)
            with mock.patch.object(eng, "collect_preflight", return_value=fake_preflight):
                v2 = eng.collect_verify(cat, home=home, app_root=app_root)
            self.assertFalse(v2["ok"])
            self.assertEqual(v2["lots"]["lot1"]["status"], "failed")
            self.assertEqual(v2["lots"]["lot5"]["status"], "failed")
            self.assertEqual(v2["lots"]["lot5"]["agents_count"], 9)


class SnapshotBackupRestoreTests(unittest.TestCase):
    @staticmethod
    def _populate_all_slots(home: Path, app_root: Path) -> dict[str, tuple[Path, bytes]]:
        slot_data: dict[str, tuple[Path, bytes]] = {
            "rules/antigravity/AGENTS.md": (
                home / ".gemini" / "config" / "rules" / "AGENTS.md",
                "# AGENTS — Minh Anh\nQuy tắc riêng.\n".encode(),
            ),
            "rules/antigravity/GEMINI.md": (
                home / ".gemini" / "config" / "rules" / "GEMINI.md",
                "# GEMINI — Kỷ luật sáng tạo.\n".encode(),
            ),
            "rules/claude/studio-ai-agents.md": (
                home / ".claude" / "rules" / "studio-ai-agents.md",
                "# Claude Agents — Minh Anh\n".encode(),
            ),
            "rules/claude/studio-ai-gemini.md": (
                home / ".claude" / "rules" / "studio-ai-gemini.md",
                "# Claude Gemini — Kỷ luật.\n".encode(),
            ),
            "state/state.json": (
                app_root / "state.json",
                (
                    json.dumps(
                        {
                            "schema_version": 2,
                            "app_version": "2.0.0",
                            "user_name": "Minh Anh",
                            "installed_lots": ["lot1", "lot3", "lot5"],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                ).encode("utf-8"),
            ),
        }
        for path, raw in slot_data.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        return slot_data

    def test_create_and_list_snapshots_manifest_hashes_same_second_and_ordering(self) -> None:
        cat = eng.load_catalog(ROOT / "catalog-lock.json")

        class _FixedDateTime:
            current = datetime(2026, 11, 25, 12, 0, 0, tzinfo=eng._UTC)

            @classmethod
            def now(cls, tz=None):
                return cls.current if tz is None else cls.current.astimezone(tz)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            slot_data = self._populate_all_slots(home, app_root)

            with mock.patch.object(eng, "datetime", _FixedDateTime):
                b1 = eng.create_snapshot_backup(cat, home=home, app_root=app_root)
                # Same-second backup must choose a non-colliding filename (-01)
                b2 = eng.create_snapshot_backup(cat, home=home, app_root=app_root)
                # Later-second backup must sort first
                _FixedDateTime.current = datetime(2026, 11, 25, 12, 0, 5, tzinfo=eng._UTC)
                b3 = eng.create_snapshot_backup(cat, home=home, app_root=app_root)

            self.assertTrue(b1["ok"])
            self.assertEqual(b1["action"], "backup")
            self.assertEqual(b1["filename"], "studio-ai-snapshot-20261125T120000Z.zip")
            self.assertEqual(b2["filename"], "studio-ai-snapshot-20261125T120000Z-01.zip")
            self.assertEqual(b3["filename"], "studio-ai-snapshot-20261125T120005Z.zip")
            self.assertNotEqual(b1["snapshot_path"], b2["snapshot_path"])
            self.assertEqual(b1["file_count"], 5)

            snap1_path = Path(b1["snapshot_path"])
            self.assertTrue(snap1_path.is_file())
            self.assertEqual(hashlib.sha256(snap1_path.read_bytes()).hexdigest(), b1["archive_sha256"])

            # Verify manifest.json schema_version == 1 and exact per-entry SHA-256 & payload bytes
            with zipfile.ZipFile(snap1_path, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("manifest.json", names)
                self.assertEqual(names - {"manifest.json"}, set(slot_data.keys()))
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                self.assertEqual(manifest["schema_version"], 1)
                self.assertEqual(manifest["app_name"], "Studio AI Setup")
                self.assertEqual(manifest["app_version"], "2.0.0")
                self.assertEqual(manifest["created_at_utc"], "2026-11-25T12:00:00Z")
                self.assertEqual(manifest["installed_lots"], ["lot1", "lot3", "lot5"])
                self.assertEqual(manifest["user_name"], "Minh Anh")
                self.assertEqual(len(manifest["entries"]), 5)

                for entry in manifest["entries"]:
                    arc = entry["arcname"]
                    _, expected_bytes = slot_data[arc]
                    self.assertEqual(entry["target_slot"], eng.SNAPSHOT_ALLOWED_SLOTS[arc])
                    self.assertEqual(entry["size"], len(expected_bytes))
                    self.assertEqual(entry["sha256"], hashlib.sha256(expected_bytes).hexdigest())
                    self.assertEqual(zf.read(arc), expected_bytes)

            # list_snapshots returns newest-first order across timestamp and same-second suffix
            listed = eng.list_snapshots(app_root=app_root)
            self.assertTrue(listed["ok"])
            self.assertEqual(listed["count"], 3)
            self.assertEqual(
                [item["filename"] for item in listed["snapshots"]],
                [
                    "studio-ai-snapshot-20261125T120005Z.zip",
                    "studio-ai-snapshot-20261125T120000Z-01.zip",
                    "studio-ai-snapshot-20261125T120000Z.zip",
                ],
            )
            self.assertEqual(listed["snapshots"][0]["sha256"], b3["archive_sha256"])
            self.assertEqual(listed["snapshots"][0]["created_at_utc"], "2026-11-25T12:00:05Z")
            self.assertEqual(listed["snapshots"][2]["sha256"], b1["archive_sha256"])
            self.assertEqual(listed["snapshots"][2]["created_at_utc"], "2026-11-25T12:00:00Z")

    def test_restore_snapshot_dry_run_and_live_restore_with_offdir_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            slot_data = self._populate_all_slots(home, app_root)

            created = eng.create_snapshot_backup(home=home, app_root=app_root)
            self.assertEqual(created["file_count"], 5)

            # Mutate all 5 live files on disk
            modified_bytes: dict[str, bytes] = {}
            for arc, (dst, _) in slot_data.items():
                mut = f"MODIFIED::{arc}\n".encode()
                dst.write_bytes(mut)
                modified_bytes[arc] = mut

            # 1. Dry-run verifies SHA-256 while leaving all modified files untouched
            dry_res = eng.restore_snapshot_backup("latest", dry_run=True, home=home, app_root=app_root)
            self.assertTrue(dry_res["ok"])
            self.assertEqual(dry_res["action"], "restore_dry_run")
            self.assertTrue(dry_res["verified"])
            self.assertEqual(sorted(dry_res["would_restore"]), sorted(slot_data.keys()))
            for arc, (dst, _) in slot_data.items():
                self.assertEqual(dst.read_bytes(), modified_bytes[arc])
            self.assertFalse((app_root / "backups").exists())

            # 2. Live restore restores exact original bytes & backs up pre-existing files off-dir
            live_res = eng.restore_snapshot_backup("latest", dry_run=False, home=home, app_root=app_root)
            self.assertTrue(live_res["ok"])
            self.assertEqual(live_res["action"], "restore")
            self.assertTrue(live_res["verified"])
            self.assertEqual(sorted(live_res["restored"]), sorted(slot_data.keys()))

            for dst, orig_bytes in slot_data.values():
                self.assertEqual(dst.read_bytes(), orig_bytes)

            # Pre-restore backups stored strictly under app_root/backups/pre-restore-*
            backup_dir = Path(live_res["backup_dir"])
            self.assertTrue(backup_dir.is_dir())
            self.assertEqual(backup_dir.parent, app_root / "backups")
            self.assertTrue(backup_dir.name.startswith("pre-restore-"))
            for arc, (dst, _) in slot_data.items():
                saved_bak = backup_dir / dst.name
                self.assertTrue(saved_bak.is_file(), f"Expected pre-restore backup for {dst.name}")
                self.assertEqual(saved_bak.read_bytes(), modified_bytes[arc])

            # Zero .bak files inside Antigravity or Claude rules/ directories
            self.assertEqual(list((home / ".gemini" / "config" / "rules").glob("*.bak*")), [])
            self.assertEqual(list((home / ".claude" / "rules").glob("*.bak*")), [])

    def test_restore_snapshot_rejects_tampering_and_security_violations_with_zero_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            home = tmp_path / "home"
            app_root = tmp_path / "app"
            slot_data = self._populate_all_slots(home, app_root)

            base_snap = Path(eng.create_snapshot_backup(home=home, app_root=app_root)["snapshot_path"])
            with zipfile.ZipFile(base_snap, "r") as zf:
                base_entries = {name: zf.read(name) for name in zf.namelist()}

            # Overwrite live files with sentinel content to assert zero writes on rejection
            sentinels: dict[str, bytes] = {}
            for arc, (dst, _) in slot_data.items():
                sentinel = f"SENTINEL-UNTOUCHED::{arc}\n".encode()
                dst.write_bytes(sentinel)
                sentinels[arc] = sentinel

            def _write_crafted_zip(name: str, items: dict[str, bytes]) -> Path:
                zpath = tmp_path / f"bad-{name}.zip"
                with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for member_name, raw in items.items():
                        zf.writestr(member_name, raw)
                return zpath

            # Case 1: 1-byte tampered payload (same byte length so SHA-256 check catches it)
            tampered_items = dict(base_entries)
            orig_agents = bytearray(tampered_items["rules/antigravity/AGENTS.md"])
            orig_agents[0] ^= 0x01
            tampered_items["rules/antigravity/AGENTS.md"] = bytes(orig_agents)
            zip_tampered = _write_crafted_zip("tampered-1byte", tampered_items)

            # Case 2: Extra unlisted file in ZIP
            extra_items = dict(base_entries)
            extra_items["rules/antigravity/unlisted.md"] = b"# sneaky extra file\n"
            zip_extra = _write_crafted_zip("extra-unlisted", extra_items)

            # Case 3: Unknown target_slot in manifest.json
            bad_slot_items = dict(base_entries)
            bad_manifest = json.loads(bad_slot_items["manifest.json"].decode("utf-8"))
            bad_manifest["entries"][0]["target_slot"] = "rogue_slot"
            bad_slot_items["manifest.json"] = json.dumps(bad_manifest).encode("utf-8")
            zip_bad_slot = _write_crafted_zip("unknown-slot", bad_slot_items)

            # Case 4: Zip-Slip traversal member
            zipslip_items = dict(base_entries)
            zipslip_items["../escaped-zipslip.txt"] = b"pwned"
            zip_slip = _write_crafted_zip("zip-slip", zipslip_items)

            for label, bad_zip in (
                ("1-byte tamper", zip_tampered),
                ("extra unlisted file", zip_extra),
                ("unknown target_slot", zip_bad_slot),
                ("Zip-Slip member", zip_slip),
            ):
                with self.assertRaises(eng.SetupError, msg=f"Snapshot case '{label}' must raise SetupError"):
                    eng.restore_snapshot_backup(str(bad_zip), dry_run=False, home=home, app_root=app_root)

                for arc, (dst, _) in slot_data.items():
                    self.assertEqual(
                        dst.read_bytes(),
                        sentinels[arc],
                        f"Snapshot case '{label}' must leave {arc} untouched on disk",
                    )
                self.assertFalse(
                    (app_root / "backups").exists(),
                    f"Snapshot case '{label}' must not create backups/ directory",
                )
                self.assertFalse((tmp_path / "escaped-zipslip.txt").exists())

    def test_snapshot_cli_backup_list_and_restore_dry_run_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            home = tmp_path / "home"
            local_app = tmp_path / "localappdata"
            app_root = local_app / "StudioAISetup"

            agents_path = home / ".gemini" / "config" / "rules" / "AGENTS.md"
            gemini_path = home / ".gemini" / "config" / "rules" / "GEMINI.md"
            state_path = app_root / "state.json"
            _write_text(agents_path, "# AGENTS CLI SMOKE\n")
            _write_text(gemini_path, "# GEMINI CLI SMOKE\n")
            _write_text(state_path, json.dumps({"schema_version": 2, "user_name": "Lan", "installed_lots": ["lot1"]}))

            env = os.environ.copy()
            env["USERPROFILE"] = str(home)
            env["HOME"] = str(home)
            env["LOCALAPPDATA"] = str(local_app)
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "-B", str(ROOT / "engine" / "setup_engine.py"), *args],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    timeout=20,
                    check=False,
                )

            # 1. --backup --json
            r_bk = _run_cli("--backup", "--json")
            self.assertEqual(r_bk.returncode, 0, r_bk.stderr)
            bk_data = json.loads(r_bk.stdout)
            self.assertTrue(bk_data["ok"])
            self.assertEqual(bk_data["action"], "backup")
            self.assertEqual(bk_data["file_count"], 3)
            snap_file = Path(bk_data["snapshot_path"])
            self.assertTrue(snap_file.is_file())
            self.assertEqual(snap_file.parent, app_root / "snapshots")
            self.assertEqual(hashlib.sha256(snap_file.read_bytes()).hexdigest(), bk_data["archive_sha256"])

            # 2. --list-backups --json
            r_list = _run_cli("--list-backups", "--json")
            self.assertEqual(r_list.returncode, 0, r_list.stderr)
            list_data = json.loads(r_list.stdout)
            self.assertTrue(list_data["ok"])
            self.assertEqual(list_data["count"], 1)
            self.assertEqual(list_data["snapshots"][0]["filename"], bk_data["filename"])
            self.assertEqual(list_data["snapshots"][0]["sha256"], bk_data["archive_sha256"])

            # 3. Modify file, then --restore latest --dry-run --json (must verify without overwriting)
            _write_text(agents_path, "# AGENTS MODIFIED\n")
            r_dry = _run_cli("--restore", "latest", "--dry-run", "--json")
            self.assertEqual(r_dry.returncode, 0, r_dry.stderr)
            dry_data = json.loads(r_dry.stdout)
            self.assertTrue(dry_data["ok"])
            self.assertTrue(dry_data["verified"])
            self.assertEqual(dry_data["action"], "restore_dry_run")
            self.assertIn("rules/antigravity/AGENTS.md", dry_data["would_restore"])
            self.assertEqual(agents_path.read_text(encoding="utf-8"), "# AGENTS MODIFIED\n")


class WindowsWpfInstallerTests(unittest.TestCase):
    def test_ps1_files_have_utf8_bom_and_crlf(self) -> None:
        for fname in ("cai-dat.ps1", "hop-thong-bao.ps1", "tai-nen-tang.ps1"):
            raw = (ROOT / "scripts" / fname).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), f"{fname} must start with UTF-8 BOM for PowerShell 5.1")
            self.assertIn(b"\r\n", raw, f"{fname} must use CRLF line endings")

    def test_cai_dat_security_and_v2_controls(self) -> None:
        ps_text = (ROOT / "scripts" / "cai-dat.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("cmd.exe", ps_text.lower())
        self.assertIsNone(re.search(r"(?i)cmd(?:\.exe)?\s+/c", ps_text))
        self.assertIn("function Format-Win32Arg", ps_text)
        self.assertIn("ReadToEndAsync()", ps_text)
        self.assertIn("$el.FooterChao.Visibility = 'Collapsed'", ps_text)

        # Screen 3 snapshot backup controls in XAML & $el (keeping 'Dau' first) + --backup --json wiring
        self.assertIn('x:Name="NutSaoLuu"', ps_text)
        self.assertIn('x:Name="TrangThaiSaoLuu"', ps_text)
        m_names = re.search(r"(?s)@\(\s*('Dau'.*?)\s*\)\s*\|\s*ForEach-Object\s*\{\s*\$el\[\$_\]\s*=\s*\$w\.FindName\(\$_\)", ps_text)
        self.assertIsNotNone(m_names)
        expected_names = re.findall(r"'([^']+)'", m_names.group(1))
        self.assertEqual(expected_names[0], "Dau")
        for ctrl in (
            "KhungCuon",
            "FooterChao",
            "CardLot5",
            "ChkLot5",
            "NhanPhienBan",
            "MoTaLot4",
            "NutSaoLuu",
            "TrangThaiSaoLuu",
        ):
            self.assertIn(ctrl, expected_names)

        m_backup_click = re.search(r"(?s)\$el\.NutSaoLuu\.Add_Click\(\{(.*?)\n\}\)", ps_text)
        self.assertIsNotNone(m_backup_click, "Missing $el.NutSaoLuu.Add_Click handler")
        handler_body = m_backup_click.group(1)
        self.assertIn("'--backup'", handler_body)
        self.assertIn("'--json'", handler_body)
        self.assertIn("ChayLenhAn", handler_body)

        tai_text = (ROOT / "scripts" / "tai-nen-tang.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("--proto-redir", tai_text)
        self.assertIn("536870912", tai_text)
        self.assertIn("65536", tai_text)

    def test_tai_nen_tang_authenticode_definition_and_unsigned_rejection(self) -> None:
        tai_path = ROOT / "scripts" / "tai-nen-tang.ps1"
        tai_text = tai_path.read_text(encoding="utf-8-sig")

        # 1. Static assertions: defines Assert-AuthenticodeValid and enforces it on python_exe & git_exe before Start-Process
        self.assertIn("function Assert-AuthenticodeValid", tai_text)
        self.assertIn("Get-AuthenticodeSignature", tai_text)
        m_guard = re.search(
            r"(?s)if\s*\(\s*\$kind\s+-in\s+@\('python_exe',\s*'git_exe'\)[^\n]*\)\s*\{\s*Assert-AuthenticodeValid\b",
            tai_text,
        )
        self.assertIsNotNone(m_guard, "Assert-AuthenticodeValid must guard python_exe and git_exe downloads")
        sha_idx = tai_text.index("Get-FileHash")
        auth_idx = m_guard.start()
        start_proc_idx = tai_text.index("Start-Process")
        self.assertLess(sha_idx, auth_idx)
        self.assertLess(auth_idx, start_proc_idx)

        # 2. Live PS 5.1 check: Assert-AuthenticodeValid rejects an unsigned temp .exe and deletes it
        ps = shutil.which("powershell.exe")
        if not ps:
            self.skipTest("powershell.exe not available")

        with tempfile.TemporaryDirectory() as tmp:
            unsigned_exe = Path(tmp).resolve() / "unsigned-dummy.exe"
            unsigned_exe.write_bytes(b"MZ" + b"\x00" * 254)
            self.assertTrue(unsigned_exe.is_file())

            tai_ps1 = str(tai_path).replace("'", "''")
            exe_ps = str(unsigned_exe).replace("'", "''")
            ps_script = f"""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{tai_ps1}', [ref]$tokens, [ref]$errs)
if ($errs.Count -gt 0) {{ throw ("AST parse error: " + ($errs | Out-String)) }}
$fns = $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Write-Info', 'Assert-AuthenticodeValid') }}, $true)
if ($fns.Count -ne 2) {{ throw ("Expected 2 functions, found " + $fns.Count) }}
foreach ($fn in $fns) {{
  . ([scriptblock]::Create($fn.Extent.Text))
}}
$rejected = $false
$errText = ''
try {{
  Assert-AuthenticodeValid -FilePath '{exe_ps}' -ToolName 'dummy_unsigned'
}} catch {{
  $rejected = $true
  $errText = $_.Exception.Message
}}
if (-not $rejected) {{ throw 'Assert-AuthenticodeValid unexpectedly accepted unsigned .exe' }}
if ($errText -notmatch 'Authenticode') {{ throw ("Unexpected error message: " + $errText) }}
if (Test-Path -LiteralPath '{exe_ps}') {{ throw 'Assert-AuthenticodeValid failed to delete unsigned temp .exe' }}
Write-Output 'AUTHENTICODE_UNSIGNED_REJECTED_AND_DELETED_OK'
"""
            enc = base64.b64encode(ps_script.encode("utf-16-le")).decode("ascii")
            res = subprocess.run(
                [ps, "-NoProfile", "-EncodedCommand", enc],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"stdout={res.stdout}\nstderr={res.stderr}")
            self.assertIn("AUTHENTICODE_UNSIGNED_REJECTED_AND_DELETED_OK", res.stdout)
            self.assertFalse(unsigned_exe.exists(), "Unsigned temp .exe must be deleted from disk")

    def test_powershell_ast_and_wpf_xaml_parse_and_findname_integrity(self) -> None:
        ps = shutil.which("powershell.exe")
        if not ps:
            self.skipTest("powershell.exe not available")
        cai_dat_ps1 = str(ROOT / "scripts" / "cai-dat.ps1")
        hop_ps1 = str(ROOT / "scripts" / "hop-thong-bao.ps1")
        tai_ps1 = str(ROOT / "scripts" / "tai-nen-tang.ps1")
        ps_text = (ROOT / "scripts" / "cai-dat.ps1").read_text(encoding="utf-8-sig")
        m_names = re.search(r"(?s)@\(\s*('Dau'.*?)\s*\)\s*\|\s*ForEach-Object\s*\{\s*\$el\[\$_\]\s*=\s*\$w\.FindName\(\$_\)", ps_text)
        self.assertIsNotNone(m_names)
        expected_names = re.findall(r"'([^']+)'", m_names.group(1))
        self.assertEqual(expected_names[0], "Dau")
        self.assertGreaterEqual(len(expected_names), 54)
        for ctrl in (
            "KhungCuon",
            "FooterChao",
            "CardLot5",
            "ChkLot5",
            "NhanPhienBan",
            "MoTaLot4",
            "NutSaoLuu",
            "TrangThaiSaoLuu",
        ):
            self.assertIn(ctrl, expected_names)

        names_ps_literal = "@(" + ",".join(f"'{n}'" for n in expected_names) + ")"
        script = f"""
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
foreach ($f in @('{cai_dat_ps1}', '{hop_ps1}', '{tai_ps1}')) {{
  $tokens = $null; $errs = $null
  $null = [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errs)
  if ($errs.Count -gt 0) {{ throw ("AST parse error in " + $f + ": " + ($errs | Out-String)) }}
  if ($f -eq '{tai_ps1}') {{ continue }}
  $raw = [IO.File]::ReadAllText($f, [Text.Encoding]::UTF8)
  $m = [regex]::Match($raw, '(?s)\\$XAML\\s*=\\s*@''\\r?\\n(.*?)\\r?\\n''@')
  if (-not $m.Success) {{ throw ("Missing XAML block in " + $f) }}
  $win = [Windows.Markup.XamlReader]::Parse($m.Groups[1].Value)
  if ($f -eq '{cai_dat_ps1}') {{
    foreach ($n in {names_ps_literal}) {{
      if ($null -eq $win.FindName($n)) {{ throw ("Missing x:Name in XAML: " + $n) }}
    }}
    if ($win.FindName('TrangThaiSaoLuu').Visibility -ne [Windows.Visibility]::Collapsed) {{
      throw 'TrangThaiSaoLuu must start Collapsed'
    }}
    $scroll = $win.FindName('KhungCuon')
    $footer = $win.FindName('FooterChao')
    $cur = $footer.Parent
    while ($null -ne $cur) {{
      if ([object]::ReferenceEquals($cur, $scroll)) {{ throw 'FooterChao must be outside KhungCuon ScrollViewer' }}
      $cur = $cur.Parent
    }}
  }}
}}
Write-Output "AST_AND_XAML_OK"
"""
        enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        res = subprocess.run([ps, "-NoProfile", "-STA", "-EncodedCommand", enc], capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("AST_AND_XAML_OK", res.stdout)


class ReleaseSanitizerTests(unittest.TestCase):
    def test_build_release_produces_deterministic_clean_zip_and_sha256sums(self) -> None:
        self.assertEqual(BUILD_MOD.APP_VERSION, "2.0.0")
        self.assertEqual(BUILD_MOD.RELEASE_NAME, "Studio-AI-Setup-v2.0.0")
        self.assertEqual(len(BUILD_MOD.ALLOWLIST_FILES), 20)
        self.assertIn("chi-dan/05-lo-phan-bien-egm.md", BUILD_MOD.ALLOWLIST_FILES)
        self.assertNotIn("test-in-windows-sandbox.wsb", BUILD_MOD.ALLOWLIST_FILES)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir_1 = Path(tmp) / "dist1"
            out_dir_2 = Path(tmp) / "dist2"
            self.assertEqual(BUILD_MOD.main(["--out-dir", str(out_dir_1)]), 0)
            self.assertEqual(BUILD_MOD.main(["--out-dir", str(out_dir_2)]), 0)

            zip_1 = out_dir_1 / f"{BUILD_MOD.RELEASE_NAME}.zip"
            zip_2 = out_dir_2 / f"{BUILD_MOD.RELEASE_NAME}.zip"
            audit_file = out_dir_1 / "SECURITY-AUDIT.md"
            sums_file = out_dir_1 / "SHA256SUMS.txt"

            self.assertTrue(zip_1.is_file())
            self.assertTrue(zip_2.is_file())
            self.assertLess(zip_1.stat().st_size, BUILD_MOD.MAX_ZIP_BYTES)
            self.assertIn("VERDICT:** **PASS (0 CRITICAL)**", audit_file.read_text(encoding="utf-8"))

            # Byte-for-byte deterministic reproducible ZIP across consecutive builds
            raw_1 = zip_1.read_bytes()
            raw_2 = zip_2.read_bytes()
            self.assertEqual(raw_1, raw_2)
            sha_1 = hashlib.sha256(raw_1).hexdigest()
            sha_2 = hashlib.sha256(raw_2).hexdigest()
            self.assertEqual(sha_1, sha_2)

            # SHA256SUMS.txt format (UTF-8 LF) and hash match
            sums_raw = sums_file.read_bytes()
            self.assertNotIn(b"\r\n", sums_raw)
            self.assertEqual(sums_raw.decode("utf-8"), f"{sha_1}  {zip_1.name}\n")

    def test_version_parity_catches_drift_and_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src_root = Path(tmp) / "repo"
            for rel in (*BUILD_MOD.ALLOWLIST_FILES, "test-in-windows-sandbox.wsb"):
                dst = src_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, dst)

            self.assertEqual(BUILD_MOD.check_version_parity(src_root, "2.0.0"), [])

            # 1. Drift in README.md blocks build
            readme = src_root / "README.md"
            orig_readme = readme.read_text(encoding="utf-8")
            readme.write_text(orig_readme.replace("# Studio AI Setup v2.0.0", "# Studio AI Setup v1.0.0", 1), encoding="utf-8")
            findings = BUILD_MOD.check_version_parity(src_root, "2.0.0")
            self.assertTrue(any(f["file"] == "README.md" and f["severity"] == "CRITICAL" for f in findings))

            out_drift = Path(tmp) / "dist_drift"
            self.assertEqual(BUILD_MOD.main(["--src-root", str(src_root), "--out-dir", str(out_drift)]), 1)
            self.assertFalse((out_drift / "Studio-AI-Setup-v2.0.0.zip").exists())
            self.assertFalse((out_drift / "SHA256SUMS.txt").exists())

            # 2. Restore README, drift in test-in-windows-sandbox.wsb blocks build
            readme.write_text(orig_readme, encoding="utf-8")
            wsb = src_root / "test-in-windows-sandbox.wsb"
            wsb.write_text(wsb.read_text(encoding="utf-8").replace("v2.0.0", "v1.0.0"), encoding="utf-8")
            findings_wsb = BUILD_MOD.check_version_parity(src_root, "2.0.0")
            self.assertTrue(any(f["file"] == "test-in-windows-sandbox.wsb" and f["severity"] == "CRITICAL" for f in findings_wsb))

            out_wsb = Path(tmp) / "dist_wsb"
            self.assertEqual(BUILD_MOD.main(["--src-root", str(src_root), "--out-dir", str(out_wsb)]), 1)
            self.assertFalse((out_wsb / "Studio-AI-Setup-v2.0.0.zip").exists())

            # 3. Wrong expected_version flags catalog-lock.json too
            findings_cat = BUILD_MOD.check_version_parity(src_root, "9.9.9")
            flagged_files = {f["file"] for f in findings_cat}
            self.assertEqual(flagged_files, {"catalog-lock.json", "README.md", "test-in-windows-sandbox.wsb"})

    def test_audit_catches_planted_secret_path_and_brand_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / "leak.py").write_text(
                'AWS = "AKIAIOSFODNN7EXAMPLE"\n'
                'PATH_LEAK = r"C:\\Users\\Alice\\secrets"\n'
                'BRAND = "Go" + "ha"\n',
                encoding="utf-8",
            )
            (stage / "secret.ps1").write_text(
                'Invoke-Expression $x\n'
                '$brand = "goha"\n',
                encoding="utf-8",
            )
            report = BUILD_MOD.audit_directory(stage)
            self.assertEqual(report["verdict"], "FAIL")
            cats = {f["category"] for f in report["findings"]}
            self.assertIn("AWS Access Key", cats)
            self.assertIn("Hardcoded Windows user path", cats)
            self.assertIn("Brand leak", cats)
            self.assertIn("Invoke-Expression / iex", cats)


if __name__ == "__main__":
    unittest.main()
