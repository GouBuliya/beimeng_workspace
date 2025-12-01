"""
@PURPOSE: 自定义安装器, 将 TemuWebPanel.exe 拷贝到目标目录并创建桌面快捷方式
@OUTLINE:
  - Typer CLI: 安装目录、是否创建快捷方式
  - 复制打包内置的 TemuWebPanel.exe 到目标目录
  - 通过 PowerShell 创建桌面快捷方式
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import typer

try:  # pragma: no cover - Windows specific enhancement
    import winreg  # type: ignore
except Exception:  # pragma: no cover - non Windows environments
    winreg = None

try:  # pragma: no cover - Windows specific enhancement
    import ctypes
except Exception:  # pragma: no cover - non Windows environments
    ctypes = None

APP_NAME: Final[str] = "TemuWebPanel"
PAYLOAD_DIR: Final[str] = "payload"
PAYLOAD_EXE: Final[str] = "TemuWebPanel.exe"
DESKTOP_SHORTCUT: Final[str] = f"{APP_NAME}.lnk"
DEFAULT_INSTALL_DIR: Final[Path] = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / APP_NAME
)
FALLBACK_INSTALL_DIR: Final[Path] = Path.home() / "AppData" / "Local" / APP_NAME

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent


def _payload_path() -> Path:
    payload = _resource_dir() / PAYLOAD_DIR / PAYLOAD_EXE
    if not payload.exists():
        raise FileNotFoundError(f"内置可执行文件缺失: {payload}")
    return payload


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ps_escape(value: Path) -> str:
    return str(value).replace("'", "''")


def _query_shell_folder(value_name: str) -> Path | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            path = Path(value).expanduser()
            if path.exists():
                return path
    except OSError:
        return None
    return None


def _query_known_folder_desktop() -> Path | None:
    if ctypes is None:
        return None
    try:
        CSIDL_DESKTOPDIRECTORY = 0x0010
        buffer = ctypes.create_unicode_buffer(260)
        result = ctypes.windll.shell32.SHGetFolderPathW(  # type: ignore[attr-defined]
            0,
            CSIDL_DESKTOPDIRECTORY,
            0,
            0,
            buffer,
        )
        if result == 0:
            path = Path(buffer.value).expanduser()
            if path.exists():
                return path
    except Exception:
        return None
    return None


def _find_desktop_dir() -> Path:
    candidates: list[Path | None] = [
        _query_shell_folder("Desktop"),
        _query_known_folder_desktop(),
    ]

    home = Path.home().expanduser()
    user_profile = Path(os.environ.get("USERPROFILE") or home).expanduser()

    candidates.extend(
        [
            home / "Desktop",
            home / "桌面",
            user_profile / "Desktop",
            user_profile / "桌面",
        ],
    )

    for env_name in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        base = os.environ.get(env_name)
        if base:
            base_path = Path(base).expanduser()
            candidates.append(base_path / "Desktop")
            candidates.append(base_path / "桌面")

    public = os.environ.get("PUBLIC")
    if public:
        candidates.append(Path(public).expanduser() / "Desktop")

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate

    fallback = user_profile / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _create_shortcut(target: Path, shortcut_path: Path) -> None:
    script = (
        "$shell = New-Object -ComObject WScript.Shell;"
        f"$sc = $shell.CreateShortcut('{_ps_escape(shortcut_path)}');"
        f"$sc.TargetPath = '{_ps_escape(target)}';"
        f"$sc.WorkingDirectory = '{_ps_escape(target.parent)}';"
        f"$sc.IconLocation = '{_ps_escape(target)}';"
        "$sc.Save();"
    )
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=True,
    )


def _copy_payload(target_dir: Path) -> Path:
    src = _payload_path()
    dest = target_dir / PAYLOAD_EXE
    shutil.copy2(src, dest)
    return dest


def _hide_directory(path: Path) -> None:
    if os.name != "nt" or ctypes is None:
        return
    path = path.resolve()
    try:
        FILE_ATTRIBUTE_HIDDEN = 0x02
        FILE_ATTRIBUTE_SYSTEM = 0x04
        current_attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if current_attrs == -1:
            return
        desired_attrs = current_attrs | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
        ctypes.windll.kernel32.SetFileAttributesW(str(path), desired_attrs)
    except Exception:
        return


@app.command(help="安装 Temu Web Panel 并创建桌面快捷方式")
def install(
    target: Path = typer.Option(
        DEFAULT_INSTALL_DIR,
        "--target",
        "-t",
        help="安装目录",
    ),
    shortcut: bool = typer.Option(
        True,
        "--shortcut/--no-shortcut",
        help="是否创建桌面快捷方式",
    ),
) -> None:
    try:
        install_dir = _ensure_dir(target.expanduser())
    except PermissionError:
        typer.echo(f"⚠️ 对 {target} 没有写权限, 自动切换到 {FALLBACK_INSTALL_DIR}")
        install_dir = _ensure_dir(FALLBACK_INSTALL_DIR)

    typer.echo(f"Installing into {install_dir}")
    installed_exe = _copy_payload(install_dir)
    typer.echo(f"Copied {installed_exe.name}")
    typer.echo("Hiding install directory")
    _hide_directory(install_dir)

    if shortcut:
        desktop = _find_desktop_dir()
        shortcut_path = desktop / DESKTOP_SHORTCUT
        typer.echo(f"Creating desktop shortcut: {shortcut_path}")
        _create_shortcut(installed_exe, shortcut_path)
        typer.echo("Shortcut created successfully")

    typer.echo("Temu Web Panel 安装完成，可通过快捷方式或安装目录运行。")


if __name__ == "__main__":
    app()
