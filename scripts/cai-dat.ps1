# Trình cài đặt giao diện Windows WPF cho Studio AI Setup.
# Chạy ẩn qua `conhost.exe --headless powershell -STA -File scripts\cai-dat.ps1` từ cai-dat.bat.
$ErrorActionPreference = 'Stop'
$GOC = Split-Path -Parent $PSScriptRoot
$ENGINE = Join-Path $GOC 'engine\setup_engine.py'
$TAI_NEN_TANG = Join-Path $PSScriptRoot 'tai-nen-tang.ps1'
$CATALOG_PATH = Join-Path $GOC 'catalog-lock.json'

$DATA_ROOT = Join-Path $env:LOCALAPPDATA 'StudioAISetup'
$STATE_PATH = Join-Path $DATA_ROOT 'state.json'
$LOGS = Join-Path $DATA_ROOT 'logs'
$LOG = Join-Path $LOGS 'cai-dat.log'
$DA_MO = Join-Path $LOGS 'gui-opened.txt'
$CHIDAN_DIR = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Studio AI Setup\Chi-Dan'

# Đọc siêu dữ liệu phiên bản động từ catalog-lock.json (có giá trị dự phòng an toàn)
$script:appVer = '2.0.0'
$script:ffmpegVer = '9.1'
$script:reaVer = '6.10.1'
$script:egmVer = '0.1.1+egm-lite'
if (Test-Path -LiteralPath $CATALOG_PATH) {
  try {
    $catObj = Get-Content -LiteralPath $CATALOG_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($catObj.app_version) { $script:appVer = [string]$catObj.app_version }
    if ($catObj.lot2_video -and $catObj.lot2_video.ffmpeg -and $catObj.lot2_video.ffmpeg.version) {
      $script:ffmpegVer = [string]$catObj.lot2_video.ffmpeg.version
    }
    if ($catObj.lot4_data -and $catObj.lot4_data.rea_agents -and $catObj.lot4_data.rea_agents.version) {
      $script:reaVer = [string]$catObj.lot4_data.rea_agents.version
    }
    if ($catObj.lot5_review -and $catObj.lot5_review.egm -and $catObj.lot5_review.egm.upstream_version) {
      $script:egmVer = [string]$catObj.lot5_review.egm.upstream_version
    }
  } catch {}
}

# Đọc tên người dùng đã lưu từ state.json (chỉ đọc, giữ tên khi nâng cấp v1 -> v2)
$script:savedUserName = $null
if (Test-Path -LiteralPath $STATE_PATH) {
  try {
    $stObj = Get-Content -LiteralPath $STATE_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($stObj -and $stObj.user_name) {
      $candTen = ([string]$stObj.user_name).Trim()
      if ($candTen -and ($candTen -ne 'bạn')) {
        $script:savedUserName = $candTen
      }
    }
  } catch {}
}

try {
  New-Item -ItemType Directory -Force -Path $LOGS | Out-Null
  [IO.File]::WriteAllText($LOG, "Studio AI Setup v$($script:appVer) — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`r`nThu muc: $GOC`r`n", [Text.UTF8Encoding]::new($true))
  Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
} catch {
  exit 91
}

function Ghi([string]$dong) {
  try {
    [IO.File]::AppendAllText($LOG, "$dong`r`n", [Text.UTF8Encoding]::new($false))
  } catch {}
}

function Format-Win32Arg([string]$arg) {
  if ($null -eq $arg -or $arg.Length -eq 0) {
    return '""'
  }
  if ($arg -notmatch '[\s"&^%()<>|]') {
    return $arg
  }
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append('"')
  $bsCount = 0
  foreach ($ch in $arg.ToCharArray()) {
    if ($ch -eq '\') {
      $bsCount++
    } elseif ($ch -eq '"') {
      [void]$sb.Append('\', ($bsCount * 2 + 1))
      [void]$sb.Append('"')
      $bsCount = 0
    } else {
      if ($bsCount -gt 0) {
        [void]$sb.Append('\', $bsCount)
        $bsCount = 0
      }
      [void]$sb.Append($ch)
    }
  }
  if ($bsCount -gt 0) {
    [void]$sb.Append('\', ($bsCount * 2))
  }
  [void]$sb.Append('"')
  return $sb.ToString()
}

function Join-Win32Args([string[]]$argList) {
  if (-not $argList -or $argList.Count -eq 0) { return '' }
  $parts = New-Object 'System.Collections.Generic.List[string]'
  foreach ($a in $argList) {
    $parts.Add((Format-Win32Arg ([string]$a)))
  }
  return ($parts -join ' ')
}

function NapLaiPath {
  $may = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $nguoi = [Environment]::GetEnvironmentVariable('Path', 'User')
  $links = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links'
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA 'StudioAISetup\bin'),
    (Join-Path $env:LOCALAPPDATA 'StudioAISetup\runtime\node'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd'),
    $links,
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\Scripts'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\Scripts'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\Scripts'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\Scripts'),
    (Join-Path $env:ProgramFiles 'nodejs'),
    (Join-Path $env:ProgramFiles 'Git\cmd'),
    (Join-Path $env:ProgramFiles 'GitHub CLI'),
    (Join-Path $env:APPDATA 'npm')
  )
  $extra = @($candidates | Where-Object { Test-Path -LiteralPath $_ })
  $env:Path = (@($extra) + @($may, $nguoi) | Where-Object { $_ }) -join ';'
}

function Co([string]$ten) {
  [bool](Get-Command $ten -CommandType Application -ErrorAction SilentlyContinue)
}

function TimPythonHopLe {
  NapLaiPath
  $cands = @()
  foreach ($cmdName in @('python', 'python3')) {
    $cmds = @(Get-Command $cmdName -All -CommandType Application -ErrorAction SilentlyContinue)
    foreach ($cmd in $cmds) {
      if ($cmd -and $cmd.Source -and ($cmd.Source -notlike '*\WindowsApps\*')) {
        $cands += $cmd.Source
      }
    }
  }
  foreach ($d in @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
    'C:\Python313\python.exe',
    'C:\Python312\python.exe',
    'C:\Python311\python.exe',
    'C:\Python-3.10.12\python.exe'
  )) {
    if (Test-Path -LiteralPath $d) { $cands += $d }
  }
  foreach ($exe in ($cands | Select-Object -Unique)) {
    try {
      $out = & $exe -c "import sys; print('OK' if sys.version_info >= (3,10) else 'OLD')" 2>$null
      if ($LASTEXITCODE -eq 0 -and ($out -join '').Trim() -eq 'OK') { return $exe }
    } catch {}
  }
  return $null
}

function NodeDatChuan {
  NapLaiPath
  $cands = @()
  $localNode = Join-Path $env:LOCALAPPDATA 'StudioAISetup\runtime\node\node.exe'
  if (Test-Path -LiteralPath $localNode) { $cands += $localNode }
  $nodeCmds = @(Get-Command node.exe -All -CommandType Application -ErrorAction SilentlyContinue)
  foreach ($c in $nodeCmds) {
    if ($c -and $c.Source) { $cands += $c.Source }
  }
  $pfNode = Join-Path $env:ProgramFiles 'nodejs\node.exe'
  if (Test-Path -LiteralPath $pfNode) { $cands += $pfNode }

  $lastVer = $null
  foreach ($exe in ($cands | Select-Object -Unique)) {
    try {
      $raw = (& $exe --version 2>$null | Select-Object -First 1).Trim().TrimStart('v')
      if (-not $raw) { continue }
      $lastVer = $raw
      $v = [version]$raw
      $ok = (($v.Major -eq 22 -and $v -ge [version]'22.23.4') -or
             ($v.Major -eq 24 -and $v -ge [version]'24.22.1') -or
             ($v -ge [version]'26.12.1'))
      if ($ok) { return @{ ok = $true; version = $raw } }
    } catch {}
  }
  return @{ ok = $false; version = $lastVer }
}

function QuetMayNhanh {
  $is64 = [Environment]::Is64BitOperatingSystem
  $ramGb = '?'
  try {
    Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
    $ci = New-Object Microsoft.VisualBasic.Devices.ComputerInfo
    $ramGb = [Math]::Round($ci.TotalPhysicalMemory / 1GB, 0)
  } catch {
    try {
      $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
      $ramGb = [Math]::Round($cs.TotalPhysicalMemory / 1GB, 0)
    } catch {}
  }

  $gpuInfo = @{ present = $false; name = 'Không có GPU rời NVIDIA'; supports3d = $false }
  $smi = Get-Command nvidia-smi -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($smi) {
    try {
      $line = (& $smi.Source --query-gpu=name,compute_cap --format=csv,noheader 2>$null | Select-Object -First 1)
      if ($line) {
        $parts = $line -split ','
        $gName = $parts[0].Trim()
        $cap = if ($parts.Count -gt 1) { $parts[1].Trim() } else { '' }
        $sup = $false
        try { if ($cap -and ([double]$cap -ge 7.5)) { $sup = $true } } catch {}
        $gpuInfo = @{ present = $true; name = $gName; supports3d = $sup }
      }
    } catch {}
  }

  $ides = @()
  if ((Test-Path (Join-Path $env:USERPROFILE '.gemini')) -or (Test-Path (Join-Path $env:USERPROFILE '.antigravity'))) { $ides += 'Antigravity' }
  if ((Test-Path (Join-Path $env:USERPROFILE '.claude')) -or (Co 'claude')) { $ides += 'Claude Code' }
  if ((Test-Path (Join-Path $env:USERPROFILE '.codex')) -or (Co 'codex')) { $ides += 'Codex' }
  if ((Test-Path (Join-Path $env:APPDATA 'Code')) -or (Co 'code')) { $ides += 'VS Code' }
  $ideText = if ($ides.Count -gt 0) { $ides -join ', ' } else { 'Chưa phát hiện (vẫn cài chuẩn)' }

  return @{ is64 = $is64; ramGb = $ramGb; gpu = $gpuInfo; ideText = $ideText }
}

function Parse-JsonAnToan([string]$raw) {
  if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
  $trimmed = $raw.Trim()
  try {
    return ($trimmed | ConvertFrom-Json)
  } catch {}
  $first = $trimmed.IndexOf('{')
  $last = $trimmed.LastIndexOf('}')
  if ($first -ge 0 -and $last -gt $first) {
    try {
      return ($trimmed.Substring($first, $last - $first + 1) | ConvertFrom-Json)
    } catch {}
  }
  return $null
}

function LayThuocTinh($obj, [string]$name) {
  if ($null -eq $obj) { return $null }
  $prop = $obj.PSObject.Properties[$name]
  if ($prop) { return $prop.Value }
  return $null
}

function DemSoLuong($val, [int]$macDinh = 0) {
  if ($null -eq $val) { return $macDinh }
  if ($val -is [int] -or $val -is [long] -or $val -is [double]) { return [int]$val }
  if ($val -is [System.Collections.ICollection]) { return $val.Count }
  $arr = @($val)
  return $arr.Count
}

