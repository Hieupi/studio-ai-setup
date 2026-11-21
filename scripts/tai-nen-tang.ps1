# Trinh tai va cai dat truc tiep cac nen tang chinh thuc (khong phu thuoc Winget).
# Kiem tra bat buoc HTTPS + SHA-256 tu catalog-lock.json cho tung goi.
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('python', 'uv', 'node', 'git', 'gh', 'ffmpeg')]
  [string]$Package,

  [string]$Catalog = (Join-Path (Split-Path -Parent $PSScriptRoot) 'catalog-lock.json')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Write-Info([string]$Msg) {
  Write-Output "[StudioAISetup] $Msg"
}

function TaiTepAnToan([string]$Url, [string]$DestPath) {
  if (-not $Url.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Chi cho phep tai tu dia chi HTTPS an toan: $Url"
  }
  $curl = Get-Command 'curl.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($curl -and $curl.Source) {
    Write-Info "Dang tai $Url (curl.exe)..."
    & $curl.Source -fSL --retry 3 --connect-timeout 25 -sS -o $DestPath $Url
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $DestPath) -and ((Get-Item -LiteralPath $DestPath).Length -gt 0)) {
      return
    }
    if (Test-Path -LiteralPath $DestPath) {
      Remove-Item -LiteralPath $DestPath -Force -ErrorAction SilentlyContinue
    }
    Write-Info "curl.exe khong tai duoc (ma $LASTEXITCODE), chuyen sang WebClient..."
  }

  Write-Info "Dang tai $Url (WebClient)..."
  $wc = New-Object Net.WebClient
  try {
    $wc.Headers.Add('User-Agent', 'StudioAISetup/1.0')
    $wc.DownloadFile($Url, $DestPath)
  } finally {
    $wc.Dispose()
  }
  if (-not (Test-Path -LiteralPath $DestPath) -or ((Get-Item -LiteralPath $DestPath).Length -le 0)) {
    throw "Khong tai duoc tep tu $Url"
  }
}

