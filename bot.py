import json, time, random
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from keep_alive import keep_alive   # Dùng cho Render

#================= CONFIG =================#
BOT_TOKEN = "6367532329:AAFDbKOG4-I8pxo66gF3PPBBzVuxr5xnFUY"          # Thay token bot
ADMIN_ID = 5736655322                  # Thay ID admin
RDP_PRICE = 2000                      # Giá mỗi acc RDP

ACC_FILE = "acc_rdp.txt"
DB_FILE  = "users.json"
SOLD_FILE = "sold.txt"

#================= DATABASE =================#
def load_db():
    try: return json.load(open(DB_FILE))
    except: return {}

def save_db(data):
    json.dump(data, open(DB_FILE,"w"), indent=4)

users = load_db()

def get_balance(uid): return users.get(str(uid),0)
def add_balance(uid,amount):
    users[str(uid)] = get_balance(uid) + amount
    save_db(users)

#================= STOCK RDP =================#
def load_rdp():
    try:
        return [i.strip() for i in open(ACC_FILE,encoding="utf-8") if i.strip()]
    except:
        return []

def save_rdp(lst):
    open(ACC_FILE,"w",encoding="utf-8").write("\n".join(lst))

#================= PENDING NẠP =================#
pending = {}  # lưu tạm các yêu cầu nạp tiền

#================= COMMANDS =================#
async def start(update,ctx):
    await update.message.reply_text(
        "🖥 BOT BÁN RDP AUTO\n"
        "====================\n"
        "📌 Lệnh người dùng:\n"
        "/balance - xem số dư\n"
        "/nap <số tiền> - yêu cầu nạp\n"
        "/buyrd - mua 1 RDP\n"
        "/stockrd - xem còn bao nhiêu RDP\n\n"
        "👑 Admin:\n"
        "/addacc user|pass - thêm stock\n"
        "/checkacccuaban - xem acc chưa bán\n"
        "/checkaccban - xem acc đã bán\n"
        "/sendstock - gửi file stock\n"
        "/sendsold - gửi file đã bán\n"
    )

async def balance(update,ctx):
    uid = update.effective_user.id
    await update.message.reply_text(f"💰 Số dư hiện tại: {get_balance(uid)}đ")

#================= LỆNH NẠP =================#
async def nap(update,ctx):
    uid = update.effective_user.id
    try:
        amount = int(ctx.args[0])
    except:
        return await update.message.reply_text("❗ Dùng: /nap <số tiền>")

    # Tạo mã giao dịch: UID + timestamp + random
    txn_code = f"{uid}_{int(time.time())}_{random.randint(100,999)}"
    pending[uid] = {"amount": amount, "txn": txn_code}

    msg = (
        "💳 HƯỚNG DẪN NẠP TIỀN\n\n"
        "- STK: 0971487462\n"
        "- Ngân hàng: MB Bank\n"
        f"- Nội dung chuyển khoản: {uid}\n"
        f"- Số tiền: {amount}₫\n\n"
        "📸 Sau khi chuyển khoản, vui lòng gửi ảnh bill tại đây để admin duyệt.\n"
        f"🆔 Mã giao dịch: {txn_code}"
    )
    await update.message.reply_text(msg)

#================= XỬ LÝ ẢNH BILL =================#
async def handle_image(update,ctx):
    uid = update.effective_user.id
    if uid not in pending:
        return await update.message.reply_text("⚠ Bạn chưa yêu cầu nạp. Dùng /nap <số tiền>")

    data = pending.pop(uid)
    amount = data["amount"]
    txn_code = data["txn"]
    photo = update.message.photo[-1].file_id

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✔ DUYỆT", callback_data=f"ok_{uid}_{amount}_{txn_code}")],
        [InlineKeyboardButton("✖ HỦY", callback_data=f"no_{uid}_{amount}_{txn_code}")]
    ])

    await ctx.bot.send_photo(
        ADMIN_ID,
        photo=photo,
        caption=f"📥 YÊU CẦU NẠP\nUser: {uid}\nSố tiền: {amount}₫\nMã giao dịch: {txn_code}",
        reply_markup=kb
    )
    await update.message.reply_text("⏳ Bill đã gửi Admin chờ duyệt...")

