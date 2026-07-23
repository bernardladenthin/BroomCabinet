# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

# Matrix digital rain for the console.
# Green characters fall from top to bottom, each column with a bright head and a fading tail.
# Quit with Esc or Q (or Ctrl+C). Resizing the window is handled live.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Character pool: half-width katakana (the classic look) + digits + latin + a few symbols.
$chars = @()
for ($c = 0xFF66; $c -le 0xFF9D; $c++) { $chars += [char]$c }
$chars += '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ:.=*+<>|'.ToCharArray()
$pool  = $chars.Count

function Reset-Field($w, $h) {
    $script:drops = New-Object 'int[]' $w   # head position (row) per column
    $script:speed = New-Object 'int[]' $w   # 1 = fast, 3 = slow
    for ($i = 0; $i -lt $w; $i++) {
        $script:drops[$i] = Get-Random -Minimum (-$h) -Maximum 0
        $script:speed[$i] = Get-Random -Minimum 1 -Maximum 4
    }
}

$w = [Console]::WindowWidth
$h = [Console]::WindowHeight
$trail = 12
$frame = 0
Reset-Field $w $h

[Console]::CursorVisible = $false
[Console]::Clear()

try {
    while ($true) {
        # adapt to a resized window
        if ([Console]::WindowWidth -ne $w -or [Console]::WindowHeight -ne $h) {
            $w = [Console]::WindowWidth
            $h = [Console]::WindowHeight
            Reset-Field $w $h
            [Console]::Clear()
        }

        # stop one short of the last column so the bottom-right cell never scrolls the buffer
        for ($x = 0; $x -lt $w - 1; $x++) {
            $y = $script:drops[$x]

            # bright head (a fresh random glyph each frame -> the head shimmers)
            if ($y -ge 0 -and $y -lt $h) {
                [Console]::SetCursorPosition($x, $y)
                [Console]::ForegroundColor = 'White'
                [Console]::Write($chars[(Get-Random -Maximum $pool)])
            }
            # repaint the cell just above the head green -> turns last frame's white head into the trail
            $by = $y - 1
            if ($by -ge 0 -and $by -lt $h) {
                [Console]::SetCursorPosition($x, $by)
                [Console]::ForegroundColor = 'Green'
                [Console]::Write($chars[(Get-Random -Maximum $pool)])
            }
            # erase the far end of the trail
            $ey = $y - $trail
            if ($ey -ge 0 -and $ey -lt $h) {
                [Console]::SetCursorPosition($x, $ey)
                [Console]::Write(' ')
            }

            # advance this column only on its own cadence, so columns fall at different speeds
            if ($frame % $script:speed[$x] -eq 0) {
                $script:drops[$x]++
                if ($script:drops[$x] - $trail -gt $h) {
                    $script:drops[$x] = Get-Random -Minimum (-20) -Maximum 0
                    $script:speed[$x] = Get-Random -Minimum 1 -Maximum 4
                }
            }
        }

        $frame++
        Start-Sleep -Milliseconds 45

        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq 'Escape' -or $key.Key -eq 'Q') { break }
        }
    }
}
finally {
    [Console]::ResetColor()
    [Console]::CursorVisible = $true
    [Console]::Clear()
    Write-Host 'Wake up, Neo...' -ForegroundColor Green
}
