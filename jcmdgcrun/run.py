import subprocess

result = subprocess.run(['wmic', 'process', 'where', 'caption=\'javaw.exe\'', 'get', 'ProcessId'], stdout=subprocess.PIPE)

s = result.stdout.decode('utf-8')

lines = s.splitlines()
pIDs = []

for line in lines:
    try:
        pIDs.append(int(line))
    except ValueError:
        pass

print(pIDs)

for pid in pIDs:
    subprocess.run(['C:\\Program Files\\Java\\jdk-9.0.1\\bin\\jcmd.exe', str(pid), 'GC.run'])