function Expand-ZipSafe([string]$ZipPath, [string]$DestDir) {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $destFull = [IO.Path]::GetFullPath($DestDir)
  $sep = [IO.Path]::DirectorySeparatorChar
  $destPrefix = $destFull.TrimEnd('\', '/') + $sep
  [IO.Directory]::CreateDirectory($destFull) | Out-Null

  $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    foreach ($item in $zip.Entries) {
      $posixMode = (($item.ExternalAttributes -shr 16) -band 0xF000)
      if ($posixMode -eq 0xA000) {
        throw "Tu choi lien ket symlink trong file nen: $($item.FullName)"
      }
      $rel = ($item.FullName -replace '/', [string]$sep)
      if ([IO.Path]::IsPathRooted($rel)) {
        throw "Duong dan khong an toan trong file nen: $($item.FullName)"
      }
      $targetFull = [IO.Path]::GetFullPath([IO.Path]::Combine($destFull, $rel))
      if (-not ($targetFull.Equals($destFull, [StringComparison]::OrdinalIgnoreCase) -or $targetFull.StartsWith($destPrefix, [StringComparison]::OrdinalIgnoreCase))) {
        throw "Phat hien thoat thu muc trong file nen: $($item.FullName)"
      }
      if ($item.FullName.EndsWith('/') -or $item.FullName.EndsWith('\')) {
        [IO.Directory]::CreateDirectory($targetFull) | Out-Null
      } else {
        $parentDir = [IO.Path]::GetDirectoryName($targetFull)
        if ($parentDir) {
          [IO.Directory]::CreateDirectory($parentDir) | Out-Null
        }
        $inStream = $item.Open()
        try {
          $outStream = [IO.File]::Open($targetFull, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
          try {
            $inStream.CopyTo($outStream)
          } finally {
            $outStream.Dispose()
          }
        } finally {
          $inStream.Dispose()
        }
      }
    }
  } finally {
    $zip.Dispose()
  }
}

function Add-UserPath([string[]]$Dirs) {
  $currentUser = [Environment]::GetEnvironmentVariable('Path', 'User')
  $existing = @()
  if ($currentUser) {
    $existing = @($currentUser -split ';' | Where-Object { $_ -and $_.Trim() })
  }
  $normSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($item in $existing) {
    [void]$normSet.Add($item.Trim().TrimEnd('\', '/'))
  }

  $added = @()
  foreach ($dir in $Dirs) {
    if (-not $dir) { continue }
    if (-not (Test-Path -LiteralPath $dir)) { continue }
    $clean = $dir.Trim().TrimEnd('\', '/')
    if (-not $normSet.Contains($clean)) {
      [void]$normSet.Add($clean)
      $existing += $clean
      $added += $clean
    }
  }

  if ($added.Count -gt 0) {
    $newUserPath = ($existing -join ';')
    [Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')
    Write-Info "Da them vao User PATH: $($added -join '; ')"
  }

  foreach ($dir in $Dirs) {
    if ($dir -and (Test-Path -LiteralPath $dir)) {
      if ($env:Path) {
        $env:Path = "$dir;$env:Path"
      } else {
        $env:Path = $dir
      }
    }
  }
}

try {
  if (-not (Test-Path -LiteralPath $Catalog)) {
    throw "Khong tim thay catalog-lock.json tai: $Catalog"
  }
  $cat = Get-Content -LiteralPath $Catalog -Raw -Encoding UTF8 | ConvertFrom-Json
  $entry = if ($Package -eq 'ffmpeg') { $cat.lot2_video.ffmpeg } else { $cat.lot0_core.$Package }
  if (-not $entry) {
    throw "Khong co muc '$Package' trong catalog-lock.json"
  }

  $url = [string]$entry.direct_url
  $expectedSha = ([string]$entry.direct_sha256).Trim().ToLowerInvariant()
  $kind = [string]$entry.install_kind

  if (-not $url.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Dia chi tai cho '$Package' khong hop le: $url"
  }
  if ($expectedSha -notmatch '^[0-9a-f]{64}$') {
    throw "Thieu ma SHA-256 hop le trong catalog-lock.json cho '$Package'"
  }

  $dlDir = Join-Path $env:LOCALAPPDATA 'StudioAISetup\downloads'
  [IO.Directory]::CreateDirectory($dlDir) | Out-Null
  $runId = [Guid]::NewGuid().ToString('N').Substring(0, 8)
  $urlExt = [IO.Path]::GetExtension(([Uri]$url).AbsolutePath)
  if (-not $urlExt) { $urlExt = '.bin' }
  $tmpFile = Join-Path $dlDir "$Package-$runId$urlExt"
  $tmpExtract = Join-Path $dlDir "extract-$Package-$runId"

  try {
    TaiTepAnToan -Url $url -DestPath $tmpFile

    $actualSha = (Get-FileHash -LiteralPath $tmpFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha -ne $expectedSha) {
      throw "Sai ma kiem tra SHA-256 cho $Package (ky vong $expectedSha, thuc te $actualSha)."
    }
    Write-Info "Da xac minh SHA-256 cho $Package ($($entry.version)): OK"

    switch ($kind) {
      'python_exe' {
        Write-Info 'Dang cai dat Python 3.12 (che do im lang)...'
        $proc = Start-Process -FilePath $tmpFile -ArgumentList @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_test=0', 'Include_pip=1') -Wait -PassThru
        if ($proc.ExitCode -notin 0, 3010) {
          throw "Trinh cai Python tra ve ma loi $($proc.ExitCode)"
        }
        $pyDir = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
        $pyScripts = Join-Path $pyDir 'Scripts'
        $pyExe = Join-Path $pyDir 'python.exe'
        if (-not (Test-Path -LiteralPath $pyExe)) {
          throw "Khong tim thay python.exe sau khi cai tai: $pyExe"
        }
        Add-UserPath @($pyDir, $pyScripts)
        Write-Info "Da cai xong Python tai: $pyExe"
      }

      'git_exe' {
        $gitDir = Join-Path $env:LOCALAPPDATA 'Programs\Git'
        Write-Info "Dang cai dat Git vao $gitDir..."
        $proc = Start-Process -FilePath $tmpFile -ArgumentList @('/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-', '/CURRENTUSER', "/DIR=$gitDir") -Wait -PassThru
        if ($proc.ExitCode -notin 0, 3010) {
          throw "Trinh cai Git tra ve ma loi $($proc.ExitCode)"
        }
        $gitCmd = Join-Path $gitDir 'cmd'
        $gitExe = Join-Path $gitCmd 'git.exe'
        if (-not (Test-Path -LiteralPath $gitExe)) {
          throw "Khong tim thay git.exe sau khi cai tai: $gitExe"
        }
        Add-UserPath @($gitCmd)
        Write-Info "Da cai xong Git tai: $gitExe"
      }

      'node_zip' {
        Expand-ZipSafe -ZipPath $tmpFile -DestDir $tmpExtract
        $nodeExe = Get-ChildItem -LiteralPath $tmpExtract -Filter 'node.exe' -Recurse -File | Select-Object -First 1
        if (-not $nodeExe) {
          throw 'Khong tim thay node.exe trong goi Node.js tai ve.'
        }
        $srcRoot = $nodeExe.DirectoryName
        $nodeDest = Join-Path $env:LOCALAPPDATA 'StudioAISetup\runtime\node'
        $nodeParent = Split-Path -Parent $nodeDest
        [IO.Directory]::CreateDirectory($nodeParent) | Out-Null
        if (Test-Path -LiteralPath $nodeDest) {
          Remove-Item -LiteralPath $nodeDest -Recurse -Force
        }
        Copy-Item -LiteralPath $srcRoot -Destination $nodeDest -Recurse -Force
        $destNodeExe = Join-Path $nodeDest 'node.exe'
        $destNpmCmd = Join-Path $nodeDest 'npm.cmd'
        if (-not ((Test-Path -LiteralPath $destNodeExe) -and (Test-Path -LiteralPath $destNpmCmd))) {
          throw "Thieu node.exe hoac npm.cmd tai: $nodeDest"
        }
        $npmGlobal = Join-Path $env:APPDATA 'npm'
        [IO.Directory]::CreateDirectory($npmGlobal) | Out-Null
        Add-UserPath @($nodeDest, $npmGlobal)
        Write-Info "Da cai xong Node.js tai: $destNodeExe"
      }

      'bin_zip' {
        Expand-ZipSafe -ZipPath $tmpFile -DestDir $tmpExtract
        $binDir = Join-Path $env:LOCALAPPDATA 'StudioAISetup\bin'
        [IO.Directory]::CreateDirectory($binDir) | Out-Null

        $wanted = switch ($Package) {
          'uv'     { @('uv.exe', 'uvx.exe') }
          'gh'     { @('gh.exe') }
          'ffmpeg' { @('ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe') }
          default  { throw "Goi bin_zip khong duoc ho tro: $Package" }
        }
        $primary = $wanted[0]
        foreach ($exeName in $wanted) {
          $found = Get-ChildItem -LiteralPath $tmpExtract -Filter $exeName -Recurse -File | Select-Object -First 1
          if ($found) {
            Copy-Item -LiteralPath $found.FullName -Destination (Join-Path $binDir $exeName) -Force
          }
        }
        $primaryPath = Join-Path $binDir $primary
        if (-not (Test-Path -LiteralPath $primaryPath)) {
          throw "Khong tim thay $primary trong goi tai ve cho $Package"
        }
        Add-UserPath @($binDir)
        Write-Info "Da cai xong $Package tai: $primaryPath"
      }

      default {
        throw "Kieu cai dat khong duoc ho tro: $kind"
      }
    }
  } finally {
    if (Test-Path -LiteralPath $tmpFile) {
      Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $tmpExtract) {
      Remove-Item -LiteralPath $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
    }
  }

  exit 0
} catch {
  [Console]::Error.WriteLine("[StudioAISetup] LOI ($Package): $($_.Exception.Message)")
  exit 1
}
