; TW_Prophet Windows インストーラ定義
; Inno Setup 6.x を使用してください。
; https://jrsoftware.org/isinfo.php
;
; ビルド方法:
;   scripts\build_installer.ps1 を実行（PyInstaller → Inno Setup を一括ビルド）
;   または手動:
;     1. pyinstaller installer\run_web.spec      --distpath installer\dist --workpath installer\build
;     2. pyinstaller installer\setup_wizard.spec --distpath installer\dist --workpath installer\build
;     3. "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\tw_prophet.iss
;
; 出力: installer\Output\TW_Prophet_Setup_x.x.x.exe

#define AppName      "TW_Prophet"
#define AppVersion   "3.3.3"
#define AppPublisher "TW-salty4512"
#define AppURL       "https://github.com/TW-salty4512/TW_Prophet"
; このファイルの親 = project/
#define SourceDir    ".."
; PyInstaller ビルド出力先
#define DistDir      "dist"

[Setup]
AppId={{B4E2F1C3-A8D9-4F7E-B2A1-3C5E6D7F8A0B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#SourceDir}\installer\Output
OutputBaseFilename=TW_Prophet_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Flags: unchecked
Name: "autostart";   Description: "Windows 起動時に自動起動する（推奨）";  GroupDescription: "サービス:"; Flags: checkedonce
Name: "runwizard";   Description: "インストール後にセットアップウィザードを起動する"; GroupDescription: "初回設定:"; Flags: checkedonce

[Files]
; ── PyInstaller ビルド済み exe ──────────────────────────────
; ビルド前に scripts\build_installer.ps1 を実行してください
Source: "{#SourceDir}\installer\{#DistDir}\TW_Prophet_Web.exe";           DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\installer\{#DistDir}\TW_Prophet_Setup_Wizard.exe";  DestDir: "{app}"; Flags: ignoreversion

; ── スクリプト・設定テンプレート ───────────────────────────
Source: "{#SourceDir}\scripts\register_startup.ps1";   DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#SourceDir}\scripts\unregister_startup.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "{#SourceDir}\settings.example.json";          DestDir: "{app}";         Flags: ignoreversion
Source: "{#SourceDir}\mysql_config.example.json";      DestDir: "{app}";         Flags: ignoreversion
Source: "{#SourceDir}\icon.ico";                       DestDir: "{app}";         Flags: ignoreversion skipifsourcedoesntexist

; ── サンプルデータ（sample モード用）──────────────────────
Source: "{#SourceDir}\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
; スタートメニュー
Name: "{group}\TW_Prophet Web（手動起動）";   Filename: "{app}\TW_Prophet_Web.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\セットアップウィザード";       Filename: "{app}\TW_Prophet_Setup_Wizard.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
; デスクトップ
Name: "{autodesktop}\TW_Prophet Web"; Filename: "{app}\TW_Prophet_Web.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; ── 自動起動タスクをタスクスケジューラに登録 ──────────────
; TW_Prophet_Web.exe を SYSTEM アカウント・起動時・ウィンドウなしで登録する
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\register_startup.ps1"" -InstallDir ""{app}"" -PythonExe ""{app}\TW_Prophet_Web.exe"""; \
  StatusMsg: "自動起動タスクを登録中..."; \
  Tasks: autostart; Flags: runhidden waituntilterminated

; ── セットアップウィザードを起動（インストール後・非同期）──
Filename: "{app}\TW_Prophet_Setup_Wizard.exe"; \
  WorkingDir: "{app}"; \
  StatusMsg: "セットアップウィザードを起動中..."; \
  Tasks: runwizard; Flags: postinstall nowait

[UninstallRun]
; アンインストール時に自動起動タスクを削除
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\unregister_startup.ps1"""; \
  StatusMsg: "自動起動タスクを削除中..."; \
  RunOnceId: "UnregisterTask"; Flags: runhidden waituntilterminated

[Dirs]
Name: "{commonappdata}\TW_Prophet\data\config"
Name: "{commonappdata}\TW_Prophet\data\models"
Name: "{commonappdata}\TW_Prophet\data\logs"

[Code]
// インストール後に settings.json が存在しない場合、example をコピー
procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsFile, ExampleFile: string;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsFile := ExpandConstant('{commonappdata}\TW_Prophet\data\config\settings.json');
    ExampleFile  := ExpandConstant('{app}\settings.example.json');
    if not FileExists(SettingsFile) and FileExists(ExampleFile) then
    begin
      CopyFile(ExampleFile, SettingsFile, False);
    end;
  end;
end;
