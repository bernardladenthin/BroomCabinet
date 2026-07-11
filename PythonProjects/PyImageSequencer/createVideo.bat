rem https://video.stackexchange.com/questions/7903/how-to-losslessly-encode-a-jpg-image-sequence-to-a-video-in-ffmpeg
rem https://trac.ffmpeg.org/wiki/Encode/H.264
"C:\\Users\\Bernard\\Downloads\\ffmpeg-4.3.1-win64-static\\bin\ffmpeg" -f image2 -framerate 60 -i image-%%09d.jpg -vcodec libx264 -preset veryslow output.mp4