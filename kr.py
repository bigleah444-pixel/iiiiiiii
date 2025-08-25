import os
import logging
import asyncio
from datetime import datetime, time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import CreateChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.errors import FloodWaitError

logging.basicConfig(level=logging.INFO)

ASK_PHONE, ASK_CODE, ASK_PASSWORD = range(3)

API_ID = 28985532
API_HASH = "de298028aac85bce7db3aa688bdf2322"

user_sessions = {}
created_groups = {}
developer_id = 79375405  # ID المطور

# ---- لوحة الأزرار ----
def main_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تشغيل", callback_data="start_manual")],
        [InlineKeyboardButton("إيقاف", callback_data="stop_manual")],
        [InlineKeyboardButton("تفعيل النظام الأوتوماتيكي", callback_data="enable_daily")],
        [InlineKeyboardButton("إيقاف النظام الأوتوماتيكي", callback_data="disable_daily")],
        [InlineKeyboardButton("المطور", url="https://t.me/M_R_Q_P")]
    ])

def login_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تسجيل دخول", callback_data="login")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id == developer_id:
        await update.message.reply_text("اهلا مطور 😎", reply_markup=main_keyboard(user_id))
    elif user_id in user_sessions and user_sessions[user_id].get("logged_in"):
        await update.message.reply_text("اختر أحد الخيارات:", reply_markup=main_keyboard(user_id))
    else:
        await update.message.reply_text(
            "📲 لتتمكن من استخدام البوت سجل دخول بحسابك أولاً.",
            reply_markup=login_keyboard()
        )
    return ASK_PHONE


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "login":
        await query.message.edit_text("📱 أرسل رقم هاتفك (مع رمز الدولة):")
        return ASK_PHONE

    elif data == "logout":
        user_sessions.pop(user_id, None)
        created_groups.pop(user_id, None)
        await query.message.edit_text("✅ تم تسجيل الخروج.", reply_markup=login_keyboard())

  
    elif data == "start_manual":
        if user_id not in user_sessions:
            return await query.answer("⚠️ سجل دخول أولاً!", show_alert=True)

        if len(created_groups.get(user_id, [])) >= 50:
            await query.message.edit_text("⚠️ وصلت إلى الحد الأقصى (50 مجموعة).", reply_markup=main_keyboard(user_id))
            return

        user_sessions[user_id]["manual"] = True
        await query.message.edit_text("✅ تم تشغيل الإنشاء اليدوي (50 مجموعة).", reply_markup=main_keyboard(user_id))
        start_index = len(created_groups.get(user_id, [])) + 1
        asyncio.create_task(run_manual(user_id, start_index, context, query))


    elif data == "stop_manual":
        if user_id not in user_sessions:
            return await query.answer("⚠️ سجل دخول أولاً!", show_alert=True)
        user_sessions[user_id]["manual"] = False
        await query.message.edit_text("🛑 تم إيقاف الإنشاء اليدوي.", reply_markup=main_keyboard(user_id))

    
    elif data == "enable_daily":
        if user_id not in user_sessions:
            return await query.answer("⚠️ سجل دخول أولاً!", show_alert=True)
        user_sessions[user_id]["daily"] = True
        if not created_groups.get(user_id):
            created_groups[user_id] = []
        await query.message.edit_text("✅ تم تفعيل النظام الأوتوماتيكي.\n🚀 جاري إنشاء المجموعات...", reply_markup=main_keyboard(user_id))
        asyncio.create_task(run_daily(user_id, context, query))

    elif data == "disable_daily":
        if user_id not in user_sessions:
            return await query.answer("⚠️ سجل دخول أولاً!", show_alert=True)
        user_sessions[user_id]["daily"] = False
        await query.message.edit_text("🛑 تم إيقاف النظام الأوتوماتيكي.", reply_markup=main_keyboard(user_id))


async def run_manual(user_id, start_index, context, query):
    for i in range(start_index, 51):
        if not user_sessions[user_id].get("manual", False):
            break
        try:
            await create_group(user_id, i, context)
        except FloodWaitError:
            await query.message.reply_text("⚠️ تم الوصول إلى حد السرعة، سيتم المحاولة لاحقاً.")
            break
        await asyncio.sleep(2)


