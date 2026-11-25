#!/usr/bin/env python3
"""Studio AI Setup — Clean Release Packager & AK Kit V3 Security Sanitizer.

Stages ONLY the verified allowlist into dist/Studio-AI-Setup-v<version>/, verifies
cross-file version parity, runs multi-layer secrets, PII, internal path, zero-brand,
dangerous-file, and code-security audits, and emits a deterministic reproducible
Studio-AI-Setup-v<version>.zip + SHA256SUMS.txt + SECURITY-AUDIT.md only on 0 CRITICAL.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

_UTC = getattr(_dt, "UTC", None) or _dt.timezone(_dt.timedelta(0))

ROOT = Path(__file__).resolve().parents[1]
MAX_ZIP_BYTES = 500 * 1024
REPRODUCIBLE_ZIP_DATE = (2026, 11, 25, 0, 0, 0)

ALLOWLIST_FILES = (
    "cai-dat.bat",
    "README.md",
    "LICENSE",
    "DISCLAIMER.md",
    "THIRD-PARTY-NOTICES.md",
    "catalog-lock.json",
    "brand/studio-ai.ico",
    "brand/studio-ai.png",
    "scripts/cai-dat.ps1",
    "scripts/hop-thong-bao.ps1",
    "scripts/tai-nen-tang.ps1",
    "engine/setup_engine.py",
    "templates/rules/AGENTS.md",
    "templates/rules/GEMINI.md",
    "chi-dan/00-BAT-DAU-NHANH.md",
    "chi-dan/01-lo-content.md",
    "chi-dan/02-lo-edit-video.md",
    "chi-dan/03-lo-code.md",
    "chi-dan/04-lo-cao-du-lieu.md",
    "chi-dan/05-lo-phan-bien-egm.md",
)

TEXT_EXTENSIONS = {".py", ".ps1", ".bat", ".cmd", ".md", ".json", ".txt", ".yml", ".yaml", ".toml"}
CODE_EXTENSIONS = {".py", ".ps1", ".bat", ".cmd"}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("API key/secret assignment", re.compile(r"""[A-Za-z0-9_]*(?:api[_-]?key|apikey|api[_-]?secret)[A-Za-z0-9_]*\s*[=:]\s*['"]?[A-Za-z0-9+/=_-]{16,}""")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(r"""(?i)(?:aws_secret_access_key|aws_secret)\s*[=:]\s*['"]?[A-Za-z0-9+/=]{20,}""")),
    ("Database credential URL", re.compile(r"""(?:postgres|mysql|mongodb|redis)://[^:\s'"]+:[^@\s'"]+@[^\s'"]+""")),
    ("JWT token", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+")),
    ("Private key PEM", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("Google OAuth secret", re.compile(r"GOCSPX-[A-Za-z0-9_-]+")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+")),
    ("SendGrid/Mailgun key", re.compile(r"(?:SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}|key-[A-Za-z0-9]{32})")),
]

PII_AND_PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Personal email address", re.compile(r"[a-zA-Z0-9._%+-]+@(?:gmail|yahoo|hotmail|outlook|protonmail|icloud)\.(?:com|net|org)")),
    ("Private internal IPv4", re.compile(r"\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b")),
    ("Hardcoded Windows user path", re.compile(r"C:[\\/]+Users[\\/]+[A-Za-z][A-Za-z0-9_.-]*")),
    ("Hardcoded macOS user path", re.compile(r"/Users/[A-Za-z][A-Za-z0-9_-]*/")),
    ("Hardcoded Linux home path", re.compile(r"/home/[a-z][a-z0-9_-]*/")),
    ("Internal quarantine path", re.compile(r"(?i)D:[\\/]+_CACH-LY|D:[\\/]+SKILL_ARCHIVE|E:[\\/]+BYPASS")),
]

# Built programmatically so build-release.py itself keeps zero plaintext triggers if scanned externally
BRAND_AND_SAFETY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Brand leak", re.compile(r"(?i)\b(?:" + "|".join([
        "go" + "ha",
        "nguyen" + "hieuai",
        "hieu" + "pi",
        "kaze" + "lab",
    ]) + r")\b")),
    ("Personal identity leak", re.compile(r"(?i)\b(?:" + "|".join([
        "b\u1ed1" + " t\u00fa",
        "\u0111\u1ea1i" + " ca",
    ]) + r")\b")),
    ("Red-team / evasion leak", re.compile(r"(?i)(?:" + "|".join([
        "filter-by" + "pass",
        "amsi_et" + "w",
        "shell" + "code",
        "ntdll_un" + "hook",
    ]) + r")")),
]

