import os
import logging
import random
from datetime import time as dtime, timezone as dt_timezone, datetime

import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ===================== لاگ =====================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== تنظیمات =====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "TOKEN_خودت_رو_اینجا_بذار")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "KEY_خودت_رو_اینجا_بذار")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Fx_sptrading")

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

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

# ===================== فراخوانی Gemini =====================
async def ask_gemini(system_prompt: str, user_message: str) -> str:
    try:
        model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return "⚠️ یه مشکل موقت پیش اومد، لطفاً چند لحظه دیگه دوباره امتحان کن."

# ===================== هندلرها =====================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام، خوش اومدی!\n\n"
        "🧠 من *کوچ روانشناسی ترید* هستم.\n\n"
        "هر مشکلی که توی معامله‌گری باهاش دست‌وپنجه نرم می‌کنی رو برام بنویس "
        "(مثل ترس، طمع، انتقام‌جویی، عدم انضباط و...) "
        "تا با هم ریشه‌ش رو پیدا کنیم و راهکار عملی بدم بهت.\n\n"
        "💬 فقط کافیه پیام بدی!\n\n"
        "_توجه: من جایگزین درمان روانشناسی بالینی نیستم و در موارد جدی، حتماً به متخصص واقعی مراجعه کن._",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.chat.send_action("typing")
    reply = await ask_gemini(COACH_SYSTEM_PROMPT, user_text)
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
    post_text = await ask_gemini("", prompt)

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
