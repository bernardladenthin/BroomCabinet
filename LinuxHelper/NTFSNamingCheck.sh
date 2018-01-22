find -iname "* .*"
find -iname "*  *"
find -iname " *"
find -iname "* "
find -iname "*."
rename -v -n "s/  / /g" *
rename -v    "s/  / /g" *
