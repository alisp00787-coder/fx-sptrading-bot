import os
import logging
import asyncio
import re
import gc
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
BOT_TOKEN = os.getenv("BOT_TOKEN", "TOKEN_خودت")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "KEY_خودت")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Fx_sptrading")

groq_client = Groq(api_key=GROQ_API_KEY)
# 🔥 تغییر مدل به مدل سبک‌تر و سریع‌تر
MODEL_NAME = "llama-3.1-8b-instant"  # یا "llama-3.3-70b-versatile" اگه واقعاً لازم داری
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

# 🔥 محدودیت طول پیام کاربر
MAX_USER_MESSAGE_LENGTH = 1000

# ===================== شخصیت ربات =====================
COACH_SYSTEM_PROMPT = """قانون مطلق: تمام پاسخ‌هات ۱۰۰٪ فارسی باشه. اصطلاحات تخصصی انگلیسی فقط داخل پرانتز.

اصطلاحاتی که فارسی نمی‌نویسی: ترید، تریدر، پوزیشن، چارت، بروکر، لوریج، اسکالپ، پیپ، لات، فارکس، کریپتو

اصطلاحات با معادل فارسی + پرانتز: حد ضرر (Stop Loss)، حد سود (Take Profit)، ترید انتقامی (Revenge Trading)، ترس از جا موندن (FOMO)، ترس از ضرر (Loss Aversion)

تو یک کوچ روانشناسی ترید هستی با تخصص در CBT، نظریه چشم‌انداز کانمن، و نوروساینس.

سبک:
- گرم و انسانی، نه چت‌بات
- اول احساس کاربر رو بازتاب بده
- از «تو» و «برات» استفاده کن
- هرگز با «البته» شروع نکن

ساختار پاسخ:
۱. همدلی واقعی (۲ جمله)
۲. ریشه روانشناختی با مفهوم علمی (Loss Aversion، Amygdala Hijack، سیستم ۱ و ۲ کانمن)
۳. ۳ راهکار عملی با مثال
۴. یک سوال تأملی در پایان

اگر نشانه بحران دیدی، به متخصص ارجاع بده."""

DAILY_POST_PROMPT = """یک پست کوتاه برای کانال تلگرام روانشناسی ترید درباره: {topic}

ساختار:
۱. عنوان جذاب با ایموجی
۲. توضیح مشکل (۲ جمله)
۳. ریشه روانشناختی (یک پاراگراف)
۴. ۲ راهکار عملی
۵. سوال تعاملی در پایان

فارسی، صمیمی، حداکثر ۱۵۰ کلمه. از **بولد** استفاده کن. فقط متن پست."""

TOPICS = [
    "ترس از دست دادن فرصت (FOMO) و ورود عجولانه",
    "ترید انتقامی بعد از ضرر بزرگ",
    "عدم پایبندی به حد ضرر",
    "بیش‌اعتمادی بعد از معاملات موفق",
    "ترس از خروج با سود کم",
    "اضطراب قبل از باز کردن معامله",
    "وابستگی روانی به نتیجه معامله",
    "مقایسه با تریدرهای دیگه",
    "افزایش حجم بعد از ضرر",
    "تصمیم‌گیری احساسی بدون برنامه",
    "ترس از شکست و عدم ورود",
    "خستگی ذهنی بعد از تحلیل طولانی",
]

# ===================== فراخوانی Groq =====================
def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def _clean_persian(text: str) -> str:
    """نسخه بهینه‌شده با regex - خیلی سریع‌تر و سبک‌تر"""
    # فقط کاراکترهای مجاز رو نگه دار
    allowed_pattern = re.compile(
        r'[\u0600-\u06FF'  # فارسی/عربی
        r'a-zA-Z0-9'        # لاتین و اعداد
        r'\s.,!?:;()\[\]{}«»\-_/\\@#%^&+=<>|~`"\'…—–*'  # علائم
        r'\u1F300-\u1FAFF'  # ایموجی
        r'\u2600-\u27BF'
        r'\u231A-\u2B55'
        r'،؛؟]+'
    )
    matches = allowed_pattern.findall(text)
    result = ' '.join(matches)
    return re.sub(r'\s+', ' ', result).strip()

def _call_groq(system_prompt: str, user_message: str) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1500,  # 🔥 کاهش از 4096 به 1500
        )
        raw = completion.choices[0].message.content
        cleaned = _strip_thinking(raw)
        result = cleaned if cleaned else raw
        final = _clean_persian(result)
        
        # 🔥 پاکسازی حافظه
        del completion, raw, cleaned, result, messages
        gc.collect()
        
        return final
    except Exception as e:
        logger.error(f"خطا در فراخوانی Groq: {e}")
        raise

