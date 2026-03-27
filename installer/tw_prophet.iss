; TW_Prophet Windows インストーラ定義
; Inno Setup 6.x を使用してください。
; https://jrsoftware.org/isinfo.php
;
; ビルド方法:
;   1. Inno Setup をインストール
;   2. このファイルを Inno Setup IDE で開く
;   3. [Build] → [Compile] でインストーラを生成
;      → installer\Output\TW_Prophet_Setup.exe が生成される
;
; 前提:
;   - Python 仮想環境を project\.venv\ に作成済みであること
;   - あるいは PyInstaller で exe 化した後にパスを変更すること

#define AppName     "TW_Prophet"
#define AppVersion  "3.2.0"
#define AppPublisher "TW-salty4512"
#define AppURL      "https://github.com/TW-salty4512/TW_Prophet"
#define AppExeName  "TW_Prophet_Setup.exe"
; インストーラのソースディレクトリ (このファイルの親の親 = project/)
#define SourceDir   ".."

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
; 管理者権限を要求
PrivilegesRequired=admin
; アーキテクチャ
ArchitecturesInstallIn64BitMode=x64
; セットアップウィザードを起動後に実行
; (setup_wizard.exe を PyInstaller でビルドした場合は以下を変更)

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon";     Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"; Flags: unchecked
Name: "autostart";       Description: "Windows 起動時に自動起動する（推奨）"; GroupDescription: "サービス:"; Flags: checkedonce
Name: "runwizard";       Description: "インストール後にセットアップウィザードを起動する"; GroupDescription: ""; Flags: checkedonce

[Files]
; プロジェクトのソース一式
Source: "{#SourceDir}\*.py";              DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\requirements.txt";  DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\.env.example";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\settings.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\mysql_config.example.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\icon.ico";          DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; サブパッケージ
Source: "{#SourceDir}\api\*";      DestDir: "{app}\api";      Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\model\*";    DestDir: "{app}\model";    Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\public\*";   DestDir: "{app}\public";   Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\scripts\*";  DestDir: "{app}\scripts";  Flags: ignoreversion recursesubdirs
Source: "{#SourceDir}\docs\*";     DestDir: "{app}\docs";     Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

; Python 仮想環境（事前に pip install -r requirements.txt で作成済みのもの）
; PyInstaller でビルドした場合はこのセクションを変更する
Source: "{#SourceDir}\.venv\*";    DestDir: "{app}\.venv";    Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\TW_Prophet Web";             Filename: "{app}\scripts\start_service.bat"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{group}\セットアップウィザード";     Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setup_wizard.py"""; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\TW_Prophet Web"; Filename: "{app}\scripts\start_service.bat"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; 自動起動タスクを登録
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\register_startup.ps1"" -InstallDir ""{app}"""; \
  StatusMsg: "自動起動タスクを登録中..."; \
  Tasks: autostart; Flags: runhidden waituntilterminated

; セットアップウィザードを起動
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -Command ""python '{app}\setup_wizard.py'"""; \
  WorkingDir: "{app}"; \
  StatusMsg: "セットアップウィザードを起動中..."; \
  Tasks: runwizard; Flags: postinstall nowait

[UninstallRun]
; アンインストール時に自動起動タスクを削除
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\unregister_startup.ps1"""; \
  StatusMsg: "自動起動タスクを削除中..."; \
  Flags: runhidden waituntilterminated

[Dirs]
Name: "{commonappdata}\TW_Prophet\data\config"
Name: "{commonappdata}\TW_Prophet\data\models"
Name: "{commonappdata}\TW_Prophet\data\logs"

[Code]
// インストール後に設定ファイルが存在しない場合、example をコピー
procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsFile, ExampleFile: string;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsFile := ExpandConstant('{commonappdata}\TW_Prophet\settings.json');
    ExampleFile  := ExpandConstant('{app}\settings.example.json');
    if not FileExists(SettingsFile) and FileExists(ExampleFile) then
    begin
      FileCopy(ExampleFile, SettingsFile, False);
    end;
  end;
end;
