; ------------------------------------------------------------------
; tw_prophet_patch.iss  --  TW_Prophet パッチインストーラ
;
; ウィザードなし・設定不変で exe のみ差し替える。
; タスクスケジューラのタスクを自動停止 → 差し替え → 再起動する。
;
; ビルド方法:
;   scripts\build_patch_installer.ps1          (推奨)
;   または手動:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ^
;       /DAppVersion="3.3.2" installer\tw_prophet_patch.iss
; ------------------------------------------------------------------

; AppVersion は /DAppVersion="x.x.x" で上書き可能
#ifndef AppVersion
  #define AppVersion "3.3.1"
#endif
#define AppName          "TW_Prophet"
#define AppPublisher     "TW-salty4512"
#define SourceDir        ".."
#define DistDir          "dist"
; フルインストーラの AppId GUID（レジストリ検索・バージョン更新に使用）
#define FullInstallGUID  "{B4E2F1C3-A8D9-4F7E-B2A1-3C5E6D7F8A0B}"

[Setup]
; パッチ専用 AppId（フルインストーラの登録と競合しないよう別 GUID）
AppId={{C9D8E7F6-B5A4-3210-FEDC-BA9876543210}
AppName={#AppName} Patch
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/TW-salty4512/TW_Prophet
; 既存インストールディレクトリをコードで取得
DefaultDirName={code:GetInstallDir}
; すべてのウィザードページを非表示
DisableWelcomePage=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
; パッチはアンインストールエントリを作らない（フルインストーラの管理に委ねる）
CreateUninstallRegKey=no
OutputDir={#SourceDir}\installer\Output
OutputBaseFilename=TW_Prophet_Patch_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[CustomMessages]
japanese.InstallingLabel=TW_Prophet v{#AppVersion} へアップデート中...
japanese.FinishedLabel=TW_Prophet v{#AppVersion} へのアップデートが完了しました。%n%nWebサービスを自動で再起動しました。

[Files]
Source: "{#SourceDir}\installer\{#DistDir}\TW_Prophet_Web.exe";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\installer\{#DistDir}\TW_Prophet_Setup_Wizard.exe"; DestDir: "{app}"; Flags: ignoreversion

[Code]
const
  TASK_NAME = 'TW_Prophet_Web';

// ------------------------------------------------------------------
// 既存インストールパスをレジストリから取得
// DefaultDirName={code:GetInstallDir} から呼ばれる
// ------------------------------------------------------------------
function GetInstallDir(Param: string): string;
begin
  // 64bit レジストリを先に検索、次に 32bit
  if not RegQueryStringValue(HKLM64,
      'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
      'InstallLocation', Result) then
    if not RegQueryStringValue(HKLM,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
        'InstallLocation', Result) then
      Result := ExpandConstant('{autopf}\{#AppName}');
  // レジストリ値の末尾バックスラッシュを除去
  if (Length(Result) > 0) and (Result[Length(Result)] = '\') then
    Result := Copy(Result, 1, Length(Result) - 1);
end;

// ------------------------------------------------------------------
// セットアップ開始前にフルインストール済みか確認
// ------------------------------------------------------------------
function InitializeSetup: Boolean;
begin
  Result := True;
  if not DirExists(GetInstallDir('')) then
  begin
    MsgBox('{#AppName} がインストールされていません。' + #13#10 +
           '先にフルインストーラ (TW_Prophet_Setup_*.exe) を実行してください。',
           mbError, MB_OK);
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
    // ファイルロック解除: タスク無効化 → プロセス強制終了 → 少し待機
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Change /TN "' + TASK_NAME + '" /Disable',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'),
         '/F /IM TW_Prophet_Web.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;

  if CurStep = ssPostInstall then
  begin
    // フルインストーラの DisplayVersion を新バージョンに更新
    RegWriteStringValue(HKLM64,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
        'DisplayVersion', '{#AppVersion}');
    RegWriteStringValue(HKLM,
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#FullInstallGUID}_is1',
        'DisplayVersion', '{#AppVersion}');
    // タスク再有効化 → 起動
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Change /TN "' + TASK_NAME + '" /Enable',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Run /TN "' + TASK_NAME + '"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