CODE_SECURITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Unsafe shell=True", re.compile(r"\bshell\s*=\s*True\b")),
    ("Piped curl install", re.compile(r"(?i)curl\s+[^|\n]*\|\s*(?:ba)?sh\b")),
    ("Invoke-Expression / iex", re.compile(r"(?i)(?:Invoke-Expression|\biex\b)")),
    ("Unpinned @latest package", re.compile(r"@latest\b")),
]

DANGEROUS_FILENAMES = {
    ".env", ".env.local", ".env.production", "credentials.json",
}
DANGEROUS_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".exe", ".dll", ".map")
DANGEROUS_DIRS = {".git", ".secrets", "secrets", "node_modules", "__pycache__", ".venv", "venv", "sessions"}


def load_app_version(src_root: Path = ROOT) -> str:
    """Read app_version from catalog-lock.json as the single source of truth."""
    catalog_path = src_root / "catalog-lock.json"
    if not catalog_path.is_file():
        raise FileNotFoundError(f"catalog-lock.json missing: {catalog_path}")
    data = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    version = data.get("app_version") if isinstance(data, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Missing or invalid app_version in {catalog_path}")
    return version.strip()


APP_VERSION = load_app_version(ROOT)
RELEASE_NAME = f"Studio-AI-Setup-v{APP_VERSION}"


def check_version_parity(src_root: Path, expected_version: str) -> list[dict[str, Any]]:
    """Verify catalog-lock.json, README.md, and test-in-windows-sandbox.wsb match expected_version."""
    findings: list[dict[str, Any]] = []
    expected = expected_version.strip()

    # 1. catalog-lock.json
    cat_path = src_root / "catalog-lock.json"
    if not cat_path.is_file():
        findings.append({
            "severity": "CRITICAL",
            "category": "Version Parity",
            "file": "catalog-lock.json",
            "line": 0,
            "detail": "Missing catalog-lock.json",
        })
    else:
        try:
            cat_data = json.loads(cat_path.read_text(encoding="utf-8-sig"))
            actual_ver = cat_data.get("app_version") if isinstance(cat_data, dict) else None
            if actual_ver != expected:
                findings.append({
                    "severity": "CRITICAL",
                    "category": "Version Parity",
                    "file": "catalog-lock.json",
                    "line": 1,
                    "detail": f"app_version={actual_ver!r} != expected {expected!r}",
                })
        except (OSError, ValueError) as exc:
            findings.append({
                "severity": "CRITICAL",
                "category": "Version Parity",
                "file": "catalog-lock.json",
                "line": 0,
                "detail": f"Invalid JSON: {exc}",
            })

    # 2. README.md first heading
    readme_path = src_root / "README.md"
    expected_heading = f"# Studio AI Setup v{expected}"
    if not readme_path.is_file():
        findings.append({
            "severity": "CRITICAL",
            "category": "Version Parity",
            "file": "README.md",
            "line": 0,
            "detail": "Missing README.md",
        })
    else:
        lines = readme_path.read_text(encoding="utf-8-sig").splitlines()
        first_heading = next(((idx, ln.strip()) for idx, ln in enumerate(lines, 1) if ln.strip().startswith("#")), None)
        if first_heading is None:
            findings.append({
                "severity": "CRITICAL",
                "category": "Version Parity",
                "file": "README.md",
                "line": 1,
                "detail": f"Missing top heading; expected {expected_heading!r}",
            })
        elif first_heading[1] != expected_heading:
            findings.append({
                "severity": "CRITICAL",
                "category": "Version Parity",
                "file": "README.md",
                "line": first_heading[0],
                "detail": f"Heading {first_heading[1]!r} != expected {expected_heading!r}",
            })

    # 3. test-in-windows-sandbox.wsb (kept OUT of ALLOWLIST_FILES, checked in src_root)
    wsb_path = src_root / "test-in-windows-sandbox.wsb"
    expected_wsb_token = f"Studio-AI-Setup-v{expected}"
    if not wsb_path.is_file():
        findings.append({
            "severity": "CRITICAL",
            "category": "Version Parity",
            "file": "test-in-windows-sandbox.wsb",
            "line": 0,
            "detail": "Missing test-in-windows-sandbox.wsb",
        })
    else:
        wsb_text = wsb_path.read_text(encoding="utf-8-sig")
        if expected_wsb_token not in wsb_text:
            findings.append({
                "severity": "CRITICAL",
                "category": "Version Parity",
                "file": "test-in-windows-sandbox.wsb",
                "line": 1,
                "detail": f"Expected {expected_wsb_token!r} in HostFolder path",
            })

    return findings


def audit_directory(target_root: Path) -> dict[str, Any]:
    """Audit every file inside target_root and return structured PASS/FAIL findings."""
    findings: list[dict[str, Any]] = []
    scanned_files = 0

    for item in sorted(target_root.rglob("*")):
        rel = item.relative_to(target_root).as_posix()
        parts = set(item.relative_to(target_root).parts)

        if any(bad_dir in parts for bad_dir in DANGEROUS_DIRS):
            findings.append({"severity": "CRITICAL", "category": "Dangerous Directory", "file": rel, "line": 0, "detail": "Forbidden directory present"})
            continue
        if item.is_dir():
            continue

        scanned_files += 1
        fname = item.name.lower()
        if fname in DANGEROUS_FILENAMES or fname.startswith(".env.") or fname.endswith(DANGEROUS_SUFFIXES) or ".bak" in fname:
            findings.append({"severity": "CRITICAL", "category": "Dangerous File", "file": rel, "line": 0, "detail": f"Forbidden file type/name: {item.name}"})
            continue

        suffix = item.suffix.lower()
        if suffix not in TEXT_EXTENSIONS and item.name != "LICENSE":
            continue

        try:
            text = item.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            findings.append({"severity": "CRITICAL", "category": "Encoding", "file": rel, "line": 0, "detail": "Non-UTF8 text file"})
            continue

        checks = list(SECRET_PATTERNS) + list(PII_AND_PATH_PATTERNS) + list(BRAND_AND_SAFETY_PATTERNS)
        if suffix in CODE_EXTENSIONS:
            checks.extend(CODE_SECURITY_PATTERNS)

        for lineno, line_text in enumerate(text.splitlines(), 1):
            for cat, pat in checks:
                if pat.search(line_text):
                    findings.append({
                        "severity": "CRITICAL",
                        "category": cat,
                        "file": rel,
                        "line": lineno,
                        "detail": line_text.strip()[:120],
                    })

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    return {
        "verdict": "PASS" if critical_count == 0 else "FAIL",
        "scanned_files": scanned_files,
        "critical_count": critical_count,
        "findings": findings,
    }


def stage_release(src_root: Path, stage_dir: Path) -> int:
    """Copy ONLY the verified allowlist into stage_dir."""
    if stage_dir.exists():
        try:
            shutil.rmtree(stage_dir)
        except OSError:
            # Windows Sandbox shares keep the mapped directory handle open, so clean children in place
            for child in list(stage_dir.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    stage_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for rel_posix in ALLOWLIST_FILES:
        src = src_root / rel_posix
        if not src.is_file():
            raise FileNotFoundError(f"Allowlist file missing: {src}")
        dst = stage_dir / rel_posix
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def create_zip(stage_dir: Path, zip_path: Path, release_name: str | None = None) -> tuple[int, str]:
    """Create byte-for-byte deterministic reproducible ZIP and return (size_bytes, sha256_hex)."""
    prefix = release_name or RELEASE_NAME
    if zip_path.exists():
        zip_path.unlink()
    files = sorted(
        (p for p in stage_dir.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(stage_dir).as_posix(),
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in files:
            arcname = f"{prefix}/{file_path.relative_to(stage_dir).as_posix()}"
            zi = zipfile.ZipInfo(arcname, date_time=REPRODUCIBLE_ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3
            zi.external_attr = 0o644 << 16
            zf.writestr(
                zi,
                file_path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    raw = zip_path.read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest()


def write_sha256sums(sums_path: Path, zip_path: Path, zip_sha256: str) -> None:
    """Write standard UTF-8 LF SHA256SUMS.txt for the release archive."""
    sums_path.write_bytes(f"{zip_sha256}  {zip_path.name}\n".encode())


def write_audit_report(
    report_path: Path,
    audit: dict[str, Any],
    zip_path: Path | None,
    zip_size: int,
    zip_sha256: str,
    release_name: str | None = None,
) -> None:
    """Write human-readable AK Kit V3 SECURITY-AUDIT.md summary."""
    rel_label = release_name or RELEASE_NAME
    now = datetime.now(_UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Security & Sanitization Audit Report — {rel_label}",
        "",
        f"- **Generated:** `{now}`",
        f"- **Scanned Files:** `{audit['scanned_files']}`",
        f"- **Critical Findings:** `{audit['critical_count']}`",
        f"- **VERDICT:** **{audit['verdict']} ({audit['critical_count']} CRITICAL)**",
    ]
    if zip_path and audit["critical_count"] == 0:
        lines.extend([
            f"- **Release Artifact:** `{zip_path.name}`",
            f"- **Archive Size:** `{zip_size:,} bytes` (`{zip_size / 1024:.1f} KB` / limit `{MAX_ZIP_BYTES // 1024} KB`)",
            f"- **Archive SHA-256:** `{zip_sha256}`",
        ])
    lines.append("")
    if audit["findings"]:
        lines.append("## Findings")
        for f in audit["findings"]:
            lines.append(f"- `[{f['severity']}]` **{f['category']}** at `{f['file']}:{f['line']}` — `{f['detail']}`")
    else:
        lines.extend([
            "## Checks Passed",
            "- Version parity check (`catalog-lock.json`, `README.md`, `test-in-windows-sandbox.wsb`): **0 findings**",
            "- Secrets scan (API keys, AWS, DB URLs, JWT, private keys, GitHub/Google tokens): **0 findings**",
            "- PII & internal machine paths scan (`C:\\Users\\...`, internal drives, personal emails): **0 findings**",
            "- Zero-brand & safety scan (zero proprietary branding, zero evasion/red-team terms): **0 findings**",
            "- Dangerous files check (`.env`, `.exe`, `.dll`, `.key`, `.bak`, `node_modules`, `.venv`): **0 findings**",
            "- Code security pattern check (`shell=True`, `curl | bash`, `Invoke-Expression`, `@latest`): **0 findings**",
        ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except OSError:
            pass
    parser = argparse.ArgumentParser(description="Build clean Studio AI Setup ZIP with AK Kit V3 security audit")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist", help="Output directory (default: dist/)")
    parser.add_argument("--src-root", type=Path, default=ROOT, help="Source repository root (default: repo root)")
    args = parser.parse_args(argv)

    src_root = args.src_root.resolve()
    app_version = load_app_version(src_root)
    release_name = f"Studio-AI-Setup-v{app_version}"

    out_dir = args.out_dir.resolve()
    stage_dir = out_dir / release_name
    zip_path = out_dir / f"{release_name}.zip"
    sums_path = out_dir / "SHA256SUMS.txt"
    audit_path = out_dir / "SECURITY-AUDIT.md"

    copied = stage_release(src_root, stage_dir)
    audit = audit_directory(stage_dir)
    parity_findings = check_version_parity(src_root, app_version)
    if parity_findings:
        audit["findings"].extend(parity_findings)
        audit["critical_count"] = sum(1 for f in audit["findings"] if f["severity"] == "CRITICAL")
        audit["verdict"] = "PASS" if audit["critical_count"] == 0 else "FAIL"

    if audit["critical_count"] > 0:
        write_audit_report(audit_path, audit, None, 0, "", release_name=release_name)
        print(f"SECURITY AUDIT FAILED: {audit['critical_count']} critical finding(s):", file=sys.stderr)
        for f in audit["findings"]:
            print(f"  - [{f['category']}] {f['file']}:{f['line']} -> {f['detail']}", file=sys.stderr)
        return 1

    zip_size, zip_sha256 = create_zip(stage_dir, zip_path, release_name=release_name)
    if zip_size > MAX_ZIP_BYTES:
        if zip_path.exists():
            zip_path.unlink()
        print(f"ERROR: Release ZIP exceeded {MAX_ZIP_BYTES} bytes ({zip_size} bytes).", file=sys.stderr)
        return 1

    write_sha256sums(sums_path, zip_path, zip_sha256)
    write_audit_report(audit_path, audit, zip_path, zip_size, zip_sha256, release_name=release_name)
    print(f"Staged files : {copied}")
    print(f"Audit verdict: {audit['verdict']} ({audit['critical_count']} CRITICAL)")
    print(f"Archive path : {zip_path}")
    print(f"Archive size : {zip_size:,} bytes ({zip_size / 1024:.1f} KB)")
    print(f"Archive SHA256: {zip_sha256}")
    print(f"SHA256SUMS   : {sums_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
