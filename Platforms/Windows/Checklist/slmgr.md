<!--
SPDX-FileCopyrightText: 2018 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Uninstall Product Key
slmgr -upk

# Clear product key from the registry (prevents disclosure attacks)
slmgr -cpky

# Enter a new product key supplied as xxxxx-xxxxx-xxxxx-xxxxx-xxxxx.
-ipk Key
