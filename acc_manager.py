# acc_manager.py
import os
import shutil
from datetime import datetime
from typing import List, Optional
from config import ACC_FILE, SOLD_FILE, BACKUP_FOLDER

# ensure files/folders
os.makedirs(os.path.dirname(ACC_FILE), exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)
for f in (ACC_FILE, SOLD_FILE):
    if not os.path.exists(f):
        open(f, "a", encoding="utf-8").close()

def list_accs() -> List[str]:
    with open(ACC_FILE, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

def list_sold() -> List[str]:
    with open(SOLD_FILE, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

def add_accs_from_text(text: str) -> int:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return 0
    with open(ACC_FILE, "a", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")
    return len(lines)

def pop_acc() -> Optional[str]:
    accs = list_accs()
    if not accs:
        return None
    acc = accs.pop(0)
    with open(ACC_FILE, "w", encoding="utf-8") as f:
        if accs:
            f.write("\n".join(accs) + "\n")
    with open(SOLD_FILE, "a", encoding="utf-8") as f:
        f.write(acc + "\n")
    return acc

def backup_files():
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in (ACC_FILE, SOLD_FILE):
        if os.path.exists(path):
            try:
                shutil.copy(path, os.path.join(BACKUP_FOLDER, os.path.basename(path) + "_" + t + ".bak"))
            except Exception:
                pass
