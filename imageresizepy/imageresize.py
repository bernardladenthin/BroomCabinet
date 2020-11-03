import glob
from PIL import Image

for name in glob.glob('**/*.jpg', recursive=True):
    im = Image.open(name)
    print(name)
    im.thumbnail((600,600), Image.LANCZOS)
    im.save(name,quality=75)
