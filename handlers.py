from telebot import types
from db import get_balance,create_user,history_save,get_top,get_history,add_money,minus,add_request
from acc import get_random_acc,add_account

PRICE = 2000
ADMIN_ID = 5736655322   # <<< ĐỔI ID ADMIN

def register_handlers(bot):

    #===== START =====#
    @bot.message_handler(commands=['start'])
    def start(m):
        create_user(m.from_user.id)
        bot.reply_to(m,f"""👋 Chào {m.from_user.first_name}
💰 Số dư: {get_balance(m.from_user.id)}đ

⚙ Lệnh:
• /buy – Mua acc {PRICE}đ
• /nap – Cách nạp
• /top – Top nạp tiền
• /history – Lịch sử mua

👑 Admin:
• /addacc user|pass
• /sendfile – Xuất acc.txt
""")

    #===== BUY =====#
    @bot.message_handler(commands=['buy'])
    def buy(m):
        uid=m.from_user.id
        if get_balance(uid)<PRICE:
            return bot.reply_to(m,f"Không đủ tiền ({PRICE}đ)!")
        acc=get_random_acc()
        if not acc: return bot.reply_to(m,"❗ Hết acc!")
        minus(uid,PRICE)
        history_save(uid,acc)
        bot.reply_to(m,f"🔑 `{acc}`",parse_mode="Markdown")

    #===== NẠP =====#
    @bot.message_handler(commands=['nap'])
    def nap(m):
        bot.reply_to(m,"💳 Gửi ảnh chuyển khoản + caption:\n`nap 20000`",parse_mode="Markdown")

    @bot.message_handler(content_types=['photo'])
    def image(m):
        if not m.caption or not m.caption.startswith("nap"):
            return bot.reply_to(m,"📌 Gửi ảnh + caption đúng dạng `nap số_tiền`")

        try: amount=int(m.caption.split()[1])
        except: return bot.reply_to(m,"Sai cú pháp!")

        uid=m.from_user.id
        img_id=m.photo[-1].file_id

        add_request(uid,amount,img_id)

        markup=types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔ Duyệt",callback_data=f"ok_{uid}_{amount}"),
            types.InlineKeyboardButton("✖ Từ chối",callback_data=f"no_{uid}")
        )

        bot.send_photo(ADMIN_ID,img_id,f"💰 User {uid} yêu cầu nạp {amount}đ",reply_markup=markup)
        bot.reply_to(m,"⏳ Đợi admin duyệt...")

    #===== CALLBACK ADMIN =====#
    @bot.callback_query_handler(func=lambda c:True)
    def confirm(c):
        if c.from_user.id!=ADMIN_ID:
            return bot.answer_callback_query(c.id,"Không phải admin!")

        data=c.data.split("_")

        # DUYỆT
        if data[0]=="ok":
            uid,amount=int(data[1]),int(data[2])
            add_money(uid,amount)
            bot.send_message(uid,f"💳 Nạp +{amount}đ thành công!")
            return bot.edit_message_caption(chat_id=c.message.chat.id,
                    message_id=c.message.message_id,
                    caption="✔ Đã DUYỆT")

        # TỪ CHỐI
        if data[0]=="no":
            uid=int(data[1])
            bot.send_message(uid,"❗ Giao dịch bị từ chối!")
            return bot.edit_message_caption(chat_id=c.message.chat.id,
                    message_id=c.message.message_id,
                    caption="✖ Đã từ chối yêu cầu")

    #===== TOP - HISTORY =====#
    @bot.message_handler(commands=['top'])
    def top(m):
        data=get_top()
        if not data: return bot.reply_to(m,"Chưa có ai nạp")
        msg="🏆 TOP NẠP\n\n"
        for i,(uid,total) in enumerate(data,1): msg+=f"{i}. {uid} – {total}đ\n"
        bot.reply_to(m,msg)

    @bot.message_handler(commands=['history'])
    def his(m):
        row=get_history(m.from_user.id)
        if not row: return bot.reply_to(m,"Chưa mua acc nào")
        msg="\n".join([f"🔑 {x[0]}" for x in row[-10:]])
        bot.reply_to(m,"📜 Lịch sử mua:\n"+msg)

    #===== ADMIN ADD ACC =====#
    @bot.message_handler(commands=['addacc'])
    def addacc(m):
        if m.from_user.id!=ADMIN_ID: return
        acc=m.text.replace("/addacc ","")
        add_account(acc)
        bot.reply_to(m,"✔ Đã thêm!")

    @bot.message_handler(commands=['sendfile'])
    def sendfile(m):
        if m.from_user.id==ADMIN_ID:
            bot.send_document(m.chat.id,open("acc.txt","rb"))
