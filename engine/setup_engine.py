#!/usr/bin/env python3
"""Studio AI Setup — Clean, modular environment bootstrapper engine for Creators.

Supports preflight hardware/tool detection, 5-Lot isolated installation (including
Google Elephant-Goldfish Model blind review), multi-harness plugin deployment,
managed rule upgrades with v1->v2 migration, SHA-256 configuration snapshot
backup & atomic restore, live Doctor healthcheck, and a plain-Vietnamese CLI
fallback when WPF GUI is unavailable.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as _dt
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

_UTC = getattr(_dt, "UTC", None) or _dt.timezone(_dt.timedelta(0))

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog-lock.json"
RULES_TEMPLATES_DIR = ROOT / "templates" / "rules"
GUIDES_DIR = ROOT / "chi-dan"

DEFAULT_APP_VERSION = "2.0.0"
VALID_LOTS = ("lot1", "lot2", "lot3", "lot4", "lot5")

# Archive extraction safety caps
MAX_ARCHIVE_ENTRIES = 4096
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024  # 128 MiB uncompressed
STREAM_CHUNK_BYTES = 64 * 1024
WIN_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# Windows reparse point constants (Python 3.10+ os.lstat().st_reparse_tag)
FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
IO_REPARSE_TAG_SYMLINK = 0xA000000C
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
IO_REPARSE_TAG_CLOUD_BASE = 0x9000001A
IO_REPARSE_TAG_ONEDRIVE = 0x80000021

# Managed rule markers & canonical v1.0.0 template hashes (LF-normalized)
RULE_MARKER_BEGIN = "<!-- STUDIO-AI-SETUP:BEGIN v2 -->"
RULE_MARKER_END = "<!-- STUDIO-AI-SETUP:END -->"
RULE_MARKER_RE = re.compile(
    r"<!-- STUDIO-AI-SETUP:BEGIN(?:\s+v\d+)? -->.*?<!-- STUDIO-AI-SETUP:END -->",
    re.DOTALL,
)
V1_AGENTS_CANONICAL_SHA256 = "5cf149d0276e4772b21d60e7a0c57ecea3f8208e20cc0ec93567a39c5081bd51"
V1_GEMINI_CANONICAL_SHA256 = "91d5d98db4f72e4959886ad96430e01b8200fb8fcf8448e5c178bb756cd40cc8"
V1_AGENTS_USER_LINE_RE = re.compile(r"(?m)^(- \*\*Người dùng\*\*: \*\*).+?(\*\*\.)")

# Plugin verification constants
FORBIDDEN_EGM_MANIFEST_KEYS = ("hooks", "mcpServers", "mcp", "apps")
SUPERPOWERS_MANIFEST_CANDIDATES = (
    "plugin.json",
    ".antigravity-plugin/plugin.json",
    "gemini-extension.json",
)
CODEX_EGM_SECTION_RE = re.compile(r'(?m)^\s*\[plugins\."egm@[^"]+"\]')

# Network retry backoff delays (seconds) for transient failures
DOWNLOAD_BACKOFF_SECONDS = (1.0, 3.0)

# SHA-256 configuration snapshot backup & atomic restore constants
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_FILENAME_PREFIX = "studio-ai-snapshot-"
SNAPSHOT_MAX_ENTRIES = 64
SNAPSHOT_MAX_BYTES = 32 * 1024 * 1024  # 32 MiB uncompressed cap for config snapshots
SNAPSHOT_MANIFEST_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB cap when peeking manifest.json
SNAPSHOT_NAME_RE = re.compile(r"^studio-ai-snapshot-(\d{8}T\d{6}Z)(?:-(\d+))?(?:-(.+))?$")
SNAPSHOT_ALLOWED_SLOTS: dict[str, str] = {
    "rules/antigravity/AGENTS.md": "antigravity_agents",
    "rules/antigravity/GEMINI.md": "antigravity_gemini",
    "rules/claude/studio-ai-agents.md": "claude_agents",
    "rules/claude/studio-ai-gemini.md": "claude_gemini",
    "state/state.json": "app_state",
}

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
    """Load and validate catalog-lock.json (supports schema_version 1 and 2)."""
    if not catalog_path.is_file():
        raise SetupError(f"Thiếu tệp catalog-lock.json tại {catalog_path}")
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SetupError(f"Tệp catalog-lock.json không hợp lệ: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") not in (1, 2):
        raise SetupError("Phiên bản schema trong catalog-lock.json không được hỗ trợ.")
    return data


def get_app_version(catalog: dict[str, Any] | None = None, catalog_path: Path = CATALOG_PATH) -> str:
    """Derive app_version dynamically from catalog-lock.json."""
    if isinstance(catalog, dict):
        ver = catalog.get("app_version")
        if isinstance(ver, str) and ver.strip():
            return ver.strip()
    try:
        loaded = load_catalog(catalog_path)
        ver = loaded.get("app_version")
        if isinstance(ver, str) and ver.strip():
            return ver.strip()
    except SetupError:
        pass
    return DEFAULT_APP_VERSION


def _is_allowed_cloudfiles_tag(tag: int) -> bool:
    """Return True strictly for Windows OneDrive / CloudFiles reparse tags."""
    return (tag & 0xFFFF0FFF) == IO_REPARSE_TAG_CLOUD_BASE or tag == IO_REPARSE_TAG_ONEDRIVE


def _check_reparse_tag(part: Path, info: os.stat_result) -> None:
    """Validate stat_result against symlinks, junctions, and non-CloudFiles reparse points."""
    if stat.S_ISLNK(info.st_mode):
        raise SetupError(f"Từ chối đường dẫn liên kết (symlink): {part}")
    tag = int(getattr(info, "st_reparse_tag", 0) or 0)
    has_reparse_attr = bool(getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)
    if tag == 0 and not has_reparse_attr:
        return
    if tag in (IO_REPARSE_TAG_SYMLINK, IO_REPARSE_TAG_MOUNT_POINT):
        raise SetupError(f"Từ chối đường dẫn liên kết (symlink/junction): {part}")
    if tag != 0 and _is_allowed_cloudfiles_tag(tag):
        return
    raise SetupError(f"Từ chối đường dẫn liên kết (reparse tag=0x{tag:08X}): {part}")


def reject_links(path: Path) -> None:
    """Reject symlinks, junctions, non-CloudFiles reparse points, and non-directory ancestors."""
    for part in (path, *path.parents):
        try:
            info = os.lstat(part)
        except FileNotFoundError:
            continue
        except NotADirectoryError as exc:
            raise SetupError(f"Đường dẫn chứa thành phần không phải thư mục: {part}") from exc
        _check_reparse_tag(part, info)
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


def atomic_replace_dir(
    stage_dir_or_src: Path | Callable[[Path], Any],
    dst_dir: Path,
) -> Path:
    """Atomically replace dst_dir using same-volume sibling staging with rollback.

    Stages inside dst_dir.parent to guarantee same-volume rename (preventing WinError 17
    EXDEV across drives) and prunes any stale files left by prior versions.
    """
    reject_links(dst_dir.parent)
    if dst_dir.exists():
        reject_links(dst_dir)
    dst_dir.parent.mkdir(parents=True, exist_ok=True)

    stage_dir = dst_dir.parent / f".{dst_dir.name}.stage-{uuid.uuid4().hex[:8]}"
    old_dir: Path | None = None
    try:
        stage_dir.mkdir(parents=True, exist_ok=False)
        if callable(stage_dir_or_src):
            stage_dir_or_src(stage_dir)
        else:
            src_path = Path(stage_dir_or_src)
            if not src_path.is_dir():
                raise SetupError(f"Thư mục nguồn không tồn tại: {src_path}")
            _copy_tree_filtered(src_path, stage_dir)

        if dst_dir.exists():
            stamp = datetime.now(_UTC).strftime("%Y%m%dT%H%M%SZ")
            old_dir = dst_dir.parent / f".{dst_dir.name}.old-{stamp}-{uuid.uuid4().hex[:6]}"
            os.replace(dst_dir, old_dir)

        try:
            os.replace(stage_dir, dst_dir)
        except Exception:
            if old_dir is not None and old_dir.exists() and not dst_dir.exists():
                try:
                    os.replace(old_dir, dst_dir)
                except OSError:
                    pass
            raise

        if old_dir is not None and old_dir.exists():
            shutil.rmtree(old_dir, ignore_errors=True)
        return dst_dir
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise


def backup_file(path: Path, backup_dir: Path | None = None) -> Path | None:
    """Create a timestamped backup before overwriting an existing file."""
    if not path.is_file():
        return None
    reject_links(path)
    stamp = datetime.now(_UTC).strftime("%Y%m%dT%H%M%SZ")
    if backup_dir is not None:
        reject_links(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        bak = backup_dir / path.name
        if bak.exists():
            bak = backup_dir / f"{path.stem}-{uuid.uuid4().hex[:6]}{path.suffix}"
    else:
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


def _win32_known_documents_dir() -> Path | None:
    """Query FOLDERID_Documents via Win32 SHGetKnownFolderPath (OneDrive KFM aware)."""
    if os.name != "nt":
        return None

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
    folder_id = _GUID(
        0xFDD39AD0,
        0x238F,
        0x46AF,
        (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
    )
    ptr = ctypes.c_void_p()
    try:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None

        hr = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(ptr))
        if hr == 0 and ptr.value:
            resolved = Path(ctypes.wstring_at(ptr.value))
            if resolved.is_dir():
                return resolved
    except (AttributeError, OSError, ValueError):
        return None
    finally:
        if ptr.value:
            with contextlib.suppress(AttributeError, OSError):
                ctypes.windll.ole32.CoTaskMemFree(ptr)
    return None


def get_documents_dir(home: Path | None = None) -> Path:
    """Resolve the user's Documents directory (OneDrive Known Folder Move aware on Windows)."""
    if home is None:
        known = _win32_known_documents_dir()
        if known is not None:
            return known
    base = home or Path.home()
    docs = base / "Documents"
    return docs if docs.is_dir() else base


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
            stdin=subprocess.DEVNULL,
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
        code, out, _ = _run_quick(
            [exe, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            timeout=8,
        )
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


def _find_git_exe() -> str | None:
    """Locate git executable across PATH and common Windows per-user/system locations."""
    found = shutil.which("git")
    if found:
        return found
    local_bin = get_data_root() / "bin" / ("git.exe" if os.name == "nt" else "git")
    if local_bin.is_file():
        return str(local_bin)
    if os.name == "nt":
        candidates: list[Path] = []
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            candidates.append(Path(local_app) / "Programs" / "Git" / "cmd" / "git.exe")
        for base in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"), r"C:\Program Files"):
            if base:
                candidates.append(Path(base) / "Git" / "cmd" / "git.exe")
        for cand in candidates:
            if cand.is_file():
                return str(cand)
    return None


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
    if cmd == "git":
        git_found = _find_git_exe()
        if git_found:
            candidates.append(git_found)
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
    except (AttributeError, OSError, ValueError):
        return None
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
    appdata = Path(os.environ.get("APPDATA", str(base / "AppData" / "Roaming"))) if home is None else (base / "AppData" / "Roaming")
    antigravity_root = base / ".gemini" / "config"
    ag_present = (base / ".gemini").is_dir() or (base / ".antigravity").is_dir()
    claude_dir = base / ".claude"
    claude_present = claude_dir.is_dir() or (home is None and bool(shutil.which("claude")))
    codex_dir = base / ".codex"
    codex_present = codex_dir.is_dir() or (home is None and bool(shutil.which("codex")))
    vscode_dir = appdata / "Code"
    vscode_present = vscode_dir.is_dir() or (home is None and bool(shutil.which("code")))

    return {
        "antigravity": {
            "detected": ag_present,
            "label": "Antigravity",
            "skills_dir": str(antigravity_root / "skills"),
            "rules_dir": str(antigravity_root / "rules"),
            "plugins_dir": str(antigravity_root / "plugins"),
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
        gh_logged_in = c == 0
    gh_info["logged_in"] = gh_logged_in

    return {
        "app_version": get_app_version(),
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


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block any HTTP redirect that downgrades or leaves HTTPS."""

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        parsed = urllib.parse.urlparse(resolved)
        if parsed.scheme.lower() != "https":
            raise SetupError(f"Từ chối chuyển hướng không an toàn (không phải HTTPS): {resolved}")
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def download_bytes(
    url: str,
    timeout: int = 120,
    *,
    expected_sha256: str | None = None,
    retries: int = 3,
    app_version: str | None = None,
) -> bytes:
    """Download bytes over HTTPS only with redirect guard, retries, and optional SHA-256 verification."""
    if not url.lower().startswith("https://"):
        raise SetupError(f"Chỉ cho phép tải từ địa chỉ HTTPS an toàn: {url}")

    ua = f"StudioAISetup/{app_version or get_app_version()}"
    opener = urllib.request.build_opener(_HttpsOnlyRedirectHandler())
    attempts = max(1, int(retries))
    last_exc: Exception | None = None

    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with opener.open(req, timeout=timeout) as resp:
                final_url = resp.geturl() if hasattr(resp, "geturl") else url
                if isinstance(final_url, str) and not final_url.lower().startswith("https://"):
                    raise SetupError(f"Từ chối phản hồi không phải HTTPS: {final_url}")
                data = resp.read()
            if expected_sha256 is not None:
                actual_sha = hashlib.sha256(data).hexdigest().lower()
                if actual_sha != expected_sha256.strip().lower():
                    raise SetupError(
                        f"Mã kiểm tra SHA-256 không khớp cho {url}: "
                        f"mong đợi {expected_sha256[:12]}..., thực tế {actual_sha[:12]}..."
                    )
            return data
        except SetupError:
            raise
        except urllib.error.HTTPError as exc:
            last_exc = exc
            is_transient = (500 <= exc.code < 600) or exc.code == 429
            if not is_transient or attempt + 1 >= attempts:
                raise SetupError(f"Không tải được dữ liệu từ {url} (HTTP {exc.code}): {exc}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                raise SetupError(f"Không tải được dữ liệu từ {url}: {exc}") from exc

        delay = DOWNLOAD_BACKOFF_SECONDS[min(attempt, len(DOWNLOAD_BACKOFF_SECONDS) - 1)]
        time.sleep(delay)

    raise SetupError(f"Không tải được dữ liệu từ {url}: {last_exc}")


def compute_tree_sha256(root_dir: Path) -> str:
    """Compute deterministic SHA-256 digest over all regular files in root_dir."""
    entries: list[tuple[bytes, str, str]] = []
    for item in root_dir.rglob("*"):
        info = os.lstat(item)
        if stat.S_ISLNK(info.st_mode):
            raise SetupError(f"Phát hiện liên kết symlink khi tính tree_sha256: {item}")
        if stat.S_ISREG(info.st_mode):
            rel_posix = item.relative_to(root_dir).as_posix()
            file_sha = hashlib.sha256(item.read_bytes()).hexdigest()
            entries.append((rel_posix.encode("utf-8"), rel_posix, file_sha))
    entries.sort(key=lambda row: row[0])
    digest = hashlib.sha256()
    for _, rel_posix, file_sha in entries:
        digest.update(f"{rel_posix}\0{file_sha}\n".encode())
    return digest.hexdigest()


def _validate_archive_member_path(
    raw_name: str,
    is_dir: bool,
    seen_lower: dict[str, tuple[str, bool]],
    label: str,
) -> Path | None:
    """Validate one archive member path against traversal, reserved names, and case collisions."""
    if "\x00" in raw_name:
        raise SetupError(f"Phát hiện ký tự NUL không hợp lệ trong {label}: {raw_name!r}")

    norm = raw_name.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        raise SetupError(f"Đường dẫn tuyệt đối/ổ đĩa không an toàn trong {label}: {raw_name}")

    stripped = norm.rstrip("/")
    if stripped in ("", "."):
        return None

    parts = [seg for seg in stripped.split("/") if seg not in ("", ".")]
    if not parts:
        return None

    for seg in parts:
        if seg == ".." or ":" in seg:
            raise SetupError(f"Đường dẫn thoát thư mục không an toàn trong {label}: {raw_name}")
        stem = seg.split(".", 1)[0].rstrip(" ").upper()
        if stem in WIN_RESERVED_NAMES:
            raise SetupError(f"Tên tệp dành riêng của Windows không hợp lệ trong {label}: {raw_name}")

    canon = "/".join(parts)
    lower_key = canon.lower()
    if lower_key in seen_lower:
        prev_canon, prev_is_dir = seen_lower[lower_key]
        if prev_canon != canon:
            raise SetupError(f"Phát hiện xung đột đường dẫn phân biệt hoa/thường trong {label}: {raw_name}")
        if not (prev_is_dir and is_dir):
            raise SetupError(f"Phát hiện đường dẫn trùng lặp trong {label}: {raw_name}")
    else:
        seen_lower[lower_key] = (canon, is_dir)

    return Path(*parts)


def safe_extract_zip(
    zip_path: Path,
    dest_dir: Path,
    *,
    max_entries: int = MAX_ARCHIVE_ENTRIES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> Path:
    """2-pass hardened ZIP extraction blocking Zip-Slip, Zip-Bomb, symlinks, reserved names, and case collisions."""
    reject_links(dest_dir)
    dest_resolved = dest_dir.resolve()
    dest_existed = dest_resolved.exists()

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        if len(members) > max_entries:
            raise SetupError(f"File nén ZIP vượt quá giới hạn {max_entries} mục ({len(members)} mục).")

        # Pass 1: full validation before writing a single byte
        seen_lower: dict[str, tuple[str, bool]] = {}
        declared_bytes = 0
        validated: list[tuple[zipfile.ZipInfo, Path | None, bool]] = []

        for member in members:
            unix_mode = (member.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(unix_mode):
                raise SetupError(f"Từ chối liên kết symlink bên trong file nén: {member.filename}")
            if unix_mode != 0 and not (stat.S_ISREG(unix_mode) or stat.S_ISDIR(unix_mode)):
                raise SetupError(f"Từ chối tệp đặc biệt bên trong file nén: {member.filename}")

            is_dir = member.is_dir() or member.filename.endswith(("/", "\\"))
            if not is_dir:
                if member.file_size < 0:
                    raise SetupError(f"Kích thước tệp âm không hợp lệ trong file nén: {member.filename}")
                declared_bytes += member.file_size
                if declared_bytes > max_bytes:
                    raise SetupError(f"File nén ZIP vượt quá giới hạn dung lượng giải nén ({max_bytes // (1024 * 1024)} MiB).")

            rel = _validate_archive_member_path(member.filename, is_dir, seen_lower, "file nén ZIP")
            if rel is not None:
                target = (dest_resolved / rel).resolve()
                if target != dest_resolved and dest_resolved not in target.parents:
                    raise SetupError(f"Phát hiện thoát thư mục trong file nén: {member.filename}")
            validated.append((member, rel, is_dir))

        # Pass 2: streamed write with cumulative byte cap
        dest_resolved.mkdir(parents=True, exist_ok=True)
        streamed_bytes = 0
        try:
            for member, rel, is_dir in validated:
                if rel is None:
                    continue
                target = dest_resolved / rel
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, open(target, "wb") as dst:
                        while True:
                            chunk = src.read(STREAM_CHUNK_BYTES)
                            if not chunk:
                                break
                            streamed_bytes += len(chunk)
                            if streamed_bytes > max_bytes:
                                raise SetupError(
                                    f"Dung lượng giải nén thực tế vượt quá giới hạn {max_bytes // (1024 * 1024)} MiB."
                                )
                            dst.write(chunk)
        except Exception:
            if not dest_existed and dest_resolved.exists():
                shutil.rmtree(dest_resolved, ignore_errors=True)
            raise

    subdirs = [p for p in dest_resolved.iterdir() if p.is_dir()]
    return subdirs[0] if len(subdirs) == 1 else dest_resolved


def safe_extract_tar(
    tgz_path: Path,
    dest_dir: Path,
    *,
    max_entries: int = MAX_ARCHIVE_ENTRIES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> Path:
    """2-pass hardened TAR extraction blocking traversal, symlinks/hardlinks, reserved names, case collisions, and bombs."""
    reject_links(dest_dir)
    dest_resolved = dest_dir.resolve()
    dest_existed = dest_resolved.exists()

    with tarfile.open(tgz_path, "r:*") as tf:
        members = tf.getmembers()
        if len(members) > max_entries:
            raise SetupError(f"Gói tar vượt quá giới hạn {max_entries} mục ({len(members)} mục).")

        # Pass 1: full validation before writing a single byte
        seen_lower: dict[str, tuple[str, bool]] = {}
        declared_bytes = 0
        validated: list[tuple[tarfile.TarInfo, Path | None, bool]] = []

        for member in members:
            if member.issym() or member.islnk():
                raise SetupError(f"Từ chối liên kết symlink/hardlink bên trong gói tar: {member.name}")
            if not (member.isdir() or member.isfile()):
                raise SetupError(f"Từ chối tệp đặc biệt bên trong gói tar: {member.name}")

            is_dir = member.isdir()
            if not is_dir:
                if member.size < 0:
                    raise SetupError(f"Kích thước tệp âm không hợp lệ trong gói tar: {member.name}")
                declared_bytes += member.size
                if declared_bytes > max_bytes:
                    raise SetupError(f"Gói tar vượt quá giới hạn dung lượng giải nén ({max_bytes // (1024 * 1024)} MiB).")

            rel = _validate_archive_member_path(member.name, is_dir, seen_lower, "gói tar")
            if rel is not None:
                target = (dest_resolved / rel).resolve()
                if target != dest_resolved and dest_resolved not in target.parents:
                    raise SetupError(f"Phát hiện thoát thư mục trong gói tar: {member.name}")
            validated.append((member, rel, is_dir))

        # Pass 2: streamed write with cumulative byte cap
        dest_resolved.mkdir(parents=True, exist_ok=True)
        streamed_bytes = 0
        try:
            for member, rel, is_dir in validated:
                if rel is None:
                    continue
                target = dest_resolved / rel
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    extracted = tf.extractfile(member)
                    if extracted is not None:
                        with extracted, open(target, "wb") as dst:
                            while True:
                                chunk = extracted.read(STREAM_CHUNK_BYTES)
                                if not chunk:
                                    break
                                streamed_bytes += len(chunk)
                                if streamed_bytes > max_bytes:
                                    raise SetupError(
                                        f"Dung lượng giải nén tar vượt quá giới hạn {max_bytes // (1024 * 1024)} MiB."
                                    )
                                dst.write(chunk)
        except Exception:
            if not dest_existed and dest_resolved.exists():
                shutil.rmtree(dest_resolved, ignore_errors=True)
            raise

    pkg_dir = dest_resolved / "package"
    return pkg_dir if pkg_dir.is_dir() else dest_resolved


def download_and_verify_github_tree(
    entry: dict[str, Any],
    tmp_dir: Path,
    *,
    app_version: str | None = None,
) -> Path:
    """Download a pinned GitHub codeload ZIP, extract safely, and verify tree_sha256."""
    archive_url = entry.get("archive_url")
    if not isinstance(archive_url, str) or not archive_url.lower().startswith("https://"):
        raise SetupError(f"Thiếu hoặc sai archive_url HTTPS trong catalog: {archive_url!r}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_dir / "archive.zip"
    atomic_write_bytes(zip_path, download_bytes(archive_url, app_version=app_version))
    extracted = safe_extract_zip(zip_path, tmp_dir / "src")
    expected_tree = entry.get("tree_sha256")
    if expected_tree:
        actual_tree = compute_tree_sha256(extracted)
        if actual_tree.lower() != str(expected_tree).strip().lower():
            raise SetupError(
                f"Mã kiểm tra cây tệp (tree_sha256) không khớp cho {entry.get('repo', archive_url)}: "
                f"mong đợi {str(expected_tree)[:12]}..., thực tế {actual_tree[:12]}..."
            )
    return extracted


def _copy_tree_filtered(src: Path, dst: Path, *, exclude_dirs: set[str] | None = None) -> int:
    """Copy directory tree atomically file-by-file, rejecting symlinks and excluded dirs."""
    excludes = exclude_dirs or set()
    copied = 0
    for item in src.rglob("*"):
        if any(part in excludes for part in item.relative_to(src).parts):
            continue
        info = os.lstat(item)
        if stat.S_ISLNK(info.st_mode):
            continue
        if stat.S_ISREG(info.st_mode):
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


def _ensure_managed_block(rendered_block: str) -> str:
    """Ensure rendered rule content is wrapped exactly once in STUDIO-AI-SETUP v2 markers."""
    norm = rendered_block.replace("\r\n", "\n").replace("\r", "\n")
    m = RULE_MARKER_RE.search(norm)
    if m:
        return m.group(0).strip("\n") + "\n"
    body = norm.strip("\n")
    return f"{RULE_MARKER_BEGIN}\n{body}\n{RULE_MARKER_END}\n"


def _canonical_v1_hashes_for_text(text: str, *, normalize_user_line: bool) -> set[str]:
    """Compute candidate LF-normalized canonical SHA-256 digests for v1 comparison."""
    norm = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if normalize_user_line:
        norm = V1_AGENTS_USER_LINE_RE.sub(r"\1{{USER_NAME}}\2", norm, count=1)
    variants = {norm, norm.rstrip("\n"), norm.rstrip("\n") + "\n"}
    return {hashlib.sha256(v.encode("utf-8")).hexdigest().lower() for v in variants}


def sync_rule_file(
    dst: Path,
    rendered_block: str,
    backup_root: Path,
    v1_canonical_hashes: set[str] | frozenset[str],
    *,
    normalize_user_line: bool = False,
) -> dict[str, Any]:
    """Safely install or upgrade a rule file without clobbering user customizations.

    Handles 4 cases:
    1. File absent -> write marker-wrapped v2 block cleanly.
    2. Markers present -> backup to backup_root and replace ONLY inside BEGIN..END.
    3. No markers, matches embedded canonical v1.0.0 hash -> backup & auto-upgrade to v2.
    4. No markers, user-customized/foreign -> leave dst untouched; write v2 reference to backup_root.
    """
    reject_links(dst)
    reject_links(backup_root)
    managed = _ensure_managed_block(rendered_block)

    if not dst.exists():
        atomic_write_text(dst, managed)
        return {"path": str(dst), "status": "created", "backup": None, "reference": None}

    raw_bytes = dst.read_bytes()
    existing_text = raw_bytes.decode("utf-8-sig", errors="replace")
    existing_norm = existing_text.replace("\r\n", "\n").replace("\r", "\n")

    # Case 2: managed markers present
    match = RULE_MARKER_RE.search(existing_norm)
    if match:
        bak_path = backup_file(dst, backup_dir=backup_root)
        replacement = managed.rstrip("\n")
        updated = existing_norm[: match.start()] + replacement + existing_norm[match.end() :]
        if not updated.endswith("\n"):
            updated += "\n"
        atomic_write_text(dst, updated)
        return {"path": str(dst), "status": "updated_markers", "backup": str(bak_path), "reference": None}

    # Case 3: unmodified v1.0.0 file matching embedded canonical SHA-256
    target_hashes = {h.strip().lower() for h in v1_canonical_hashes if h}
    candidates = _canonical_v1_hashes_for_text(existing_norm, normalize_user_line=normalize_user_line)
    if target_hashes and (candidates & target_hashes):
        bak_path = backup_file(dst, backup_dir=backup_root)
        atomic_write_text(dst, managed)
        return {"path": str(dst), "status": "upgraded_v1", "backup": str(bak_path), "reference": None}

    # Case 4: user-customized or foreign rule file -> preserve active file untouched
    backup_root.mkdir(parents=True, exist_ok=True)
    ref_path = backup_root / f"{dst.name}.v2-reference.md"
    if ref_path.exists():
        ref_path = backup_root / f"{dst.name}-{uuid.uuid4().hex[:6]}.v2-reference.md"
    atomic_write_text(ref_path, managed)
    return {"path": str(dst), "status": "preserved_user_custom", "backup": None, "reference": str(ref_path)}


def get_state_path(app_root: Path | None = None) -> Path:
    """Return path to Studio AI Setup state.json."""
    return (app_root or get_data_root()) / "state.json"


def load_state(app_root: Path | None = None) -> dict[str, Any]:
    """Read Studio AI Setup state.json safely, returning empty dict if absent/invalid."""
    state_path = get_state_path(app_root)
    if not state_path.is_file():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, Any], app_root: Path | None = None) -> Path:
    """Persist Studio AI Setup state.json atomically."""
    state_path = get_state_path(app_root)
    atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return state_path


def parse_lots_arg(lots_raw: str | None) -> list[str] | None:
    """Parse optional comma-separated --lots argument into sorted valid lot IDs."""
    if lots_raw is None:
        return None
    items = [part.strip().lower() for part in lots_raw.split(",") if part.strip()]
    return sorted({lot for lot in items if lot in VALID_LOTS})


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
            atomic_replace_dir(
                lambda stage, s=src_skill: _copy_tree_filtered(s, stage, exclude_dirs={"__pycache__"}),
                target_root / skill_name,
            )
            deployed_skills.append(str(target_root / skill_name))
        for bad in forbidden_names:
            if (target_root / bad).exists():
                raise SetupError(f"Vi phạm bộ lọc bảo mật: phát hiện thành phần bị cấm {bad} tại {target_root}")

    # Copy only clean package files needed by `viet-writing-lint` CLI (excluding .agents, .impeccable, web)
    copied_counter = {"count": 0}

    def _stage_cli(stage: Path) -> None:
        for file_name in ("pyproject.toml", "LICENSE", "README.md"):
            f = extracted_root / file_name
            if f.is_file():
                atomic_write_bytes(stage / file_name, f.read_bytes())
                copied_counter["count"] += 1
        for dir_name in ("src", "patterns", "examples", "benchmarks"):
            d = extracted_root / dir_name
            if d.is_dir():
                copied_counter["count"] += _copy_tree_filtered(d, stage / dir_name, exclude_dirs={"__pycache__"})
        for skill_name in allowed_skills:
            d = skills_src / skill_name
            if d.is_dir():
                copied_counter["count"] += _copy_tree_filtered(
                    d, stage / "skills" / skill_name, exclude_dirs={"__pycache__"}
                )
        for bad in (".agents", ".impeccable", "web"):
            if (stage / bad).exists():
                raise SetupError(f"Vi phạm bộ lọc bảo mật: phát hiện {bad} trong {tools_dest}")

    atomic_replace_dir(_stage_cli, tools_dest)
    return {"skills": deployed_skills, "cli_files": copied_counter["count"], "tools_dest": str(tools_dest)}


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
            atomic_replace_dir(
                lambda stage, s=src_dir: _copy_tree_filtered(s, stage, exclude_dirs={"evals", "__pycache__"}),
                target_root / skill_name,
            )
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
        atomic_replace_dir(
            lambda stage: _copy_tree_filtered(
                package_root, stage, exclude_dirs={"node_modules", "__pycache__", ".git", "tests", "demos"}
            ),
            dest,
        )
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
        atomic_replace_dir(
            lambda stage: _copy_tree_filtered(skill_src, stage, exclude_dirs={"node_modules", "__pycache__", ".git"}),
            dest,
        )
        deployed.append(str(dest))
    return deployed


def deploy_rea_video_from_tree(extracted_root: Path, tools_dest: Path, skill_targets: list[Path]) -> dict[str, Any]:
    """Copy rea-video source into isolated tools dir and copy SKILL.md into AI skill dirs."""
    skill_src = extracted_root / "skills" / "rea-video"
    if not skill_src.is_dir():
        raise SetupError(f"Thiếu skills/rea-video trong gói rea-video: {extracted_root}")
    copied_counter = {"count": 0}

    def _stage_rv(stage: Path) -> None:
        copied_counter["count"] = _copy_tree_filtered(extracted_root, stage, exclude_dirs={".git", "__pycache__"})

    atomic_replace_dir(_stage_rv, tools_dest)
    deployed: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        atomic_replace_dir(
            lambda stage: _copy_tree_filtered(skill_src, stage, exclude_dirs={"__pycache__"}),
            target_root / "rea-video",
        )
        deployed.append(str(target_root / "rea-video"))
    return {"tools_dest": str(tools_dest), "copied_files": copied_counter["count"], "skills": deployed}


def deploy_superpowers_from_tree(
    extracted_root: Path,
    skill_targets: list[Path],
    antigravity_plugin_dir: Path | None = None,
) -> dict[str, Any]:
    """Deploy obra/superpowers cleanly via atomic swap to Antigravity plugin dir and/or skill targets."""
    skills_src = extracted_root / "skills"
    if not skills_src.is_dir():
        raise SetupError(f"Thiếu thư mục skills/ trong superpowers: {extracted_root}")
    deployed_plugins: str | None = None
    if antigravity_plugin_dir is not None:
        atomic_replace_dir(
            lambda stage: _copy_tree_filtered(extracted_root, stage, exclude_dirs={".git", "__pycache__"}),
            antigravity_plugin_dir,
        )
        deployed_plugins = str(antigravity_plugin_dir)
    copied_skills: list[str] = []
    for target_root in skill_targets:
        reject_links(target_root)
        for skill_dir in sorted(p for p in skills_src.iterdir() if p.is_dir()):
            atomic_replace_dir(
                lambda stage, s=skill_dir: _copy_tree_filtered(s, stage, exclude_dirs={"__pycache__"}),
                target_root / skill_dir.name,
            )
            copied_skills.append(skill_dir.name)
    return {"plugin_dir": deployed_plugins, "skill_names": sorted(set(copied_skills))}


def _collect_allowlist_files(src_root: Path, patterns: list[str]) -> dict[str, Path]:
    """Collect regular files matching exact-depth Path.glob() patterns while rejecting symlinks."""
    src_resolved = src_root.resolve()
    selected: dict[str, Path] = {}
    for pattern in patterns:
        for match in sorted(src_root.glob(pattern)):
            rel = match.relative_to(src_root)
            # Ensure no ancestor inside src_root is a symlink
            cur = src_root
            for part in rel.parts:
                cur = cur / part
                info = os.lstat(cur)
                if stat.S_ISLNK(info.st_mode):
                    raise SetupError(f"Từ chối liên kết symlink trong gói plugin: {cur}")
            info = os.lstat(match)
            if not stat.S_ISREG(info.st_mode):
                continue
            resolved = match.resolve()
            if src_resolved not in resolved.parents:
                raise SetupError(f"Phát hiện tệp thoát thư mục nguồn plugin: {match}")
            selected[rel.as_posix()] = match
    return dict(sorted(selected.items()))


def _assert_egm_manifest_clean(manifest_path: Path, rel_label: str) -> dict[str, Any]:
    """Validate an EGM plugin manifest JSON and reject forbidden executable/hook/MCP keys."""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SetupError(f"Tệp kê khai EGM không hợp lệ ({rel_label}): {exc}") from exc
    if not isinstance(data, dict):
        raise SetupError(f"Tệp kê khai EGM phải là đối tượng JSON ({rel_label}).")
    for key in FORBIDDEN_EGM_MANIFEST_KEYS:
        if key in data:
            raise SetupError(f"Phát hiện khóa bảo mật bị cấm '{key}' trong {rel_label}.")
    extensions = data.get("extensions")
    if isinstance(extensions, dict):
        for ext_name, ext_val in extensions.items():
            if isinstance(ext_val, dict):
                for key in FORBIDDEN_EGM_MANIFEST_KEYS:
                    if key in ext_val:
                        raise SetupError(
                            f"Phát hiện khóa bảo mật bị cấm '{key}' trong {rel_label} (extensions.{ext_name})."
                        )
    return data


def _read_json_quiet(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _claude_plugin_installed(installed_json_path: Path, plugin_id: str) -> bool:
    data = _read_json_quiet(installed_json_path)
    if isinstance(data, dict):
        plugins = data.get("plugins")
        if isinstance(plugins, dict) and plugin_id in plugins:
            return True
        if isinstance(plugins, list):
            for entry in plugins:
                if entry == plugin_id or (isinstance(entry, dict) and plugin_id in (entry.get("id"), entry.get("name"))):
                    return True
        if plugin_id in data:
            return True
    elif isinstance(data, list):
        return plugin_id in data
    return False


def _claude_marketplace_state(marketplaces_json_path: Path, marketplace_name: str, expected_dir: Path) -> str:
    """Return 'absent', 'matches', or 'other' for a Claude Code known marketplace entry."""
    data = _read_json_quiet(marketplaces_json_path)
    if not isinstance(data, dict):
        return "absent"
    container = data.get("marketplaces") if isinstance(data.get("marketplaces"), dict) else data
    if marketplace_name not in container:
        return "absent"
    entry = container[marketplace_name]
    expected_norm = os.path.normcase(str(expected_dir.resolve()))
    candidates: list[str] = []
    if isinstance(entry, str):
        candidates.append(entry)
    elif isinstance(entry, dict):
        for k in ("installLocation", "path", "location"):
            if isinstance(entry.get(k), str):
                candidates.append(entry[k])
        src = entry.get("source")
        if isinstance(src, str):
            candidates.append(src)
        elif isinstance(src, dict):
            for k in ("path", "directory", "url"):
                if isinstance(src.get(k), str):
                    candidates.append(src[k])
    for cand in candidates:
        try:
            if os.path.normcase(str(Path(cand).resolve())) == expected_norm:
                return "matches"
        except OSError:
            continue
    return "other"


def _codex_plugin_configured(config_toml_path: Path, plugin_name: str) -> bool:
    if not config_toml_path.is_file():
        return False
    try:
        text = config_toml_path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    pat = CODEX_EGM_SECTION_RE if plugin_name == "egm" else re.compile(
        rf'(?m)^\s*\[plugins\."{re.escape(plugin_name)}@[^"]+"\]'
    )
    return bool(pat.search(text))


def _run_harness_cli(argv: list[str], runner: Runner = subprocess.run, timeout: int = 30) -> tuple[int, str]:
    try:
        res = runner(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        detail = (res.stderr or res.stdout or "").strip()[:300]
        return res.returncode, detail
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)[:300]


def register_harness_plugin(
    plugin_name: str,
    unified_bundle_dir: Path,
    ide_info: dict[str, dict[str, Any]],
    *,
    home: Path | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Register a multi-harness plugin with Claude Code and Codex CLI safely (non-clobber, non-fatal)."""
    base_home = home or Path.home()
    plugin_id = f"{plugin_name}@{plugin_name}"
    ag_plugins_dir = Path(ide_info["antigravity"]["plugins_dir"])

    harnesses: dict[str, Any] = {
        "antigravity": {
            "status": "installed",
            "path": str(ag_plugins_dir / plugin_name),
        }
    }

    # 1. Claude Code (B4: read-only non-clobber guard; skip redundant enable after install)
    claude_manual = [
        f'claude plugin marketplace add "{unified_bundle_dir}"',
        f"claude plugin install {plugin_id}",
    ]
    claude_installed_json = base_home / ".claude" / "plugins" / "installed_plugins.json"
    claude_marketplaces_json = base_home / ".claude" / "plugins" / "known_marketplaces.json"
    if _claude_plugin_installed(claude_installed_json, plugin_id):
        harnesses["claude_code"] = {"status": "already_installed", "manual_commands": claude_manual}
    elif not ide_info.get("claude_code", {}).get("detected", False):
        harnesses["claude_code"] = {"status": "not_detected", "manual_commands": claude_manual}
    else:
        claude_exe = shutil.which("claude")
        if not claude_exe:
            harnesses["claude_code"] = {"status": "cli_not_found", "manual_commands": claude_manual}
        else:
            mkt_state = _claude_marketplace_state(claude_marketplaces_json, plugin_name, unified_bundle_dir)
            if mkt_state == "other":
                # Do NOT overwrite existing user marketplace; attempt direct install only
                rc, detail = _run_harness_cli([claude_exe, "plugin", "install", plugin_id], runner=runner)
                if rc == 0:
                    harnesses["claude_code"] = {
                        "status": "installed",
                        "marketplace_preserved": True,
                        "manual_commands": claude_manual,
                    }
                else:
                    harnesses["claude_code"] = {
                        "status": "already_configured_marketplace",
                        "detail": detail,
                        "manual_commands": claude_manual,
                    }
            else:
                add_ok = True
                add_detail = ""
                if mkt_state == "absent":
                    rc_add, add_detail = _run_harness_cli(
                        [claude_exe, "plugin", "marketplace", "add", str(unified_bundle_dir)],
                        runner=runner,
                    )
                    add_ok = rc_add == 0
                if not add_ok:
                    harnesses["claude_code"] = {
                        "status": "manual_required",
                        "step": "marketplace_add",
                        "detail": add_detail,
                        "manual_commands": claude_manual,
                    }
                else:
                    # `claude plugin install` auto-enables; never call redundant `enable` (RC=1)
                    rc_inst, inst_detail = _run_harness_cli(
                        [claude_exe, "plugin", "install", plugin_id],
                        runner=runner,
                    )
                    if rc_inst == 0:
                        harnesses["claude_code"] = {"status": "installed", "manual_commands": claude_manual}
                    else:
                        harnesses["claude_code"] = {
                            "status": "manual_required",
                            "step": "install",
                            "detail": inst_detail,
                            "manual_commands": claude_manual,
                        }

    # 2. Codex CLI (M2: TOML section regex guard + shutil.which("codex"))
    codex_manual = [
        f'codex plugin marketplace add "{unified_bundle_dir}"',
        f"codex plugin add {plugin_id}",
    ]
    codex_config = base_home / ".codex" / "config.toml"
    if _codex_plugin_configured(codex_config, plugin_name):
        harnesses["codex"] = {"status": "already_installed", "manual_commands": codex_manual}
    elif not ide_info.get("codex", {}).get("detected", False):
        harnesses["codex"] = {"status": "not_detected", "manual_commands": codex_manual}
    else:
        codex_exe = shutil.which("codex")
        if not codex_exe:
            harnesses["codex"] = {"status": "cli_not_found", "manual_commands": codex_manual}
        else:
            rc_mkt, mkt_detail = _run_harness_cli(
                [codex_exe, "plugin", "marketplace", "add", str(unified_bundle_dir)],
                runner=runner,
            )
            if rc_mkt != 0:
                harnesses["codex"] = {
                    "status": "manual_required",
                    "step": "marketplace_add",
                    "detail": mkt_detail,
                    "manual_commands": codex_manual,
                }
            else:
                rc_add, add_detail = _run_harness_cli(
                    [codex_exe, "plugin", "add", plugin_id],
                    runner=runner,
                )
                if rc_add == 0:
                    harnesses["codex"] = {"status": "installed", "manual_commands": codex_manual}
                else:
                    harnesses["codex"] = {
                        "status": "manual_required",
                        "step": "add",
                        "detail": add_detail,
                        "manual_commands": codex_manual,
                    }

    return harnesses


def deploy_egm_from_tree(
    src_root: Path,
    egm_entry: dict[str, Any],
    ide_info: dict[str, dict[str, Any]],
    app_root: Path,
    *,
    home: Path | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Validate and deploy Google Elephant-Goldfish Model across Antigravity, Claude Code, and Codex."""
    ag_allowlist = list(egm_entry.get("antigravity_allowlist", []))
    extra_allowlist = list(egm_entry.get("unified_extra_allowlist", []))
    required_skills = list(egm_entry.get("required_skills", []))
    required_agent_count = int(egm_entry.get("required_agent_count", 10))
    required_standard_count = int(egm_entry.get("required_standard_count", 5))

    ag_files = _collect_allowlist_files(src_root, ag_allowlist)
    unified_files = _collect_allowlist_files(src_root, ag_allowlist + extra_allowlist)

    # Pre-swap security & completeness assertions
    if "plugin.json" not in ag_files:
        raise SetupError("Gói EGM thiếu tệp plugin.json ở thư mục gốc.")
    if "LICENSE" not in ag_files:
        raise SetupError("Gói EGM thiếu tệp bản quyền LICENSE (Apache-2.0).")

    root_manifest = _assert_egm_manifest_clean(ag_files["plugin.json"], "plugin.json")
    if root_manifest.get("name") != "egm":
        raise SetupError(f"Tên plugin trong plugin.json không hợp lệ: {root_manifest.get('name')!r}")

    for extra_manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        if extra_manifest in unified_files:
            _assert_egm_manifest_clean(unified_files[extra_manifest], extra_manifest)

    missing_skills = [s for s in required_skills if f"skills/{s}/SKILL.md" not in ag_files]
    if missing_skills:
        raise SetupError(f"Gói EGM thiếu kỹ năng bắt buộc: {', '.join(missing_skills)}")

    agent_files = [rel for rel in ag_files if rel.startswith("agents/") and rel.endswith(".md") and rel.count("/") == 1]
    if len(agent_files) < required_agent_count:
        raise SetupError(
            f"Gói EGM không đủ Goldfish agents (yêu cầu >= {required_agent_count}, tìm thấy {len(agent_files)})."
        )

    standard_files = [
        rel
        for rel in ag_files
        if rel.startswith("resources/document_standards/") and rel.endswith(".md") and rel.count("/") == 2
    ]
    if len(standard_files) < required_standard_count:
        raise SetupError(
            f"Gói EGM không đủ tiêu chuẩn tài liệu (yêu cầu >= {required_standard_count}, tìm thấy {len(standard_files)})."
        )

    def _write_selected(files_map: dict[str, Path], stage: Path) -> None:
        for rel_posix, src_file in files_map.items():
            atomic_write_bytes(stage / rel_posix, src_file.read_bytes())

    # 1. Antigravity plugin bundle (NEVER edit config.json; NEVER flatten into skills/)
    ag_plugins_root = Path(ide_info["antigravity"]["plugins_dir"])
    ag_egm_dir = ag_plugins_root / "egm"
    atomic_replace_dir(lambda stage: _write_selected(ag_files, stage), ag_egm_dir)

    # 2. Unified local marketplace bundle (for Claude Code & Codex CLI)
    unified_dir = app_root / "plugins" / "egm"
    atomic_replace_dir(lambda stage: _write_selected(unified_files, stage), unified_dir)

    # 3. Multi-harness registration (non-clobber, non-fatal)
    harnesses = register_harness_plugin("egm", unified_dir, ide_info, home=home, runner=runner)

    return {
        "antigravity_dir": str(ag_egm_dir),
        "antigravity_files": len(ag_files),
        "unified_dir": str(unified_dir),
        "unified_files": len(unified_files),
        "skills_count": len(required_skills),
        "agents_count": len(agent_files),
        "standards_count": len(standard_files),
        "harnesses": harnesses,
    }


def _checked_run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    runner: Runner = subprocess.run,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    try:
        res = runner(
            argv,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
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


def _clone_pinned_repo(
    repo_url: str,
    commit_sha: str,
    dest: Path,
    *,
    git_exe: str | None = None,
    runner: Runner = subprocess.run,
) -> Path:
    """Clone an optional repository at an exact 40-char commit SHA via sibling temp staging."""
    if not repo_url.lower().startswith("https://"):
        raise SetupError(f"Chỉ cho phép clone kho mã nguồn HTTPS: {repo_url}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha.strip().lower()):
        raise SetupError(f"Mã commit của {repo_url} phải đủ 40 ký tự hex: {commit_sha!r}")
    if dest.exists():
        return dest

    git = git_exe or _find_git_exe()
    if not git:
        raise SetupError("Cần có Git để tải kho mã nguồn tùy chọn.")

    reject_links(dest.parent)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_clone = dest.parent / f".tmp-{dest.name}-{uuid.uuid4().hex[:8]}"
    try:
        tmp_clone.mkdir(parents=True, exist_ok=False)
        _checked_run([git, "init"], cwd=tmp_clone, runner=runner, timeout=60)
        _checked_run([git, "remote", "add", "origin", repo_url], cwd=tmp_clone, runner=runner, timeout=60)
        _checked_run([git, "fetch", "--depth", "1", "origin", commit_sha.strip().lower()], cwd=tmp_clone, runner=runner, timeout=300)
        _checked_run([git, "checkout", "--detach", "FETCH_HEAD"], cwd=tmp_clone, runner=runner, timeout=120)
        os.replace(tmp_clone, dest)
        return dest
    except Exception:
        if tmp_clone.exists():
            shutil.rmtree(tmp_clone, ignore_errors=True)
        raise


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
                stdin=subprocess.DEVNULL,
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


def _pip_install(
    venv_py: Path,
    specs: list[str],
    *,
    runner: Runner = subprocess.run,
    editable: bool = False,
    no_deps: bool = False,
) -> None:
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


def _target_skill_and_rule_dirs(ides: dict[str, dict[str, Any]]) -> tuple[list[Path], list[Path], list[str], Path]:
    """Collect active skill dirs, rule dirs, REA client IDs, and Antigravity plugins root.

    Always returns Antigravity's plugins_dir even on clean machines (detected == False)
    so plugins are staged cleanly before the user opens Antigravity for the first time.
    """
    skill_dirs: list[Path] = []
    rule_dirs: list[Path] = []
    rea_clients: list[str] = []

    ag = ides["antigravity"]
    skill_dirs.append(Path(ag["skills_dir"]))
    if ag.get("rules_dir"):
        rule_dirs.append(Path(ag["rules_dir"]))
    ag_plugins_root = Path(ag["plugins_dir"])
    if ag.get("detected"):
        rea_clients.append("antigravity")

    for key in ("claude_code", "codex", "vscode"):
        info = ides[key]
        if info.get("detected"):
            if info.get("skills_dir"):
                skill_dirs.append(Path(info["skills_dir"]))
            if info.get("rules_dir") and key == "claude_code":
                rule_dirs.append(Path(info["rules_dir"]))
            if info.get("rea_client"):
                rea_clients.append(info["rea_client"])

    uniq_skills = list(dict.fromkeys(skill_dirs))
    uniq_rules = list(dict.fromkeys(rule_dirs))
    uniq_clients = list(dict.fromkeys(rea_clients or ["antigravity"]))
    return uniq_skills, uniq_rules, uniq_clients, ag_plugins_root


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

    app_ver = get_app_version(catalog)
    with tempfile.TemporaryDirectory(prefix="studio-lot1-") as tmp:
        extracted = download_and_verify_github_tree(spec, Path(tmp), app_version=app_ver)
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

    app_ver = get_app_version(catalog)
    with tempfile.TemporaryDirectory(prefix="studio-lot2-") as tmp:
        tmp_path = Path(tmp)
        # 1. rea-video (tree_sha256 verified)
        rv_src = download_and_verify_github_tree(lot2["rea_video"], tmp_path / "rv", app_version=app_ver)
        rv_info = deploy_rea_video_from_tree(rv_src, rea_video_dest, skill_dirs)
        _pip_install(venv_py, [str(rea_video_dest)], runner=runner, editable=True)

        # 2. EditAtlas (sound-design + media-picker only, tree_sha256 verified)
        ea_src = download_and_verify_github_tree(lot2["editatlas_skills"], tmp_path / "ea", app_version=app_ver)
        ea_info = deploy_editatlas_from_tree(ea_src, skill_dirs)

        # 3. ffmpeg-skill@3.8.16 (safe npm pack + tar extract without running postinstall)
        ff_pkg = _npm_pack_and_extract(lot2["ffmpeg_skill"]["npm_spec"], tmp_path / "ff_stage", runner=runner)
        ff_info = deploy_ffmpeg_skill_from_tree(ff_pkg, skill_dirs)

    optional_cloned: list[str] = []
    if opt_openmontage or opt_assetfurnace:
        git_exe = _find_git_exe()
        if not git_exe:
            raise SetupError("Cần có Git để tải tùy chọn nâng cao (OpenMontage / AssetFurnace 3D).")
        if opt_openmontage:
            om_spec = lot2["optional_openmontage"]
            dest = _clone_pinned_repo(
                om_spec["repo"], om_spec["commit"], optional_root / "OpenMontage", git_exe=git_exe, runner=runner
            )
            optional_cloned.append(str(dest))
        if opt_assetfurnace:
            af_spec = lot2["optional_assetfurnace"]
            dest = _clone_pinned_repo(
                af_spec["repo"], af_spec["commit"], optional_root / "AssetFurnace", git_exe=git_exe, runner=runner
            )
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
    """Install Lot 3 (Code): ruff, pytest, superpowers, Karpathy guidelines, Modern Web Guidance.

    Rule files (AGENTS.md / GEMINI.md) are deployed independently in finalize_setup().
    """
    del user_name  # Kept for signature backwards compatibility; rules live in finalize_setup()
    lot3 = catalog["lot3_code"]
    ides = detect_ides()
    skill_dirs, _, _, ag_plugins_root = _target_skill_and_rule_dirs(ides)
    ag_superpowers_dir = ag_plugins_root / "superpowers"

    if dry_run:
        return {
            "lot": "lot3",
            "status": "planned",
            "superpowers_plugin_dir": str(ag_superpowers_dir),
            "skill_dirs": [str(p) for p in skill_dirs],
        }

    venv_py = _ensure_venv("dev", runner=runner)
    _pip_install(venv_py, list(lot3["dev_tools"]), runner=runner)

    app_ver = get_app_version(catalog)
    with tempfile.TemporaryDirectory(prefix="studio-lot3-") as tmp:
        tmp_path = Path(tmp)
        sp_src = download_and_verify_github_tree(lot3["superpowers"], tmp_path / "sp", app_version=app_ver)
        # Antigravity gets whole plugin (always staged even on clean machines); other IDEs get flat skills
        non_ag_skill_dirs = [d for d in skill_dirs if d != Path(ides["antigravity"]["skills_dir"])]
        sp_info = deploy_superpowers_from_tree(sp_src, non_ag_skill_dirs, ag_superpowers_dir)

        # Karpathy guidelines with strict SHA-256 verification
        k_spec = lot3["karpathy_guidelines"]
        k_bytes = download_bytes(
            k_spec["raw_url"],
            expected_sha256=k_spec["expected_sha256"],
            app_version=app_ver,
        )
        for sdir in skill_dirs:
            atomic_write_bytes(sdir / "karpathy-guidelines" / "SKILL.md", k_bytes)

        # Modern Web Guidance (Google Chrome / Edge / Firefox / MDN)
        mwg_pkg = _npm_pack_and_extract(lot3["modern_web_guidance"]["npm_spec"], tmp_path / "mwg_stage", runner=runner)
        mwg_info = deploy_modern_web_guidance_from_tree(mwg_pkg, skill_dirs)

    return {
        "lot": "lot3",
        "status": "installed",
        "venv_python": str(venv_py),
        "superpowers": sp_info,
        "modern_web_guidance": mwg_info,
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
        git_exe = _find_git_exe()
        if not git_exe:
            raise SetupError("Cần có Git để tải tùy chọn Agent-Reach.")
        ar_spec = lot4["optional_agent_reach"]
        dest = _clone_pinned_repo(
            ar_spec["repo"],
            ar_spec["commit"],
            Path.home() / "StudioAI-Tools" / "Agent-Reach",
            git_exe=git_exe,
            runner=runner,
        )
        optional_cloned.append(str(dest))

    return {
        "lot": "lot4",
        "status": "installed",
        "venv_python": str(venv_py),
        "rea_clients": rea_clients,
        "optional_cloned": optional_cloned,
    }


def install_lot5(
    catalog: dict[str, Any],
    *,
    dry_run: bool = False,
    runner: Runner = subprocess.run,
    home: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Install Lot 5 (Blind Review & Verification): Google Elephant-Goldfish Model (EGM)."""
    lot5 = catalog.get("lot5_review")
    if not isinstance(lot5, dict) or "egm" not in lot5:
        raise SetupError("catalog-lock.json chưa có cấu hình lot5_review.egm.")
    egm_spec = lot5["egm"]
    ides = detect_ides(home=home)
    data_root = app_root or get_data_root()
    ag_egm_dir = Path(ides["antigravity"]["plugins_dir"]) / "egm"
    unified_dir = data_root / "plugins" / "egm"

    if dry_run:
        return {
            "lot": "lot5",
            "status": "planned",
            "antigravity_dir": str(ag_egm_dir),
            "unified_dir": str(unified_dir),
        }

    app_ver = get_app_version(catalog)
    with tempfile.TemporaryDirectory(prefix="studio-lot5-") as tmp:
        extracted = download_and_verify_github_tree(egm_spec, Path(tmp), app_version=app_ver)
        deploy_info = deploy_egm_from_tree(extracted, egm_spec, ides, data_root, home=home, runner=runner)

    # Persist harness registration status into state.json without disturbing other fields
    prev = load_state(data_root)
    prev["egm_harnesses"] = {k: v.get("status", "unknown") for k, v in deploy_info["harnesses"].items()}
    prev["egm_harnesses_detail"] = deploy_info["harnesses"]
    prev.setdefault("schema_version", 2)
    prev["app_version"] = app_ver
    prev["updated_at_utc"] = datetime.now(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(prev, data_root)

    return {"lot": "lot5", "status": "installed", **deploy_info}


def finalize_setup(
    catalog: dict[str, Any] | None = None,
    user_name: str | None = None,
    *,
    installed_lots: list[str] | None = None,
    guides_src: Path = GUIDES_DIR,
    templates_dir: Path = RULES_TEMPLATES_DIR,
    dry_run: bool = False,
    home: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Deploy/upgrade managed rules, copy Vietnamese guides, and persist state.json."""
    cat = catalog if catalog is not None else load_catalog()
    data_root = app_root or get_data_root()
    prev_state = load_state(data_root)
    ides = detect_ides(home=home)
    _, rule_dirs, _, _ = _target_skill_and_rule_dirs(ides)

    raw_name = user_name
    if raw_name is None or not raw_name.strip():
        raw_name = prev_state.get("user_name")
    effective_name = sanitize_user_name(raw_name)

    prev_lots = [lot for lot in prev_state.get("installed_lots", []) if lot in VALID_LOTS]
    if installed_lots is not None:
        merged_lots = sorted(set(prev_lots) | {lot for lot in installed_lots if lot in VALID_LOTS})
    else:
        merged_lots = sorted(set(prev_lots))

    dest_guides = get_documents_dir(home=home) / "Studio AI Setup" / "Chi-Dan"

    if dry_run:
        return {
            "lot": "finalize",
            "status": "planned",
            "user_name": effective_name,
            "installed_lots": merged_lots,
            "rule_dirs": [str(p) for p in rule_dirs],
            "guides_dir": str(dest_guides),
        }

    # 1. Decoupled rule sync with managed markers + v1.0.0 hash upgrade + off-dir backups
    rendered_rules = render_rules(effective_name, templates_dir=templates_dir)
    stamp = datetime.now(_UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_root = data_root / "backups" / stamp
    rules_status: dict[str, str] = {}
    rules_details: list[dict[str, Any]] = []

    for rdir in rule_dirs:
        reject_links(rdir)
        rdir.mkdir(parents=True, exist_ok=True)
        is_claude_rules = rdir.name == "rules" and rdir.parent.name == ".claude"
        for fname, content in rendered_rules.items():
            target_name = f"studio-ai-{fname.lower()}" if is_claude_rules else fname
            v1_hashes = {V1_AGENTS_CANONICAL_SHA256} if fname == "AGENTS.md" else {V1_GEMINI_CANONICAL_SHA256}
            result = sync_rule_file(
                rdir / target_name,
                content,
                backup_root,
                v1_hashes,
                normalize_user_line=(fname == "AGENTS.md"),
            )
            result["rule_name"] = fname
            rules_details.append(result)
            if not is_claude_rules or fname not in rules_status:
                rules_status[fname] = result["status"]

    # 2. Copy beginner Vietnamese guides to Documents\Studio AI Setup\Chi-Dan
    reject_links(dest_guides)
    copied_guides = _copy_tree_filtered(guides_src, dest_guides)

    # 3. Persist state.json (merging installed_lots non-destructively)
    app_ver = get_app_version(cat)
    new_state = {
        "schema_version": 2,
        "app_version": app_ver,
        "user_name": effective_name,
        "installed_lots": merged_lots,
        "egm_harnesses": prev_state.get("egm_harnesses", {}),
        "egm_harnesses_detail": prev_state.get("egm_harnesses_detail", {}),
        "rules_status": rules_status,
        "rules_details": rules_details,
        "updated_at_utc": datetime.now(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    state_path = save_state(new_state, data_root)

    return {
        "lot": "finalize",
        "status": "installed",
        "user_name": effective_name,
        "installed_lots": merged_lots,
        "rules_status": rules_status,
        "rules_details": rules_details,
        "guides_dir": str(dest_guides),
        "copied_files": copied_guides,
        "state_path": str(state_path),
    }


def get_snapshots_dir(app_root: Path | None = None) -> Path:
    """Return the configuration snapshot vault directory under app_root."""
    return (app_root or get_data_root()) / "snapshots"


def _snapshot_slot_paths(*, home: Path, app_root: Path) -> dict[str, Path]:
    """Map each whitelisted snapshot arcname to its live filesystem destination."""
    return {
        "rules/antigravity/AGENTS.md": home / ".gemini" / "config" / "rules" / "AGENTS.md",
        "rules/antigravity/GEMINI.md": home / ".gemini" / "config" / "rules" / "GEMINI.md",
        "rules/claude/studio-ai-agents.md": home / ".claude" / "rules" / "studio-ai-agents.md",
        "rules/claude/studio-ai-gemini.md": home / ".claude" / "rules" / "studio-ai-gemini.md",
        "state/state.json": app_root / "state.json",
    }


def _snapshot_sort_key(path: Path) -> tuple[str, int, int, str]:
    """Deterministic newest-first sort key (UTC stamp, same-second counter, mtime_ns, stem)."""
    try:
        mtime_ns = os.lstat(path).st_mtime_ns
    except OSError:
        mtime_ns = 0
    match = SNAPSHOT_NAME_RE.fullmatch(path.stem)
    if match:
        ts_str = match.group(1)
        counter = int(match.group(2)) if match.group(2) is not None else 0
        return (ts_str, counter, mtime_ns, path.stem)
    return ("", -1, mtime_ns, path.stem)


def _next_snapshot_path(snapshots_dir: Path, stamp: str) -> Path:
    """Choose a non-colliding snapshot filename for the given UTC timestamp."""
    base_name = f"{SNAPSHOT_FILENAME_PREFIX}{stamp}"
    candidate = snapshots_dir / f"{base_name}.zip"
    if not candidate.exists():
        return candidate
    for idx in range(1, 1000):
        candidate = snapshots_dir / f"{base_name}-{idx:02d}.zip"
        if not candidate.exists():
            return candidate
    return snapshots_dir / f"{base_name}-999-{uuid.uuid4().hex[:6]}.zip"


def _peek_snapshot_created_at(zip_path: Path) -> str | None:
    """Safely read created_at_utc from manifest.json inside a snapshot ZIP."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            info = zf.getinfo("manifest.json")
            if info.is_dir() or info.file_size < 0 or info.file_size > SNAPSHOT_MANIFEST_MAX_BYTES:
                return None
            with zf.open(info, "r") as fh:
                raw = fh.read(SNAPSHOT_MANIFEST_MAX_BYTES + 1)
            if len(raw) > SNAPSHOT_MANIFEST_MAX_BYTES:
                return None
            data = json.loads(raw.decode("utf-8-sig"))
            if isinstance(data, dict):
                val = data.get("created_at_utc")
                if isinstance(val, str) and val.strip():
                    return val.strip()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, KeyError, ValueError, OSError, RuntimeError, zlib.error):
        return None
    return None


def _list_snapshot_files(snapshots_dir: Path) -> list[Path]:
    """Return regular studio-ai-snapshot-*.zip files sorted newest-first without following symlinks."""
    if not snapshots_dir.exists():
        return []
    reject_links(snapshots_dir)
    if not snapshots_dir.is_dir():
        raise SetupError(f"Đường dẫn thư mục sao lưu không phải thư mục: {snapshots_dir}")
    candidates: list[Path] = []
    for item in snapshots_dir.glob(f"{SNAPSHOT_FILENAME_PREFIX}*.zip"):
        try:
            info = os.lstat(item)
            _check_reparse_tag(item, info)
        except (OSError, SetupError):
            continue
        if stat.S_ISREG(info.st_mode):
            candidates.append(item)
    candidates.sort(key=_snapshot_sort_key, reverse=True)
    return candidates


def create_snapshot_backup(
    catalog: dict[str, Any] | None = None,
    *,
    home: Path | None = None,
    app_root: Path | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Capture existing Studio AI config files into a SHA-256 verified ZIP snapshot."""
    base_home = Path(home) if home is not None else Path.home()
    data_root = Path(app_root) if app_root is not None else get_data_root()
    slot_paths = _snapshot_slot_paths(home=base_home, app_root=data_root)

    entries: list[dict[str, Any]] = []
    payloads: list[tuple[str, bytes]] = []
    state_data: dict[str, Any] = {}

    for arcname in sorted(SNAPSHOT_ALLOWED_SLOTS):
        src_path = slot_paths[arcname]
        reject_links(src_path)
        if not src_path.is_file():
            continue
        raw_bytes = src_path.read_bytes()
        file_sha = hashlib.sha256(raw_bytes).hexdigest()
        entries.append(
            {
                "arcname": arcname,
                "target_slot": SNAPSHOT_ALLOWED_SLOTS[arcname],
                "size": len(raw_bytes),
                "sha256": file_sha,
            }
        )
        payloads.append((arcname, raw_bytes))
        if arcname == "state/state.json":
            try:
                parsed = json.loads(raw_bytes.decode("utf-8-sig"))
                if isinstance(parsed, dict):
                    state_data = parsed
            except (UnicodeDecodeError, ValueError):
                state_data = {}

    now_utc = datetime.now(_UTC)
    created_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")

    raw_lots = state_data.get("installed_lots")
    installed_lots = [lot for lot in raw_lots if isinstance(lot, str)] if isinstance(raw_lots, list) else []
    raw_user = state_data.get("user_name")
    user_name = raw_user if isinstance(raw_user, str) else None

    manifest: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "app_name": "Studio AI Setup",
        "app_version": get_app_version(catalog),
        "created_at_utc": created_at_utc,
        "installed_lots": installed_lots,
        "user_name": user_name,
        "entries": entries,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    zip_dt = (
        max(now_utc.year, 1980),
        now_utc.month,
        now_utc.day,
        now_utc.hour,
        now_utc.minute,
        now_utc.second,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zi_manifest = zipfile.ZipInfo("manifest.json", date_time=zip_dt)
        zi_manifest.compress_type = zipfile.ZIP_DEFLATED
        zi_manifest.external_attr = (stat.S_IFREG | 0o644) << 16
        zf.writestr(zi_manifest, manifest_bytes, compress_type=zipfile.ZIP_DEFLATED)
        for arcname, raw_bytes in payloads:
            zi = zipfile.ZipInfo(arcname, date_time=zip_dt)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(zi, raw_bytes, compress_type=zipfile.ZIP_DEFLATED)

    zip_bytes = buf.getvalue()
    archive_sha256 = hashlib.sha256(zip_bytes).hexdigest()

    if out_path is not None:
        target_zip = Path(out_path)
        reject_links(target_zip)
        if target_zip.exists() and target_zip.is_dir():
            target_zip = _next_snapshot_path(target_zip, stamp)
    else:
        snapshots_dir = get_snapshots_dir(data_root)
        reject_links(snapshots_dir)
        target_zip = _next_snapshot_path(snapshots_dir, stamp)

    atomic_write_bytes(target_zip, zip_bytes)

    return {
        "ok": True,
        "action": "backup",
        "snapshot_path": str(target_zip),
        "filename": target_zip.name,
        "archive_sha256": archive_sha256,
        "file_count": len(entries),
        "entries": [e["arcname"] for e in entries],
    }


def list_snapshots(*, app_root: Path | None = None) -> dict[str, Any]:
    """List configuration snapshots in app_root/snapshots sorted newest-first."""
    data_root = Path(app_root) if app_root is not None else get_data_root()
    snapshots_dir = get_snapshots_dir(data_root)
    files = _list_snapshot_files(snapshots_dir)
    snapshots: list[dict[str, Any]] = []
    for snap in files:
        raw = snap.read_bytes()
        snapshots.append(
            {
                "filename": snap.name,
                "path": str(snap),
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "created_at_utc": _peek_snapshot_created_at(snap),
            }
        )
    return {
        "ok": True,
        "action": "list_backups",
        "snapshots_dir": str(snapshots_dir),
        "count": len(snapshots),
        "snapshots": snapshots,
    }


def restore_snapshot_backup(
    snapshot_ref: str,
    *,
    dry_run: bool = False,
    home: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Strictly verify a SHA-256 snapshot in 2 passes and atomically restore configuration files."""
    if not isinstance(snapshot_ref, (str, os.PathLike)) or not str(snapshot_ref).strip():
        raise SetupError("Thiếu đường dẫn bản sao lưu hoặc từ khóa 'latest'.")

    base_home = Path(home) if home is not None else Path.home()
    data_root = Path(app_root) if app_root is not None else get_data_root()
    ref_text = str(snapshot_ref).strip()

    if ref_text.lower() == "latest":
        snapshots_dir = get_snapshots_dir(data_root)
        candidates = _list_snapshot_files(snapshots_dir)
        if not candidates:
            raise SetupError(f"Chưa tìm thấy bản sao lưu nào trong {snapshots_dir}")
        snapshot_path = candidates[0]
    else:
        snapshot_path = Path(ref_text)

    reject_links(snapshot_path)
    if not snapshot_path.is_file():
        raise SetupError(f"Không tìm thấy tệp sao lưu: {snapshot_path}")

    slot_paths = _snapshot_slot_paths(home=base_home, app_root=data_root)

    # Pass 1: hardened extraction + full manifest, whitelist & SHA-256 verification before writing any byte
    restore_plan: list[tuple[str, Path, bytes]] = []
    with tempfile.TemporaryDirectory(prefix="studio-restore-") as tmp:
        extract_root = Path(tmp) / "extracted"
        try:
            safe_extract_zip(
                snapshot_path,
                extract_root,
                max_entries=SNAPSHOT_MAX_ENTRIES,
                max_bytes=SNAPSHOT_MAX_BYTES,
            )
        except SetupError:
            raise
        except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError, EOFError, zlib.error) as exc:
            raise SetupError(f"Tệp sao lưu ZIP không hợp lệ hoặc bị hỏng: {exc}") from exc

        extracted_files: dict[str, Path] = {}
        extracted_dirs: set[str] = set()
        for item in sorted(extract_root.rglob("*")):
            info = os.lstat(item)
            _check_reparse_tag(item, info)
            rel_posix = item.relative_to(extract_root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                extracted_dirs.add(rel_posix)
            elif stat.S_ISREG(info.st_mode):
                extracted_files[rel_posix] = item
            else:
                raise SetupError(f"Phát hiện tệp đặc biệt không hợp lệ trong bản sao lưu: {rel_posix}")

        manifest_path = extracted_files.get("manifest.json")
        if manifest_path is None:
            raise SetupError("Bản sao lưu thiếu tệp manifest.json.")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (UnicodeDecodeError, OSError, ValueError) as exc:
            raise SetupError(f"Tệp manifest.json trong bản sao lưu không hợp lệ: {exc}") from exc

        if not isinstance(manifest, dict):
            raise SetupError("Tệp manifest.json phải là đối tượng JSON hợp lệ.")

        schema_ver = manifest.get("schema_version")
        if type(schema_ver) is not int or schema_ver != SNAPSHOT_SCHEMA_VERSION:
            raise SetupError(
                f"Phiên bản schema_version của bản sao lưu không được hỗ trợ: {schema_ver!r} "
                f"(mong đợi {SNAPSHOT_SCHEMA_VERSION})."
            )

        raw_entries = manifest.get("entries")
        if not isinstance(raw_entries, list):
            raise SetupError("Trường 'entries' trong manifest.json phải là danh sách.")

        validated_entries: dict[str, tuple[int, str]] = {}
        for entry in raw_entries:
            if not isinstance(entry, dict):
                raise SetupError("Mục trong manifest.json['entries'] phải là đối tượng JSON.")
            arcname = entry.get("arcname")
            if not isinstance(arcname, str) or arcname not in SNAPSHOT_ALLOWED_SLOTS:
                raise SetupError(f"Đường dẫn tệp không nằm trong danh sách cho phép: {arcname!r}")
            if arcname in validated_entries:
                raise SetupError(f"Phát hiện mục trùng lặp trong manifest.json: {arcname}")
            target_slot = entry.get("target_slot")
            expected_slot = SNAPSHOT_ALLOWED_SLOTS[arcname]
            if not isinstance(target_slot, str) or target_slot != expected_slot:
                raise SetupError(
                    f"Slot đích không hợp lệ cho {arcname}: {target_slot!r} (mong đợi {expected_slot!r})."
                )
            declared_size = entry.get("size")
            if type(declared_size) is not int or declared_size < 0:
                raise SetupError(f"Kích thước tệp không hợp lệ trong manifest.json cho {arcname}: {declared_size!r}")
            declared_sha = entry.get("sha256")
            if not isinstance(declared_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", declared_sha.strip().lower()):
                raise SetupError(f"Mã SHA-256 không hợp lệ trong manifest.json cho {arcname}: {declared_sha!r}")
            validated_entries[arcname] = (declared_size, declared_sha.strip().lower())

        # Enforce exact 1-to-1 match between extracted files/dirs and manifest entries
        payload_keys = {k for k in extracted_files if k != "manifest.json"}
        declared_keys = set(validated_entries.keys())
        missing_files = sorted(declared_keys - payload_keys)
        if missing_files:
            raise SetupError(f"Bản sao lưu thiếu tệp dữ liệu đã kê khai: {', '.join(missing_files)}")
        extra_files = sorted(payload_keys - declared_keys)
        if extra_files:
            raise SetupError(f"Phát hiện tệp lạ không nằm trong manifest.json: {', '.join(extra_files)}")

        allowed_dirs: set[str] = set()
        for arcname in declared_keys:
            parts = arcname.split("/")[:-1]
            for idx in range(1, len(parts) + 1):
                allowed_dirs.add("/".join(parts[:idx]))
        extra_dirs = sorted(extracted_dirs - allowed_dirs)
        if extra_dirs:
            raise SetupError(f"Phát hiện thư mục lạ không nằm trong danh sách cho phép: {', '.join(extra_dirs)}")

        # Re-compute SHA-256 and validate every target path before touching disk
        for arcname in sorted(validated_entries):
            declared_size, expected_sha = validated_entries[arcname]
            raw_bytes = extracted_files[arcname].read_bytes()
            if len(raw_bytes) != declared_size:
                raise SetupError(
                    f"Kích thước tệp {arcname} không khớp với manifest.json "
                    f"(mong đợi {declared_size}, thực tế {len(raw_bytes)})."
                )
            actual_sha = hashlib.sha256(raw_bytes).hexdigest().lower()
            if actual_sha != expected_sha:
                raise SetupError(
                    f"Mã kiểm tra SHA-256 không khớp cho {arcname} "
                    f"(mong đợi {expected_sha[:12]}..., thực tế {actual_sha[:12]}...)."
                )
            dst_path = slot_paths[arcname]
            reject_links(dst_path)
            if dst_path.exists() and not dst_path.is_file():
                raise SetupError(f"Đích khôi phục không phải tệp thường: {dst_path}")
            restore_plan.append((arcname, dst_path, raw_bytes))

    if dry_run:
        return {
            "ok": True,
            "action": "restore_dry_run",
            "verified": True,
            "snapshot_path": str(snapshot_path),
            "would_restore": [arcname for arcname, _, _ in restore_plan],
            "targets": {arcname: str(dst_path) for arcname, dst_path, _ in restore_plan},
        }

    # Pass 2: back up existing destination files under app_root/backups/ and write atomically
    ts = datetime.now(_UTC).strftime("%Y%m%dT%H%M%SZ")
    backups_parent = data_root / "backups"
    reject_links(backups_parent)
    backup_dir = backups_parent / f"pre-restore-{ts}"
    if backup_dir.exists():
        backup_dir = backups_parent / f"pre-restore-{ts}-{uuid.uuid4().hex[:6]}"

    backed_up: list[str] = []
    for _arcname, dst_path, raw_bytes in restore_plan:
        reject_links(dst_path)
        bak = backup_file(dst_path, backup_dir=backup_dir)
        if bak is not None:
            backed_up.append(str(bak))
        atomic_write_bytes(dst_path, raw_bytes)

    return {
        "ok": True,
        "action": "restore",
        "verified": True,
        "snapshot_path": str(snapshot_path),
        "backup_dir": str(backup_dir) if backed_up else None,
        "restored": [arcname for arcname, _, _ in restore_plan],
        "targets": {arcname: str(dst_path) for arcname, dst_path, _ in restore_plan},
    }


def _venv_bin_exists(data_root: Path, venv_name: str, cmd: str) -> bool:
    scripts_dir = data_root / "venvs" / venv_name / ("Scripts" if os.name == "nt" else "bin")
    ext = ".exe" if os.name == "nt" else ""
    return (scripts_dir / f"{cmd}{ext}").is_file() or (scripts_dir / cmd).is_file()


def _venv_package_exists(data_root: Path, venv_name: str, pkg_prefix: str) -> bool:
    venv_dir = data_root / "venvs" / venv_name
    site_candidates = [venv_dir / "Lib" / "site-packages"]
    lib_dir = venv_dir / "lib"
    if lib_dir.is_dir():
        site_candidates.extend(lib_dir.glob("python*/site-packages"))
    for sp in site_candidates:
        if sp.is_dir() and any(sp.glob(f"{pkg_prefix}*")):
            return True
    return False


def _lot_status(lot_id: str, is_ok: bool, selected_lots: set[str]) -> str:
    if is_ok:
        return "ok"
    if lot_id in selected_lots:
        return "failed"
    return "not_selected"


def collect_verify(
    catalog: dict[str, Any] | None = None,
    *,
    home: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Run live Doctor healthcheck across core tools, all 5 Lots, rules, guides, and harnesses."""
    cat: dict[str, Any]
    if catalog is not None:
        cat = catalog
    else:
        try:
            cat = load_catalog()
        except SetupError:
            cat = {}

    app_ver = get_app_version(cat if cat else None)
    base_home = home or Path.home()
    data_root = app_root or get_data_root()
    state = load_state(data_root)
    selected_lots = {lot for lot in state.get("installed_lots", []) if lot in VALID_LOTS}

    pre = collect_preflight()
    tools = pre["tools"]
    ides = detect_ides(home=base_home)

    ag_skills = Path(ides["antigravity"]["skills_dir"])
    ag_rules = Path(ides["antigravity"]["rules_dir"])
    ag_plugins = Path(ides["antigravity"]["plugins_dir"])

    core_tools = {
        "python": tools["python"],
        "uv": tools["uv"],
        "node": tools["node"],
        "git": tools["git"],
        "gh": tools["gh"],
    }

    # Lot 1 · Content
    l1_venv = _venv_bin_exists(data_root, "content", "python")
    l1_hum = (ag_skills / "humanizer-vi" / "SKILL.md").is_file()
    l1_trans = (ag_skills / "translationese-cleaner-vi" / "SKILL.md").is_file()
    l1_ok = l1_venv and l1_hum and l1_trans

    # Lot 2 · Edit Video
    l2_ffmpeg = bool(tools["ffmpeg"]["installed"]) or (data_root / "bin" / "ffmpeg.exe").is_file()
    l2_venv = _venv_bin_exists(data_root, "media", "python")
    l2_ae = _venv_bin_exists(data_root, "media", "auto-editor")
    l2_rv = _venv_bin_exists(data_root, "media", "rea-video") or (ag_skills / "rea-video" / "SKILL.md").is_file()
    l2_ffskill = (ag_skills / "ffmpeg-skill" / "SKILL.md").is_file()
    l2_sound = (ag_skills / "sound-design" / "SKILL.md").is_file()
    l2_picker = (ag_skills / "media-picker" / "SKILL.md").is_file()
    l2_ok = l2_ffmpeg and l2_venv and l2_ae and l2_rv and l2_ffskill and l2_sound and l2_picker

    # Lot 3 · Code (B3: superpowers manifest check supports .antigravity-plugin/plugin.json)
    l3_venv = _venv_bin_exists(data_root, "dev", "python")
    l3_ruff = _venv_bin_exists(data_root, "dev", "ruff")
    l3_pytest = _venv_bin_exists(data_root, "dev", "pytest")
    sp_dir = ag_plugins / "superpowers"
    sp_manifest_ok = any((sp_dir / m).is_file() for m in SUPERPOWERS_MANIFEST_CANDIDATES)
    sp_skills_dir = sp_dir / "skills"
    sp_skills_ok = sp_skills_dir.is_dir() and any(sp_skills_dir.iterdir())
    l3_sp = sp_manifest_ok and sp_skills_ok
    l3_karpathy = (ag_skills / "karpathy-guidelines" / "SKILL.md").is_file()
    l3_mwg = (ag_skills / "modern-web-guidance" / "SKILL.md").is_file()
    l3_ok = l3_venv and l3_ruff and l3_pytest and l3_sp and l3_karpathy and l3_mwg

    # Lot 4 · Data & Research
    l4_venv = _venv_bin_exists(data_root, "data", "python")
    l4_ytdlp = _venv_bin_exists(data_root, "data", "yt-dlp")
    l4_markitdown = _venv_bin_exists(data_root, "data", "markitdown")
    l4_trendspyg = _venv_package_exists(data_root, "data", "trendspyg")
    l4_rea = bool(tools["rea"]["installed"])
    l4_ok = l4_venv and l4_ytdlp and l4_markitdown and l4_trendspyg and l4_rea

    # Lot 5 · EGM Blind Review
    egm_spec = cat.get("lot5_review", {}).get("egm", {})
    req_skills = list(
        egm_spec.get(
            "required_skills",
            [
                "egm-bootstrap",
                "egm-brainstorm",
                "egm-draft",
                "egm-drift-report",
                "egm-lite",
                "egm-resolve",
                "egm-review",
                "egm-review-loop",
            ],
        )
    )
    req_agents = int(egm_spec.get("required_agent_count", 10))
    req_standards = int(egm_spec.get("required_standard_count", 5))
    egm_dir = ag_plugins / "egm"
    egm_plugin_ok = (egm_dir / "plugin.json").is_file()
    egm_license_ok = (egm_dir / "LICENSE").is_file()
    egm_present_skills = [s for s in req_skills if (egm_dir / "skills" / s / "SKILL.md").is_file()]
    egm_agents_count = len(list((egm_dir / "agents").glob("*.md"))) if (egm_dir / "agents").is_dir() else 0
    egm_standards_count = (
        len(list((egm_dir / "resources" / "document_standards").glob("*.md")))
        if (egm_dir / "resources" / "document_standards").is_dir()
        else 0
    )
    egm_unified_ok = (data_root / "plugins" / "egm" / "plugin.json").is_file()
    l5_ok = (
        egm_plugin_ok
        and egm_license_ok
        and len(egm_present_skills) == len(req_skills)
        and egm_agents_count >= req_agents
        and egm_standards_count >= req_standards
    )

    # Live harness probe merged with persisted registration state
    saved_harnesses = state.get("egm_harnesses", {}) if isinstance(state.get("egm_harnesses"), dict) else {}
    claude_installed = _claude_plugin_installed(base_home / ".claude" / "plugins" / "installed_plugins.json", "egm@egm")
    codex_installed = _codex_plugin_configured(base_home / ".codex" / "config.toml", "egm")
    egm_harnesses = {
        "antigravity": "installed" if l5_ok else "missing",
        "claude_code": "installed" if claude_installed else saved_harnesses.get("claude_code", "not_installed"),
        "codex": "installed" if codex_installed else saved_harnesses.get("codex", "not_installed"),
    }

    lots = {
        "lot1": {
            "status": _lot_status("lot1", l1_ok, selected_lots),
            "details": {
                "venv_content": l1_venv,
                "humanizer_vi": l1_hum,
                "translationese_cleaner_vi": l1_trans,
            },
        },
        "lot2": {
            "status": _lot_status("lot2", l2_ok, selected_lots),
            "details": {
                "ffmpeg": l2_ffmpeg,
                "venv_media": l2_venv,
                "auto_editor": l2_ae,
                "rea_video": l2_rv,
                "ffmpeg_skill": l2_ffskill,
                "sound_design": l2_sound,
                "media_picker": l2_picker,
            },
        },
        "lot3": {
            "status": _lot_status("lot3", l3_ok, selected_lots),
            "details": {
                "venv_dev": l3_venv,
                "ruff": l3_ruff,
                "pytest": l3_pytest,
                "superpowers": l3_sp,
                "superpowers_manifest": sp_manifest_ok,
                "superpowers_skills": sp_skills_ok,
                "karpathy_guidelines": l3_karpathy,
                "modern_web_guidance": l3_mwg,
            },
        },
        "lot4": {
            "status": _lot_status("lot4", l4_ok, selected_lots),
            "details": {
                "venv_data": l4_venv,
                "yt_dlp": l4_ytdlp,
                "trendspyg": l4_trendspyg,
                "markitdown": l4_markitdown,
                "rea": l4_rea,
            },
        },
        "lot5": {
            "status": _lot_status("lot5", l5_ok, selected_lots),
            "skills_count": len(egm_present_skills),
            "agents_count": egm_agents_count,
            "standards_count": egm_standards_count,
            "harnesses": egm_harnesses,
            "details": {
                "plugin_json": egm_plugin_ok,
                "license": egm_license_ok,
                "skills_present": len(egm_present_skills),
                "skills_required": len(req_skills),
                "missing_skills": [s for s in req_skills if s not in egm_present_skills],
                "agents_count": egm_agents_count,
                "agents_required": req_agents,
                "standards_count": egm_standards_count,
                "standards_required": req_standards,
                "unified_bundle": egm_unified_ok,
                "harnesses": egm_harnesses,
            },
        },
    }

    # Rules & Guides
    docs_dir = get_documents_dir(home=home)
    guides_dest = docs_dir / "Studio AI Setup" / "Chi-Dan"
    guide_files = sorted(p.name for p in guides_dest.glob("*.md")) if guides_dest.is_dir() else []
    guides_ok = (guides_dest / "00-BAT-DAU-NHANH.md").is_file()
    agents_md_ok = (ag_rules / "AGENTS.md").is_file()
    gemini_md_ok = (ag_rules / "GEMINI.md").is_file()
    rules_status = state.get("rules_status", {}) if isinstance(state.get("rules_status"), dict) else {}
    rules_details = state.get("rules_details", []) if isinstance(state.get("rules_details"), list) else []
    preserved_custom_rules = [d for d in rules_details if isinstance(d, dict) and d.get("status") == "preserved_user_custom"]

    rules_and_guides = {
        "AGENTS.md": agents_md_ok,
        "GEMINI.md": gemini_md_ok,
        "rules_status": rules_status,
        "preserved_custom_rules": preserved_custom_rules,
        "guides_ok": guides_ok,
        "guides_files": guide_files,
        "guides_dir": str(guides_dest),
        "documents_dir": str(docs_dir),
        "state_version": state.get("app_version"),
    }

    # Plain-Vietnamese user-facing warnings
    warnings: list[str] = []
    if lots["lot5"]["status"] == "ok":
        warnings.append(
            "Lưu ý EGM: Chế độ phản biện mù Goldfish cần ứng dụng hỗ trợ subagent tươi "
            "(Antigravity App, Antigravity for IDEs trên VS Code, agy CLI, Claude Code >=2.1.271, hoặc Codex CLI). "
            "Antigravity IDE độc lập nạp thông tin plugin nhưng chưa chạy được subagent."
        )
        for h_key, h_label in (("claude_code", "Claude Code"), ("codex", "Codex CLI")):
            h_st = egm_harnesses.get(h_key)
            if h_st in ("manual_required", "already_configured_marketplace"):
                warnings.append(
                    f"EGM trên {h_label} chưa tự đăng ký xong ({h_st}) — xem lệnh đăng ký thủ công trong "
                    "Chi-Dan\\05-lo-phan-bien-egm.md."
                )
    if preserved_custom_rules or any(v == "preserved_user_custom" for v in rules_status.values()):
        warnings.append(
            "Tệp quy tắc cá nhân hóa (AGENTS.md / GEMINI.md) của bạn đã được giữ nguyên; "
            "bản tham khảo v2 được lưu an toàn trong %LOCALAPPDATA%\\StudioAISetup\\backups\\."
        )

    core_base_ok = bool(tools["python"]["installed"] and tools["node"]["supported"] and tools["git"]["installed"])
    no_failed_lots = all(info["status"] != "failed" for info in lots.values())

    return {
        "ok": core_base_ok and no_failed_lots,
        "app_version": app_ver,
        "core_tools": core_tools,
        "lots": lots,
        "rules_and_guides": rules_and_guides,
        "warnings": warnings,
        # Backwards-compatible summary fields
        "guides_dir": str(guides_dest),
        "guides_ready": guides_ok,
        "rules_ready": agents_md_ok,
        "tools": tools,
        "ides": ides,
    }


def interactive_fallback() -> int:
    """Friendly Vietnamese CLI fallback when WPF GUI cannot launch."""
    catalog = load_catalog()
    app_ver = get_app_version(catalog)
    print("=" * 72)
    print(f"  STUDIO AI SETUP v{app_ver} — TRÌNH CÀI ĐẶT DỰ PHÒNG (CHẾ ĐỘ DÒNG LỆNH)")
    print("=" * 72)
    pre = collect_preflight()
    print(f"  Hệ điều hành : {pre['os']} {pre['os_release']} ({pre['arch']})")
    print(f"  RAM / Ổ trống : {pre['ram_gb']} GB / {pre['free_disk_gb']} GB")

    prev_state = load_state()
    default_name = prev_state.get("user_name") or "bạn"
    raw_name = input(f"  [?] AI sẽ gọi bạn là gì? [Enter = '{default_name}']: ").strip()
    user_name = sanitize_user_name(raw_name if raw_name else default_name)

    ans = input(
        "  [?] Bắt đầu cài cả 5 Lô khuyên dùng (Content, Edit Video, Code, Cào dữ liệu, Phản biện EGM)? [y/N]: "
    ).strip().lower()
    if ans not in ("y", "yes", "co", "có"):
        print("  Đã hủy. Không có thay đổi nào được ghi lên máy.")
        return 0

    succeeded_lots: list[str] = []
    steps: list[tuple[str, str, Callable[[], Any]]] = [
        ("lot1", "Lô 1 · Content", lambda: install_lot1(catalog)),
        ("lot2", "Lô 2 · Edit Video", lambda: install_lot2(catalog)),
        ("lot3", "Lô 3 · Code", lambda: install_lot3(catalog)),
        ("lot4", "Lô 4 · Cào & Nghiên cứu", lambda: install_lot4(catalog)),
        ("lot5", "Lô 5 · Phản biện & Kiểm chứng (EGM)", lambda: install_lot5(catalog)),
    ]
    for lot_id, label, fn in steps:
        print(f"  [*] Đang chạy: {label}...")
        try:
            fn()
            succeeded_lots.append(lot_id)
            print(f"  [OK] Xong: {label}")
        except SetupError as exc:
            print(f"  [!] Lỗi ở {label}: {exc}")

    print("  [*] Đang cập nhật Quy tắc AI & chép 5 Bộ Chỉ Dẫn...")
    try:
        finalize_setup(catalog, user_name=user_name, installed_lots=succeeded_lots)
        print("  [OK] Xong: Quy tắc & 5 Bộ Chỉ Dẫn")
    except SetupError as exc:
        print(f"  [!] Lỗi ở bước hoàn tất: {exc}")

    v = collect_verify(catalog)
    print("\n  --- KIỂM TRA SỨC KHỎE HỆ THỐNG (DOCTOR) ---")
    for lot_id in VALID_LOTS:
        st = v["lots"][lot_id]["status"]
        print(f"  - {lot_id.upper()}: {st}")
    l5_det = v["lots"]["lot5"]["details"]
    if v["lots"]["lot5"]["status"] == "ok":
        print(
            f"    EGM Antigravity: {l5_det['skills_present']}/{l5_det['skills_required']} skills · "
            f"{l5_det['agents_count']} agents · {l5_det['standards_count']} standards"
        )
    for warn in v.get("warnings", []):
        print(f"  [!] {warn}")
    print(f"\n  [HOÀN TẤT] Thư mục chỉ dẫn đã sẵn sàng tại: {v['guides_dir']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Studio AI Setup Engine")
    p.add_argument("--preflight-json", action="store_true", help="Emit machine hardware & tool probe JSON")
    p.add_argument("--verify-json", action="store_true", help="Emit post-install Doctor verification JSON")
    p.add_argument(
        "--install-lot",
        choices=("lot1", "lot2", "lot3", "lot4", "lot5", "finalize"),
        help="Install one specific Lot or run finalize",
    )
    p.add_argument("--lots", default=None, help="Comma-separated list of succeeded lot IDs for finalize state.json")
    p.add_argument("--user-name", default=None, help="Display name for AI rules")
    p.add_argument("--opt-openmontage", action="store_true", help="Include optional OpenMontage in lot2")
    p.add_argument("--opt-assetfurnace", action="store_true", help="Include optional AssetFurnace 3D in lot2")
    p.add_argument("--opt-agent-reach", action="store_true", help="Include optional Agent-Reach in lot4")
    p.add_argument("--force-gpu", action="store_true", help="Override NVIDIA GPU check for optional 3D tool")
    p.add_argument("--dry-run", action="store_true", help="Plan only without downloading or writing files")
    p.add_argument("--json", action="store_true", help="Print JSON output")
    p.add_argument("--interactive", action="store_true", help="Run friendly Vietnamese CLI fallback")
    p.add_argument("--backup", action="store_true", help="Create a SHA-256 verified configuration snapshot ZIP")
    p.add_argument("--snapshot-out", default=None, help="Optional custom output path for --backup")
    p.add_argument("--list-backups", action="store_true", help="List available configuration snapshots newest-first")
    p.add_argument(
        "--restore",
        default=None,
        metavar="PATH_OR_LATEST",
        help="Verify SHA-256 and atomically restore a configuration snapshot ('latest' or ZIP path)",
    )
    return p


def _resolve_finalize_user_name(cli_user_name: str | None) -> str:
    """Resolve display name via strict priority: --user-name -> STUDIO_AI_USER_NAME -> state.json -> 'bạn'."""
    if cli_user_name is not None and cli_user_name.strip():
        return sanitize_user_name(cli_user_name)
    env_name = os.environ.get("STUDIO_AI_USER_NAME")
    if env_name is not None and env_name.strip():
        return sanitize_user_name(env_name)
    prev = load_state()
    saved_name = prev.get("user_name")
    if isinstance(saved_name, str) and saved_name.strip():
        return sanitize_user_name(saved_name)
    return "bạn"


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
        if args.backup:
            res = create_snapshot_backup(out_path=args.snapshot_out)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                print(
                    f"[OK] Đã tạo bản sao lưu cấu hình ({res['file_count']} tệp): {res['snapshot_path']}\n"
                    f"     SHA-256: {res['archive_sha256']}"
                )
            return 0
        if args.list_backups:
            res = list_snapshots()
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                snaps = res["snapshots"]
                if not snaps:
                    print(f"Chưa có bản sao lưu nào trong: {res['snapshots_dir']}")
                else:
                    print(f"Danh sách bản sao lưu ({res['count']}) tại {res['snapshots_dir']}:")
                    for item in snaps:
                        ts_label = item.get("created_at_utc") or "unknown"
                        print(
                            f"  - {item['filename']} | {ts_label} | {item['size']} bytes | "
                            f"SHA-256: {item['sha256'][:12]}..."
                        )
            return 0
        if args.restore is not None:
            res = restore_snapshot_backup(args.restore, dry_run=args.dry_run)
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
            elif args.dry_run:
                print(
                    f"[OK] Kiểm tra toàn vẹn SHA-256 đạt (dry-run, chưa ghi tệp): {res['snapshot_path']}\n"
                    f"     Sẽ khôi phục ({len(res['would_restore'])} tệp): {', '.join(res['would_restore'])}"
                )
            else:
                bak_note = f"\n     Bản dự phòng cũ: {res['backup_dir']}" if res.get("backup_dir") else ""
                print(
                    f"[OK] Đã xác thực SHA-256 và khôi phục ({len(res['restored'])} tệp) từ: "
                    f"{res['snapshot_path']}{bak_note}"
                )
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
                res = install_lot3(catalog, dry_run=args.dry_run)
            elif args.install_lot == "lot4":
                res = install_lot4(catalog, opt_agent_reach=args.opt_agent_reach, dry_run=args.dry_run)
            elif args.install_lot == "lot5":
                res = install_lot5(catalog, dry_run=args.dry_run)
            else:
                effective_name = _resolve_finalize_user_name(args.user_name)
                lots_list = parse_lots_arg(args.lots)
                res = finalize_setup(
                    catalog,
                    user_name=effective_name,
                    installed_lots=lots_list,
                    dry_run=args.dry_run,
                )
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
