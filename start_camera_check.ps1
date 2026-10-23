# Close Windows Camera and Arduino Serial Monitor before running.
param([int]$Camera = 0, [string]$Port = 'COM3')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH = Join-Path $PSScriptRoot '.edge-deps'
python vision_serial_bridge.py --preview-only --camera $Camera --port $Port --no-display
