#!/usr/bin/env python3
"""Studio AI Setup — Clean, modular environment bootstrapper engine for Creators.

Supports preflight hardware/tool detection, 4-Lot isolated installation,
rule/skill deployment with backup and atomic writes, verification, and a
plain-Vietnamese CLI fallback when WPF GUI is unavailable.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
import zipfile
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog-lock.json"
RULES_TEMPLATES_DIR = ROOT / "templates" / "rules"
GUIDES_DIR = ROOT / "chi-dan"

Runner = Callable[..., subprocess.CompletedProcess[str]]


class SetupError(RuntimeError):
    """Controlled failure raised during verification or installation."""


def configure_stdio_utf8() -> None:
    """Ensure UTF-8 console output on Windows when supported."""
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except OSError:
                pass


def load_catalog(catalog_path: Path = CATALOG_PATH) -> dict[str, Any]:
    """Load and validate catalog-lock.json."""
    if not catalog_path.is_file():
        raise SetupError(f"Thiếu tệp catalog-lock.json tại {catalog_path}")
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SetupError(f"Tệp catalog-lock.json không hợp lệ: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SetupError("Phiên bản schema trong catalog-lock.json không được hỗ trợ.")
    return data


def reject_links(path: Path) -> None:
    """Reject symlinks, Windows reparse points, and non-directory ancestors."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        except NotADirectoryError as exc:
            raise SetupError(f"Đường dẫn chứa thành phần không phải thư mục: {part}") from exc
        reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(info.st_mode) or reparse:
            raise SetupError(f"Từ chối đường dẫn liên kết (symlink/reparse): {part}")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise SetupError(f"Thành phần cha không phải thư mục: {part}")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes atomically using a temporary staged file + fsync + os.replace."""
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        with open(staged, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(staged, path)
    finally:
        if staged.exists():
            staged.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text atomically."""
    atomic_write_bytes(path, text.encode("utf-8"))


