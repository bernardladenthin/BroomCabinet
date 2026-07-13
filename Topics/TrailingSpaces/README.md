<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Trailing spaces

`TrailingSpaces.groovy` recursively scans the current directory and reports file
names that are invalid or problematic across operating systems (Windows/NTFS in
particular):

* names that **start** with a space,
* names that **end** with a space,
* names that contain **double** spaces.

Run it from the directory you want to check:

```bash
groovy TrailingSpaces.groovy
```

Each file is printed as `ok:` or `nok:` with the reason. See also the Linux
shell equivalent in [`../../Platforms/Linux/Helper/NTFSNamingCheck.sh`](../../Platforms/Linux/Helper/NTFSNamingCheck.sh).
