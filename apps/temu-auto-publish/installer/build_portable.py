"""
@PURPOSE: 构建便携版安装包 - 单个 exe 安装程序,包含所有依赖
@OUTLINE:
  - 下载嵌入式 Python
  - 安装依赖到便携目录
  - 下载 Playwright 浏览器
  - 使用 PyInstaller 打包启动器
  - 使用 7z 创建自解压包 或 Inno Setup 创建安装程序
@USAGE:
  python installer/build_portable.py
"""

import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

# 配置
PYTHON_VERSION = "3.12.7"
PYTHON_EMBED_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
)
APP_NAME = "TemuWebPanel"
BUILD_DIR = Path("build/portable")
DIST_DIR = Path("dist")


def download_file(url: str, dest: Path) -> None:
    """下载文件 - 仅允许 HTTPS"""
    if not url.startswith("https://"):
        raise ValueError(f"仅允许 HTTPS URL: {url}")
    print(f"下载: {url}")
    urllib.request.urlretrieve(url, dest)  # nosec B310 - 已验证 HTTPS
    print(f"已保存到: {dest}")


def extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """解压 ZIP 文件"""
    print(f"解压: {zip_path} -> {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    """运行命令"""
    print(f"执行: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=cwd)


def build_portable():
    """构建便携版"""
    print("=" * 60)
    print(f"  构建 {APP_NAME} 便携版")
    print("=" * 60)

    # 清理并创建目录
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)

    portable_dir = BUILD_DIR / APP_NAME
    portable_dir.mkdir()

    # 1. 下载嵌入式 Python
    print("\n[1/5] 下载嵌入式 Python...")
    python_zip = BUILD_DIR / "python-embed.zip"
    download_file(PYTHON_EMBED_URL, python_zip)

    python_dir = portable_dir / "python"
    python_dir.mkdir()
    extract_zip(python_zip, python_dir)

    # 修改 python312._pth 允许 pip
    pth_file = python_dir / f"python{PYTHON_VERSION.replace('.', '')[:3]}._pth"
    if pth_file.exists():
        content = pth_file.read_text()
        content = content.replace("#import site", "import site")
        content += "\n../Lib/site-packages\n"
        pth_file.write_text(content)

    # 2. 安装 pip
    print("\n[2/5] 安装 pip...")
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip = BUILD_DIR / "get-pip.py"
    download_file(get_pip_url, get_pip)

    python_exe = python_dir / "python.exe"
    run_cmd([str(python_exe), str(get_pip), "--no-warn-script-location"])

    # 3. 安装依赖
    print("\n[3/5] 安装应用依赖...")
    requirements = Path("requirements.txt")
    lib_dir = portable_dir / "Lib" / "site-packages"
    lib_dir.mkdir(parents=True)

    run_cmd(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements),
            "-t",
            str(lib_dir),
            "--no-warn-script-location",
        ]
    )

    # 4. 安装 Playwright 浏览器
    print("\n[4/5] 安装 Playwright Chromium 浏览器...")
    browsers_dir = portable_dir / "browsers"
    browsers_dir.mkdir()

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)

    subprocess.run(
        [str(python_exe), "-m", "playwright", "install", "chromium"], check=True, env=env
    )

    # 5. 复制应用代码
    print("\n[5/5] 复制应用代码...")
    app_dir = portable_dir / "app"

    # 复制源代码
    for item in ["src", "web_panel", "config", "cli"]:
        src = Path(item)
        if src.exists():
            shutil.copytree(src, app_dir / item)

    # 复制必要文件
    for item in ["main.py", "__init__.py", "__main__.py"]:
        src = Path(item)
        if src.exists():
            shutil.copy(src, app_dir / item)

    # 创建数据目录
    data_dir = portable_dir / "data"
    for subdir in ["input", "output", "logs", "temp", "debug"]:
        (data_dir / subdir).mkdir(parents=True)

    # 复制示例选品表
    sample_file = Path("data/input/selection.xlsx")
    if sample_file.exists():
        shutil.copy(sample_file, data_dir / "input" / "selection_sample.xlsx")

    # 创建启动脚本
    create_launcher(portable_dir)

    # 创建配置文件
    create_env_template(portable_dir)

    print("\n" + "=" * 60)
    print("✅ 便携版构建完成!")
    print(f"   位置: {portable_dir}")
    print("=" * 60)

    return portable_dir


def create_launcher(portable_dir: Path) -> None:
    """创建启动脚本"""
    # 批处理启动器
    bat_content = """@echo off
setlocal

cd /d "%~dp0"

set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"
set "PYTHONPATH=%~dp0app;%~dp0Lib\\site-packages"

echo =========================================
echo   Temu Web Panel - 启动中...
echo =========================================

"%~dp0python\\python.exe" -c "from web_panel.api import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8899)"

pause
"""
    (portable_dir / f"启动_{APP_NAME}.bat").write_text(bat_content, encoding="gbk")

    # 自动打开浏览器的启动器
    bat_auto_content = """@echo off
setlocal

cd /d "%~dp0"

set "PLAYWRIGHT_BROWSERS_PATH=%~dp0browsers"
set "PYTHONPATH=%~dp0app;%~dp0Lib\\site-packages"

echo =========================================
echo   Temu Web Panel
echo   访问: http://127.0.0.1:8899
echo =========================================

start http://127.0.0.1:8899

"%~dp0python\\python.exe" -c "from web_panel.api import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8899)"
"""
    (portable_dir / f"{APP_NAME}.bat").write_text(bat_auto_content, encoding="gbk")


def create_env_template(portable_dir: Path) -> None:
    """创建环境变量模板"""
    env_content = """# Temu Web Panel 配置文件
# 复制此文件为 .env 并填写相关配置

# 妙手ERP账号
MIAOSHOU_USERNAME=your_username
MIAOSHOU_PASSWORD=your_password

# AI标题生成(阿里云 DashScope)
DASHSCOPE_API_KEY=your_api_key

# 可选配置
# BROWSER_HEADLESS=false
# LOG_LEVEL=INFO
"""
    (portable_dir / ".env.example").write_text(env_content, encoding="utf-8")


def create_installer_script() -> None:
    """创建 Inno Setup 安装脚本"""
    iss_content = """
; Inno Setup 安装脚本
; 使用: iscc installer.iss

#define AppName "Temu Web Panel"
#define AppVersion "1.0.0"
#define AppPublisher "Beimeng"
#define AppExeName "TemuWebPanel.bat"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\\dist
OutputBaseFilename=TemuWebPanel_Setup_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\\ChineseSimplified.isl"

[Files]
Source: "..\\build\\portable\\TemuWebPanel\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"
Name: "{group}\\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Run]
Filename: "{app}\\{#AppExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
"""

    installer_dir = Path("installer")
    installer_dir.mkdir(exist_ok=True)
    (installer_dir / "installer.iss").write_text(iss_content, encoding="utf-8")
    print("已创建 Inno Setup 脚本: installer/installer.iss")


def create_7z_sfx() -> None:
    """创建 7z 自解压包"""
    sfx_config = """;!@Install@!UTF-8!
Title="Temu Web Panel"
BeginPrompt="是否安装 Temu Web Panel?"
RunProgram="TemuWebPanel.bat"
;!@InstallEnd@!
"""

    installer_dir = Path("installer")
    (installer_dir / "sfx_config.txt").write_text(sfx_config, encoding="utf-8")

    print("""
要创建自解压包,请执行:

1. 安装 7-Zip
2. 运行以下命令:

cd build\\portable
7z a -t7z -mx=9 TemuWebPanel.7z TemuWebPanel
copy /b "C:\\Program Files\\7-Zip\\7zSD.sfx" + ..\\..\\installer\\sfx_config.txt + TemuWebPanel.7z ..\\..\\dist\\TemuWebPanel_Portable.exe
""")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="构建便携版安装包")
    parser.add_argument("--skip-browsers", action="store_true", help="跳过浏览器下载")
    parser.add_argument("--create-installer", action="store_true", help="创建 Inno Setup 脚本")
    args = parser.parse_args()

    if args.create_installer:
        create_installer_script()
        create_7z_sfx()
    else:
        build_portable()
        create_installer_script()
        create_7z_sfx()
