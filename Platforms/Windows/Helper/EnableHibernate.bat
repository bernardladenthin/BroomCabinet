@echo off
:: Enable hibernation (adds the hibernate power option back).
:: Afterwards you may want to disable "Allow hybrid sleep" in the advanced
:: power options if you only want plain hibernate.
powercfg -H on
pause
