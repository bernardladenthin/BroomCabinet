# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

"""Does the new oldskool drivers/ exclusion decide the way it is documented?

Reproduces the crawler's own test verbatim -- rel = child[len(base_url):], then startswith --
and runs it over URLs built the way the crawler builds them, by urljoin from the href the live
listing actually served.
"""
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mirror as M

BASE = "http://ftp.oldskool.org/pub/"
EX = M.EXCLUDE["oldskool"]


def excluded(path_from_base):
    child = urllib.parse.urljoin(BASE, path_from_base)
    rel = child[len(BASE):]
    return any(rel.startswith(x) for x in EX)


OUT = [
    "drivers/KATT/", "drivers/KATT/KATT%20Games%20Master%20Keyboard/x.zip",
    "drivers/LG/", "drivers/LG/OLED65C8PUA/a.bin", "drivers/AOOSTAR/N1%20PRO%20N150/d.exe",
    "drivers/Gigabyte/", "drivers/MSI/", "drivers/Blackmagic%20Design/", "drivers/Insta360/",
    "drivers/Samsung/", "drivers/Samsung/Dish%20washers/", "drivers/EVGA/", "drivers/Atomos/",
    "drivers/Google/", "drivers/x-rite/", "drivers/USB-AVCPT%20video%20DVD%20maker/",
    "drivers/Dell/Inspiron%2013%207368%202-in-1/", "drivers/Dell/Studio%201555/deep/er/f.cab",
    "drivers/Dell/T1600/", "drivers/Dell/Unknown%202003%20computer/",
    "drivers/nvidia/Vista64_7_8/", "drivers/nvidia/GT%20730/", "drivers/nvidia/Windows%2010/",
    "drivers/nvidia/win2kxp/", "drivers/nvidia/personal/", "drivers/nvidia/WinXPx64/",
    "drivers/nvidia/Linux/", "drivers/nvidia/broadcast/",
    "drivers/HP/HP%20Pavillion%20p6000/", "drivers/HP/Z2%20Mini%20G4%20workstation/",
    "drivers/HP/HP%20Scanjet%203970/", "drivers/HP/LP2475w/",
    "drivers/Compaq/Softpaq%20files%20(partial)/", "drivers/Compaq/Softpaq%20files%20(partial)/sp6001-6500/a.exe",
    "drivers/Fujitsu/ScanSnap%20SV600/", "drivers/Fujitsu/ScanSnap%20ix500/", "drivers/Fujitsu/fi-5530C2/",
    # Matrox: the exclusion was narrowed on 2026-09-22 from the whole `RT Series/` to the ten
    # branches that really are the video-editing suite. Each of the ten was confirmed to answer
    # 200 at the origin on that date, and the listing of `RT Series/` splits exactly twelve ways
    # with no rule left over.
    "drivers/Matrox/RT%20Series/RTX.100/", "drivers/Matrox/RT%20Series/RT2000/",
    "drivers/Matrox/RT%20Series/RTX100XtremePro/", "drivers/Matrox/RT%20Series/dvdit/",
    "drivers/Matrox/RT%20Series/Premiere%20Upgrade/", "drivers/Matrox/RT%20Series/PROPack/",
    "drivers/Matrox/RT%20Series/documentation/", "drivers/Matrox/RT%20Series/misc/",
    "drivers/Matrox/RT%20Series/utilities/", "drivers/Matrox/RT%20Series/VFW/",
    "drivers/Matrox/RT%20Series/RTX.100/deep/er/still.zip",
    "drivers/ASUS/BW-16D1HT/", "drivers/ASUS/RT-AC66U/",
    "drivers/ASUS/rt-66ac/", "drivers/ASUS/C60M1-I/", "drivers/ASUS/asus_m4a88t_v_evo_driver_dvd.iso",
    "drivers/ASUS/asus_m4a88t_v_evo_driver_dvd.mds", "drivers/ASUS/BDP1000_XAA_110324_01.iso.zip",
    "drivers/Creative/CDs/SB_X-Fi/", "drivers/Creative/CDs/SB_Live1024/", "drivers/Creative/CDs/SB_Live5.1/",
    "drivers/IBM/ardent_tool_outdated_mirror_ohlandl.ipv7.net.7z",
    # the non-drivers exclusions must still hold
    "misc/Video/", "simtelnet/", "IBM_PC_BBS/", "ftp.bocaresearch.com/", "MindCandy/",
]

