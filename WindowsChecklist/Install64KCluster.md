These are the steps to change the cluster size to 64K

Step 1

If you have one partition (it's not the default) for windows like me (the other partitions that you see are form the external drive) click drive options (advanced) and delete the partition. If you have two (the default for windows installations), delete first the big partition and then the small 100MB System reserved one.

Step 2

After delete the partitions you will have one big Unallocated Space on Disk 0

Click new and apply

You will have something like this

Step 3

Press Shift - F10 to open the console and type: diskpart

Then type: select disk 0

Then type: select partition 1

Then type: active

Then type: select partition 2

Then type: format fs=ntfs quick unit=64k

Then type: exit and again exit

Step 4

Click Refresh and then click on the Disk 0 partition 2 and press next

Step 5

After you finish with windows installation open a command promt as administrator and type: fsutil fsinfo ntfsinfo C:

If it says Bytes per cluster: 65536 then your installation was successful and your cluster size (or else allocation unit size) is 64K instead of 4K.
