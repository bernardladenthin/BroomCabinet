# SPDX-FileCopyrightText: 2018 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

find -iname "* .*"
find -iname "*  *"
find -iname " *"
find -iname "* "
find -iname "*."
rename -v -n "s/  / /g" *
rename -v    "s/  / /g" *
