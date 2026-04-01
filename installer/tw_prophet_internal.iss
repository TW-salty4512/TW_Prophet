; ------------------------------------------------------------------
; tw_prophet_internal.iss  --  TW_Prophet 社内専用設定インストーラ
;
; mysql_config.json を %ProgramData%\TW_Prophet\data\config\ に展開する。
; フルインストーラとは独立して動作し、MySQL 接続情報のみを配布する。
;
; ビルド方法:
;   scripts\build_internal_installer.ps1          (推奨)
;   または手動:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\tw_prophet_internal.iss
;
; 注意:
;   このインストーラは GitHub Release に上げず、社内でのみ配布すること。
;   ソース元ファイル mysql_config.internal.json は git 追跡対象外。
; ------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "3.3.2"
#endif
#define AppName      "TW_Prophet"
#define AppPublisher "TW-salty4512"
#define SourceDir    ".."
; フルインストーラの AppId（インストール確認に使用）
#define FullInstallGUID "{B4E2F1C3-A8D9-4F7E-B2A1-3C5E6D7F8A0B}"

[Setup]
; 社内設定専用 AppId
AppId={{F2E1D0C9-B8A7-6543-2100-FEDCBA987654}
AppName={#AppName} Internal Config
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/TW-salty4512/TW_Prophet
; アプリディレクトリは不要（設定ファイルのみ展開）
CreateAppDir=no
; すべてのウィザードページを非表示
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
; アンインストールエントリも不要
CreateUninstallRegKey=no
OutputDir={#SourceDir}\installer\Output
OutputBaseFilename=TW_Prophet_Internal_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[CustomMessages]
japanese.FinishedLabel=社内MySQL設定が完了しました。%nWebサービスを再起動しました。

[Files]
; mysql_config.internal.json を mysql_config.json として config ディレクトリへ展開
Source: "{#SourceDir}\mysql_config.internal.json"; \
  DestDir: "{commonappdata}\TW_Prophet\data\config"; \
  DestName: "mysql_config.json"; \
  Flags: ignoreversion

[Code]
const
  TASK_NAME = 'TW_Prophet_Web';

// ------------------------------------------------------------------
// セットアップ開始前にフルインストール済みか確認
// ------------------------------------------------------------------
function InitializeSetup: Boolean;
var
  InstallLocation: string;
begin
  Result := True;
  if not RegQueryStringValue(HKLM64,
      'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
      'InstallLocation', InstallLocation) then
    if not RegQueryStringValue(HKLM,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
        'InstallLocation', InstallLocation) then
    begin
      MsgBox('{#AppName} がインストールされていません。' + #13#10 +
             '先にフルインストーラ (TW_Prophet_Setup_*.exe) を実行してください。',
             mbError, MB_OK);
      Result := False;
      Exit;
    end;

  // 確認ダイアログ
  if MsgBox('社内MySQL設定ファイルを展開します。' + #13#10 +
            '既存の mysql_config.json は上書きされます。続行しますか？',
            mbConfirmation, MB_YESNO) = IDNO then
  begin
    Result := False;
  end;
end;

// ------------------------------------------------------------------
// 各インストールステップで実行
// ------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // サービス停止（設定ファイル書き換え中の競合を防ぐ）
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Change /TN "' + TASK_NAME + '" /Disable',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'),
         '/F /IM TW_Prophet_Web.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;

  if CurStep = ssPostInstall then
  begin
    // サービス再起動
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Change /TN "' + TASK_NAME + '" /Enable',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Run /TN "' + TASK_NAME + '"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