async def ask_ai(system_prompt: str, user_message: str) -> str:
    for attempt in range(2):  # 🔥 کاهش از 3 به 2
        try:
            result = await asyncio.to_thread(_call_groq, system_prompt, user_message)
            if result:
                return result
        except Exception as e:
            logger.error(f"Groq Error (attempt {attempt+1}): {e}")
            if attempt < 1:
                await asyncio.sleep(2)
    return "⚠️ یه مشکل موقت پیش اومد، لطفاً چند لحظه دیگه دوباره امتحان کن."

# ===================== بررسی عضویت =====================
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
    try:
        if not await is_member(ctx.bot, update.effective_user.id):
            await update.message.reply_text(JOIN_PROMPT, reply_markup=join_keyboard())
            return

        await update.message.reply_text(
            "🧠✨ به *Fx_sptrading* خوش اومدی!\n\n"
            "اینجا روانشناسی معامله‌گری رو جدی می‌گیریم. "
            "بیشتر شکست‌های ترید از *ذهنیتیه که با اون وارد بازار می‌شیم.*\n\n"
            "من کوچ شخصی توام برای: FOMO، انتقام‌جویی، بی‌انضباطی، ترس از ضرر و...\n\n"
            "📝 *چطور کار می‌کنه؟*\n"
            "هر چالشی توی ترید داری برام بنویس. ریشه‌ش رو پیدا می‌کنیم و راهکار عملی می‌دم.\n\n"
            "💬 پیامت رو بفرست!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در /start: {e}")

async def handle_check_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if await is_member(ctx.bot, query.from_user.id):
            await query.answer("✅ عضویتت تایید شد!")
            await query.message.edit_text(
                "✅ عالی! حالا چالشت رو برام بنویس تا ریشه‌ش رو پیدا کنیم 💬"
            )
        else:
            await query.answer("هنوز عضو کانال نشدی! اول عضو شو.", show_alert=True)
    except Exception as e:
        logger.error(f"خطا در check_join: {e}")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if not await is_member(ctx.bot, update.effective_user.id):
            await update.message.reply_text(JOIN_PROMPT, reply_markup=join_keyboard())
            return

        user_text = update.message.text
        
        # 🔥 محدودیت طول پیام
        if len(user_text) > MAX_USER_MESSAGE_LENGTH:
            await update.message.reply_text(
                f"⚠️ پیامت خیلی طولانیه! لطفاً کمتر از {MAX_USER_MESSAGE_LENGTH} کاراکتر بنویس."
            )
            return
        
        wait_msg = await update.message.reply_text(
            "🧠 در حال بررسی... چند لحظه صبر کن ✍️"
        )
        
        reply = await ask_ai(COACH_SYSTEM_PROMPT, user_text)
        
        try:
            await wait_msg.edit_text(reply, parse_mode="Markdown")
        except Exception:
            try:
                await update.message.reply_text(reply, parse_mode="Markdown")
            except Exception:
                # اگه Markdown مشکل داشت، بدون فرمت بفرست
                await update.message.reply_text(reply)
        
        # 🔥 پاکسازی حافظه
        del reply, user_text
        gc.collect()
        
    except Exception as e:
        logger.error(f"خطا در handle_message: {e}")
        try:
            await update.message.reply_text("⚠️ یه مشکل پیش اومد، دوباره امتحان کن.")
        except:
            pass

async def cmd_testpost(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("⏳ در حال ساخت پست...")
        await send_daily_post(ctx)
        await update.message.reply_text("✅ پست ارسال شد.")
    except Exception as e:
        logger.error(f"خطا در testpost: {e}")

# ===================== پست خودکار روزانه =====================
async def send_daily_post(ctx: ContextTypes.DEFAULT_TYPE):
    try:
        topic_index = datetime.now(dt_timezone.utc).toordinal() % len(TOPICS)
        topic = TOPICS[topic_index]
        prompt = DAILY_POST_PROMPT.format(topic=topic)
        post_text = await ask_ai("", prompt)

        await ctx.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=post_text,
            parse_mode="Markdown"
        )
        logger.info(f"✅ پست روزانه ارسال شد: {topic}")
        
        # 🔥 پاکسازی
        del post_text, prompt
        gc.collect()
        
    except Exception as e:
        logger.error(f"خطا در ارسال پست: {e}")

# 🔥 Error Handler کلی
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception: {context.error}", exc_info=context.error)

# ===================== اجرا =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("testpost", cmd_testpost))
    app.add_handler(CallbackQueryHandler(handle_check_join, pattern="^check_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 🔥 اضافه کردن error handler
    app.add_error_handler(error_handler)

    app.job_queue.run_daily(
        send_daily_post,
        time=dtime(hour=17, minute=30, tzinfo=dt_timezone.utc)
    )

    logger.info("✅ ربات کوچ روانشناسی ترید شروع به کار کرد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