async def run_daily(user_id, context, query):
    start_index = len(created_groups.get(user_id, [])) + 1
    for i in range(start_index, 51):
        if not user_sessions[user_id].get("daily", False):
            break
        try:
            await create_group(user_id, i, context)
        except FloodWaitError:
            await query.message.reply_text("⚠️ تم الوصول إلى حد السرعة، سيتم المحاولة لاحقاً.")
            break
        await asyncio.sleep(2)


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.text
    context.user_data["phone"] = phone
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(phone)
    context.user_data["client"] = client
    await update.message.reply_text("✉️ أدخل كود التحقق الذي وصلك على تليجرام\n\n🧧 ملاحظـه: "
        "عليك عند ارسال كود التحقق ان تضع مسافات بين كل رقم مثال:\n1 2 3 4 5")
    return ASK_CODE


async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    code = update.message.text.replace(" ", "")
    phone = context.user_data["phone"]
    client = context.user_data["client"]

    try:
        await client.sign_in(phone, code)
    except Exception:
        await update.message.reply_text("🔒 الحساب محمي بكلمة مرور، أرسل الباسورد:")
        return ASK_PASSWORD

    await update.message.reply_text("اهلا بك في بوت انشاء الكروبات اضغط احد الازرار للبدء", reply_markup=main_keyboard(user_id))
    session_str = client.session.save()
    with open(f"session_{user_id}.session", "w") as f:
        f.write(session_str)

    user_sessions[user_id] = {"logged_in": True, "manual": False, "daily": False}
    created_groups[user_id] = []
    await client.disconnect()
    return ConversationHandler.END


async def ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    password = update.message.text
    client = context.user_data["client"]
    await client.sign_in(password=password)

    await update.message.reply_text("✅ تم تسجيل الدخول!", reply_markup=main_keyboard(user_id))
    session_str = client.session.save()
    with open(f"session_{user_id}.session", "w") as f:
        f.write(session_str)

    user_sessions[user_id] = {"logged_in": True, "manual": False, "daily": False}
    created_groups[user_id] = []
    await client.disconnect()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

async def create_group(user_id, index, context):
    if not os.path.exists(f"session_{user_id}.session"):
        return
    client = TelegramClient(StringSession(open(f"session_{user_id}.session").read()), API_ID, API_HASH)
    await client.connect()
    try:
        title = f"{datetime.now().strftime('%Y-%m-%d')}"
        result = await client(CreateChannelRequest(
            title=title,
            about='مطور السورس – @M_R_Q_P',
            megagroup=True
        ))
        chat = result.chats[0]
        created_groups[user_id].append(chat.id)

        invite = await client(ExportChatInviteRequest(chat.id))
        link = invite.link

        await context.bot.send_message(
            user_id,
            f"✅ تم إنشاء المجموعة {index}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رابط المجموعة", url=link)]])
        )

        await asyncio.sleep(1)
        await client(LeaveChannelRequest(channel=chat.id))
    except Exception as e:
        print(f"❌ خطأ: {e}")
    await client.disconnect()


async def daily_task(context):
    for user_id, data in user_sessions.items():
        if data.get("daily"):
            created_groups.setdefault(user_id, [])
            if len(created_groups[user_id]) < 50:
                start_index = len(created_groups[user_id]) + 1
                for i in range(start_index, 51):
                    if not user_sessions[user_id].get("daily", False):
                        break
                    try:
                        await create_group(user_id, i, context)
                    except FloodWaitError:
                        await context.bot.send_message(user_id, "**تم الوصول الى الحد الاقصى 50 كروب**")
                        break
                    await asyncio.sleep(2)


async def scheduler(app):
    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), time(hour=9, minute=0))
        if now > target:
            target = target.replace(day=now.day + 1)
        await asyncio.sleep((target - now).total_seconds())
        await daily_task(app)


async def run_app():
    TOKEN = os.environ.get("TOKEN", None)
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    asyncio.create_task(scheduler(app))
    print("✅ البوت يعمل الآن...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(run_app())