function NhanTrangThaiHarness([string]$st) {
  switch ($st) {
    'installed'                      { return @{ chu = 'Đã đăng ký'; mau = '#a3e635' } }
    'already_installed'              { return @{ chu = 'Đã có sẵn'; mau = '#a3e635' } }
    'missing'                        { return @{ chu = 'Chưa có tệp plugin'; mau = '#fb7185' } }
    'not_detected'                   { return @{ chu = 'Chưa phát hiện trên máy'; mau = '#94a3b8' } }
    'not_installed'                  { return @{ chu = 'Chưa cài trên máy'; mau = '#94a3b8' } }
    'cli_not_found'                  { return @{ chu = 'Chưa tìm thấy CLI trên PATH'; mau = '#94a3b8' } }
    'cli_missing'                    { return @{ chu = 'Chưa tìm thấy CLI trên PATH'; mau = '#94a3b8' } }
    'skipped'                        { return @{ chu = 'Đã bỏ qua'; mau = '#94a3b8' } }
    'already_configured_marketplace' { return @{ chu = 'Giữ cấu hình sẵn (xem Chỉ dẫn Lô 5)'; mau = '#fbbf24' } }
    'manual_required'                { return @{ chu = 'Cần đăng ký thủ công (xem Chỉ dẫn Lô 5)'; mau = '#fbbf24' } }
    'manual_action_required'         { return @{ chu = 'Cần đăng ký thủ công (xem Chỉ dẫn Lô 5)'; mau = '#fbbf24' } }
    'failed'                         { return @{ chu = 'Cần đăng ký thủ công (xem Chỉ dẫn Lô 5)'; mau = '#fbbf24' } }
    default {
      return @{ chu = 'Cần kiểm tra (xem Chỉ dẫn Lô 5)'; mau = '#cbd5e1' }
    }
  }
}

