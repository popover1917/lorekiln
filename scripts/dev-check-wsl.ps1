[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu',
    [switch]$Benchmark
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($repoRoot -notmatch '^(?<drive>[A-Za-z]):\\(?<path>.+)$') {
    throw "The WSL wrapper requires a local Windows drive path."
}
$drive = $Matches.drive.ToLowerInvariant()
$relativePath = $Matches.path.Replace('\', '/')
$linuxRoot = "/mnt/$drive/$relativePath"
if ($linuxRoot.Contains("'")) {
    throw "Repository paths containing a single quote are not supported by this wrapper."
}
$command = "cd '$linuxRoot' && python3 scripts/dev_check.py"
if ($Benchmark) {
    $command += ' --benchmark'
}
& wsl.exe -d $Distribution -- bash -lc $command
if ($LASTEXITCODE -ne 0) {
    throw "WSL developer checks failed with exit code $LASTEXITCODE."
}
