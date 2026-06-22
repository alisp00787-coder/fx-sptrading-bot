import os
import logging
import asyncio
import re
from datetime import time as dtime, timezone as dt_timezone, datetime

from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ===================== لاگ =====================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== تنظیمات =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "TOKEN_خودت_رو_اینجا_بذار")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "KEY_خودت_رو_اینجا_بذار")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Fx_sptrading")

groq_client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "qwen/qwen3.6-27b"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

# ===================== شخصیت ربات =====================
COACH_SYSTEM_PROMPT = """تو یک کوچ تخصصی روانشناسی معامله‌گری (ترید) هستی، نه یک تراپیست یا روانپزشک دارای مجوز بالینی.
وظیفه‌ت کمک به معامله‌گرها برای شناخت ریشه مشکلات روانی‌شون در بازارهای مالی (مثل ترس از دست دادن فرصت، طمع، انتقام‌جویی بعد از ضرر، عدم انضباط، بیش‌اعتمادی، ترس از ضرر) و ارائه راهکارهای عملی و قابل اجراست.

اصول پاسخ‌دهی:
- همیشه فارسی و با لحن گرم، همدلانه و حرفه‌ای صحبت کن
- اول با مشکل کاربر همدلی کن، بعد تحلیلش کن
- ریشه روانشناختی مشکل رو دقیق و عمیق توضیح بده، نه فقط سطحی
- ۲ تا ۳ راهکار عملی و قابل اجرا بده
- پاسخ نسبتاً کوتاه و خوانا باشه (نه مقاله بلند)

نکته ایمنی مهم: اگر کاربر نشونه‌های جدی پریشانی روانی، افسردگی شدید، بحران مالی فاجعه‌بار، یا افکار آسیب به خود نشون داد:
فوراً صحبت درباره ترید رو متوقف کن، با محبت و بدون قضاوت باهاش صحبت کن، و او رو جدی به صحبت با یک متخصص سلامت روان واقعی یا نزدیکانش تشویق کن. در این حالت هرگز ادامه تحلیل ترید نده."""

DAILY_POST_PROMPT = """یک پست آموزشی کوتاه برای کانال تلگرام روانشناسی ترید درباره موضوع زیر بنویس:

موضوع: {topic}

ساختار پست:
۱. یک عنوان جذاب با ایموجی مرتبط (خط اول)
۲. توضیح مشکل در ۲-۳ جمله
۳. ریشه روانشناختی مشکل (یک پاراگراف کوتاه)
۴. ۲-۳ راهکار عملی و قابل اجرا (به صورت لیست)
۵. یک سوال تعاملی برای کامنت‌های مخاطبین در پایان

پست باید کاملاً فارسی، صمیمی، حداکثر ۱۸۰ کلمه، و برای تریدرهای ایرانی قابل فهم باشه.
از Markdown ساده استفاده کن (بولد با **متن**). فقط متن پست رو بنویس، بدون مقدمه اضافه."""

TOPICS = [
    "ترس از دست دادن فرصت (FOMO) و ورود عجولانه به معامله",
    "انتقام‌جویی در معامله بعد از یک ضرر بزرگ (Revenge Trading)",
    "عدم پایبندی به حد ضرر (Stop Loss) و امیدواری بیجا",
    "بیش‌اعتمادی به نفس بعد از چند معامله موفق پیاپی",
    "ترس از خروج با سود کم و از دست دادن سودهای بزرگ‌تر",
    "اضطراب و استرس قبل از باز کردن معامله",
    "وابستگی روانی به نتیجه هر معامله و نوسان خلق‌وخو",
    "مقایسه خودت با تریدرهای دیگه و حس حسادت یا ناامیدی",
    "افزایش حجم معامله بعد از ضرر برای جبران سریع",
    "عدم داشتن برنامه معاملاتی مشخص و تصمیم‌گیری احساسی",
    "ترس از شکست که باعث عدم ورود به معاملات خوب می‌شه",
    "خستگی ذهنی و فرسودگی بعد از ساعت‌ها تحلیل بازار",
]

# ===================== فراخوانی Groq =====================
def _strip_thinking(text: str) -> str:
    """حذف بخش 'فکر کردن' مدل (داخل تگ think) و نگه داشتن فقط جواب نهایی"""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()

def _call_groq(system_prompt: str, user_message: str) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    completion = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
    )
    raw = completion.choices[0].message.content
    cleaned = _strip_thinking(raw)
    return cleaned if cleaned else raw

