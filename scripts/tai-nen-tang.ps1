# Trinh tai va cai dat truc tiep cac nen tang chinh thuc (khong phu thuoc Winget).
# Kiem tra bat buoc HTTPS + SHA-256 tu catalog-lock.json + chu ky so Authenticode (.exe).
param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('python', 'uv', 'node', 'git', 'gh', 'ffmpeg')]
  [string]$Package,

  [string]$Catalog = (Join-Path (Split-Path -Parent $PSScriptRoot) 'catalog-lock.json')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls13
} catch {}

$USER_AGENT = 'StudioAISetup/2.0'

function Write-Info([string]$Msg) {
  Write-Output "[StudioAISetup] $Msg"
}

function Assert-AuthenticodeValid([string]$FilePath, [string]$ToolName) {
  if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "Khong tim thay tep cai dat de kiem tra chu ky so Authenticode cho $($ToolName): $FilePath"
  }
  $sig = $null
  try {
    $sig = Get-AuthenticodeSignature -FilePath $FilePath
  } catch {
    if (Test-Path -LiteralPath $FilePath) {
      Remove-Item -LiteralPath $FilePath -Force -ErrorAction SilentlyContinue
    }
    throw "Khong doc duoc chu ky so Authenticode cho $($ToolName): $($_.Exception.Message)"
  }
  $status = if ($null -ne $sig -and $null -ne $sig.Status) { [string]$sig.Status } else { 'Unknown' }
  $statusMsg = if ($null -ne $sig -and -not [string]::IsNullOrWhiteSpace([string]$sig.StatusMessage)) {
    ([string]$sig.StatusMessage).Trim()
  } else {
    'Khong co thong diep trang thai'
  }
  if ($null -eq $sig -or $sig.Status -ne 'Valid' -or $null -eq $sig.SignerCertificate) {
    if (Test-Path -LiteralPath $FilePath) {
      Remove-Item -LiteralPath $FilePath -Force -ErrorAction SilentlyContinue
    }
    throw "Chu ky so Authenticode khong hop le cho $ToolName (Trang thai: $status - $statusMsg). Da xoa tep tam de bao ve may."
  }
  $subject = [string]$sig.SignerCertificate.Subject
  if ([string]::IsNullOrWhiteSpace($subject)) {
    $subject = [string]$sig.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
  }
  Write-Info "Authenticode OK ($ToolName): $subject"
}