#================= CALLBACK DUYỆT =================#
async def callback(update, ctx):
    q = update.callback_query
    data = q.data.split("_")
    act, uid, amount, txn = data[0], int(data[1]), int(data[2]), data[3]

    if update.effective_user.id != ADMIN_ID:
        return await q.answer("🚫 Không phải Admin", show_alert=True)

    if act == "ok":
        add_balance(uid, amount)
        await ctx.bot.send_message(uid, f"✔ Nạp thành công +{amount}₫ (Mã: {txn})")
        await q.edit_message_caption(f"ĐÃ DUYỆT +{amount}₫ cho {uid} (Mã: {txn})")
    else:
        await ctx.bot.send_message(uid, f"❌ Bill bị từ chối (Mã: {txn})")
        await q.edit_message_caption(f"ĐÃ HỦY bill của {uid} (Mã: {txn})")

    await q.answer()

#================= MUA RDP =================#
async def buyrd(update,ctx):
    uid = update.effective_user.id
    bal = get_balance(uid)
    stock = load_rdp()

    if not stock: return await update.message.reply_text("⚠ Hết hàng")
    if bal < RDP_PRICE:
        return await update.message.reply_text(
            f"❗ Không đủ tiền!\nGiá: {RDP_PRICE}đ\nSố dư: {bal}đ"
        )

    acc = stock.pop(0)
    save_rdp(stock)
    add_balance(uid, -RDP_PRICE)

    # Lưu log acc đã bán
    with open(SOLD_FILE, "a", encoding="utf-8") as f:
        f.write(f"{acc} | buyer:{uid}\n")

    await update.message.reply_text(
        f"🎉 MUA THÀNH CÔNG\n`{acc}`\nĐã trừ {RDP_PRICE}₫",
        parse_mode="Markdown"
    )

async def stockrd(update,ctx):
    await update.message.reply_text(f"📦 Stock còn {len(load_rdp())} acc")

#================= ADMIN =================#
async def addacc(update,ctx):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Admin Only")

    acc = " ".join(ctx.args)
    if "|" not in acc:
        return await update.message.reply_text("Dùng /addacc user|pass")

    with open(ACC_FILE,"a",encoding="utf-8") as f:
        f.write(acc+"\n")
    await update.message.reply_text(f"✔ Đã thêm RDP:\n{acc}")

async def checkaccban(update,ctx):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Admin Only")
    try:
        data = open(SOLD_FILE,"r",encoding="utf-8").read().strip()
        if not data: return await update.message.reply_text("⚠ Chưa bán acc nào")
    except:
        return await update.message.reply_text("⚠ File sold.txt chưa tồn tại")

    await update.message.reply_text(f"📑 ACC ĐÃ BÁN:\n\n{data}")

async def checkacccuaban(update,ctx):
    stock = load_rdp()
    if not stock: return await update.message.reply_text("⚠ Hết stock")
    await update.message.reply_text(
        f"📦 ACC CHƯA BÁN ({len(stock)}):\n\n" + "\n".join(stock)
    )

async def sendstock(update,ctx):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Admin Only")
    await update.message.reply_document(open(ACC_FILE,"rb"))

async def sendsold(update,ctx):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Admin Only")
    await update.message.reply_document(open(SOLD_FILE,"rb"))

#================= RUN BOT =================#
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("balance",balance))
    app.add_handler(CommandHandler("nap",nap))
    app.add_handler(CommandHandler("buyrd",buyrd))
    app.add_handler(CommandHandler("stockrd",stockrd))
    app.add_handler(CommandHandler("addacc",addacc))
    app.add_handler(CommandHandler("checkacccuaban",checkacccuaban))
    app.add_handler(CommandHandler("checkaccban",checkaccban))
    app.add_handler(CommandHandler("sendstock",sendstock))
    app.add_handler(CommandHandler("sendsold",sendsold))

    app.add_handler(MessageHandler(filters.PHOTO,handle_image))
    app.add_handler(CallbackQueryHandler(callback))

    print("BOT RUNNING...")
    app.run_polling()

if __name__=="__main__":
    keep_alive()   # giữ bot hoạt động 24/7 trên Render
    main()
