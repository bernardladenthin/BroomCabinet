rem start /low java ^
java ^
-server ^
-XX:GCTimeRatio=19 ^
-XX:MinHeapFreeRatio=20 ^
-XX:MaxHeapFreeRatio=30 ^
-XX:MaxDirectMemorySize=32M ^
-Xdebug ^
-Xrunjdwp:transport=dt_socket,address=1000,server=y,suspend=n ^
-Dcom.sun.management.jmxremote.port=3333 ^
-Dcom.sun.management.jmxremote.ssl=false ^
-Dcom.sun.management.jmxremote.authenticate=false ^
-Dorg.slf4j.simpleLogger.defaultLogLevel=INFO ^
-jar ^
btcdetector-1.0.0-SNAPSHOT-jar-with-dependencies.jar ^
config.js > log.txt 2>&1
