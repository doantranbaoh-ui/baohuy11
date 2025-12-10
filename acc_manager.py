import os, shutil
from datetime import datetime
from config import ACC_FILE,SOLD_FILE,BACKUP_FOLDER

def get_acc_list():
    if not os.path.exists(ACC_FILE): return []
    return [i.strip() for i in open(ACC_FILE,"r",encoding="utf-8") if i.strip()]

def get_sold_list():
    if not os.path.exists(SOLD_FILE): return []
    return [i.strip() for i in open(SOLD_FILE,"r",encoding="utf-8") if i.strip()]

def add_acc(data):
    open(ACC_FILE,"a",encoding="utf-8").write(data+"\n")

def sale_acc():
    accs=get_acc_list()
    if not accs: return None
    acc=accs.pop(0)
    open(ACC_FILE,"w",encoding="utf-8").writelines([i+"\n" for i in accs])
    open(SOLD_FILE,"a",encoding="utf-8").write(acc+"\n")
    return acc

def backup():
    os.makedirs(BACKUP_FOLDER,exist_ok=True)
    for f in [ACC_FILE,SOLD_FILE]:
        if os.path.exists(f):
            shutil.copy(f, f"{BACKUP_FOLDER}/{os.path.basename(f)}_{datetime.now().strftime('%H%M%S')}.bak")