def backup_file(path: Path) -> Path | None:
    """Create a timestamped .bak-studio-ai backup before overwriting an existing file."""
    if not path.is_file():
        return None
    reject_links(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_name(f"{path.name}.bak-studio-ai-{stamp}")
    if bak.exists():
        bak = path.with_name(f"{path.name}.bak-studio-ai-{stamp}-{uuid.uuid4().hex[:6]}")
    atomic_write_bytes(bak, path.read_bytes())
    return bak


def sanitize_user_name(raw: str | None) -> str:
    """Normalize display name cleanly, stripping control characters and bounding length."""
    if not raw or not isinstance(raw, str):
        return "bạn"
    cleaned = "".join(ch for ch in raw if ord(ch) >= 32 and ch not in "<>{}$`\\\"")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "bạn"
    return cleaned[:48]


def get_data_root() -> Path:
    """Return per-user isolated runtime data root under LocalAppData."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local)
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"
    return base / "StudioAISetup"


def get_documents_dir() -> Path:
    """Resolve the user's Documents directory."""
    home = Path.home()
    docs = home / "Documents"
    return docs if docs.is_dir() else home


def node_supported(version: str) -> bool:
    """Validate Node.js against ^22.23.4 || ^24.22.1 || >=26.12.1."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        return False
    major, minor, patch = map(int, match.groups())
    return (
        (major == 22 and (minor, patch) >= (23, 4))
        or (major == 24 and (minor, patch) >= (22, 1))
        or (major == 26 and (minor, patch) >= (12, 1))
        or major > 26
    )


def _run_quick(argv: list[str], timeout: int = 12) -> tuple[int, str, str]:
    try:
        res = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


def _probe_python() -> dict[str, Any]:
    candidates: list[str] = []
    which_py = shutil.which("python")
    if which_py:
        candidates.append(which_py)
    if sys.executable:
        candidates.append(sys.executable)
    for exe in dict.fromkeys(candidates):
        code, out, _ = _run_quick([exe, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"], timeout=8)
        if code == 0 and re.match(r"^\d+\.\d+\.\d+$", out):
            parts = tuple(int(x) for x in out.split(".")[:3])
            if parts >= (3, 10, 0):
                return {"installed": True, "version": out, "path": exe}
    return {"installed": False, "version": None, "path": None}


def _probe_node() -> dict[str, Any]:
    candidates: list[str] = []
    local_node = get_data_root() / "runtime" / "node" / ("node.exe" if os.name == "nt" else "node")
    if local_node.is_file():
        candidates.append(str(local_node))
    node_exe = shutil.which("node")
    if node_exe:
        candidates.append(node_exe)
    if os.name == "nt":
        for base in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"):
            if base and (Path(base) / "nodejs" / "node.exe").is_file():
                candidates.append(str(Path(base) / "nodejs" / "node.exe"))
    last_ver: str | None = None
    last_exe: str | None = None
    for exe in dict.fromkeys(candidates):
        code, out, _ = _run_quick([exe, "--version"], timeout=8)
        if code != 0 or not out:
            continue
        ver = out.lstrip("v")
        last_ver = ver
        last_exe = exe
        if node_supported(ver):
            return {"installed": True, "supported": True, "version": ver, "path": exe}
    if last_exe:
        return {"installed": True, "supported": False, "version": last_ver, "path": last_exe}
    return {"installed": False, "supported": False, "version": None, "path": None}


def _probe_simple_tool(cmd: str, args: list[str] | None = None, *, venv_name: str | None = None) -> dict[str, Any]:
    candidates: list[str] = []
    data_root = get_data_root()
    ext = ".exe" if os.name == "nt" else ""
    if venv_name:
        scripts_dir = data_root / "venvs" / venv_name / ("Scripts" if os.name == "nt" else "bin")
        venv_bin = scripts_dir / f"{cmd}{ext}"
        if venv_bin.is_file():
            candidates.append(str(venv_bin))
    local_bin = data_root / "bin" / f"{cmd}{ext}"
    if local_bin.is_file():
        candidates.append(str(local_bin))
    if cmd == "git" and os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            git_user = Path(local_app) / "Programs" / "Git" / "cmd" / "git.exe"
            if git_user.is_file():
                candidates.append(str(git_user))
    npm_prefix = os.environ.get("NPM_CONFIG_PREFIX")
    if npm_prefix:
        prefix_path = Path(npm_prefix)
        for cand in (prefix_path / f"{cmd}.cmd", prefix_path / cmd, prefix_path / "bin" / cmd):
            if cand.is_file():
                candidates.append(str(cand))
    else:
        runtime_node = data_root / "runtime" / "node"
        for cand in (runtime_node / f"{cmd}.cmd", runtime_node / cmd):
            if cand.is_file():
                candidates.append(str(cand))
        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_global = Path(appdata) / "npm"
            for cand in (npm_global / f"{cmd}.cmd", npm_global / cmd):
                if cand.is_file():
                    candidates.append(str(cand))
    found = shutil.which(cmd)
    if found:
        candidates.append(found)
    for exe in dict.fromkeys(candidates):
        code, out, err = _run_quick([exe, *(args or ["--version"])], timeout=10)
        text = out or err
        if code == 0 and text:
            first_line = text.splitlines()[0].strip()
            return {"installed": True, "version": first_line[:80], "path": exe}
        if Path(exe).is_file():
            return {"installed": True, "version": "installed", "path": exe}
    return {"installed": False, "version": None, "path": None}


def _probe_ram_gb() -> float | None:
    if os.name != "nt":
        return None
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat_obj = MEMORYSTATUSEX()
        stat_obj.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat_obj)):
            return round(stat_obj.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        pass
    return None


def _probe_nvidia_gpu() -> dict[str, Any]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"present": False, "name": None, "compute_cap": None, "supports_3d": False}
    code, out, _ = _run_quick([smi, "--query-gpu=name,compute_cap", "--format=csv,noheader"], timeout=8)
    if code != 0 or not out:
        return {"present": False, "name": None, "compute_cap": None, "supports_3d": False}
    line = out.splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    name = parts[0] if parts else "NVIDIA GPU"
    cap = parts[1] if len(parts) > 1 else ""
    supports_3d = False
    try:
        if cap and float(cap) >= 7.5:
            supports_3d = True
    except ValueError:
        pass
    return {"present": True, "name": name, "compute_cap": cap or None, "supports_3d": supports_3d}


def detect_ides(home: Path | None = None) -> dict[str, dict[str, Any]]:
    """Detect installed AI assistants on this machine without touching unrelated apps."""
    base = home or Path.home()
    appdata = Path(os.environ.get("APPDATA", str(base / "AppData" / "Roaming")))
    antigravity_root = base / ".gemini" / "config"
    ag_present = (base / ".gemini").is_dir() or (base / ".antigravity").is_dir()
    claude_dir = base / ".claude"
    claude_present = claude_dir.is_dir() or bool(shutil.which("claude"))
    codex_dir = base / ".codex"
    codex_present = codex_dir.is_dir() or bool(shutil.which("codex"))
    vscode_dir = appdata / "Code"
    vscode_present = vscode_dir.is_dir() or bool(shutil.which("code"))

    return {
        "antigravity": {
            "detected": ag_present,
            "label": "Antigravity",
            "skills_dir": str(antigravity_root / "skills"),
            "rules_dir": str(antigravity_root / "rules"),
            "rea_client": "antigravity",
        },
        "claude_code": {
            "detected": claude_present,
            "label": "Claude Code",
            "skills_dir": str(claude_dir / "skills"),
            "rules_dir": str(claude_dir / "rules"),
            "rea_client": "claude_code",
        },
        "codex": {
            "detected": codex_present,
            "label": "Codex",
            "skills_dir": str(codex_dir / "skills"),
            "rules_dir": str(codex_dir),
            "rea_client": "codex",
        },
        "vscode": {
            "detected": vscode_present,
            "label": "VS Code",
            "skills_dir": str(base / ".agents" / "skills"),
            "rules_dir": None,
            "rea_client": "vscode",
        },
    }


def collect_preflight() -> dict[str, Any]:
    """Read-only machine hardware, tool, and IDE detection snapshot."""
    is_64bit = platform.machine().lower() in ("amd64", "x86_64", "arm64", "aarch64") or (sys.maxsize > 2**32)
    try:
        disk = shutil.disk_usage(str(get_data_root().drive + "\\") if os.name == "nt" and get_data_root().drive else "/")
        free_gb = round(disk.free / (1024 ** 3), 1)
    except OSError:
        free_gb = None

    gh_info = _probe_simple_tool("gh", ["--version"])
    gh_logged_in = False
    if gh_info["installed"]:
        c, _, _ = _run_quick([gh_info["path"], "auth", "status"], timeout=8)
        gh_logged_in = (c == 0)
    gh_info["logged_in"] = gh_logged_in

    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "is_64bit": is_64bit,
        "ram_gb": _probe_ram_gb(),
        "free_disk_gb": free_gb,
        "nvidia_gpu": _probe_nvidia_gpu(),
        "tools": {
            "python": _probe_python(),
            "uv": _probe_simple_tool("uv", ["--version"]),
            "node": _probe_node(),
            "git": _probe_simple_tool("git", ["--version"]),
            "gh": gh_info,
            "ffmpeg": _probe_simple_tool("ffmpeg", ["-version"]),
            "ffprobe": _probe_simple_tool("ffprobe", ["-version"]),
            "auto_editor": _probe_simple_tool("auto-editor", ["--version"], venv_name="media"),
            "rea_video": _probe_simple_tool("rea-video", ["--help"], venv_name="media"),
            "yt_dlp": _probe_simple_tool("yt-dlp", ["--version"], venv_name="data"),
            "markitdown": _probe_simple_tool("markitdown", ["--version"], venv_name="data"),
            "rea": _probe_simple_tool("rea", ["--version"]),
            "ruff": _probe_simple_tool("ruff", ["--version"], venv_name="dev"),
            "pytest": _probe_simple_tool("pytest", ["--version"], venv_name="dev"),
        },
        "ides": detect_ides(),
    }


def download_bytes(url: str, timeout: int = 120) -> bytes:
    """Download bytes over HTTPS only with explicit User-Agent."""
    if not url.startswith("https://"):
        raise SetupError(f"Chỉ cho phép tải từ địa chỉ HTTPS an toàn: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "StudioAISetup/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except OSError as exc:
        raise SetupError(f"Không tải được dữ liệu từ {url}: {exc}") from exc


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Safely extract ZIP archive while blocking Zip-Slip path traversal and symlinks."""
    dest_resolved = dest_dir.resolve()
    dest_resolved.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            mode = (member.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode):
                raise SetupError(f"Từ chối liên kết symlink bên trong file nén: {member.filename}")
            rel = Path(member.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise SetupError(f"Đường dẫn không an toàn trong file nén: {member.filename}")
            target = (dest_resolved / rel).resolve()
            if target != dest_resolved and dest_resolved not in target.parents:
                raise SetupError(f"Phát hiện thoát thư mục trong file nén: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    subdirs = [p for p in dest_resolved.iterdir() if p.is_dir()]
    return subdirs[0] if len(subdirs) == 1 else dest_resolved


def safe_extract_tar(tgz_path: Path, dest_dir: Path) -> Path:
    """Safely extract .tgz/.tar.gz archive while blocking traversal and symlinks."""
    dest_resolved = dest_dir.resolve()
    dest_resolved.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tgz_path, "r:gz") as tf:
        for member in tf.getmembers():
            if member.issym() or member.islnk():
                raise SetupError(f"Từ chối liên kết symlink bên trong gói tar: {member.name}")
            rel = Path(member.name)
            if rel.is_absolute() or ".." in rel.parts:
                raise SetupError(f"Đường dẫn không an toàn trong gói tar: {member.name}")
            target = (dest_resolved / rel).resolve()
            if target != dest_resolved and dest_resolved not in target.parents:
                raise SetupError(f"Phát hiện thoát thư mục trong gói tar: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tf.extractfile(member)
                if extracted is not None:
                    with extracted, open(target, "wb") as dst:
                        shutil.copyfileobj(extracted, dst)
    pkg_dir = dest_resolved / "package"
    return pkg_dir if pkg_dir.is_dir() else dest_resolved


def _copy_tree_filtered(src: Path, dst: Path, *, exclude_dirs: set[str] | None = None) -> int:
    """Copy directory tree atomically file-by-file, rejecting symlinks and excluded dirs."""
    excludes = exclude_dirs or set()
    copied = 0
    for item in src.rglob("*"):
        if any(part in excludes for part in item.relative_to(src).parts):
            continue
        if item.is_symlink():
            continue
        if item.is_file():
            rel = item.relative_to(src)
            target = dst / rel
            atomic_write_bytes(target, item.read_bytes())
            copied += 1
    return copied


def render_rules(user_name: str, templates_dir: Path = RULES_TEMPLATES_DIR) -> dict[str, str]:
    """Render AGENTS.md and GEMINI.md templates with sanitized user display name."""
    safe_name = sanitize_user_name(user_name)
    rendered: dict[str, str] = {}
    for fname in ("AGENTS.md", "GEMINI.md"):
        src = templates_dir / fname
        if not src.is_file():
            raise SetupError(f"Thiếu tệp mẫu quy tắc: {src}")
        text = src.read_text(encoding="utf-8")
        rendered[fname] = text.replace("{{USER_NAME}}", safe_name)
    return rendered


def deploy_vietnamese_humanizer_from_tree(
    extracted_root: Path,
    tools_dest: Path,
    skill_targets: list[Path],
) -> dict[str, Any]:
    """Strictly deploy ONLY allowed skills (humanizer-vi, translationese-cleaner-vi) and clean CLI."""
    allowed_skills = ("humanizer-vi", "translationese-cleaner-vi")
    forbidden_names = ("impeccable", "web")
    skills_src = extracted_root / "skills"
    if not skills_src.is_dir():
        raise SetupError(f"Không thấy thư mục skills/ trong nguồn vietnamese-humanizer: {extracted_root}")

    deployed_skills: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        for skill_name in allowed_skills:
            src_skill = skills_src / skill_name
            if not src_skill.is_dir():
                raise SetupError(f"Thiếu skill {skill_name} trong nguồn vietnamese-humanizer.")
            _copy_tree_filtered(src_skill, target_root / skill_name, exclude_dirs={"__pycache__"})
            deployed_skills.append(str(target_root / skill_name))
        for bad in forbidden_names:
            if (target_root / bad).exists():
                raise SetupError(f"Vi phạm bộ lọc bảo mật: phát hiện thành phần bị cấm {bad} tại {target_root}")

    # Copy only clean package files needed by `viet-writing-lint` CLI (excluding .agents, .impeccable, web)
    if tools_dest.exists():
        shutil.rmtree(tools_dest)
    tools_dest.mkdir(parents=True, exist_ok=True)
    copied_cli_files = 0
    for file_name in ("pyproject.toml", "LICENSE", "README.md"):
        f = extracted_root / file_name
        if f.is_file():
            atomic_write_bytes(tools_dest / file_name, f.read_bytes())
            copied_cli_files += 1
    for dir_name in ("src", "patterns", "examples", "benchmarks"):
        d = extracted_root / dir_name
        if d.is_dir():
            copied_cli_files += _copy_tree_filtered(d, tools_dest / dir_name, exclude_dirs={"__pycache__"})
    for skill_name in allowed_skills:
        d = skills_src / skill_name
        if d.is_dir():
            copied_cli_files += _copy_tree_filtered(d, tools_dest / "skills" / skill_name, exclude_dirs={"__pycache__"})
    for bad in (".agents", ".impeccable", "web"):
        if (tools_dest / bad).exists():
            raise SetupError(f"Vi phạm bộ lọc bảo mật: phát hiện {bad} trong {tools_dest}")

    return {"skills": deployed_skills, "cli_files": copied_cli_files, "tools_dest": str(tools_dest)}


def deploy_editatlas_from_tree(extracted_root: Path, skill_targets: list[Path]) -> list[str]:
    """Strictly deploy ONLY sound-design and media-picker skills (skip evals/ and other skills)."""
    allowed = ("sound-design", "media-picker")
    forbidden = ("evals", "video-breakdown", "editable-export", "transcribe")
    skills_src = extracted_root / "skills"
    if not skills_src.is_dir():
        skills_src = extracted_root
    deployed: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        for skill_name in allowed:
            src_dir = skills_src / skill_name
            if not src_dir.is_dir():
                raise SetupError(f"Thiếu kỹ năng {skill_name} trong EditAtlas/skills.")
            _copy_tree_filtered(src_dir, target_root / skill_name, exclude_dirs={"evals", "__pycache__"})
            deployed.append(str(target_root / skill_name))
        for bad in forbidden:
            if (target_root / bad).exists() or any((target_root / s / bad).exists() for s in allowed):
                raise SetupError(f"Vi phạm bộ lọc bảo mật EditAtlas: {bad}")
    return deployed


def deploy_ffmpeg_skill_from_tree(package_root: Path, skill_targets: list[Path]) -> list[str]:
    """Deploy ffmpeg-skill cleanly without invoking untrusted postinstall scripts."""
    if not (package_root / "SKILL.md").is_file():
        raise SetupError(f"Gói ffmpeg-skill không chứa SKILL.md tại {package_root}")
    deployed: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        dest = target_root / "ffmpeg-skill"
        _copy_tree_filtered(package_root, dest, exclude_dirs={"node_modules", "__pycache__", ".git", "tests", "demos"})
        deployed.append(str(dest))
    return deployed


def deploy_modern_web_guidance_from_tree(package_root: Path, skill_targets: list[Path]) -> list[str]:
    """Deploy modern-web-guidance skill cleanly from an extracted npm tarball."""
    skill_src = package_root / "skills" / "modern-web-guidance"
    if not (skill_src / "SKILL.md").is_file():
        raise SetupError(f"Gói modern-web-guidance không chứa skills/modern-web-guidance/SKILL.md tại {package_root}")
    deployed: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        dest = target_root / "modern-web-guidance"
        _copy_tree_filtered(skill_src, dest, exclude_dirs={"node_modules", "__pycache__", ".git"})
        deployed.append(str(dest))
    return deployed


def deploy_rea_video_from_tree(extracted_root: Path, tools_dest: Path, skill_targets: list[Path]) -> dict[str, Any]:
    """Copy rea-video source into isolated tools dir and copy SKILL.md into AI skill dirs."""
    if tools_dest.exists():
        shutil.rmtree(tools_dest)
    copied = _copy_tree_filtered(extracted_root, tools_dest, exclude_dirs={".git", "__pycache__"})
    skill_src = extracted_root / "skills" / "rea-video"
    if not skill_src.is_dir():
        raise SetupError(f"Thiếu skills/rea-video trong gói rea-video: {extracted_root}")
    deployed: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        _copy_tree_filtered(skill_src, target_root / "rea-video", exclude_dirs={"__pycache__"})
        deployed.append(str(target_root / "rea-video"))
    return {"tools_dest": str(tools_dest), "copied_files": copied, "skills": deployed}


def deploy_superpowers_from_tree(
    extracted_root: Path,
    skill_targets: list[Path],
    antigravity_plugin_dir: Path | None = None,
) -> dict[str, Any]:
    """Deploy obra/superpowers skills cleanly to Antigravity plugin dir and/or skill targets."""
    skills_src = extracted_root / "skills"
    if not skills_src.is_dir():
        raise SetupError(f"Thiếu thư mục skills/ trong superpowers: {extracted_root}")
    deployed_plugins: str | None = None
    if antigravity_plugin_dir is not None:
        reject_links(antigravity_plugin_dir)
        _copy_tree_filtered(extracted_root, antigravity_plugin_dir, exclude_dirs={".git", "__pycache__"})
        deployed_plugins = str(antigravity_plugin_dir)
    copied_skills: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        for skill_dir in sorted(p for p in skills_src.iterdir() if p.is_dir()):
            _copy_tree_filtered(skill_dir, target_root / skill_dir.name, exclude_dirs={"__pycache__"})
            copied_skills.append(skill_dir.name)
    return {"plugin_dir": deployed_plugins, "skill_names": sorted(set(copied_skills))}


def _checked_run(argv: list[str], *, cwd: Path | None = None, runner: Runner = subprocess.run, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        res = runner(
            argv,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"Không thể chạy lệnh {argv[0]}: {exc}") from exc
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or "Không có thông báo lỗi").strip()
        raise SetupError(f"Lệnh thất bại (mã {res.returncode}): {' '.join(argv)}\n{detail[:1000]}")
    return res


def _resolve_uv_cmd() -> str | None:
    local_uv = get_data_root() / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    if local_uv.is_file():
        return str(local_uv)
    return shutil.which("uv")


def _ensure_venv(venv_name: str, runner: Runner = subprocess.run) -> Path:
    venv_dir = get_data_root() / "venvs" / venv_name
    py_exe = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if py_exe.is_file():
        code, _, _ = _run_quick([str(py_exe), "-c", "import sys; assert sys.version_info >= (3, 10)"], timeout=8)
        if code == 0:
            return py_exe
        shutil.rmtree(venv_dir, ignore_errors=True)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    uv_exe = _resolve_uv_cmd()
    if uv_exe:
        try:
            res = runner(
                [uv_exe, "venv", "--python", "3.12", str(venv_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )
            if res.returncode == 0 and py_exe.is_file():
                return py_exe
        except (OSError, subprocess.TimeoutExpired):
            pass
        shutil.rmtree(venv_dir, ignore_errors=True)
        _checked_run([uv_exe, "venv", "--python", sys.executable, str(venv_dir)], runner=runner, timeout=120)
        if py_exe.is_file():
            return py_exe
    _checked_run([sys.executable, "-m", "venv", str(venv_dir)], runner=runner, timeout=180)
    if not py_exe.is_file():
        raise SetupError(f"Không tạo được môi trường ảo Python tại {venv_dir}")
    return py_exe


def _pip_install(venv_py: Path, specs: list[str], *, runner: Runner = subprocess.run, editable: bool = False, no_deps: bool = False) -> None:
    uv_exe = _resolve_uv_cmd()
    if uv_exe:
        argv = [uv_exe, "pip", "install", "--python", str(venv_py)]
    else:
        argv = [str(venv_py), "-m", "pip", "install", "--disable-pip-version-check"]
    if no_deps:
        argv.append("--no-deps")
    if editable:
        argv.append("-e")
    argv.extend(specs)
    _checked_run(argv, runner=runner, timeout=600)


def _target_skill_and_rule_dirs(ides: dict[str, dict[str, Any]]) -> tuple[list[Path], list[Path], list[str], Path | None]:
    """Collect active skill dirs, rule dirs, REA client IDs, and Antigravity plugin dir."""
    skill_dirs: list[Path] = []
    rule_dirs: list[Path] = []
    rea_clients: list[str] = []
    ag_plugin_dir: Path | None = None

    # Always prepare Antigravity config dirs as default baseline even if user installs IDE right after
    ag = ides["antigravity"]
    skill_dirs.append(Path(ag["skills_dir"]))
    if ag["rules_dir"]:
        rule_dirs.append(Path(ag["rules_dir"]))
    if ag["detected"]:
        rea_clients.append("antigravity")
        ag_plugin_dir = Path.home() / ".gemini" / "config" / "plugins" / "superpowers"

    for key in ("claude_code", "codex", "vscode"):
        info = ides[key]
        if info["detected"]:
            if info.get("skills_dir"):
                skill_dirs.append(Path(info["skills_dir"]))
            if info.get("rules_dir") and key == "claude_code":
                rule_dirs.append(Path(info["rules_dir"]))
            if info.get("rea_client"):
                rea_clients.append(info["rea_client"])

    # Deduplicate preserving order
    uniq_skills = list(dict.fromkeys(skill_dirs))
    uniq_rules = list(dict.fromkeys(rule_dirs))
    uniq_clients = list(dict.fromkeys(rea_clients or ["antigravity"]))
    return uniq_skills, uniq_rules, uniq_clients, ag_plugin_dir


def _resolve_npm_cmd() -> str:
    local_npm = get_data_root() / "runtime" / "node" / ("npm.cmd" if os.name == "nt" else "npm")
    if local_npm.is_file():
        return str(local_npm)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm and os.name == "nt":
        for base in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"):
            cand = Path(base) / "nodejs" / "npm.cmd" if base else None
            if cand and cand.is_file():
                npm = str(cand)
                break
    if not npm:
        raise SetupError("Không tìm thấy npm trên máy. Hãy hoàn tất cài đặt Node.js trước.")
    return npm


def _npm_pack_and_extract(npm_spec: str, stage_root: Path, runner: Runner = subprocess.run) -> Path:
    """Download an npm package tarball via `npm pack` and safely extract it without running install hooks."""
    npm_cmd = _resolve_npm_cmd()
    pack_dir = stage_root / "npm_pack"
    extract_dir = stage_root / "npm_extract"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_res = _checked_run([npm_cmd, "pack", npm_spec], cwd=pack_dir, runner=runner, timeout=120)
    lines = [line.strip() for line in pack_res.stdout.splitlines() if line.strip()]
    tgz_path = (pack_dir / lines[-1]) if lines else Path()
    if not tgz_path.is_file():
        tgz_candidates = list(pack_dir.glob("*.tgz"))
        if not tgz_candidates:
            raise SetupError(f"Không tải được gói {npm_spec} từ npm.")
        tgz_path = tgz_candidates[0]
    return safe_extract_tar(tgz_path, extract_dir)


def install_lot1(catalog: dict[str, Any], *, dry_run: bool = False, runner: Runner = subprocess.run) -> dict[str, Any]:
    """Install Lot 1 (Content): Vietnamese Humanizer skills & isolated CLI."""
    spec = catalog["lot1_content"]["vietnamese_humanizer"]
    ides = detect_ides()
    skill_dirs, _, _, _ = _target_skill_and_rule_dirs(ides)
    tools_dest = get_data_root() / "tools" / "vietnamese-humanizer"
    if dry_run:
        return {"lot": "lot1", "status": "planned", "tools_dest": str(tools_dest), "skill_dirs": [str(p) for p in skill_dirs]}

    with tempfile.TemporaryDirectory(prefix="studio-lot1-") as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "vh.zip"
        atomic_write_bytes(zip_file, download_bytes(spec["archive_url"]))
        extracted = safe_extract_zip(zip_file, tmp_path / "src")
        deploy_info = deploy_vietnamese_humanizer_from_tree(extracted, tools_dest, skill_dirs)

    venv_py = _ensure_venv("content", runner=runner)
    _pip_install(venv_py, list(spec["python_deps"]) + ["hatchling>=1.27"], runner=runner)
    _pip_install(venv_py, [str(tools_dest)], runner=runner, editable=True, no_deps=True)
    return {"lot": "lot1", "status": "installed", "venv_python": str(venv_py), **deploy_info}


def install_lot2(
    catalog: dict[str, Any],
    *,
    opt_openmontage: bool = False,
    opt_assetfurnace: bool = False,
    force_gpu: bool = False,
    dry_run: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Install Lot 2 (Edit Video): auto-editor, media venv, rea-video, ffmpeg-skill, EditAtlas clean skills."""
    lot2 = catalog["lot2_video"]
    ides = detect_ides()
    skill_dirs, _, _, _ = _target_skill_and_rule_dirs(ides)
    rea_video_dest = get_data_root() / "tools" / "rea-video"
    optional_root = Path.home() / "StudioAI-Tools"
    gpu = _probe_nvidia_gpu()

    if opt_assetfurnace and not gpu["supports_3d"] and not force_gpu:
        raise SetupError(
            "Máy chưa phát hiện card đồ họa NVIDIA RTX hỗ trợ 3D (sm_75+). "
            "Vui lòng bỏ chọn AssetFurnace 3D để tránh tải dữ liệu lớn không chạy được."
        )
    if dry_run:
        return {
            "lot": "lot2",
            "status": "planned",
            "rea_video_dest": str(rea_video_dest),
            "skill_dirs": [str(p) for p in skill_dirs],
            "opt_openmontage": opt_openmontage,
            "opt_assetfurnace": opt_assetfurnace,
        }

    venv_py = _ensure_venv("media", runner=runner)
    _pip_install(venv_py, [lot2["auto_editor"]["pypi_spec"], *lot2["media_python_deps"]], runner=runner)

    with tempfile.TemporaryDirectory(prefix="studio-lot2-") as tmp:
        tmp_path = Path(tmp)
        # 1. rea-video
        rv_zip = tmp_path / "rea-video.zip"
        atomic_write_bytes(rv_zip, download_bytes(lot2["rea_video"]["archive_url"]))
        rv_src = safe_extract_zip(rv_zip, tmp_path / "rv_src")
        rv_info = deploy_rea_video_from_tree(rv_src, rea_video_dest, skill_dirs)
        _pip_install(venv_py, [str(rea_video_dest)], runner=runner, editable=True)

        # 2. EditAtlas (sound-design + media-picker only)
        ea_zip = tmp_path / "editatlas.zip"
        atomic_write_bytes(ea_zip, download_bytes(lot2["editatlas_skills"]["archive_url"]))
        ea_src = safe_extract_zip(ea_zip, tmp_path / "ea_src")
        ea_info = deploy_editatlas_from_tree(ea_src, skill_dirs)

        # 3. ffmpeg-skill@3.8.16 (safe npm pack + tar extract without running postinstall)
        ff_pkg = _npm_pack_and_extract(lot2["ffmpeg_skill"]["npm_spec"], tmp_path / "ff_stage", runner=runner)
        ff_info = deploy_ffmpeg_skill_from_tree(ff_pkg, skill_dirs)

    optional_cloned: list[str] = []
    git_exe = shutil.which("git")
    if (opt_openmontage or opt_assetfurnace) and not git_exe:
        raise SetupError("Cần có Git để tải tùy chọn nâng cao (OpenMontage / AssetFurnace 3D).")
    if opt_openmontage and git_exe:
        dest = optional_root / "OpenMontage"
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            _checked_run([git_exe, "clone", "--depth", "1", lot2["optional_openmontage"]["repo"], str(dest)], runner=runner)
        optional_cloned.append(str(dest))
    if opt_assetfurnace and git_exe:
        dest = optional_root / "AssetFurnace"
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            _checked_run([git_exe, "clone", "--depth", "1", lot2["optional_assetfurnace"]["repo"], str(dest)], runner=runner)
        optional_cloned.append(str(dest))

    return {
        "lot": "lot2",
        "status": "installed",
        "venv_python": str(venv_py),
        "rea_video": rv_info,
        "editatlas": ea_info,
        "ffmpeg_skill": ff_info,
        "optional_cloned": optional_cloned,
    }


def install_lot3(
    catalog: dict[str, Any],
    *,
    user_name: str = "bạn",
    dry_run: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Install Lot 3 (Code): ruff, pytest, superpowers, Karpathy guidelines, Auto-Router rules."""
    lot3 = catalog["lot3_code"]
    ides = detect_ides()
    skill_dirs, rule_dirs, _, ag_plugin_dir = _target_skill_and_rule_dirs(ides)
    rendered_rules = render_rules(user_name)

    if dry_run:
        return {
            "lot": "lot3",
            "status": "planned",
            "user_name": sanitize_user_name(user_name),
            "rule_dirs": [str(p) for p in rule_dirs],
            "skill_dirs": [str(p) for p in skill_dirs],
        }

    venv_py = _ensure_venv("dev", runner=runner)
    _pip_install(venv_py, list(lot3["dev_tools"]), runner=runner)

    with tempfile.TemporaryDirectory(prefix="studio-lot3-") as tmp:
        tmp_path = Path(tmp)
        sp_zip = tmp_path / "superpowers.zip"
        atomic_write_bytes(sp_zip, download_bytes(lot3["superpowers"]["archive_url"]))
        sp_src = safe_extract_zip(sp_zip, tmp_path / "sp_src")
        # For Antigravity, plugin directory provides superpowers; for other IDEs copy skills directly
        non_ag_skill_dirs = [d for d in skill_dirs if d != Path(ides["antigravity"]["skills_dir"])]
        sp_info = deploy_superpowers_from_tree(sp_src, non_ag_skill_dirs, ag_plugin_dir)

        # Karpathy guidelines with strict SHA-256 verification
        k_spec = lot3["karpathy_guidelines"]
        k_bytes = download_bytes(k_spec["raw_url"])
        actual_sha = hashlib.sha256(k_bytes).hexdigest().lower()
        if actual_sha != k_spec["expected_sha256"].lower():
            raise SetupError("Mã kiểm tra SHA-256 của Karpathy Guidelines không khớp, đã hủy cài tệp này.")
        for sdir in skill_dirs:
            atomic_write_bytes(sdir / "karpathy-guidelines" / "SKILL.md", k_bytes)

        # Modern Web Guidance (Google Chrome / Edge / Firefox / MDN)
        mwg_pkg = _npm_pack_and_extract(lot3["modern_web_guidance"]["npm_spec"], tmp_path / "mwg_stage", runner=runner)
        mwg_info = deploy_modern_web_guidance_from_tree(mwg_pkg, skill_dirs)

    written_rules: list[str] = []
    for rdir in rule_dirs:
        reject_links(rdir)
        rdir.mkdir(parents=True, exist_ok=True)
        is_claude_rules = rdir.name == "rules" and rdir.parent.name == ".claude"
        for fname, content in rendered_rules.items():
            target_name = f"studio-ai-{fname.lower()}" if is_claude_rules else fname
            dest = rdir / target_name
            backup_file(dest)
            atomic_write_text(dest, content)
            written_rules.append(str(dest))

    return {
        "lot": "lot3",
        "status": "installed",
        "venv_python": str(venv_py),
        "superpowers": sp_info,
        "modern_web_guidance": mwg_info,
        "rules_written": written_rules,
    }


def install_lot4(
    catalog: dict[str, Any],
    *,
    opt_agent_reach: bool = False,
    dry_run: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Install Lot 4 (Data & Research): REA 6.10.1 MCP, yt-dlp, trendspyg, markitdown."""
    lot4 = catalog["lot4_data"]
    ides = detect_ides()
    _, _, rea_clients, _ = _target_skill_and_rule_dirs(ides)

    if dry_run:
        return {"lot": "lot4", "status": "planned", "rea_clients": rea_clients, "opt_agent_reach": opt_agent_reach}

    venv_py = _ensure_venv("data", runner=runner)
    _pip_install(
        venv_py,
        [lot4["yt_dlp"]["pypi_spec"], lot4["trendspyg"]["pypi_spec"], lot4["markitdown"]["pypi_spec"]],
        runner=runner,
    )

    rea_spec = lot4["rea_agents"]
    npm_prefix = os.environ.get("NPM_CONFIG_PREFIX")
    prefix_rea_candidates: list[Path] = []
    if npm_prefix:
        p = Path(npm_prefix)
        prefix_rea_candidates.extend([p / "rea.cmd", p / "rea", p / "bin" / "rea"])

    def _find_rea_exe() -> str | None:
        for cand in prefix_rea_candidates:
            if cand.is_file():
                return str(cand)
        if npm_prefix:
            return None
        runtime_node = get_data_root() / "runtime" / "node"
        for cand in (runtime_node / "rea.cmd", runtime_node / "rea"):
            if cand.is_file():
                return str(cand)
        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_global = Path(appdata) / "npm"
            for cand in (npm_global / "rea.cmd", npm_global / "rea"):
                if cand.is_file():
                    return str(cand)
        return shutil.which("rea.cmd") or shutil.which("rea")

    rea_exe = _find_rea_exe()
    needs_install = True
    if rea_exe:
        c, out, _ = _run_quick([rea_exe, "--version"], timeout=10)
        if c == 0 and out.strip().startswith(rea_spec["version"]):
            needs_install = False

    if needs_install:
        npm_cmd = _resolve_npm_cmd()
        _checked_run([npm_cmd, "install", "--global", rea_spec["npm_spec"]], runner=runner, timeout=300)
        rea_exe = _find_rea_exe()

    if not rea_exe:
        raise SetupError("Đã cài rea-agents nhưng chưa tìm thấy lệnh rea trên PATH.")

    setup_argv = [rea_exe, "setup", "--yes"]
    for cid in rea_clients:
        setup_argv.extend(["--client", cid])
    _checked_run(setup_argv, runner=runner, timeout=180)

    optional_cloned: list[str] = []
    if opt_agent_reach:
        git_exe = shutil.which("git")
        if not git_exe:
            raise SetupError("Cần có Git để tải tùy chọn Agent-Reach.")
        dest = Path.home() / "StudioAI-Tools" / "Agent-Reach"
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            _checked_run([git_exe, "clone", "--depth", "1", lot4["optional_agent_reach"]["repo"], str(dest)], runner=runner)
        optional_cloned.append(str(dest))

    return {
        "lot": "lot4",
        "status": "installed",
        "venv_python": str(venv_py),
        "rea_clients": rea_clients,
        "optional_cloned": optional_cloned,
    }


def finalize_setup(guides_src: Path = GUIDES_DIR) -> dict[str, Any]:
    """Copy beginner Vietnamese Lot guides to Documents/Studio AI Setup/Chi-Dan."""
    dest_guides = get_documents_dir() / "Studio AI Setup" / "Chi-Dan"
    reject_links(dest_guides)
    copied = _copy_tree_filtered(guides_src, dest_guides)
    return {"guides_dir": str(dest_guides), "copied_files": copied}


def collect_verify() -> dict[str, Any]:
    """Run truth-based checks across tools, virtualenvs, guides, and IDE configs."""
    pre = collect_preflight()
    tools = pre["tools"]
    guides_dest = get_documents_dir() / "Studio AI Setup" / "Chi-Dan"
    guides_ok = (guides_dest / "00-BAT-DAU-NHANH.md").is_file()
    ides = pre["ides"]
    ag_rules = Path(ides["antigravity"]["rules_dir"]) / "AGENTS.md"
    return {
        "ok": bool(tools["python"]["installed"] and tools["node"]["supported"] and tools["git"]["installed"]),
        "guides_dir": str(guides_dest),
        "guides_ready": guides_ok,
        "rules_ready": ag_rules.is_file(),
        "tools": tools,
        "ides": ides,
    }


def interactive_fallback() -> int:
    """Friendly Vietnamese CLI fallback when WPF GUI cannot launch."""
    print("=" * 72)
    print("  STUDIO AI SETUP v1.0.0 — TRÌNH CÀI ĐẶT DỰ PHÒNG (CHẾ ĐỘ DÒNG LỆNH)")
    print("=" * 72)
    pre = collect_preflight()
    print(f"  Hệ điều hành : {pre['os']} {pre['os_release']} ({pre['arch']})")
    print(f"  RAM / Ổ trống : {pre['ram_gb']} GB / {pre['free_disk_gb']} GB")
    raw_name = input("  [?] AI sẽ gọi bạn là gì? [Enter = 'bạn']: ").strip()
    user_name = sanitize_user_name(raw_name)
    ans = input("  [?] Bắt đầu cài cả 4 Lô khuyên dùng (Content, Edit Video, Code, Cào dữ liệu)? [y/N]: ").strip().lower()
    if ans not in ("y", "yes", "co", "có"):
        print("  Đã hủy. Không có thay đổi nào được ghi lên máy.")
        return 0

    catalog = load_catalog()
    for label, fn in (
        ("Lô 1 · Content", lambda: install_lot1(catalog)),
        ("Lô 2 · Edit Video", lambda: install_lot2(catalog)),
        ("Lô 3 · Code & Luật AI", lambda: install_lot3(catalog, user_name=user_name)),
        ("Lô 4 · Cào & Nghiên cứu", lambda: install_lot4(catalog)),
        ("Tạo 4 Bộ Chỉ Dẫn", finalize_setup),
    ):
        print(f"  [*] Đang chạy: {label}...")
        try:
            fn()
            print(f"  [OK] Xong: {label}")
        except SetupError as exc:
            print(f"  [!] Lỗi ở {label}: {exc}")
    v = collect_verify()
    print(f"\n  [HOÀN TẤT] Thư mục chỉ dẫn đã sẵn sàng tại: {v['guides_dir']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Studio AI Setup Engine")
    p.add_argument("--preflight-json", action="store_true", help="Emit machine hardware & tool probe JSON")
    p.add_argument("--verify-json", action="store_true", help="Emit post-install verification JSON")
    p.add_argument("--install-lot", choices=("lot1", "lot2", "lot3", "lot4", "finalize"), help="Install one specific Lot")
    p.add_argument("--user-name", default=None, help="Display name for AI rules")
    p.add_argument("--opt-openmontage", action="store_true", help="Include optional OpenMontage in lot2")
    p.add_argument("--opt-assetfurnace", action="store_true", help="Include optional AssetFurnace 3D in lot2")
    p.add_argument("--opt-agent-reach", action="store_true", help="Include optional Agent-Reach in lot4")
    p.add_argument("--force-gpu", action="store_true", help="Override NVIDIA GPU check for optional 3D tool")
    p.add_argument("--dry-run", action="store_true", help="Plan only without downloading or writing files")
    p.add_argument("--json", action="store_true", help="Print JSON output")
    p.add_argument("--interactive", action="store_true", help="Run friendly Vietnamese CLI fallback")
    return p


def main(argv: list[str] | None = None) -> int:
    configure_stdio_utf8()
    args = build_parser().parse_args(argv)
    try:
        if args.preflight_json:
            print(json.dumps(collect_preflight(), ensure_ascii=False, indent=2))
            return 0
        if args.verify_json:
            print(json.dumps(collect_verify(), ensure_ascii=False, indent=2))
            return 0
        if args.interactive:
            return interactive_fallback()
        if args.install_lot:
            catalog = load_catalog()
            if args.install_lot == "lot1":
                res = install_lot1(catalog, dry_run=args.dry_run)
            elif args.install_lot == "lot2":
                res = install_lot2(
                    catalog,
                    opt_openmontage=args.opt_openmontage,
                    opt_assetfurnace=args.opt_assetfurnace,
                    force_gpu=args.force_gpu,
                    dry_run=args.dry_run,
                )
            elif args.install_lot == "lot3":
                effective_name = args.user_name if args.user_name is not None else os.environ.get("STUDIO_AI_USER_NAME", "bạn")
                res = install_lot3(catalog, user_name=effective_name, dry_run=args.dry_run)
            elif args.install_lot == "lot4":
                res = install_lot4(catalog, opt_agent_reach=args.opt_agent_reach, dry_run=args.dry_run)
            else:
                res = finalize_setup() if not args.dry_run else {"lot": "finalize", "status": "planned"}
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                print(f"[OK] {args.install_lot}: {res.get('status', 'done')}")
            return 0
        build_parser().print_help()
        return 0
    except SetupError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