# ── Giao diện Luxury Dark Studio WPF ────────────────────────────────────────────────────────────
$XAML = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Studio AI Setup" Width="780" SizeToContent="Height" WindowStyle="None" ResizeMode="NoResize"
        WindowStartupLocation="CenterScreen" Background="#090c12" BorderBrush="#222b3e" BorderThickness="1"
        FontFamily="Segoe UI Variable Text, Segoe UI" FontSize="13.5" Foreground="#f1f5f9"
        TextOptions.TextFormattingMode="Display" UseLayoutRounding="True">
  <Window.Resources>
    <Style x:Key="NutPhu" TargetType="Button">
      <Setter Property="Foreground" Value="#e2e8f0"/>
      <Setter Property="Height" Value="42"/>
      <Setter Property="MinWidth" Value="120"/>
      <Setter Property="Margin" Value="10,0,0,0"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="#141b29" BorderBrush="#2a354d" BorderThickness="1" CornerRadius="8" Padding="18,0">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#1d263a"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter TargetName="b" Property="Opacity" Value="0.45"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="NutChinh" TargetType="Button" BasedOn="{StaticResource NutPhu}">
      <Setter Property="Foreground" Value="#081104"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="#a3e635" BorderBrush="#bef264" BorderThickness="1" CornerRadius="8" Padding="22,0">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#bef264"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter TargetName="b" Property="Opacity" Value="0.45"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="CheckLuxury" TargetType="CheckBox">
      <Setter Property="Foreground" Value="#f1f5f9"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="CheckBox">
            <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
              <Border x:Name="box" Width="20" Height="20" CornerRadius="6" Background="#0b0f18"
                      BorderBrush="#3d4d6b" BorderThickness="1.5" VerticalAlignment="Center">
                <TextBlock x:Name="tick" Text="&#xE73E;" FontFamily="Segoe MDL2 Assets" FontSize="11"
                           Foreground="#081104" FontWeight="Bold" HorizontalAlignment="Center"
                           VerticalAlignment="Center" Visibility="Collapsed"/>
              </Border>
              <ContentPresenter Margin="10,0,0,0" VerticalAlignment="Center"/>
            </StackPanel>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="box" Property="Background" Value="#a3e635"/>
                <Setter TargetName="box" Property="BorderBrush" Value="#a3e635"/>
                <Setter TargetName="tick" Property="Visibility" Value="Visible"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False">
                <Setter TargetName="box" Property="Opacity" Value="0.4"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>

  <DockPanel LastChildFill="True">
    <!-- Header thanh tiêu đề sang trọng -->
    <Grid x:Name="Dau" DockPanel.Dock="Top" Background="#111622" Height="64">
      <StackPanel Orientation="Horizontal" VerticalAlignment="Center" Margin="24,0,0,0">
        <Image x:Name="Logo" Width="36" Height="36"/>
        <StackPanel Margin="14,0,0,0" VerticalAlignment="Center">
          <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
            <TextBlock Text="Studio AI Setup" FontSize="17.5" FontWeight="SemiBold" Foreground="#f8fafc"/>
            <Border Background="#162235" BorderBrush="#263854" BorderThickness="1" CornerRadius="10"
                    Padding="8,2" Margin="10,0,0,0" VerticalAlignment="Center">
              <TextBlock x:Name="NhanPhienBan" Text="Miễn phí · MIT" FontSize="11" Foreground="#38bdf8" FontWeight="SemiBold"/>
            </Border>
          </StackPanel>
          <TextBlock Text="Bộ cài môi trường sáng tạo Content · Video · Code · Dữ liệu · Phản biện"
                     FontSize="12" Foreground="#8b9ab5" Margin="0,2,0,0"/>
        </StackPanel>
      </StackPanel>

      <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Center" Margin="0,0,10,0">
        <TextBlock x:Name="LinkHuongDanTop" Text="Hướng dẫn nhanh" Foreground="#94a3b8" FontSize="12.5"
                   VerticalAlignment="Center" Margin="0,0,14,0" Cursor="Hand" TextDecorations="Underline"/>
        <Button x:Name="Dong" Width="44" Height="44" Cursor="Hand" ToolTip="Đóng">
          <Button.Template>
            <ControlTemplate TargetType="Button">
              <Border x:Name="b" Background="Transparent" CornerRadius="8">
                <TextBlock Text="&#xE8BB;" FontFamily="Segoe MDL2 Assets" FontSize="12" Foreground="#94a3b8"
                           HorizontalAlignment="Center" VerticalAlignment="Center"/>
              </Border>
              <ControlTemplate.Triggers>
                <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#1d263a"/></Trigger>
              </ControlTemplate.Triggers>
            </ControlTemplate>
          </Button.Template>
        </Button>
      </StackPanel>
    </Grid>
    <Border DockPanel.Dock="Top" Height="1" Background="#1f293d"/>

    <!-- Footer cố định cho Màn hình 1 (nằm ngoài ScrollViewer để luôn thấy nút Bắt đầu trên 1366x768) -->
    <Border x:Name="FooterChao" DockPanel.Dock="Bottom" Background="#0c1019" BorderBrush="#1f293d"
            BorderThickness="0,1,0,0" Padding="26,12" Visibility="Visible">
      <Grid>
        <TextBlock Text="Công cụ tải trực tiếp từ nguồn mở chính thức trên máy bạn · Không key · Không gửi dữ liệu ra ngoài."
                   Foreground="#7b8ba6" FontSize="12" VerticalAlignment="Center" HorizontalAlignment="Left"
                   Width="460" TextWrapping="Wrap"/>
        <Button x:Name="NutBatDau" Style="{StaticResource NutChinh}" Content="Bắt đầu cài đặt tự động"
                HorizontalAlignment="Right" Height="44"/>
      </Grid>
    </Border>

    <ScrollViewer x:Name="KhungCuon" VerticalScrollBarVisibility="Auto" HorizontalScrollBarVisibility="Disabled">
      <StackPanel>
        <!-- MÀN HÌNH 1: CHÀO MỪNG, QUÉT MÁY & CHỌN 5 LÔ -->
        <StackPanel x:Name="ManChao" Margin="26,16,26,16" Visibility="Visible">
      <!-- Dải thông số phần cứng Pre-flight -->
      <Border Background="#111622" BorderBrush="#1f293d" BorderThickness="1" CornerRadius="10" Padding="14,10">
        <Grid>
          <Grid.ColumnDefinitions>
            <ColumnDefinition Width="*"/>
            <ColumnDefinition Width="*"/>
            <ColumnDefinition Width="1.2*"/>
            <ColumnDefinition Width="1.3*"/>
          </Grid.ColumnDefinitions>
          <StackPanel Grid.Column="0">
            <TextBlock Text="HỆ THỐNG" FontSize="10.5" Foreground="#64748b" FontWeight="SemiBold"/>
            <TextBlock x:Name="InfoOS" Text="Windows 64-bit" FontSize="12.5" Foreground="#e2e8f0" Margin="0,2,0,0"/>
          </StackPanel>
          <StackPanel Grid.Column="1">
            <TextBlock Text="BỘ NHỚ RAM" FontSize="10.5" Foreground="#64748b" FontWeight="SemiBold"/>
            <TextBlock x:Name="InfoRAM" Text="Đang kiểm..." FontSize="12.5" Foreground="#e2e8f0" Margin="0,2,0,0"/>
          </StackPanel>
          <StackPanel Grid.Column="2">
            <TextBlock Text="ĐỒ HỌA GPU" FontSize="10.5" Foreground="#64748b" FontWeight="SemiBold"/>
            <TextBlock x:Name="InfoGPU" Text="Đang kiểm..." FontSize="12.5" Foreground="#e2e8f0" Margin="0,2,0,0" TextTrimming="CharacterEllipsis"/>
          </StackPanel>
          <StackPanel Grid.Column="3">
            <TextBlock Text="TRỢ LÝ AI TRÊN MÁY" FontSize="10.5" Foreground="#64748b" FontWeight="SemiBold"/>
            <TextBlock x:Name="InfoIDE" Text="Đang kiểm..." FontSize="12.5" Foreground="#38bdf8" Margin="0,2,0,0" TextTrimming="CharacterEllipsis"/>
          </StackPanel>
        </Grid>
      </Border>

      <!-- Ô nhập tên thân thiện -->
      <Grid Margin="0,14,0,0">
        <Grid.ColumnDefinitions>
          <ColumnDefinition Width="Auto"/>
          <ColumnDefinition Width="*"/>
        </Grid.ColumnDefinitions>
        <StackPanel Grid.Column="0" VerticalAlignment="Center" Margin="0,0,16,0">
          <TextBlock Text="AI sẽ gọi bạn là gì?" FontSize="14" FontWeight="SemiBold" Foreground="#f1f5f9"/>
          <TextBlock Text="Để AI xưng hô tự nhiên trong mọi phiên làm việc" FontSize="12" Foreground="#8b9ab5"/>
        </StackPanel>
        <Border Grid.Column="1" Background="#0b0f18" BorderBrush="#263248" BorderThickness="1" CornerRadius="8" Padding="12,9">
          <Grid>
            <TextBlock x:Name="GoiYTen" Text="VD: Minh, Lan, Anh Nam... (để trống nếu muốn gọi là 'bạn')"
                       Foreground="#52607a" FontSize="13" VerticalAlignment="Center" IsHitTestVisible="False"/>
            <TextBox x:Name="ONhapTen" Background="Transparent" BorderThickness="0" Foreground="#f8fafc"
                     CaretBrush="#a3e635" FontSize="13.5" VerticalAlignment="Center" MaxLength="48"/>
          </Grid>
        </Border>
      </Grid>

      <!-- Lưới 2x2 + Thẻ Lô 5 Chọn 5 Lô Công Cụ -->
      <TextBlock Text="Chọn các Lô công cụ bạn muốn cài (Người mới nên giữ nguyên cả 5 Lô)"
                 FontSize="13" FontWeight="SemiBold" Foreground="#cbd5e1" Margin="0,14,0,10"/>
      <Grid>
        <Grid.ColumnDefinitions>
          <ColumnDefinition Width="*"/>
          <ColumnDefinition Width="12"/>
          <ColumnDefinition Width="*"/>
        </Grid.ColumnDefinitions>
        <Grid.RowDefinitions>
          <RowDefinition Height="Auto"/>
          <RowDefinition Height="10"/>
          <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <!-- Lô 1: Content -->
        <Border x:Name="CardLot1" Grid.Row="0" Grid.Column="0" Background="#121926" BorderBrush="#a3e635"
                BorderThickness="1.2" CornerRadius="10" Padding="14,11" Cursor="Hand">
          <StackPanel>
            <Grid>
              <CheckBox x:Name="ChkLot1" Style="{StaticResource CheckLuxury}" IsChecked="True" HorizontalAlignment="Left">
                <TextBlock Text="Lô 1 · Viết Content &amp; Lọc Văn AI" FontWeight="SemiBold" FontSize="14" Foreground="#f8fafc"/>
              </CheckBox>
              <Border Background="#182a14" BorderBrush="#365c21" BorderThickness="1" CornerRadius="6" Padding="7,2" HorizontalAlignment="Right">
                <TextBlock Text="Khuyên dùng" FontSize="10.5" Foreground="#a3e635" FontWeight="SemiBold"/>
              </Border>
            </Grid>
            <TextBlock Text="Viết kịch bản YouTube, Shorts tự nhiên như người thật, tự bắt lỗi câu sáo rỗng &amp; dịch máy."
                       Foreground="#94a3b8" FontSize="12.2" TextWrapping="Wrap" Margin="30,5,0,0" LineHeight="17"/>
            <TextBlock Text="Gồm: Vietnamese Humanizer · Chỉ dẫn Content" Foreground="#64748b" FontSize="11.2" Margin="30,5,0,0"/>
          </StackPanel>
        </Border>

        <!-- Lô 2: Edit Video -->
        <Border x:Name="CardLot2" Grid.Row="0" Grid.Column="2" Background="#121926" BorderBrush="#a3e635"
                BorderThickness="1.2" CornerRadius="10" Padding="14,11" Cursor="Hand">
          <StackPanel>
            <Grid>
              <CheckBox x:Name="ChkLot2" Style="{StaticResource CheckLuxury}" IsChecked="True" HorizontalAlignment="Left">
                <TextBlock Text="Lô 2 · Edit Video &amp; Âm Thanh" FontWeight="SemiBold" FontSize="14" Foreground="#f8fafc"/>
              </CheckBox>
              <Border Background="#182a14" BorderBrush="#365c21" BorderThickness="1" CornerRadius="6" Padding="7,2" HorizontalAlignment="Right">
                <TextBlock Text="Khuyên dùng" FontSize="10.5" Foreground="#a3e635" FontWeight="SemiBold"/>
              </Border>
            </Grid>
            <TextBlock Text="Cắt bỏ khoảng lặng tự động, chuẩn hóa tiếng -14 LUFS, mổ xẻ cấu trúc video mẫu &amp; dựng FFmpeg."
                       Foreground="#94a3b8" FontSize="12.2" TextWrapping="Wrap" Margin="30,5,0,0" LineHeight="17"/>
            <TextBlock Text="Gồm: FFmpeg · Auto-Editor · rea-video · Sound Design" Foreground="#64748b" FontSize="11.2" Margin="30,5,0,0"/>
          </StackPanel>
        </Border>

        <!-- Lô 3: Code -->
        <Border x:Name="CardLot3" Grid.Row="2" Grid.Column="0" Background="#121926" BorderBrush="#a3e635"
                BorderThickness="1.2" CornerRadius="10" Padding="14,11" Cursor="Hand">
          <StackPanel>
            <Grid>
              <CheckBox x:Name="ChkLot3" Style="{StaticResource CheckLuxury}" IsChecked="True" HorizontalAlignment="Left">
                <TextBlock Text="Lô 3 · Code &amp; Chạy Bộ Kit" FontWeight="SemiBold" FontSize="14" Foreground="#f8fafc"/>
              </CheckBox>
              <Border Background="#182a14" BorderBrush="#365c21" BorderThickness="1" CornerRadius="6" Padding="7,2" HorizontalAlignment="Right">
                <TextBlock Text="Khuyên dùng" FontSize="10.5" Foreground="#a3e635" FontWeight="SemiBold"/>
              </Border>
            </Grid>
            <TextBlock Text="Giúp AI lên kế hoạch trước khi viết code, tra cứu web hiện đại Chrome/MDN &amp; tự đọc luật dự án."
                       Foreground="#94a3b8" FontSize="12.2" TextWrapping="Wrap" Margin="30,5,0,0" LineHeight="17"/>
            <TextBlock Text="Gồm: Superpowers · Karpathy · Modern Web Guidance" Foreground="#64748b" FontSize="11.2" Margin="30,5,0,0"/>
          </StackPanel>
        </Border>

        <!-- Lô 4: Cào dữ liệu -->
        <Border x:Name="CardLot4" Grid.Row="2" Grid.Column="2" Background="#121926" BorderBrush="#a3e635"
                BorderThickness="1.2" CornerRadius="10" Padding="14,11" Cursor="Hand">
          <StackPanel>
            <Grid>
              <CheckBox x:Name="ChkLot4" Style="{StaticResource CheckLuxury}" IsChecked="True" HorizontalAlignment="Left">
                <TextBlock Text="Lô 4 · Cào Dữ Liệu &amp; Nghiên Cứu" FontWeight="SemiBold" FontSize="14" Foreground="#f8fafc"/>
              </CheckBox>
              <Border Background="#182a14" BorderBrush="#365c21" BorderThickness="1" CornerRadius="6" Padding="7,2" HorizontalAlignment="Right">
                <TextBlock Text="Khuyên dùng" FontSize="10.5" Foreground="#a3e635" FontWeight="SemiBold"/>
              </Border>
            </Grid>
            <TextBlock Text="Đo xu hướng Google/YouTube, đọc file PDF/DOCX sang chữ sạch &amp; phân tích app đối thủ."
                       Foreground="#94a3b8" FontSize="12.2" TextWrapping="Wrap" Margin="30,5,0,0" LineHeight="17"/>
            <TextBlock x:Name="MoTaLot4" Text="Gồm: REA MCP · yt-dlp · Trendspyg · MarkItDown" Foreground="#64748b" FontSize="11.2" Margin="30,5,0,0"/>
          </StackPanel>
        </Border>
      </Grid>

      <!-- Lô 5: Phản biện & Kiểm chứng (EGM) — Thẻ mảnh toàn chiều rộng -->
      <Border x:Name="CardLot5" Background="#121926" BorderBrush="#a3e635"
              BorderThickness="1.2" CornerRadius="10" Padding="14,10" Margin="0,10,0,0" Cursor="Hand">
        <StackPanel>
          <Grid>
            <CheckBox x:Name="ChkLot5" Style="{StaticResource CheckLuxury}" IsChecked="True" HorizontalAlignment="Left">
              <TextBlock Text="Lô 5 · Phản biện &amp; Kiểm chứng (EGM)" FontWeight="SemiBold" FontSize="14" Foreground="#f8fafc"/>
            </CheckBox>
            <Border Background="#182a14" BorderBrush="#365c21" BorderThickness="1" CornerRadius="6" Padding="7,2" HorizontalAlignment="Right">
              <TextBlock Text="Mới · Khuyên dùng" FontSize="10.5" Foreground="#a3e635" FontWeight="SemiBold"/>
            </Border>
          </Grid>
          <TextBlock Text="Google Elephant-Goldfish Model · 8 lệnh phản biện mù (có egm-lite tiết kiệm quota) · 10 góc nhìn độc lập cho cả Code &amp; Kịch bản"
                     Foreground="#94a3b8" FontSize="12" TextWrapping="Wrap" Margin="30,5,0,0" LineHeight="16.5"/>
        </StackPanel>
      </Border>

      <!-- Mục thu gọn Tùy chọn nâng cao (tắt mặc định) -->
      <Border Background="#0d121c" BorderBrush="#1f293d" BorderThickness="1" CornerRadius="10" Margin="0,12,0,0">
        <StackPanel>
          <Grid x:Name="NutMoNangCao" Margin="14,10" Cursor="Hand" Background="Transparent">
            <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
              <TextBlock x:Name="MuiTenNangCao" Text="&#xE70D;" FontFamily="Segoe MDL2 Assets" FontSize="11"
                         Foreground="#94a3b8" VerticalAlignment="Center" Margin="0,0,10,0"/>
              <TextBlock Text="Tùy chọn nâng cao (Tắt mặc định — chỉ bật khi máy mạnh hoặc có nhu cầu riêng)"
                         FontSize="12.5" Foreground="#cbd5e1" FontWeight="SemiBold"/>
            </StackPanel>
          </Grid>
          <StackPanel x:Name="KhungNangCao" Margin="14,0,14,12" Visibility="Collapsed">
            <Border Height="1" Background="#1e2738" Margin="0,0,0,10"/>
            <CheckBox x:Name="ChkOptOpenMontage" Style="{StaticResource CheckLuxury}" IsChecked="False" Margin="0,0,0,8">
              <StackPanel>
                <TextBlock Text="OpenMontage — Studio dựng video AI từ kho footage mở (AGPL-3.0)" FontSize="12.5" Foreground="#e2e8f0"/>
                <TextBlock Text="Tốn thêm ~500 MB và cần thiết lập API mô hình riêng nếu bạn dùng các pipeline AI." FontSize="11.5" Foreground="#64748b"/>
              </StackPanel>
            </CheckBox>
            <CheckBox x:Name="ChkOptAssetFurnace" Style="{StaticResource CheckLuxury}" IsChecked="False" Margin="0,0,0,8">
              <StackPanel>
                <TextBlock Text="AssetFurnace 3D — Tạo nhân vật 3D có xương chạy cục bộ (Apache-2.0)" FontSize="12.5" Foreground="#e2e8f0"/>
                <TextBlock x:Name="NoteAssetFurnace" Text="Chỉ bật khi máy có card đồ họa NVIDIA RTX và nhiều dung lượng trống." FontSize="11.5" Foreground="#fbbf24"/>
              </StackPanel>
            </CheckBox>
            <CheckBox x:Name="ChkOptAgentReach" Style="{StaticResource CheckLuxury}" IsChecked="False">
              <StackPanel>
                <TextBlock Text="Agent-Reach — Bộ định tuyến tìm kiếm đa nền tảng (MIT)" FontSize="12.5" Foreground="#e2e8f0"/>
                <TextBlock Text="Phục vụ nghiên cứu mở rộng nhiều mạng xã hội và RSS." FontSize="11.5" Foreground="#64748b"/>
              </StackPanel>
            </CheckBox>
          </StackPanel>
        </StackPanel>
      </Border>
    </StackPanel>

    <!-- MÀN HÌNH 2: TIẾN TRÌNH CÀI ĐẶT 7 BƯỚC MƯỢT MÀ -->
    <StackPanel x:Name="ManCai" Margin="26,16,26,18" Visibility="Collapsed">
      <Grid>
        <StackPanel>
          <TextBlock x:Name="TieuDe" Text="Đang thiết lập môi trường cho bạn" FontSize="20" FontWeight="SemiBold" Foreground="#f8fafc"/>
          <TextBlock x:Name="Phu" Text="Quá trình mất vài phút và cần internet. Bạn có thể làm việc khác trong lúc chờ."
                     Foreground="#94a3b8" Margin="0,4,0,0" TextWrapping="Wrap"/>
        </StackPanel>
        <TextBlock x:Name="PhanTram" Text="0%" FontSize="20" FontWeight="SemiBold" Foreground="#a3e635"
                   HorizontalAlignment="Right" VerticalAlignment="Top"/>
      </Grid>

      <Border Background="#111622" BorderBrush="#20293a" BorderThickness="1" CornerRadius="10" Margin="0,12,0,0">
        <StackPanel x:Name="Buoc"/>
      </Border>

      <Grid x:Name="VachNen" Margin="0,12,0,0" Height="6">
        <Border Background="#192131" CornerRadius="3"/>
        <Border x:Name="Vach" Background="#a3e635" CornerRadius="3" HorizontalAlignment="Left" Width="0"/>
      </Grid>

      <Border x:Name="KhungThongBao" Background="#161c2b" BorderBrush="#29354d" BorderThickness="1" CornerRadius="8"
              Padding="14,10" Margin="0,12,0,0" Visibility="Collapsed">
        <TextBlock x:Name="Loi" TextWrapping="Wrap" Foreground="#f1f5f9" LineHeight="19"/>
      </Border>

      <Grid Margin="0,14,0,0">
        <TextBlock x:Name="ChiTiet" VerticalAlignment="Center" Foreground="#94a3b8" Cursor="Hand"
                   Text="Xem nhật ký kỹ thuật" TextDecorations="Underline"/>
        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
          <Button x:Name="Phu2" Style="{StaticResource NutPhu}" Visibility="Collapsed"/>
          <Button x:Name="Chinh" Style="{StaticResource NutChinh}" Visibility="Collapsed"/>
        </StackPanel>
      </Grid>
    </StackPanel>

    <!-- MÀN HÌNH 3: HOÀN TẤT SANG TRỌNG + BÁO CÁO DOCTOR -->
    <StackPanel x:Name="ManXong" Margin="26,18,26,20" Visibility="Collapsed">
      <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
        <Border Width="44" Height="44" CornerRadius="22" Background="#1b2e13" BorderBrush="#a3e635" BorderThickness="1.5">
          <TextBlock Text="&#xE73E;" FontFamily="Segoe MDL2 Assets" FontSize="20" Foreground="#a3e635"
                     FontWeight="Bold" HorizontalAlignment="Center" VerticalAlignment="Center"/>
        </Border>
        <StackPanel Margin="14,0,0,0" VerticalAlignment="Center">
          <TextBlock Text="Cài xong rồi! Máy bạn đã sẵn sàng sáng tạo." FontSize="20" FontWeight="SemiBold" Foreground="#f8fafc"/>
          <TextBlock x:Name="PhuXong" Text="Hãy mở lại trình biên tập AI (Antigravity / Claude Code / Codex) để nạp toàn bộ kỹ năng mới."
                     Foreground="#94a3b8" Margin="0,3,0,0" TextWrapping="Wrap"/>
        </StackPanel>
      </StackPanel>

      <Border Background="#111622" BorderBrush="#20293a" BorderThickness="1" CornerRadius="10" Padding="18,14" Margin="0,16,0,0">
        <StackPanel x:Name="TomTatKetQua"/>
      </Border>

      <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,14,0,0">
        <Button x:Name="NutGitHubLogin" Style="{StaticResource NutPhu}" Content="Đăng nhập GitHub (Tải Kit)" Visibility="Collapsed"/>
        <Button x:Name="NutSaoLuu" Style="{StaticResource NutPhu}" Content="Sao lưu cấu hình (Chuyển máy)"
                ToolTip="Tạo bản sao lưu cấu hình nén ZIP có mã kiểm tra SHA-256 để chuyển sang máy mới"/>
      </StackPanel>
      <TextBlock x:Name="TrangThaiSaoLuu" Visibility="Collapsed" TextWrapping="Wrap" FontSize="12"
                 Foreground="#a3e635" Margin="0,8,0,0" HorizontalAlignment="Right" TextAlignment="Right"/>

      <Grid Margin="0,12,0,0">
        <TextBlock x:Name="ChiTietXong" VerticalAlignment="Center" Foreground="#94a3b8" Cursor="Hand"
                   Text="Xem nhật ký cài đặt" TextDecorations="Underline"/>
        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
          <Button x:Name="NutMoChiDan" Style="{StaticResource NutChinh}" Content="Mở thư mục 5 Bộ Chỉ Dẫn"/>
          <Button x:Name="NutHoanTat" Style="{StaticResource NutPhu}" Content="Hoàn tất"/>
        </StackPanel>
      </Grid>
    </StackPanel>
      </StackPanel>
    </ScrollViewer>
  </DockPanel>
