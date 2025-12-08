import random, os

ACC_FILE="acc.txt"

def get_random_acc():
    if not os.path.exists(ACC_FILE): return None
    accounts=open(ACC_FILE).read().splitlines()
    if not accounts: return None
    acc=random.choice(accounts)
    new=[i for i in accounts if i!=acc]
    open(ACC_FILE,"w").write("\n".join(new))
    return acc

def add_account(text):
    open(ACC_FILE,"a").write(text+"\n")
