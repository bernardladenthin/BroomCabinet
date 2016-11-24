## add to cron
start the gpiocounter script on start
```bash
crontab -l | { cat; echo "@reboot python /home/pi/gpiocounter.py &"; } | crontab -
```

create a graph every day
```bash
crontab -l | { cat; echo "@daily bash /home/pi/gpiocountergraphdaily.sh &"; } | crontab -
```
