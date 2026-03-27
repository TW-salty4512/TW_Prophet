<#
.SYNOPSIS
    TW_Prophet の自動起動タスクを削除する。

.NOTES
    管理者権限で実行してください。
#>

param(
    [string]$TaskName = "TW_Prophet_Web"
)

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "タスク '$TaskName' は登録されていません。"
    exit 0
}

# 実行中なら停止
$state = $existing.State
if ($state -eq "Running") {
    Write-Host "タスクを停止中..."
    Stop-ScheduledTask -TaskName $TaskName
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "[OK] タスク '$TaskName' を削除しました。"
