import subprocess
import time
import signal
import os

while True:
    print("open rescue")
    process = subprocess.Popen(["bash", "rescue.sh"])
    time.sleep(2)
    process.send_signal(signal.SIGINT)
    time.sleep(3)
    os.system("bash relaisOff.sh")
    print("off")
    time.sleep(1)
    os.system("bash relaisOn.sh")
    print("on")
    time.sleep(3)