async def ask_ai(system_prompt: str, user_message: str) -> str:
    try:
        return await asyncio.to_thread(_call_groq, system_prompt, user_message)
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        return "⚠️ یه مشکل موقت پیش اومد، لطفاً چند لحظه دیگه دوباره امتحان کن."

# ===================== بررسی عضویت در کانال =====================
async def is_member(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        return False

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")]
    ])

JOIN_PROMPT = (
    "🔒 برای استفاده از ربات، اول باید عضو کانال ما بشی:\n\n"
    "بعد از عضویت، روی دکمه «عضو شدم، بررسی کن» بزن 👇"
)

# ===================== هندلرها =====================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_member(ctx.bot, update.effective_user.id):
        await update.message.reply_text(JOIN_PROMPT, reply_markup=join_keyboard())
        return

    await update.message.reply_text(
        "🧠✨ به *Fx_sptrading* خوش اومدی!\n\n"
        "اینجا جاییه که روانشناسی معامله‌گری رو جدی می‌گیریم. "
        "بیشتر شکست‌های ترید از تحلیل تکنیکال ضعیف نمیاد — از *ذهنیتیه که با اون وارد بازار می‌شیم.*\n\n"
        "من کوچ شخصی توام برای شناخت و مدیریت همون الگوهای ذهنی: FOMO، انتقام‌جویی بعد از ضرر، بی‌انضباطی، ترس از ضرر، بیش‌اعتمادی و هر چیزی که نمی‌ذاره با آرامش معامله کنی.\n\n"
        "📝 *چطور کار می‌کنه؟*\n"
        "همین الان، هر چالشی که توی ترید باهاش دست‌وپنجه نرم می‌کنی رو برام بنویس. با هم ریشه‌ش رو پیدا می‌کنیم و چند قدم عملی و قابل اجرا بهت می‌دم.\n\n"
        "💬 فقط کافیه پیامت رو بفرستی!\n\n"
        "_من جایگزین درمان روانشناسی بالینی نیستم؛ در شرایط جدی، حتماً با یک متخصص واقعی صحبت کن._",
        parse_mode="Markdown"
    )

async def handle_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await is_member(ctx.bot, query.from_user.id):
        await query.answer("✅ عضویتت تایید شد!")
        await query.message.edit_text(
            "✅ عالی، عضویتت تایید شد!\n\n"
            "حالا هر چالشی که توی ترید باهاش دست‌وپنجه نرم می‌کنی رو برام بنویس تا با هم ریشه‌ش رو پیدا کنیم 💬"
        )
    else:
        await query.answer("هنوز عضو کانال نشدی! اول عضو شو، بعد دوباره بزن.", show_alert=True)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_member(ctx.bot, update.effective_user.id):
        await update.message.reply_text(JOIN_PROMPT, reply_markup=join_keyboard())
        return

    user_text = update.message.text
    await update.message.chat.send_action("typing")
    reply = await ask_ai(COACH_SYSTEM_PROMPT, user_text)
    await update.message.reply_text(reply, parse_mode="Markdown")

async def cmd_testpost(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ارسال دستی یک پست تستی به کانال (برای آزمایش)"""
    await update.message.reply_text("⏳ در حال ساخت پست...")
    await send_daily_post(ctx)
    await update.message.reply_text("✅ پست به کانال ارسال شد.")

# ===================== پست خودکار روزانه =====================
async def send_daily_post(ctx: ContextTypes.DEFAULT_TYPE):
    topic_index = datetime.now(dt_timezone.utc).toordinal() % len(TOPICS)
    topic = TOPICS[topic_index]
    prompt = DAILY_POST_PROMPT.format(topic=topic)
    post_text = await ask_ai("", prompt)

    try:
        await ctx.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=post_text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ پست روزانه ارسال شد: {topic}")
    except Exception as e:
        logger.error(f"خطا در ارسال پست به کانال: {e}")

# ===================== اجرا =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("testpost", cmd_testpost))
    app.add_handler(CallbackQueryHandler(handle_check_join, pattern="^check_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # پست خودکار هر روز ساعت ۹ شب به وقت ایران (۱۷:۳۰ UTC)
    app.job_queue.run_daily(
        send_daily_post,
        time=dtime(hour=17, minute=30, tzinfo=dt_timezone.utc)
    )

    logger.info("✅ ربات کوچ روانشناسی ترید شروع به کار کرد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
