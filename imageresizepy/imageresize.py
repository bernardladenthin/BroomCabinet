import glob
from pathlib import Path
from PIL import Image #pip install pillow
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageFile

#https://stackoverflow.com/questions/25705773/image-cropping-tool-python
Image.MAX_IMAGE_PIXELS = None

#https://stackoverflow.com/questions/42462431/oserror-broken-data-stream-when-reading-image-file/47958486
ImageFile.LOAD_TRUNCATED_IMAGES = True

dry = True

def resizeImage(path):
    print(path.as_posix())
    if not dry:
        try:
            im = Image.open(path)
            im.thumbnail((800,800), Image.LANCZOS)
            im.save(path,quality=75)
        except Exception as e:
            print("ERROR: Could not resize: " + path.as_posix())
            print(e)

def main():
    executor = ThreadPoolExecutor(32)
    for name in glob.glob('**/*.jpg', recursive=True):
        path = Path(name)
        executor.submit(resizeImage, path)
    executor.shutdown()

if __name__ == '__main__':
    main()
