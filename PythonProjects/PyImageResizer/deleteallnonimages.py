import glob
from pathlib import Path
import os

dry = True

def main():
    for name in glob.glob('**/*.*', recursive=True):
        path = Path(name)
        if path.is_file() and not path.suffix.endswith(".jpg") and not path.suffix.endswith(".png"):
            print ("Delete " + path.as_posix())
            if not dry:
                os.remove(path)

if __name__ == '__main__':
    main()