function TaiTepAnToan([string]$Url, [string]$DestPath) {
  if (-not $Url.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Chi cho phep tai tu dia chi HTTPS an toan: $Url"
  }
  $curl = Get-Command 'curl.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($curl -and $curl.Source) {
    Write-Info "Dang tai $Url (curl.exe)..."
    & $curl.Source -fSL --proto '=https' --proto-redir '=https' --tlsv1.2 --retry 3 --connect-timeout 25 -A $USER_AGENT -sS -o $DestPath $Url
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
    $wc.Proxy = [System.Net.WebRequest]::DefaultWebProxy
    if ($wc.Proxy) {
      $wc.Proxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials
    }
    $wc.Headers.Add('User-Agent', $USER_AGENT)
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
  $maxEntries = 4096
  $maxTotalBytes = [int64]536870912
  $bufferSize = 65536
  $reservedRx = '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$'

  $destFull = [IO.Path]::GetFullPath($DestDir)
  $sep = [IO.Path]::DirectorySeparatorChar
  $destPrefix = $destFull.TrimEnd('\', '/') + $sep
  $destExisted = Test-Path -LiteralPath $destFull

  $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
  try {
    if ($zip.Entries.Count -gt $maxEntries) {
      throw "File nen vuot qua gioi han $maxEntries tep (thuc te: $($zip.Entries.Count))."
    }

    # Pass 1: Xac thuc toan bo entry truoc khi ghi bat ky tep nao xuong dia
    $declaredTotal = [int64]0
    $planned = New-Object 'System.Collections.Generic.List[hashtable]'
    foreach ($item in $zip.Entries) {
      $rawName = [string]$item.FullName
      if ($rawName.IndexOf([char]0) -ge 0) {
        throw 'Ten tep khong hop le (ky tu NUL) trong file nen.'
      }
      $posixMode = (($item.ExternalAttributes -shr 16) -band 0xF000)
      if ($posixMode -eq 0xA000) {
        throw "Tu choi lien ket symlink trong file nen: $rawName"
      }
      $rel = ($rawName -replace '/', [string]$sep)
      if ([IO.Path]::IsPathRooted($rel)) {
        throw "Duong dan khong an toan trong file nen: $rawName"
      }
      $segments = $rawName -split '[/\\]'
      foreach ($seg in $segments) {
        if ([string]::IsNullOrEmpty($seg)) { continue }
        if ($seg -eq '..') {
          throw "Phat hien duong dan '..' trong file nen: $rawName"
        }
        if ($seg.IndexOf(':') -ge 0) {
          throw "Phat hien ky tu ':' khong hop le trong file nen: $rawName"
        }
        $cleanSeg = $seg.TrimEnd(' ', '.')
        $baseSeg = ($cleanSeg -split '\.')[0].ToUpperInvariant()
        if ($baseSeg -match $reservedRx) {
          throw "Tu choi ten thiet bi Windows cam trong file nen: $rawName"
        }
      }

      $targetFull = [IO.Path]::GetFullPath([IO.Path]::Combine($destFull, $rel))
      if (-not ($targetFull.Equals($destFull, [StringComparison]::OrdinalIgnoreCase) -or $targetFull.StartsWith($destPrefix, [StringComparison]::OrdinalIgnoreCase))) {
        throw "Phat hien thoat thu muc trong file nen: $rawName"
      }

      $isDir = $rawName.EndsWith('/') -or $rawName.EndsWith('\')
      if (-not $isDir) {
        $declaredTotal += [int64]$item.Length
        if ($declaredTotal -gt $maxTotalBytes) {
          throw 'Tong kich thuoc khai bao trong file nen vuot qua gioi han 512 MiB.'
        }
      }
      $planned.Add(@{ entry = $item; target = $targetFull; isDir = $isDir })
    }

    # Pass 2: Giai nen bang vong lap bo dem 64 KB va chan tong byte thuc te > 512 MiB
    [IO.Directory]::CreateDirectory($destFull) | Out-Null
    $createdFiles = New-Object 'System.Collections.Generic.List[string]'
    $streamedTotal = [int64]0
    $buf = New-Object byte[] $bufferSize

    try {
      foreach ($p in $planned) {
        if ($p.isDir) {
          [IO.Directory]::CreateDirectory($p.target) | Out-Null
        } else {
          $parentDir = [IO.Path]::GetDirectoryName($p.target)
          if ($parentDir) {
            [IO.Directory]::CreateDirectory($parentDir) | Out-Null
          }
          $inStream = $p.entry.Open()
          try {
            $outStream = [IO.File]::Open($p.target, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
            $createdFiles.Add($p.target)
            try {
              while (($bytesRead = $inStream.Read($buf, 0, $buf.Length)) -gt 0) {
                $streamedTotal += [int64]$bytesRead
                if ($streamedTotal -gt $maxTotalBytes) {
                  throw "Tong du lieu giai nen thuc te vuot qua gioi han 512 MiB ($maxTotalBytes bytes)."
                }
                $outStream.Write($buf, 0, $bytesRead)
              }
            } finally {
              $outStream.Dispose()
            }
          } finally {
            $inStream.Dispose()
          }
        }
      }
    } catch {
      foreach ($f in $createdFiles) {
        if (Test-Path -LiteralPath $f) {
          Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
        }
      }
      if (-not $destExisted -and (Test-Path -LiteralPath $destFull)) {
        Remove-Item -LiteralPath $destFull -Recurse -Force -ErrorAction SilentlyContinue
      }
      throw
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

    if ($kind -in @('python_exe', 'git_exe') -or $urlExt.Equals('.exe', [StringComparison]::OrdinalIgnoreCase)) {
      Assert-AuthenticodeValid -FilePath $tmpFile -ToolName "$Package ($($entry.version))"
    }

    switch ($kind) {
      'python_exe' {
        Write-Info "Dang cai dat Python $($entry.version) (che do im lang)..."
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
