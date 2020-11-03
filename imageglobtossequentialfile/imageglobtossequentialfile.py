import glob
import os
from shutil import copy2

destination = 'dst'
zfill = 9

names = list(glob.glob('**/*.jpg', recursive=True))
names.sort()

os.makedirs(destination)

number = 0
for name in names:
    copy2(name, destination + '/' + 'image-' + str(number).zfill(zfill) + '.jpg')
    number += 1