</Window>
'@

try {
  $w = [Windows.Markup.XamlReader]::Parse($XAML)
  $w.MaxHeight = [Math]::Max(520, [System.Windows.SystemParameters]::WorkArea.Height - 28)
  $w.Title = "Studio AI Setup v$($script:appVer)"
} catch {
  Ghi "Khong dung duoc giao dien WPF: $($_.Exception.Message)"
  exit 91
}

$el = @{}
@(
  'Dau','Logo','NhanPhienBan','LinkHuongDanTop','Dong','FooterChao','NutBatDau','KhungCuon',
  'ManChao','InfoOS','InfoRAM','InfoGPU','InfoIDE','GoiYTen','ONhapTen',
  'CardLot1','CardLot2','CardLot3','CardLot4','CardLot5','ChkLot1','ChkLot2','ChkLot3','ChkLot4','ChkLot5','MoTaLot4',
  'NutMoNangCao','MuiTenNangCao','KhungNangCao','ChkOptOpenMontage','ChkOptAssetFurnace','NoteAssetFurnace','ChkOptAgentReach',
  'ManCai','TieuDe','Phu','PhanTram','Buoc','VachNen','Vach','KhungThongBao','Loi','ChiTiet','Phu2','Chinh',
  'ManXong','PhuXong','TomTatKetQua','ChiTietXong','NutGitHubLogin','NutSaoLuu','TrangThaiSaoLuu','NutMoChiDan','NutHoanTat'
) | ForEach-Object { $el[$_] = $w.FindName($_) }

# Gán phiên bản động từ catalog-lock.json
$el.NhanPhienBan.Text = "v$($script:appVer) · Miễn phí · MIT"
$el.MoTaLot4.Text = "Gồm: REA $($script:reaVer) · yt-dlp · Trendspyg · MarkItDown"

$ico = Join-Path $GOC 'brand\studio-ai.ico'
if (Test-Path -LiteralPath $ico) {
  try {
    $giai = [Windows.Media.Imaging.BitmapDecoder]::Create([Uri]$ico, 'None', 'OnLoad')
    $el.Logo.Source = $giai.Frames | Sort-Object { $_.PixelWidth } -Descending | Select-Object -First 1
    $w.Icon = $giai.Frames | Sort-Object { $_.PixelWidth } | Select-Object -First 1
  } catch { Ghi "Logo: $($_.Exception.Message)" }
}

# Pre-flight ngay khi mở cửa sổ
$script:preflight = QuetMayNhanh
$el.InfoOS.Text = if ($script:preflight.is64) { 'Windows 64-bit' } else { 'Windows 32-bit' }
$el.InfoRAM.Text = "$($script:preflight.ramGb) GB"
$el.InfoGPU.Text = $script:preflight.gpu.name
$el.InfoIDE.Text = $script:preflight.ideText

if (-not $script:preflight.gpu.supports3d) {
  $el.ChkOptAssetFurnace.IsChecked = $false
  $el.ChkOptAssetFurnace.IsEnabled = $false
  $el.NoteAssetFurnace.Text = 'Máy chưa phát hiện GPU NVIDIA RTX — nên bỏ qua để tránh tải nặng vô ích.'
  $el.NoteAssetFurnace.Foreground = '#94a3b8'
}

# Watermark ô nhập tên + điền sẵn tên đã lưu từ state.json khi nâng cấp
$el.ONhapTen.Add_TextChanged({
  $el.GoiYTen.Visibility = if ([string]::IsNullOrEmpty($el.ONhapTen.Text)) { 'Visible' } else { 'Collapsed' }
})
if ($script:savedUserName) {
  $el.ONhapTen.Text = $script:savedUserName
  $el.GoiYTen.Visibility = 'Collapsed'
}

# Đồng bộ viền sáng khi chọn / bỏ chọn thẻ Lô
function CapNhatVienThe($chk, $card) {
  if ($chk.IsChecked) {
    $card.BorderBrush = '#a3e635'
    $card.Background = '#121926'
  } else {
    $card.BorderBrush = '#222b3e'
    $card.Background = '#0d121c'
  }
}
$pairs = @(
  @($el.ChkLot1, $el.CardLot1),
  @($el.ChkLot2, $el.CardLot2),
  @($el.ChkLot3, $el.CardLot3),
  @($el.ChkLot4, $el.CardLot4),
  @($el.ChkLot5, $el.CardLot5)
)
foreach ($p in $pairs) {
  $chk = $p[0]; $card = $p[1]
  $chk.Tag = $card
  $card.Tag = $chk
  $chk.Add_Checked({ param($s, $e) CapNhatVienThe $s $s.Tag })
  $chk.Add_Unchecked({ param($s, $e) CapNhatVienThe $s $s.Tag })
  $card.Add_MouseLeftButtonUp({
    param($s, $e)
    if ($e.OriginalSource -isnot [Windows.Controls.Primitives.ToggleButton]) {
      $s.Tag.IsChecked = -not $s.Tag.IsChecked
    }
  })
}

# Mục thu gọn Tùy chọn nâng cao
$el.NutMoNangCao.Add_MouseLeftButtonUp({
  if ($el.KhungNangCao.Visibility -eq 'Collapsed') {
    $el.KhungNangCao.Visibility = 'Visible'
    $el.MuiTenNangCao.Text = [string][char]0xE70E
  } else {
    $el.KhungNangCao.Visibility = 'Collapsed'
    $el.MuiTenNangCao.Text = [string][char]0xE70D
  }
})

