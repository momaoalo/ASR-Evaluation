[CmdletBinding()]
param(
    [switch]$SkipDeno,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$tools = Join-Path $project '.tools'
New-Item -ItemType Directory -Path $tools -Force | Out-Null

function Get-VerifiedArchive {
    param(
        [Parameter(Mandatory=$true)][string]$ArchiveUrl,
        [Parameter(Mandatory=$true)][string]$Sha256Url,
        [Parameter(Mandatory=$true)][string]$Name
    )
    $scratch = Join-Path ([IO.Path]::GetTempPath()) ('asr-media-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $scratch -Force | Out-Null
    try {
        $archive = Join-Path $scratch 'package.zip'
        $shaFile = Join-Path $scratch 'package.sha256'
        Write-Host ("Downloading {0} from its official distribution..." -f $Name)
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $archive -UseBasicParsing
        Invoke-WebRequest -Uri $Sha256Url -OutFile $shaFile -UseBasicParsing
        $shaText = [IO.File]::ReadAllText($shaFile)
        $match = [regex]::Match($shaText, '(?i)\b[a-f0-9]{64}\b')
        if (-not $match.Success) {
            throw "No SHA-256 checksum was returned for $Name."
        }
        $expected = $match.Value
        $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
        if (-not [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Checksum verification failed for $Name. The package was not installed."
        }
        Write-Host ("SHA-256 verified: {0}" -f $Name)
        $expanded = Join-Path $scratch 'unpacked'
        Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
        return $expanded
    }
    catch {
        Remove-Item -LiteralPath $scratch -Force -Recurse -ErrorAction SilentlyContinue
        throw
    }
}

try {
    $ffDir = Join-Path $tools 'ffmpeg'
    $ffmpeg = Join-Path $ffDir 'ffmpeg.exe'
    $ffprobe = Join-Path $ffDir 'ffprobe.exe'
    if ($Force -or !(Test-Path -LiteralPath $ffmpeg) -or !(Test-Path -LiteralPath $ffprobe)) {
        $expanded = Get-VerifiedArchive -Name 'FFmpeg' -ArchiveUrl 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -Sha256Url 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256'
        try {
            $ffmpegBin = Get-ChildItem -LiteralPath $expanded -Filter 'ffmpeg.exe' -Recurse -File | Select-Object -First 1
            if ($null -eq $ffmpegBin) { throw 'The FFmpeg archive did not contain ffmpeg.exe.' }
            $candidateDir = $ffmpegBin.DirectoryName
            if (!(Test-Path -LiteralPath (Join-Path $candidateDir 'ffprobe.exe'))) {
                throw 'The FFmpeg archive did not contain ffprobe.exe.'
            }
            New-Item -ItemType Directory -Path $ffDir -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $candidateDir 'ffmpeg.exe') -Destination $ffmpeg -Force
            Copy-Item -LiteralPath (Join-Path $candidateDir 'ffprobe.exe') -Destination $ffprobe -Force
        }
        finally {
            Remove-Item -LiteralPath (Split-Path -Parent $expanded) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host 'FFmpeg is ready:'
    $ffmpegInfo = & $ffmpeg -version
    Write-Host $ffmpegInfo[0]
    Write-Host 'FFprobe is ready:'
    $ffprobeInfo = & $ffprobe -version
    Write-Host $ffprobeInfo[0]

    if (!$SkipDeno) {
        $denoDir = Join-Path $tools 'deno'
        $deno = Join-Path $denoDir 'deno.exe'
        if ($Force -or !(Test-Path -LiteralPath $deno)) {
            $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {'aarch64'} else {'x86_64'}
            $asset = "deno-$arch-pc-windows-msvc.zip"
            $url = "https://github.com/denoland/deno/releases/latest/download/$asset"
            $expanded = Get-VerifiedArchive -Name 'Deno' -ArchiveUrl $url -Sha256Url ($url + '.sha256sum')
            try {
                $denoExe = Get-ChildItem -LiteralPath $expanded -Filter 'deno.exe' -Recurse -File | Select-Object -First 1
                if ($null -eq $denoExe) { throw 'The Deno archive did not contain deno.exe.' }
                New-Item -ItemType Directory -Path $denoDir -Force | Out-Null
                Copy-Item -LiteralPath $denoExe.FullName -Destination $deno -Force
            }
            finally {
                Remove-Item -LiteralPath (Split-Path -Parent $expanded) -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host 'Deno is ready:'
        $denoInfo = & $deno --version
        Write-Host $denoInfo[0]
    }
    Write-Host ''
    Write-Host 'Media tools are ready within this project. No winget, admin privileges, or global PATH changes were used.'
    Write-Host 'Start the app with START_WINDOWS.bat, which automatically finds these tools.'
    exit 0
}
catch {
    Write-Error ('Media tools setup failed: ' + $_.Exception.Message)
    exit 1
}
