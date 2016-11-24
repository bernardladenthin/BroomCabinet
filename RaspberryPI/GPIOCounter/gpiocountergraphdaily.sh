#!/bin/bash
DATEVAR=`date +20\%y\%m\%d_\%H\%M\%S`

rrdtool graph 'daily_$DATEVAR.png' \
--width '1800' \
--height '950' \
--end now \
--start end-86400s \
'DEF:1min=db.rrd:gpiocounter:AVERAGE' \
'LINE1:1min#0033FF' \
'HRULE:1660#FF340D:"10 kw/h"' \
'HRULE:830#E88D0C:"5 kw/h"' \
'HRULE:166#FFE000:"1 kw/h"' \
'HRULE:85#d1e80c:"500 w/h"' \
'HRULE:17#66E80C:"100 w/h"' \
'HRULE:8#00FF7C:"50 w/h"' \

#--logarithmic \
#--units=si \