# Khởi tạo 7 bước cho Màn hình 2
$MAU = @{ cho = '#3b4963'; chay = '#a3e635'; xong = '#a3e635'; loi = '#fb7185'; bo = '#94a3b8' }
$BUOC = @(
  @{ ten = 'Nền tảng chạy công cụ'; mo = 'Python · uv · Node.js LTS · Git · GitHub CLI' },
  @{ ten = 'Lô 1 · Content'; mo = 'Kỹ năng lọc văn tiếng Việt tự nhiên & công cụ rà soát' },
  @{ ten = 'Lô 2 · Edit Video'; mo = "FFmpeg $($script:ffmpegVer) · Auto-Editor · rea-video · Sound Design" },
  @{ ten = 'Lô 3 · Code & Bộ Kit'; mo = 'Superpowers · Karpathy · Modern Web Guidance' },
  @{ ten = 'Lô 4 · Cào Dữ Liệu & Nghiên Cứu'; mo = "REA $($script:reaVer) MCP · yt-dlp · Trendspyg · MarkItDown" },
  @{ ten = 'Lô 5 · Phản biện & Kiểm chứng (EGM)'; mo = 'Google Elephant-Goldfish Model · 8 lệnh phản biện mù · 10 góc nhìn độc lập' },
  @{ ten = 'Hoàn tất · Quy tắc, 5 Bộ Chỉ Dẫn & Kiểm tra Doctor'; mo = 'Đồng bộ quy tắc AI, chép 5 Bộ Chỉ Dẫn tiếng Việt & kiểm tra sức khỏe hệ thống' }
)
$hang = @()
for ($i = 0; $i -lt $BUOC.Count; $i++) {
  $g = New-Object Windows.Controls.Grid
  $g.Margin = '16,7,16,7'
  $c0 = New-Object Windows.Controls.ColumnDefinition; $c0.Width = '36'
  $c1 = New-Object Windows.Controls.ColumnDefinition
  $g.ColumnDefinitions.Add($c0); $g.ColumnDefinitions.Add($c1)
  $vong = New-Object Windows.Controls.Border
  $vong.Width = 22; $vong.Height = 22; $vong.CornerRadius = 11; $vong.BorderThickness = 2
  $vong.BorderBrush = $MAU.cho; $vong.VerticalAlignment = 'Center'; $vong.HorizontalAlignment = 'Left'
  $dau = New-Object Windows.Controls.TextBlock
  $dau.FontFamily = 'Segoe MDL2 Assets'; $dau.FontSize = 11; $dau.HorizontalAlignment = 'Center'; $dau.VerticalAlignment = 'Center'
  $vong.Child = $dau
  $chu = New-Object Windows.Controls.StackPanel
  [Windows.Controls.Grid]::SetColumn($chu, 1)
  $t = New-Object Windows.Controls.TextBlock; $t.Text = $BUOC[$i].ten; $t.FontWeight = 'SemiBold'; $t.Foreground = '#f1f5f9'
  $m = New-Object Windows.Controls.TextBlock; $m.Text = $BUOC[$i].mo; $m.Foreground = '#8b9ab5'; $m.FontSize = 12.2
  $m.Margin = '0,2,0,0'; $m.TextWrapping = 'Wrap'
  $chu.Children.Add($t) | Out-Null; $chu.Children.Add($m) | Out-Null
  $g.Children.Add($vong) | Out-Null; $g.Children.Add($chu) | Out-Null
  if ($i -gt 0) {
    $ke = New-Object Windows.Controls.Border; $ke.Height = 1; $ke.Background = '#1d2536'
    $el.Buoc.Children.Add($ke) | Out-Null
  }
  $el.Buoc.Children.Add($g) | Out-Null
  $hang += @{ vong = $vong; dau = $dau; mo = $m; title = $t }
}
$script:trangThai = @('cho') * $BUOC.Count

function CapNhatThanhTienTrinh {
  $xong = @($script:trangThai | Where-Object { $_ -in 'xong', 'bo' }).Count
  $pct = [Math]::Round(100 * $xong / $hang.Count)
  $el.PhanTram.Text = "$pct%"
  $maxW = 700
  if ($el.VachNen -and $el.VachNen.ActualWidth -gt 0) {
    $maxW = $el.VachNen.ActualWidth
  } elseif ($el.Vach -and $el.Vach.Parent -and $el.Vach.Parent.ActualWidth -gt 0) {
    $maxW = $el.Vach.Parent.ActualWidth
  }
  $el.Vach.Width = [Math]::Round($maxW * $xong / $hang.Count)
}

$el.VachNen.Add_SizeChanged({ CapNhatThanhTienTrinh })

function DatBuoc([int]$i, [string]$tt, [string]$mo) {
  $h = $hang[$i]
  switch ($tt) {
    'chay' {
      $cham = New-Object Windows.Shapes.Ellipse; $cham.Width = 8; $cham.Height = 8; $cham.Fill = $MAU.chay
      $h.vong.BorderBrush = $MAU.chay; $h.vong.Background = 'Transparent'; $h.vong.Child = $cham
      $h.title.Foreground = '#f8fafc'
    }
    'xong' {
      $h.vong.Child = $h.dau; $h.vong.BorderBrush = $MAU.xong; $h.vong.Background = $MAU.xong
      $h.dau.Text = [string][char]0xE73E; $h.dau.Foreground = '#081104'
    }
    'loi' {
      $h.vong.Child = $h.dau; $h.vong.BorderBrush = $MAU.loi; $h.vong.Background = $MAU.loi
      $h.dau.Text = [string][char]0xE8BB; $h.dau.Foreground = '#090c12'
    }
    'bo' {
      $h.vong.Child = $h.dau; $h.vong.BorderBrush = $MAU.bo; $h.vong.Background = 'Transparent'
      $h.dau.Text = [string][char]0xE738; $h.dau.Foreground = $MAU.bo
      $h.title.Foreground = '#94a3b8'
    }
  }
  if ($mo) { $h.mo.Text = $mo }
  $script:trangThai[$i] = $tt
  CapNhatThanhTienTrinh
}

$script:hanhDongChinh = $null
$script:hanhDongPhu = $null
$script:buocHienTai = { Buoc0 }
function Nut([string]$chinh, [scriptblock]$lamChinh, [string]$phu, [scriptblock]$lamPhu) {
  $script:hanhDongChinh = $lamChinh; $script:hanhDongPhu = $lamPhu
  if ($chinh) { $el.Chinh.Content = $chinh; $el.Chinh.Visibility = 'Visible' } else { $el.Chinh.Visibility = 'Collapsed' }
  if ($phu) { $el.Phu2.Content = $phu; $el.Phu2.Visibility = 'Visible' } else { $el.Phu2.Visibility = 'Collapsed' }
}

function BaoLoi([string]$chu) {
  if ($chu) {
    $el.Loi.Text = $chu
    $el.KhungThongBao.Visibility = 'Visible'
  } else {
    $el.KhungThongBao.Visibility = 'Collapsed'
  }
}

function An([scriptblock]$khoi, [object[]]$thamSo = @()) {
  try { & $khoi @thamSo } catch {
    Ghi "LOI: $($_.Exception.Message)`r`n$($_.ScriptStackTrace)"
    $dang = [Array]::IndexOf($script:trangThai, 'chay')
    if ($dang -ge 0) { DatBuoc $dang 'loi' 'Có trục trặc nhỏ ở bước này' }
    BaoLoi 'Đã gặp sự cố bất ngờ. Bạn bấm «Xem nhật ký kỹ thuật» để kiểm tra, hoặc bấm «Thử lại».'
    $retryBlock = if ($script:buocHienTai) { $script:buocHienTai } else { { Buoc0 } }
    Nut 'Thử lại' $retryBlock 'Đóng' { $w.Close() }
  }
}

