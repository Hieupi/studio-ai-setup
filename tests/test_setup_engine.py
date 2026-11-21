"""Regression and security tests for Studio AI Setup v1.0.0."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import setup_engine as eng  # noqa: E402


def _load_build_release():
    spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts" / "build-release.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BUILD_MOD = _load_build_release()


class CatalogLockTests(unittest.TestCase):
    def test_catalog_pins_all_lots_and_defaults_optional_heavy_tools_off(self) -> None:
        cat = eng.load_catalog(ROOT / "catalog-lock.json")
        self.assertEqual(cat["schema_version"], 1)
        self.assertEqual(cat["app_name"], "Studio AI Setup")
        for key in ("lot0_core", "lot1_content", "lot2_video", "lot3_code", "lot4_data"):
            self.assertIn(key, cat)
        self.assertEqual(cat["lot3_code"]["modern_web_guidance"]["npm_spec"], "modern-web-guidance@1.0.1")
        self.assertEqual(cat["lot4_data"]["rea_agents"]["version"], "6.10.1")
        self.assertFalse(cat["lot2_video"]["optional_openmontage"]["default_enabled"])
        self.assertFalse(cat["lot2_video"]["optional_assetfurnace"]["default_enabled"])
        self.assertFalse(cat["lot4_data"]["optional_agent_reach"]["default_enabled"])
        direct_entries = [cat["lot0_core"][k] for k in ("python", "uv", "node", "git", "gh")] + [cat["lot2_video"]["ffmpeg"]]
        for entry in direct_entries:
            self.assertTrue(entry["direct_url"].startswith("https://"))
            self.assertRegex(entry["direct_sha256"], r"^[0-9a-f]{64}$")
        raw_text = (ROOT / "catalog-lock.json").read_text(encoding="utf-8")
        self.assertNotIn("@latest", raw_text)


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

    def test_render_rules_preserves_local_first_and_modern_web_guidance(self) -> None:
        rendered = eng.render_rules("Anh Nam")
        self.assertIn("Anh Nam", rendered["AGENTS.md"])
        self.assertNotIn("{{USER_NAME}}", rendered["AGENTS.md"])
        self.assertIn("CLAUDE.md", rendered["AGENTS.md"])
        self.assertIn("modern-web-guidance", rendered["AGENTS.md"])
        self.assertIn("Think Before Coding", rendered["GEMINI.md"])

    def test_safe_extract_zip_blocks_zip_slip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            good_zip = tmp_path / "good.zip"
            with zipfile.ZipFile(good_zip, "w") as zf:
                zf.writestr("pkg/hello.txt", "xin chao")
            root_out = eng.safe_extract_zip(good_zip, tmp_path / "out_good")
            self.assertEqual((root_out / "hello.txt").read_text(encoding="utf-8"), "xin chao")

            evil_zip = tmp_path / "evil.zip"
            with zipfile.ZipFile(evil_zip, "w") as zf:
                zf.writestr("../escape.txt", "bad")
            with self.assertRaises(eng.SetupError):
                eng.safe_extract_zip(evil_zip, tmp_path / "out_evil")

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
                p = vh_src / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("demo", encoding="utf-8")

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
                p = ea_src / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("demo", encoding="utf-8")
            eng.deploy_editatlas_from_tree(ea_src, [skill_target])
            self.assertTrue((skill_target / "sound-design" / "SKILL.md").is_file())
            self.assertTrue((skill_target / "media-picker" / "SKILL.md").is_file())
            self.assertFalse((skill_target / "sound-design" / "evals").exists())
            self.assertFalse((skill_target / "video-breakdown").exists())
            self.assertFalse((skill_target / "editable-export").exists())

            # 3. Mock modern-web-guidance tarball tree
            mwg_src = tmp_path / "mwg_src"
            (mwg_src / "skills" / "modern-web-guidance").mkdir(parents=True, exist_ok=True)
            (mwg_src / "skills" / "modern-web-guidance" / "SKILL.md").write_text("---\nname: modern-web-guidance\n---\n", encoding="utf-8")
            (mwg_src / "skills" / "modern-web-guidance" / "modern-web.mjs").write_text("console.log('ok');\n", encoding="utf-8")
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
        for key in ("os", "arch", "is_64bit", "nvidia_gpu", "tools", "ides"):
            self.assertIn(key, data)


class WindowsWpfInstallerTests(unittest.TestCase):
    def test_ps1_files_have_utf8_bom_and_crlf(self) -> None:
        for fname in ("cai-dat.ps1", "hop-thong-bao.ps1", "tai-nen-tang.ps1"):
            raw = (ROOT / "scripts" / fname).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), f"{fname} must start with UTF-8 BOM for PowerShell 5.1")
            self.assertIn(b"\r\n", raw, f"{fname} must use CRLF line endings")

    def test_powershell_ast_and_wpf_xaml_parse_and_findname_integrity(self) -> None:
        ps = shutil.which("powershell.exe")
        if not ps:
            self.skipTest("powershell.exe not available")
        cai_dat_ps1 = str(ROOT / "scripts" / "cai-dat.ps1")
        hop_ps1 = str(ROOT / "scripts" / "hop-thong-bao.ps1")
        tai_ps1 = str(ROOT / "scripts" / "tai-nen-tang.ps1")
        # Extract expected element names from FindName array in cai-dat.ps1
        ps_text = (ROOT / "scripts" / "cai-dat.ps1").read_text(encoding="utf-8-sig")
        m_names = re.search(r"(?s)@\(\s*('Dau'.*?)\s*\)\s*\|\s*ForEach-Object\s*\{\s*\$el\[\$_\]\s*=\s*\$w\.FindName\(\$_\)", ps_text)
        self.assertIsNotNone(m_names)
        expected_names = re.findall(r"'([^']+)'", m_names.group(1))
        self.assertGreaterEqual(len(expected_names), 40)
        self.assertIn("KhungCuon", expected_names)

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
  }}
}}
Write-Output "AST_AND_XAML_OK"
"""
        enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        res = subprocess.run([ps, "-NoProfile", "-STA", "-EncodedCommand", enc], capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, f"stdout={res.stdout}\nstderr={res.stderr}")
        self.assertIn("AST_AND_XAML_OK", res.stdout)


class ReleaseSanitizerTests(unittest.TestCase):
    def test_build_release_produces_clean_zip_and_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "dist"
            code = BUILD_MOD.main(["--out-dir", str(out_dir)])
            self.assertEqual(code, 0)
            zip_file = out_dir / f"{BUILD_MOD.RELEASE_NAME}.zip"
            audit_file = out_dir / "SECURITY-AUDIT.md"
            self.assertTrue(zip_file.is_file())
            self.assertLess(zip_file.stat().st_size, BUILD_MOD.MAX_ZIP_BYTES)
            self.assertIn("VERDICT:** **PASS (0 CRITICAL)**", audit_file.read_text(encoding="utf-8"))

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
