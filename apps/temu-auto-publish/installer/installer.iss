; Temu Web Panel - Inno Setup 安装脚本
; 
; @PURPOSE: 创建单个 exe 安装程序，包含所有依赖
; @USAGE: 
;   1. 先运行 build_portable.py 生成便携版
;   2. 安装 Inno Setup: https://jrsoftware.org/isdl.php
;   3. 运行: iscc installer.iss
;
; 生成的安装程序位于: dist/TemuWebPanel_Setup_x.x.x.exe

#define AppName "Temu Web Panel"
#define AppVersion "1.0.0"
#define AppPublisher "Beimeng Team"
#define AppURL "https://github.com/beimeng"
#define AppExeName "TemuWebPanel.bat"
#define SourceDir "..\build\portable\TemuWebPanel"

[Setup]
; 应用标识（每个应用唯一）
AppId={{8E7B3A2C-F1D4-4B9E-A5C6-7D8E9F0A1B2C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; 安装目录
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; 输出设置
OutputDir=..\dist
OutputBaseFilename=TemuWebPanel_Setup_{#AppVersion}
; SetupIconFile=..\data\image\icon.ico  ; 如有图标可取消注释
; UninstallDisplayIcon={app}\icon.ico

; 压缩设置（最大压缩）
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; 界面设置
WizardStyle=modern
WizardSizePercent=120

; 权限（不需要管理员权限）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 其他设置
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableWelcomePage=no
DisableDirPage=no
DisableFinishedPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional options:"

[Files]
; 复制所有文件
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Comment: "启动 Temu Web Panel"
Name: "{group}\配置文件目录"; Filename: "{app}\data"; Comment: "打开数据目录"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"

; 桌面快捷方式
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 安装后运行
Filename: "{app}\{#AppExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallDelete]
; 卸载时删除日志和临时文件
Type: filesandordirs; Name: "{app}\data\logs"
Type: filesandordirs; Name: "{app}\data\temp"
Type: filesandordirs; Name: "{app}\data\debug"

[Code]
// 自定义安装逻辑
function InitializeSetup(): Boolean;
begin
  Result := True;
  // 检查是否已安装
  if RegKeyExists(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8E7B3A2C-F1D4-4B9E-A5C6-7D8E9F0A1B2C}_is1') then
  begin
    if MsgBox('检测到已安装旧版本，是否先卸载？', mbConfirmation, MB_YESNO) = IDYES then
    begin
      // 用户选择卸载
    end;
  end;
end;