$el.Chinh.Add_Click({ if ($script:hanhDongChinh) { An $script:hanhDongChinh } })
$el.Phu2.Add_Click({ if ($script:hanhDongPhu) { An $script:hanhDongPhu } })
$el.Dau.Add_MouseLeftButtonDown({ try { $w.DragMove() } catch {} })
$el.ChiTiet.Add_MouseLeftButtonUp({ Start-Process notepad.exe -ArgumentList "`"$LOG`"" })
$el.ChiTietXong.Add_MouseLeftButtonUp({ Start-Process notepad.exe -ArgumentList "`"$LOG`"" })
$el.LinkHuongDanTop.Add_MouseLeftButtonUp({
  $localGuide = Join-Path $GOC 'chi-dan\00-BAT-DAU-NHANH.md'
  if (Test-Path -LiteralPath $localGuide) { Start-Process notepad.exe -ArgumentList "`"$localGuide`"" }
})

# Chạy tiến trình nền an toàn bằng .NET ProcessStartInfo + ReadToEndAsync (KHÔNG qua shell trung gian)
$script:viec = $null
$script:viecOutTask = $null
$script:viecErrTask = $null
$script:sauViec = $null
$script:hanViec = $null
$script:doctorData = $null
$script:finalizeOk = $false

function ChayLenhAn(
  [string]$filePath,
  [string[]]$argList,
  [scriptblock]$xong,
  [string]$noiChay = $GOC,
  [int]$phutToiDa = 20,
  [hashtable]$extraEnv = $null
) {
  $joinedArgs = Join-Win32Args $argList
  Ghi "`r`n> `"$filePath`" $joinedArgs   (o $noiChay)"
  $psi = New-Object Diagnostics.ProcessStartInfo
  $psi.FileName = $filePath
  $psi.Arguments = $joinedArgs
  $psi.WorkingDirectory = $noiChay
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
  $psi.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
  $psi.EnvironmentVariables['PATH'] = $env:Path
  $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
  $psi.EnvironmentVariables['PYTHONUTF8'] = '1'
  if ($script:tenNguoiDung) {
    $psi.EnvironmentVariables['STUDIO_AI_USER_NAME'] = [string]$script:tenNguoiDung
  }
  if ($extraEnv) {
    foreach ($k in $extraEnv.Keys) {
      $psi.EnvironmentVariables[$k] = [string]$extraEnv[$k]
    }
  }

  $proc = New-Object Diagnostics.Process
  $proc.StartInfo = $psi
  try {
    if (-not $proc.Start()) {
      $proc.Dispose()
      throw "Khong khoi chay duoc tien trinh: $filePath"
    }
  } catch {
    try { $proc.Dispose() } catch {}
    throw
  }

  $script:viec = $proc
  $script:viecOutTask = $proc.StandardOutput.ReadToEndAsync()
  $script:viecErrTask = $proc.StandardError.ReadToEndAsync()
  $script:sauViec = $xong
  $script:hanViec = (Get-Date).AddMinutes($phutToiDa)
}

function ChayEngineAn([string[]]$engineArgs, [scriptblock]$xong, [int]$phutToiDa = 20) {
  $py = TimPythonHopLe
  if (-not $py) { throw 'Không tìm thấy Python 3.10+ hợp lệ trên máy.' }
  $fullArgs = @('-B', $ENGINE) + @($engineArgs)
  $envMap = @{
    STUDIO_AI_USER_NAME     = $script:tenNguoiDung
    PYTHONIOENCODING        = 'utf-8'
    PYTHONUTF8              = '1'
    PYTHONDONTWRITEBYTECODE = '1'
  }
  ChayLenhAn $py $fullArgs $xong -noiChay $GOC -phutToiDa $phutToiDa -extraEnv $envMap
}

function ChayTaiTrucTiep([string]$key, [scriptblock]$xong, [int]$phut = 15) {
  $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  if (-not (Test-Path -LiteralPath $psExe)) { $psExe = 'powershell.exe' }
  $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $TAI_NEN_TANG, '-Package', $key, '-Catalog', $CATALOG_PATH)
  ChayLenhAn $psExe $argList $xong -noiChay $GOC -phutToiDa $phut
}

function ChayWinget([string]$wingetId, [scriptblock]$xong, [int]$phut = 15) {
  $wgCmd = Get-Command 'winget.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $wgCmd -or -not $wgCmd.Source) {
    An $xong @(1, '', 'winget.exe khong co san')
    return
  }
  $argList = @(
    'install', '-e', '--id', $wingetId,
    '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity'
  )
  ChayLenhAn $wgCmd.Source $argList $xong -noiChay $GOC -phutToiDa $phut
}

$hen = New-Object Windows.Threading.DispatcherTimer
$hen.Interval = [TimeSpan]::FromMilliseconds(400)
$hen.Add_Tick({
  $v = $script:viec
  if (-not $v) { return }
  $ma = $null
  if ($v.HasExited) {
    $ma = $v.ExitCode
  } elseif ((Get-Date) -gt $script:hanViec) {
    Ghi '(qua thoi gian, dung tac vu)'
    try { Start-Process taskkill.exe -ArgumentList @('/PID', "$($v.Id)", '/T', '/F') -WindowStyle Hidden -Wait } catch {}
    try { if (-not $v.HasExited) { $v.Kill() } } catch {}
    $ma = -1
  }
  if ($null -eq $ma) { return }

  $outTask = $script:viecOutTask
  $errTask = $script:viecErrTask
  $sau = $script:sauViec
  $script:viec = $null
  $script:viecOutTask = $null
  $script:viecErrTask = $null
  $script:sauViec = $null

  $stdoutText = ''
  $stderrText = ''
  try {
    if ($outTask -and $outTask.Wait(3000)) {
      $stdoutText = [string]$outTask.Result
    }
  } catch {}
  try {
    if ($errTask -and $errTask.Wait(3000)) {
      $stderrText = [string]$errTask.Result
    }
  } catch {}
  try { $v.Dispose() } catch {}

  if ($stdoutText) { Ghi ($stdoutText.TrimEnd("`r", "`n")) }
  if ($stderrText) { Ghi ("[stderr]`r`n" + $stderrText.TrimEnd("`r", "`n")) }
  Ghi "(ma thoat $ma)"

  if ($sau) {
    An $sau @($ma, $stdoutText, $stderrText)
  }
})
$hen.Start()

# Lưu lựa chọn từ Screen 1
$script:luaChon = @{
  ten = 'bạn'; lot1 = $true; lot2 = $true; lot3 = $true; lot4 = $true; lot5 = $true
  openmontage = $false; assetfurnace = $false; agentreach = $false
}
$script:tenNguoiDung = 'bạn'
$script:coreQueue = @()
$script:coreTotal = 0
$script:coreDone = 0
$script:coreFailed = @()
$script:coreCurrent = $null

function KiemTraMon([string]$key) {
  NapLaiPath
  switch ($key) {
    'python' { return [bool](TimPythonHopLe) }
    'uv'     { return (Co 'uv') }
    'node'   { return [bool](NodeDatChuan).ok }
    'git'    { return (Co 'git') }
    'gh'     { return (Co 'gh') }
    'ffmpeg' { return (Co 'ffmpeg.exe') }
    default  { return $false }
  }
}

function ChayHangDoiNenTang {
  if ($script:coreQueue.Count -eq 0) {
    NapLaiPath
    if ($script:coreFailed.Count -gt 0) {
      $dsLoi = $script:coreFailed -join ', '
      DatBuoc 0 'loi' "Chưa cài được: $dsLoi"
      BaoLoi "Không tự cài được: $dsLoi (kiểm tra kết nối mạng hoặc bấm «Xem nhật ký kỹ thuật»)."
      Nut 'Thử lại' { Buoc0 } 'Đóng' { $w.Close() }
      return
    }
    Buoc0
    return
  }

  $item = $script:coreQueue[0]
  $script:coreQueue = @($script:coreQueue | Select-Object -Skip 1)
  $script:coreCurrent = $item
  $soThuTu = $script:coreDone + 1

  # Ưu tiên tải trực tiếp HTTPS + SHA-256 trước; chỉ dự phòng sang Winget nếu tải trực tiếp thất bại
  DatBuoc 0 'chay' "Đang tải trực tiếp $($item.ten) ($soThuTu/$($script:coreTotal)) (HTTPS + SHA-256)…"
  ChayTaiTrucTiep $item.key {
    param($maDirect)
    $cur = $script:coreCurrent
    if (KiemTraMon $cur.key) {
      $script:coreDone += 1
      ChayHangDoiNenTang
      return
    }
    if ((Co 'winget.exe') -and $cur.id) {
      DatBuoc 0 'chay' "Tải trực tiếp $($cur.ten) chưa xong, đang thử dự phòng qua Winget…"
      ChayWinget $cur.id {
        param($maWg)
        $c2 = $script:coreCurrent
        if (-not (KiemTraMon $c2.key)) {
          $script:coreFailed += $c2.ten
        }
        $script:coreDone += 1
        ChayHangDoiNenTang
      } 15
    } else {
      $script:coreFailed += $cur.ten
      $script:coreDone += 1
      ChayHangDoiNenTang
    }
  } 15
}

function Buoc0 {
  $script:buocHienTai = { Buoc0 }
  BaoLoi ''; Nut $null $null $null $null
  NapLaiPath
  $missing = @()
  if (-not (TimPythonHopLe)) { $missing += @{ key = 'python'; ten = 'Python 3.12'; id = 'Python.Python.3.12' } }
  if (-not (Co 'uv')) { $missing += @{ key = 'uv'; ten = 'uv (Trình tải Python)'; id = 'astral-sh.uv' } }
  $nodeInfo = NodeDatChuan
  if (-not $nodeInfo.ok) { $missing += @{ key = 'node'; ten = 'Node.js LTS'; id = 'OpenJS.NodeJS.LTS' } }
  if (-not (Co 'git')) { $missing += @{ key = 'git'; ten = 'Git'; id = 'Git.Git' } }
  if (-not (Co 'gh')) { $missing += @{ key = 'gh'; ten = 'GitHub CLI'; id = 'GitHub.cli' } }

  if ($missing.Count -eq 0) {
    DatBuoc 0 'xong' "Đã đủ nền tảng (Python · uv · Node.js $($nodeInfo.version) · Git · GitHub CLI)"
    Buoc1; return
  }

  $dsTen = ($missing | ForEach-Object { $_.ten }) -join ', '
  DatBuoc 0 'chay' "Cần cài thêm: $dsTen"
  BaoLoi "Máy cần cài thêm nền tảng miễn phí: $dsTen. Bộ cài sẽ tự tải trực tiếp từ trang chủ chính thức (HTTPS + kiểm tra SHA-256, không cần quyền Admin hay Winget). Bấm «Cài giúp mình» để bắt đầu."
  $script:pendingCoreMissing = @($missing)
  Nut 'Cài giúp mình' {
    BaoLoi 'Đang tự động tải trực tiếp và cài đặt nền tảng miễn phí (HTTPS + SHA-256). Vui lòng đợi trong giây lát…'
    Nut $null $null $null $null
    $script:coreQueue = @($script:pendingCoreMissing)
    $script:coreTotal = $script:coreQueue.Count
    $script:coreDone = 0
    $script:coreFailed = @()
    $script:coreCurrent = $null
    ChayHangDoiNenTang
  } 'Thoát' { $w.Close() }
}

function Buoc1 {
  $script:buocHienTai = { Buoc1 }
  BaoLoi ''; Nut $null $null $null $null
  if (-not $script:luaChon.lot1) { DatBuoc 1 'bo' 'Bỏ qua theo lựa chọn của bạn'; Buoc2; return }
  DatBuoc 1 'chay' 'Đang tải bộ lọc văn tiếng Việt (Vietnamese Humanizer)…'
  ChayEngineAn @('--install-lot', 'lot1', '--json') {
    param($ma)
    if ($ma -eq 0) {
      DatBuoc 1 'xong' 'Đã cài xong kỹ năng Content & công cụ lọc văn AI'
      Buoc2
    } else {
      DatBuoc 1 'loi' 'Chưa cài xong Lô 1 (kiểm tra mạng rồi thử lại)'
      BaoLoi 'Cài Lô 1 chưa thành công (thường do mạng chập chờn). Bấm «Thử lại» hoặc «Bỏ qua» để đi tiếp.'
      Nut 'Thử lại' { Buoc1 } 'Bỏ qua' { DatBuoc 1 'bo' 'Đã bỏ qua Lô 1'; Buoc2 }
    }
  }
}

function Buoc2 {
  $script:buocHienTai = { Buoc2 }
  BaoLoi ''; Nut $null $null $null $null
  if (-not $script:luaChon.lot2) { DatBuoc 2 'bo' 'Bỏ qua theo lựa chọn của bạn'; Buoc3; return }
  NapLaiPath
  if (-not (Co 'ffmpeg.exe')) {
    # Ưu tiên tải trực tiếp HTTPS + SHA-256 trước; chỉ dự phòng Winget nếu thất bại
    DatBuoc 2 'chay' "Đang tải trực tiếp FFmpeg $($script:ffmpegVer) (HTTPS + SHA-256)…"
    ChayTaiTrucTiep 'ffmpeg' {
      param($maDirect)
      NapLaiPath
      if (Co 'ffmpeg.exe') {
        Buoc2PhanPython
        return
      }
      if (Co 'winget.exe') {
        DatBuoc 2 'chay' 'Tải trực tiếp FFmpeg chưa xong, đang thử dự phòng qua Winget…'
        ChayWinget 'Gyan.FFmpeg' {
          param($maWg)
          NapLaiPath
          if (-not (Co 'ffmpeg.exe')) {
            DatBuoc 2 'loi' 'Chưa tự cài được FFmpeg'
            BaoLoi 'Không tự cài được FFmpeg. Bạn có thể bấm «Thử lại» hoặc «Bỏ qua FFmpeg» để cài tiếp các công cụ còn lại.'
            Nut 'Thử lại' { Buoc2 } 'Bỏ qua FFmpeg' { Buoc2PhanPython }
            return
          }
          Buoc2PhanPython
        } 15
      } else {
        DatBuoc 2 'loi' 'Chưa tự cài được FFmpeg'
        BaoLoi 'Không tự tải/cài được FFmpeg. Bạn có thể bấm «Thử lại» hoặc «Bỏ qua FFmpeg» để cài tiếp các công cụ còn lại.'
        Nut 'Thử lại' { Buoc2 } 'Bỏ qua FFmpeg' { Buoc2PhanPython }
      }
    } 15
    return
  }
  Buoc2PhanPython
}

function Buoc2PhanPython {
  $script:buocHienTai = { Buoc2PhanPython }
  DatBuoc 2 'chay' 'Đang cài Auto-Editor, rea-video, FFmpeg Skill & Sound Design…'
  $argsList = @('--install-lot', 'lot2', '--json')
  if ($script:luaChon.openmontage) { $argsList += '--opt-openmontage' }
  if ($script:luaChon.assetfurnace) { $argsList += '--opt-assetfurnace' }
  ChayEngineAn $argsList {
    param($ma)
    if ($ma -eq 0) {
      DatBuoc 2 'xong' 'Đã cài đủ bộ công cụ Edit Video & phân tích video mẫu'
      Buoc3
    } else {
      DatBuoc 2 'loi' 'Chưa cài xong Lô 2 · Edit Video'
      BaoLoi 'Bước cài công cụ Edit Video gặp lỗi (xem chi tiết trong nhật ký). Bạn có thể thử lại hoặc tạm bỏ qua.'
      Nut 'Thử lại' { Buoc2PhanPython } 'Bỏ qua' { DatBuoc 2 'bo' 'Đã bỏ qua Lô 2'; Buoc3 }
    }
  } 25
}

function Buoc3 {
  $script:buocHienTai = { Buoc3 }
  BaoLoi ''; Nut $null $null $null $null
  if (-not $script:luaChon.lot3) { DatBuoc 3 'bo' 'Bỏ qua theo lựa chọn của bạn'; Buoc4; return }
  DatBuoc 3 'chay' 'Đang cài Superpowers, Karpathy & Modern Web Guidance…'
  ChayEngineAn @('--install-lot', 'lot3', '--json') {
    param($ma)
    if ($ma -eq 0) {
      DatBuoc 3 'xong' 'Đã cài kỹ năng Code chuẩn (Superpowers · Karpathy · Modern Web)'
      Buoc4
    } else {
      DatBuoc 3 'loi' 'Chưa cài xong Lô 3 · Code'
      BaoLoi 'Cài Lô 3 chưa hoàn tất. Bấm «Thử lại» hoặc «Bỏ qua».'
      Nut 'Thử lại' { Buoc3 } 'Bỏ qua' { DatBuoc 3 'bo' 'Đã bỏ qua Lô 3'; Buoc4 }
    }
  }
}

function Buoc4 {
  $script:buocHienTai = { Buoc4 }
  BaoLoi ''; Nut $null $null $null $null
  if (-not $script:luaChon.lot4) { DatBuoc 4 'bo' 'Bỏ qua theo lựa chọn của bạn'; Buoc5; return }
  DatBuoc 4 'chay' "Đang cài REA $($script:reaVer) MCP, yt-dlp, Trendspyg & MarkItDown…"
  $argsList = @('--install-lot', 'lot4', '--json')
  if ($script:luaChon.agentreach) { $argsList += '--opt-agent-reach' }
  ChayEngineAn $argsList {
    param($ma)
    if ($ma -eq 0) {
      DatBuoc 4 'xong' "Đã cài REA $($script:reaVer) & bộ công cụ nghiên cứu, đọc tài liệu"
      Buoc5
    } else {
      DatBuoc 4 'loi' 'Chưa cài xong Lô 4 · Cào dữ liệu'
      BaoLoi 'Cài Lô 4 chưa hoàn tất. Bấm «Thử lại» hoặc «Bỏ qua».'
      Nut 'Thử lại' { Buoc4 } 'Bỏ qua' { DatBuoc 4 'bo' 'Đã bỏ qua Lô 4'; Buoc5 }
    }
  }
}

function Buoc5 {
  $script:buocHienTai = { Buoc5 }
  BaoLoi ''; Nut $null $null $null $null
  if (-not $script:luaChon.lot5) { DatBuoc 5 'bo' 'Bỏ qua theo lựa chọn của bạn'; Buoc6; return }
  DatBuoc 5 'chay' 'Đang cài đặt Lô 5 · Phản biện & Kiểm chứng (Google EGM)…'
  ChayEngineAn @('--install-lot', 'lot5', '--json') {
    param($ma)
    if ($ma -eq 0) {
      DatBuoc 5 'xong' 'Đã cài xong EGM (8 lệnh phản biện mù · 10 góc nhìn độc lập)'
      Buoc6
    } else {
      DatBuoc 5 'loi' 'Chưa cài xong Lô 5 · Phản biện (EGM)'
      BaoLoi 'Cài Lô 5 (EGM) chưa hoàn tất. Bấm «Thử lại» hoặc «Bỏ qua» để tiếp tục hoàn tất.'
      Nut 'Thử lại' { Buoc5 } 'Bỏ qua' { DatBuoc 5 'bo' 'Đã bỏ qua Lô 5'; Buoc6 }
    }
  }
}

function TaoLoiTatDesktop {
  $ws = New-Object -ComObject WScript.Shell
  $conhost = Join-Path $env:SystemRoot 'System32\conhost.exe'
  $ps1Path = Join-Path $GOC 'scripts\cai-dat.ps1'
  $batPath = Join-Path $GOC 'cai-dat.bat'
  $useConhost = Test-Path -LiteralPath $conhost
  foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    if (-not $dir) { continue }
    $lnkPath = Join-Path $dir 'Studio AI Setup.lnk'
    $lnk = $ws.CreateShortcut($lnkPath)
    if ($useConhost) {
      $lnk.TargetPath = $conhost
      $lnk.Arguments = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File `"$ps1Path`""
    } else {
      $lnk.TargetPath = $batPath
    }
    $lnk.WorkingDirectory = $GOC
    $lnk.WindowStyle = 7
    if (Test-Path -LiteralPath $ico) { $lnk.IconLocation = "$ico,0" }
    $lnk.Description = "Mở Studio AI Setup v$($script:appVer)"
    $lnk.Save()
  }
}

function Buoc6 {
  $script:buocHienTai = { Buoc6 }
  BaoLoi ''; Nut $null $null $null $null
  $script:doctorData = $null
  $script:finalizeOk = $false
  DatBuoc 6 'chay' 'Đang đồng bộ quy tắc AI, chép 5 Bộ Chỉ Dẫn tiếng Việt & kiểm tra Doctor…'

  $okLots = @()
  for ($idx = 1; $idx -le 5; $idx++) {
    if ($script:trangThai[$idx] -eq 'xong') { $okLots += "lot$idx" }
  }
  $finArgs = @('--install-lot', 'finalize', '--json')
  if ($okLots.Count -gt 0) {
    $finArgs += @('--lots', ($okLots -join ','))
  }

  ChayEngineAn $finArgs {
    param($maFin)
    try { TaoLoiTatDesktop } catch { Ghi "Tao shortcut: $($_.Exception.Message)" }
    $script:finalizeOk = ($maFin -eq 0)
    DatBuoc 6 'chay' 'Đang chạy kiểm tra sức khỏe hệ thống (Doctor)…'
    ChayEngineAn @('--verify-json') {
      param($maVer, $verOut, $verErr)
      if ($maVer -eq 0 -and $verOut) {
        $script:doctorData = Parse-JsonAnToan $verOut
      }
      if ($script:finalizeOk) {
        DatBuoc 6 'xong' "Đã đồng bộ quy tắc, 5 Bộ Chỉ Dẫn (Documents\Studio AI Setup\Chi-Dan) & kiểm tra Doctor"
      } else {
        DatBuoc 6 'bo' 'Cài xong công cụ (hoàn tất quy tắc/chỉ dẫn gặp trục trặc nhỏ)'
      }
      HienManXong
    } 5
  } 10
}

function ThemDongKetQua([string]$ten, [string]$trangThai, [string]$mau) {
  $g = New-Object Windows.Controls.Grid; $g.Margin = '0,4,0,4'
  $t1 = New-Object Windows.Controls.TextBlock; $t1.Text = $ten; $t1.Foreground = '#e2e8f0'; $t1.FontWeight = 'SemiBold'
  $t2 = New-Object Windows.Controls.TextBlock; $t2.Text = $trangThai; $t2.Foreground = $mau; $t2.HorizontalAlignment = 'Right'
  $g.Children.Add($t1) | Out-Null; $g.Children.Add($t2) | Out-Null
  $el.TomTatKetQua.Children.Add($g) | Out-Null
}

function HienManXong {
  $el.FooterChao.Visibility = 'Collapsed'
  $el.ManCai.Visibility = 'Collapsed'
  $el.ManXong.Visibility = 'Visible'
  $el.TrangThaiSaoLuu.Visibility = 'Collapsed'
  $el.TrangThaiSaoLuu.Text = ''
  $el.NutSaoLuu.IsEnabled = $true
  if ($el.KhungCuon) { $el.KhungCuon.ScrollToTop() }
  $el.TomTatKetQua.Children.Clear()
  $nhan = @{
    xong = @{ chu = 'Sẵn sàng'; mau = '#a3e635' }
    bo   = @{ chu = 'Đã bỏ qua'; mau = '#94a3b8' }
    loi  = @{ chu = 'Cần kiểm tra lại'; mau = '#fb7185' }
    cho  = @{ chu = 'Chưa chạy'; mau = '#64748b' }
  }
  for ($i = 0; $i -lt $BUOC.Count; $i++) {
    $st = $script:trangThai[$i]
    $info = $nhan[$st]
    ThemDongKetQua $BUOC[$i].ten $info.chu $info.mau
  }
  ThemDongKetQua 'Thư mục 5 Bộ Chỉ Dẫn' 'Documents\Studio AI Setup\Chi-Dan' '#38bdf8'

  # Tóm tắt kiểm tra Doctor trực tiếp từ --verify-json
  $doc = $script:doctorData
  if ($doc) {
    $ke = New-Object Windows.Controls.Border
    $ke.Height = 1; $ke.Background = '#1f293d'; $ke.Margin = '0,10,0,8'
    $el.TomTatKetQua.Children.Add($ke) | Out-Null

    $hdr = New-Object Windows.Controls.TextBlock
    $hdr.Text = 'KIỂM TRA SỨC KHỎE (DOCTOR)'
    $hdr.FontSize = 11; $hdr.FontWeight = 'SemiBold'; $hdr.Foreground = '#64748b'; $hdr.Margin = '0,0,0,4'
    $el.TomTatKetQua.Children.Add($hdr) | Out-Null

    $lotsObj = LayThuocTinh $doc 'lots'
    $lot5Obj = if ($lotsObj) { LayThuocTinh $lotsObj 'lot5' } else { $null }
    if ($lot5Obj) {
      $l5Status = [string](LayThuocTinh $lot5Obj 'status')
      if ($l5Status -and $l5Status -ne 'not_selected') {
        $egmNode = LayThuocTinh $lot5Obj 'egm'
        if (-not $egmNode) { $egmNode = LayThuocTinh $lot5Obj 'antigravity' }
        if (-not $egmNode) { $egmNode = $lot5Obj }
        $skRaw = LayThuocTinh $egmNode 'skills_count'
        if ($null -eq $skRaw) { $skRaw = LayThuocTinh $egmNode 'skill_count' }
        if ($null -eq $skRaw) { $skRaw = LayThuocTinh $egmNode 'skills' }
        $agRaw = LayThuocTinh $egmNode 'agents_count'
        if ($null -eq $agRaw) { $agRaw = LayThuocTinh $egmNode 'agent_count' }
        if ($null -eq $agRaw) { $agRaw = LayThuocTinh $egmNode 'agents' }
        $stdRaw = LayThuocTinh $egmNode 'standards_count'
        $skCount = DemSoLuong $skRaw ($(if ($l5Status -eq 'ok') { 8 } else { 0 }))
        $agCount = DemSoLuong $agRaw ($(if ($l5Status -eq 'ok') { 10 } else { 0 }))
        $stdCount = DemSoLuong $stdRaw ($(if ($l5Status -eq 'ok') { 5 } else { 0 }))
        if ($l5Status -eq 'ok') {
          ThemDongKetQua 'EGM · Antigravity' "$skCount/8 skills · $agCount agents · $stdCount tiêu chuẩn" '#a3e635'
        } else {
          ThemDongKetQua 'EGM · Antigravity' "Cần kiểm tra ($skCount/8 skills · $agCount agents)" '#fb7185'
        }

        $harnesses = LayThuocTinh $lot5Obj 'harnesses'
        if (-not $harnesses) { $harnesses = LayThuocTinh $lot5Obj 'egm_harnesses' }
        if (-not $harnesses) { $harnesses = LayThuocTinh $doc 'egm_harnesses' }
        if ($harnesses) {
          $ccVal = LayThuocTinh $harnesses 'claude_code'
          if ($null -eq $ccVal) { $ccVal = LayThuocTinh $harnesses 'claude' }
          if ($ccVal) {
            $ccSt = if ($ccVal -is [string]) { $ccVal } else { [string](LayThuocTinh $ccVal 'status') }
            if ($ccSt) {
              $ccInfo = NhanTrangThaiHarness $ccSt
              ThemDongKetQua 'EGM · Claude Code' $ccInfo.chu $ccInfo.mau
            }
          }
          $cxVal = LayThuocTinh $harnesses 'codex'
          if ($cxVal) {
            $cxSt = if ($cxVal -is [string]) { $cxVal } else { [string](LayThuocTinh $cxVal 'status') }
            if ($cxSt) {
              $cxInfo = NhanTrangThaiHarness $cxSt
              ThemDongKetQua 'EGM · Codex CLI' $cxInfo.chu $cxInfo.mau
            }
          }
        }
      }
    }

    $rg = LayThuocTinh $doc 'rules_and_guides'
    if ($rg) {
      $preserved = LayThuocTinh $rg 'preserved_custom_rules'
      $preservedArr = @($preserved | Where-Object { $_ })
      $rulesStObj = LayThuocTinh $rg 'rules_status'
      $hasPreserved = ($preservedArr.Count -gt 0)
      if (-not $hasPreserved -and $rulesStObj) {
        foreach ($p in $rulesStObj.PSObject.Properties) {
          if ([string]$p.Value -eq 'preserved_user_custom') { $hasPreserved = $true }
        }
      }
      $agentsOk = [bool](LayThuocTinh $rg 'AGENTS.md')
      $geminiOk = [bool](LayThuocTinh $rg 'GEMINI.md')
      $topRulesOk = [bool](LayThuocTinh $doc 'rules_ready')
      if ($hasPreserved) {
        ThemDongKetQua 'Quy tắc cá nhân' 'Giữ nguyên · bản v2 lưu tại backups\' '#fbbf24'
      } elseif ($agentsOk -and $geminiOk) {
        ThemDongKetQua 'Quy tắc AI (AGENTS / GEMINI)' 'Đã đồng bộ chuẩn v2' '#a3e635'
      } elseif ($agentsOk -or $geminiOk -or $topRulesOk) {
        ThemDongKetQua 'Quy tắc AI (AGENTS / GEMINI)' 'Đã đồng bộ một phần (xem nhật ký)' '#fbbf24'
      } else {
        ThemDongKetQua 'Quy tắc AI (AGENTS / GEMINI)' 'Chưa đồng bộ (chạy lại cài đặt)' '#fb7185'
      }
    }

    $warnings = LayThuocTinh $doc 'warnings'
    $warnList = @($warnings | Where-Object { $_ -and ([string]$_).Trim() })
    foreach ($wMsg in ($warnList | Select-Object -First 4)) {
      $tb = New-Object Windows.Controls.TextBlock
      $tb.Text = "• $([string]$wMsg)"
      $tb.Foreground = '#fbbf24'
      $tb.FontSize = 11.8
      $tb.TextWrapping = 'Wrap'
      $tb.Margin = '0,4,0,0'
      $el.TomTatKetQua.Children.Add($tb) | Out-Null
    }
  }

  # Hiện nút Đăng nhập GitHub nếu gh đã có mà chưa đăng nhập
  NapLaiPath
  $ghLoggedIn = $false
  if (Co 'gh') {
    try { & gh auth status 1>$null 2>$null; $ghLoggedIn = ($LASTEXITCODE -eq 0) } catch {}
  }
  if ((Co 'gh') -and (-not $ghLoggedIn)) {
    $el.NutGitHubLogin.Visibility = 'Visible'
  } else {
    $el.NutGitHubLogin.Visibility = 'Collapsed'
  }
}

$el.NutBatDau.Add_Click({
  $rawTen = $el.ONhapTen.Text
  if ([string]::IsNullOrWhiteSpace($rawTen)) { $rawTen = 'bạn' }
  $script:tenNguoiDung = $rawTen.Trim()
  $script:luaChon = @{
    ten          = $script:tenNguoiDung
    lot1         = [bool]$el.ChkLot1.IsChecked
    lot2         = [bool]$el.ChkLot2.IsChecked
    lot3         = [bool]$el.ChkLot3.IsChecked
    lot4         = [bool]$el.ChkLot4.IsChecked
    lot5         = [bool]$el.ChkLot5.IsChecked
    openmontage  = [bool]$el.ChkOptOpenMontage.IsChecked
    assetfurnace = [bool]$el.ChkOptAssetFurnace.IsChecked
    agentreach   = [bool]$el.ChkOptAgentReach.IsChecked
  }
  $el.ManChao.Visibility = 'Collapsed'
  $el.FooterChao.Visibility = 'Collapsed'
  $el.ManCai.Visibility = 'Visible'
  if ($el.KhungCuon) { $el.KhungCuon.ScrollToTop() }
  An { Buoc0 }
})

$el.NutMoChiDan.Add_Click({
  $targetDir = if (Test-Path -LiteralPath $CHIDAN_DIR) { $CHIDAN_DIR } else { Join-Path $GOC 'chi-dan' }
  Start-Process explorer.exe -ArgumentList "`"$targetDir`""
})

$el.NutGitHubLogin.Add_Click({
  $cmdText = "Write-Host 'Dang mo trinh duyet de dang nhap GitHub (gh auth login)...' -ForegroundColor Green; gh auth login --web -h github.com -p https; Write-Host ''; Write-Host 'Xong! Ban co the dong cua so nay.' -ForegroundColor Cyan; Pause"
  Start-Process powershell.exe -ArgumentList @('-NoProfile', '-Command', $cmdText)
})

$el.NutSaoLuu.Add_Click({
  if ($script:viec -and -not $script:viec.HasExited) { return }
  $el.NutSaoLuu.IsEnabled = $false
  $el.TrangThaiSaoLuu.Foreground = '#94a3b8'
  $el.TrangThaiSaoLuu.Text = 'Đang tạo bản sao lưu cấu hình (SHA-256)...'
  $el.TrangThaiSaoLuu.Visibility = 'Visible'

  $py = TimPythonHopLe
  if (-not $py) {
    $el.TrangThaiSaoLuu.Foreground = '#fbbf24'
    $el.TrangThaiSaoLuu.Text = 'Chưa tìm thấy Python 3.10+ hợp lệ để sao lưu cấu hình.'
    $el.TrangThaiSaoLuu.Visibility = 'Visible'
    $el.NutSaoLuu.IsEnabled = $true
    return
  }

  $backupEnv = @{
    PYTHONIOENCODING        = 'utf-8'
    PYTHONUTF8              = '1'
    PYTHONDONTWRITEBYTECODE = '1'
  }
  try {
    ChayLenhAn $py @('-B', $ENGINE, '--backup', '--json') {
      param($maBk, $bkOut, $bkErr)
      try {
        $data = Parse-JsonAnToan $bkOut
        $isOk = ($maBk -eq 0) -and ($null -ne $data) -and ([bool](LayThuocTinh $data 'ok'))
        if ($isOk) {
          $fname = [string](LayThuocTinh $data 'filename')
          if ([string]::IsNullOrWhiteSpace($fname)) {
            $snapPath = [string](LayThuocTinh $data 'snapshot_path')
            if ($snapPath) { $fname = [IO.Path]::GetFileName($snapPath) }
          }
          $shaFull = [string](LayThuocTinh $data 'archive_sha256')
          $shaShort = if ($shaFull -and $shaFull.Length -ge 12) { $shaFull.Substring(0, 12) } elseif ($shaFull) { $shaFull } else { 'N/A' }
          $el.TrangThaiSaoLuu.Foreground = '#a3e635'
          $el.TrangThaiSaoLuu.Text = "Đã sao lưu: $fname (SHA-256: $($shaShort)...) · Thư mục: %LOCALAPPDATA%\StudioAISetup\snapshots\"
          $el.TrangThaiSaoLuu.Visibility = 'Visible'
        } else {
          $errMsg = if ($data) { [string](LayThuocTinh $data 'error') } else { '' }
          if ([string]::IsNullOrWhiteSpace($errMsg) -and -not [string]::IsNullOrWhiteSpace($bkErr)) {
            $errMsg = ($bkErr.Trim() -split "`r?`n")[0]
          }
          if ([string]::IsNullOrWhiteSpace($errMsg)) {
            $errMsg = "Mã lỗi $maBk (bấm Xem nhật ký cài đặt để kiểm tra)"
          }
          if ($errMsg.Length -gt 140) { $errMsg = $errMsg.Substring(0, 137) + '...' }
          $el.TrangThaiSaoLuu.Foreground = '#fbbf24'
          $el.TrangThaiSaoLuu.Text = "Không thể sao lưu: $errMsg"
          $el.TrangThaiSaoLuu.Visibility = 'Visible'
        }
      } catch {
        Ghi "Loi xu ly ket qua sao luu: $($_.Exception.Message)"
        $el.TrangThaiSaoLuu.Foreground = '#fbbf24'
        $el.TrangThaiSaoLuu.Text = "Không thể sao lưu: $($_.Exception.Message)"
        $el.TrangThaiSaoLuu.Visibility = 'Visible'
      } finally {
        $el.NutSaoLuu.IsEnabled = $true
      }
    } -noiChay $GOC -phutToiDa 5 -extraEnv $backupEnv
  } catch {
    Ghi "Loi khoi chay sao luu: $($_.Exception.Message)"
    $el.TrangThaiSaoLuu.Foreground = '#fbbf24'
    $el.TrangThaiSaoLuu.Text = "Không thể sao lưu: $($_.Exception.Message)"
    $el.TrangThaiSaoLuu.Visibility = 'Visible'
    $el.NutSaoLuu.IsEnabled = $true
  }
})

$el.NutHoanTat.Add_Click({ $w.Close() })
$el.Dong.Add_Click({ $w.Close() })
$w.Add_Closing({
  if ($script:viec -and -not $script:viec.HasExited) {
    $r = [Windows.MessageBox]::Show($w, 'Máy đang cài đặt dở. Đóng lúc này thì lần sau phải chạy lại cai-dat.bat. Bạn vẫn muốn đóng?',
      "Studio AI Setup v$($script:appVer)", 'YesNo', 'Question')
    if ($r -ne 'Yes') { $_.Cancel = $true; return }
    try { Start-Process taskkill.exe -ArgumentList @('/PID', "$($script:viec.Id)", '/T', '/F') -WindowStyle Hidden } catch {}
    try { $script:viec.Dispose() } catch {}
    $script:viec = $null
    $script:viecOutTask = $null
    $script:viecErrTask = $null
    $script:sauViec = $null
  }
  try { $hen.Stop() } catch {}
})

$script:daBatDau = $false
$w.Add_ContentRendered({
  if ($script:daBatDau) { return }
  $script:daBatDau = $true
  try { [IO.File]::WriteAllText($DA_MO, (Get-Date -Format o)) } catch {}
  $w.Activate() | Out-Null
  # Gỡ dấu Zone.Identifier sau khi cửa sổ đã hiện lên để không làm chậm lúc mở
  try {
    @($GOC, $PSScriptRoot, (Join-Path $GOC 'engine')) | ForEach-Object {
      Get-ChildItem -LiteralPath $_ -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.bat', '.cmd', '.ps1', '.py' } | Unblock-File -ErrorAction SilentlyContinue
    }
  } catch { Ghi "Go dau tai mang: $($_.Exception.Message)" }
})

try { [void]$w.ShowDialog() } catch {
  Ghi "Cua so cai dat loi: $($_.Exception.Message)"
  exit 91
}
exit 0
