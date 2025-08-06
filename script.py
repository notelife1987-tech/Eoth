import os
folder = "/storage/emulated/0/Download"
for i, filename in enumerate(os.listdir(folder)):
    os.rename(f"{folder}/{filename}", f"{folder}/file_{i}.txt")
