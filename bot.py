import os, json, time, random
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from keep_alive import keep_alive   # dùng cho Render

#================= CONFIG =================#
BOT_TOKEN = "6367532329:AAFDbKOG4-I8pxo66gF3PPBBzVuxr5xnFUY"
ADMIN_ID = 5736655322
RDP_PRICE = 2000

ACC_FILE = "acc_rdp.txt"
DB_FILE  = "users.json"
SOLD_FILE = "sold.txt"
BILL_LOG = "bills.txt"

#================= AUTO CREATE FILE =================#
for f in [ACC_FILE, DB_FILE, SOLD_FILE, BILL_LOG]:
    if not os.path.exists(f):
        open(f,"w",encoding="utf-8").write("{}" if f==DB_FILE else "")

#================= DATABASE =================#
def load_db():
    try: return json.load(open(DB_FILE))
    except: return {}

def save_db(data):
    with open(DB_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=4)

users = load_db()

def get_balance(uid): return users.get(str(uid),0)
def add_balance(uid,amount):
    users[str(uid)] = get_balance(uid) + amount
    save_db(users)

#================= STOCK RDP =================#
def load_rdp():
    return [i.strip() for i in open(ACC_FILE,encoding="utf-8") if i.strip()]

def save_rdp(lst):
    open(ACC_FILE,"w",encoding="utf-8").write("\n".join(lst))

#================= PENDING =================#
pending = {}

#================= COMMAND =================#
async def start(update,ctx):
    await update.message.reply_text(
        "🖥 BOT BÁN RDP AUTO\n"
        "====================\n"
        "📌 Lệnh người dùng:\n"
        "/balance - xem số dư\n"
        "/nap <số tiền> - tạo yêu cầu nạp\n"
        "/buyrd - mua 1 RDP\n"
        "/stockrd - xem còn bao nhiêu RDP\n\n"
        "👑 Admin (private only):\n"
        "/addacc user|pass\n"
        "/checkacccuaban\n"
        "/checkaccban\n"
        "/sendstock\n"
        "/sendsold"
    )

async def balance(update,ctx):
    uid = update.effective_user.id
    await update.message.reply_text(f"💰 Số dư: {get_balance(uid)}đ")

#================= NẠP TIỀN =================#
async def nap(update,ctx):
    uid = update.effective_user.id
    try: amount = int(ctx.args[0])
    except: return await update.message.reply_text("❗ Dùng: /nap <số tiền>")

    txn = f"{uid}_{int(time.time())}_{random.randint(100,999)}"
    pending[uid] = {"amount": amount, "txn": txn}

    await update.message.reply_text(
        f"💳 NẠP TIỀN\n- MB BANK\n- STK: 0971487462\n"
        f"- Nội dung: {uid}\n- Số tiền: {amount}đ\n"
        "📸 Gửi ảnh bill vào chat này chờ admin duyệt"
        f"\n🆔 Mã GD: {txn}"
    )

async def handle_image(update,ctx):
    uid = update.effective_user.id
    if uid not in pending:
        return await update.message.reply_text("⚠ Bạn chưa tạo yêu cầu /nap")

    info = pending.pop(uid)
    amount, txn = info["amount"], info["txn"]
    img = update.message.photo[-1].file_id

    open(BILL_LOG,"a").write(f"{uid}|{amount}|{txn}\n")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✔ DUYỆT", callback_data=f"ok_{uid}_{amount}_{txn}")],
        [InlineKeyboardButton("✖ HỦY", callback_data=f"no_{uid}_{amount}_{txn}")]
    ])

    await ctx.bot.send_photo(
        ADMIN_ID, photo=img,
        caption=f"📥 BILL NẠP\nID:{uid}\nTiền:{amount}đ\nMã:{txn}",
        reply_markup=kb
    )
    await update.message.reply_text("⏳ Bill đã gửi admin, chờ duyệt...")

#================= CALLBACK =================#
async def callback(update,ctx):
    q = update.callback_query
    d = q.data.split("_")
    act, uid, amount, txn = d[0], int(d[1]), int(d[2]), d[3]

    if update.effective_user.id != ADMIN_ID:
        return await q.answer("🚫 Không phải admin",show_alert=True)

    if act == "ok":
        add_balance(uid,amount)
        await ctx.bot.send_message(uid,f"✔ Nạp thành công {amount}đ (Mã:{txn})")
        await q.edit_message_caption(f"Đã DUYỆT +{amount}đ cho {uid}")
    else:
        await ctx.bot.send_message(uid,f"❌ Bill bị từ chối (Mã:{txn})")
        await q.edit_message_caption(f"Đã HỦY bill {uid}")

    await q.answer()

#================= MUA RDP =================#
async def buyrd(update,ctx):
    uid = update.effective_user.id
    bal = get_balance(uid)
    stock = load_rdp()

    if not stock: return await update.message.reply_text("⚠ Hết stock")
    if bal < RDP_PRICE:
        return await update.message.reply_text(f"❗ Thiếu tiền ({bal}/{RDP_PRICE})")

    acc = stock.pop(0)
    save_rdp(stock)
    add_balance(uid,-RDP_PRICE)
    open(SOLD_FILE,"a",encoding="utf-8").write(f"{acc} | buyer:{uid}\n")

    await update.message.reply_text(f"🎉 Thành công:\n`{acc}`",parse_mode="Markdown")

async def stockrd(update,ctx):
    await update.message.reply_text(f"📦 Còn {len(load_rdp())} RDP")

#================= ADMIN (Chỉ private & đúng admin) =================#
def admin_protect(update):
    return (
        update.effective_user.id == ADMIN_ID and
        update.message.chat.type == "private"
    )

async def addacc(update,ctx):
    if not admin_protect(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    acc=" ".join(ctx.args)
    if "|" not in acc: return await update.message.reply_text("Dùng: /addacc user|pass")
    open(ACC_FILE,"a").write(acc+"\n")
    await update.message.reply_text("✔ Đã thêm")

async def checkaccban(update,ctx):
    if not admin_protect(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    data=open(SOLD_FILE).read().strip()
    await update.message.reply_text("📑 ACC ĐÃ BÁN:\n"+(data if data else "Chưa bán"))

async def checkacccuaban(update,ctx):
    if not admin_protect(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")

    stock=load_rdp()
    await update.message.reply_text("📦 STOCK:\n"+("\n".join(stock) if stock else "Hết"))

async def sendstock(update,ctx):
    if not admin_protect(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    await update.message.reply_document(open(ACC_FILE,"rb"))

async def sendsold(update,ctx):
    if not admin_protect(update):
        return await update.message.reply_text("🔐 Lệnh này chỉ admin dùng trong private chat")
    await update.message.reply_document(open(SOLD_FILE,"rb"))

#================= RUN =================#
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("balance",balance))
    app.add_handler(CommandHandler("nap",nap))
    app.add_handler(CommandHandler("buyrd",buyrd))
    app.add_handler(CommandHandler("stockrd",stockrd))
    app.add_handler(CommandHandler("addacc",addacc))
    app.add_handler(CommandHandler("checkaccban",checkaccban))
    app.add_handler(CommandHandler("checkacccuaban",checkacccuaban))
    app.add_handler(CommandHandler("sendstock",sendstock))
    app.add_handler(CommandHandler("sendsold",sendsold))
    app.add_handler(MessageHandler(filters.PHOTO,handle_image))
    app.add_handler(CallbackQueryHandler(callback))

    print("BOT RUNNING...")
    app.run_polling()

if __name__=="__main__":
    keep_alive()
    main()