KEEP = [
    "drivers/", "drivers/IBM/", "drivers/IBM/pccbbs/x.exe",
    "drivers/Miscellaneous/", "drivers/Miscellaneous/Truevision/",
    "drivers/unsorted/", "drivers/unsorted/3Dfx/", "drivers/unsorted/BocaResearch/",
    "drivers/unsorted/AdlibGoldDrivers1.01.rar",
    "drivers/Tandy/", "drivers/Gravis/", "drivers/ATI/cd_images/Mach64_970220.7z",
    "drivers/ATI/3D%20Expression+PC2TV/", "drivers/Panasonic/", "drivers/Videonics/",
    "drivers/Dell/210/", "drivers/Dell/316LT/", "drivers/Dell/316SX/", "drivers/Dell/GXpro/",
    "drivers/nvidia/NV1/", "drivers/nvidia/win3.1/", "drivers/nvidia/Win9x/", "drivers/nvidia/98/",
    "drivers/nvidia/XP/", "drivers/nvidia/older_drivers/", "drivers/nvidia/capture/",
    "drivers/nvidia/29.42_winxp.exe",
    "drivers/HP/200LX/", "drivers/HP/Colorado%20Tape/", "drivers/HP/HP%20Laserjet%204L/",
    "drivers/HP/HP%20LaserJet%205P%20and%205MP/", "drivers/HP/Voodoo/", "drivers/HP/HP%20Laserjet%201000/",
    "drivers/Compaq/Deskpro/", "drivers/Compaq/Portable%20III/",
    "drivers/Fujitsu/M2551A/", "drivers/Fujitsu/SAPV218.exe",
    "drivers/Matrox/mystique/", "drivers/Matrox/m3D/", "drivers/Matrox/Millenium_I/",
    # The two graphics branches the narrowing exists for, and the three loose files beside them.
    "drivers/Matrox/RT%20Series/", "drivers/Matrox/RT%20Series/MGA_MILL/",
    "drivers/Matrox/RT%20Series/MGA_MILL/98/1677_412.EXE",
    "drivers/Matrox/RT%20Series/G400FLEX/", "drivers/Matrox/RT%20Series/G400FLEX/OPENGL/",
    "drivers/Matrox/RT%20Series/UNTITLED.TXT",
    "drivers/Matrox/RT%20Series/matrox_pci_optimizer.zip",
    "drivers/ASUS/older%20mainboards/", "drivers/ASUS/P4PE/",
    "drivers/Creative/CDs/SB16/", "drivers/Creative/CDs/AWE64_Value_CD_OEM/",
    "drivers/Creative/CDs/SB_AudioPCI128_OEM/", "drivers/Creative/CDs/Sound_PCI128/",
    "drivers/Creative/AWE64%20Gold/", "drivers/Creative/SoundBlaster2.5/",
    "drivers/IBM/pccbbs/", "drivers/Gateway%202000/", "drivers/Leading%20Edge/",
    "misc/", "misc/Software/", "tvdog/",
]

# NOT failures -- a property this rule set HAS, recorded so nobody rediscovers it as a surprise.
#
# Narrowing `drivers/Matrox/RT%20Series/` into ten sibling rules turned a rule that failed CLOSED
# into one that fails OPEN. Whatever the old rule could not name, it still excluded; these ten
# cannot exclude a branch that did not exist when they were written. And this tree grows: most of
# its entries are dated 2016 and 2020, but `RTX.100/` and `RT2000/` are 2022-02-02.
#
# Each name below is invented. The test asserts the rules do NOT cover them, because that is the
# truth and a test that pretended otherwise would be the lie. When `RT Series/` next gains a
# branch, this block is where to look.
FAILS_OPEN = [
    "drivers/Matrox/RT%20Series/RTX200/",
    "drivers/Matrox/RT%20Series/DigiSuite/",
    "drivers/Matrox/RT%20Series/some_new_4gb_suite.iso",
]

bad, leaks = [], []
for p in OUT:
    if not excluded(p):
        bad.append("  NOT excluded, but should be:  " + p)
for p in KEEP:
    if excluded(p):
        bad.append("  excluded, but should stay:    " + p)
for p in FAILS_OPEN:
    if not excluded(p):
        leaks.append(p)
    else:
        bad.append("  FAILS_OPEN case is covered after all -- update this block: " + p)

print("%d exclusion rules for oldskool" % len(EX))
print("%d paths must go, %d must stay" % (len(OUT), len(KEEP)))
if leaks:
    print("\nknown and accepted: %d invented sibling(s) of RT Series/ would be fetched,"
          % len(leaks))
    print("because ten named rules cannot name what does not exist yet:")
    for p in leaks:
        print("    %s" % urllib.parse.unquote(p))
if bad:
    print("\nFAILURES:")
    print("\n".join(bad))
    sys.exit(1)
print("\nall %d cases correct" % (len(OUT) + len(KEEP) + len(FAILS_OPEN)))
