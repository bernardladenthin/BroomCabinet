# WindowsHelper

Windows batch scripts and quick reference commands. See [`CPU/README.md`](CPU/README.md) for the CPU power-tuning guide.

## Reference commands

Not standalone scripts - copy, adapt the placeholder, and run manually.

### Export / remove a driver package

`pnputil.exe /e > c:\drivers.txt` lists all third-party driver packages.
`pnputil.exe /d oemNN.inf` removes one - replace `oemNN.inf` with the actual package name from the export.

### Losslessly re-encode a DVD VOB sequence to MP4

```
ffmpeg -i "concat:VTS_02_1.VOB|VTS_02_2.VOB|VTS_02_3.VOB|VTS_02_4.VOB|VTS_02_5.VOB" -c:v libx264 -preset slow -crf 20 -c:a aac -b:a 160k -vf format=yuv420p -movflags +faststart video-out.mp4
```

Replace the `VTS_02_*.VOB` file list with your own DVD title's VOB files.
