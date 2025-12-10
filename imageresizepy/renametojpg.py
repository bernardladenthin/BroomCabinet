import glob
from pathlib import Path

dry = True

def renameToJpg(path):
    newPath = Path(path.parent, path.stem + ".jpg")
    if path.as_posix() != newPath.as_posix():
        print ("Rename " + path.as_posix() + " to " + newPath.as_posix())
        if not dry:
            path.rename(newPath)

def main():
    for name in glob.glob('**/*.jpeg', recursive=True):
        path = Path(name)
        renameToJpg(path)
    for name in glob.glob('**/*.jpg', recursive=True):
        path = Path(name)
        renameToJpg(path)

if __name__ == '__main__':
    main()
