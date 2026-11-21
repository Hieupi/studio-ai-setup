# Hộp thông báo giao diện tối đồng bộ với Studio AI Setup (WPF 4.8).
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$XAML = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Studio AI Setup" Width="480" SizeToContent="Height" WindowStyle="None" ResizeMode="NoResize" Topmost="True"
        WindowStartupLocation="CenterScreen" Background="#090c12" BorderBrush="#222b3e" BorderThickness="1"
        FontFamily="Segoe UI Variable Text, Segoe UI" FontSize="13.5" Foreground="#f1f5f9" ShowInTaskbar="True"
        TextOptions.TextFormattingMode="Display" UseLayoutRounding="True">
  <Window.Resources>
    <Style x:Key="NutPhu" TargetType="Button">
      <Setter Property="Foreground" Value="#e2e8f0"/>
      <Setter Property="Height" Value="38"/>
      <Setter Property="MinWidth" Value="116"/>
      <Setter Property="Margin" Value="10,0,0,0"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="#151c2c" BorderBrush="#2a354d" BorderThickness="1" CornerRadius="8" Padding="16,0">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#1e283d"/></Trigger>
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
            <Border x:Name="b" Background="#a3e635" BorderBrush="#bef264" BorderThickness="1" CornerRadius="8" Padding="18,0">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#bef264"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>
  <StackPanel>
    <Grid x:Name="Dau" Background="#111622" Height="54">
      <StackPanel Orientation="Horizontal" VerticalAlignment="Center" Margin="20,0,0,0">
        <Image x:Name="Logo" Width="28" Height="28"/>
        <TextBlock Text="Studio AI Setup" FontSize="15.5" FontWeight="SemiBold" VerticalAlignment="Center" Margin="12,0,0,0"/>
      </StackPanel>
    </Grid>
    <Border Height="1" Background="#20293a"/>
    <StackPanel Margin="24,20,24,22">
      <TextBlock x:Name="NoiDung" TextWrapping="Wrap" LineHeight="21" Foreground="#e2e8f0"/>
      <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,22,0,0">
        <Button x:Name="MoLog" Style="{StaticResource NutPhu}" Content="Xem nhật ký" Visibility="Collapsed"/>
        <Button x:Name="Dong" Style="{StaticResource NutChinh}" Content="Đóng" IsDefault="True" IsCancel="True"/>
      </StackPanel>
    </StackPanel>
  </StackPanel>
</Window>
'@

$w = [Windows.Markup.XamlReader]::Parse($XAML)
$noiDung = if ($env:STUDIO_AI_MSG) { [string]$env:STUDIO_AI_MSG } else { 'Thông báo từ Studio AI Setup.' }
$w.FindName('NoiDung').Text = $noiDung
$ico = Join-Path (Split-Path -Parent $PSScriptRoot) 'brand\studio-ai.ico'
if (Test-Path -LiteralPath $ico) {
  try {
    $giai = [Windows.Media.Imaging.BitmapDecoder]::Create([Uri]$ico, 'None', 'OnLoad')
    $w.FindName('Logo').Source = $giai.Frames | Sort-Object { $_.PixelWidth } -Descending | Select-Object -First 1
    $w.Icon = $giai.Frames | Sort-Object { $_.PixelWidth } | Select-Object -First 1
  } catch {}
}
$log = [string]$env:STUDIO_AI_LOG
if ($log -and (Test-Path -LiteralPath $log)) {
  $nut = $w.FindName('MoLog')
  $nut.Visibility = 'Visible'
  $nut.Add_Click({ Start-Process notepad.exe -ArgumentList "`"$log`""; $w.Close() })
}
$w.FindName('Dong').Add_Click({ $w.Close() })
$w.FindName('Dau').Add_MouseLeftButtonDown({ try { $w.DragMove() } catch {} })
$w.Add_ContentRendered({ [void]$w.Activate() })
[void]$w.ShowDialog()
