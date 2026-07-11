import glob
from pathlib import Path
from PIL import Image, ImageFile
from concurrent.futures import ThreadPoolExecutor
import os

# Allow loading very large or partially corrupted images
Image.MAX_IMAGE_PIXELS = None  # https://stackoverflow.com/questions/25705773/image-cropping-tool-python
ImageFile.LOAD_TRUNCATED_IMAGES = True  # https://stackoverflow.com/questions/42462431/oserror-broken-data-stream-when-reading-image-file/47958486

# ====== Configuration Parameters ======

dry = False

source_dir = Path("source_images")
destination_dir = Path("resized_images")

resize_size = (800, 800)
resample_filter = Image.LANCZOS
jpeg_quality = 95
thread_pool_size = os.cpu_count() or 4

# Supported formats (case-insensitive)
image_extensions = [
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"
]

# ======================================

def resizeImage(src_path: Path):
    rel_path = src_path.relative_to(source_dir)
    dest_path = destination_dir / rel_path

    print(f"Processing: {src_path} -> {dest_path}")

    if not dry:
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(src_path) as im:
                # Copy EXIF metadata if available
                exif_data = im.info.get("exif")

                # Resize image
                im.thumbnail(resize_size, resample_filter)

                # Determine format
                format = im.format or src_path.suffix.lstrip(".").upper()
                save_kwargs = {}

                # Apply compression options
                if format.upper() in ["JPEG", "JPG"]:
                    save_kwargs["quality"] = jpeg_quality
                    if exif_data:
                        save_kwargs["exif"] = exif_data

                # Save image with metadata if supported
                im.save(dest_path, format=format, **save_kwargs)

        except Exception as e:
            print(f"ERROR: Could not resize {src_path}")
            print(e)

def main():
    print(f"Detected {thread_pool_size} CPU threads. Using all for parallel processing.")
    image_paths = [
        path for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in image_extensions
    ]

    with ThreadPoolExecutor(thread_pool_size) as executor:
        for path in image_paths:
            executor.submit(resizeImage, path)

if __name__ == '__main__':
    main()
