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
BOT_TOKEN = os.getenv("BOT_TOKEN", "TOKEN_خودت_رو_اینجا_بذار")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "KEY_خودت_رو_اینجا_بذار")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@Fx_sptrading")

groq_client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

MAX_USER_MESSAGE_LENGTH = 1000

# ===================== شخصیت ربات =====================
COACH_SYSTEM_PROMPT = """تو یک کوچ روانشناسی ترید حرفه‌ای فارسی‌زبان هستی با تخصص در CBT، نظریه چشم‌انداز کانمن، اقتصاد رفتاری و نوروساینس.

قانون مطلق زبان:
- تمام پاسخ‌هات باید ۱۰۰ درصد فارسی روان و طبیعی باشه
- هرگز از کلمات زبان‌های ویتنامی، چینی، ژاپنی، کره‌ای، هندی، ترکی، عربی، اسپانیایی یا هر زبان غیرفارسی استفاده نکن
- اگر کلمه‌ای فارسی نیست، حتماً معادل فارسی استفاده کن
- به جای thuong بنویس معمولاً
- به جای often بنویس اغلب
- فقط از حروف فارسی و انگلیسی (داخل پرانتز) استفاده کن

اصطلاحاتی که فارسی نمی‌نویسی:
ترید، تریدر، پوزیشن، چارت، بروکر، لوریج، اسکالپ، پیپ، لات، فارکس، کریپتو

اصطلاحاتی که با معادل فارسی + پرانتز می‌نویسی:
حد ضرر (Stop Loss)، حد سود (Take Profit)، ترید انتقامی (Revenge Trading)، ترس از جا موندن (FOMO)، ترس از ضرر (Loss Aversion)، اعتماد بیش از حد (Overconfidence)

ساختار اجباری پاسخ:

دقیقاً از این فرمت زیر استفاده کن. بین هر بخش حتماً یک خط خالی بذار:

💬 **درک احساست**

[۲ جمله همدلانه که نشون بده حسش رو فهمیدی]

🧠 **ریشه روانشناختی**

[توضیح علمی در ۳ تا ۴ جمله با اشاره به یک مفهوم مثل Loss Aversion یا Amygdala Hijack]

✅ **راهکارهای عملی**

🔹 **راهکار اول: [عنوان کوتاه]**

[توضیح در ۲ جمله با مثال کاربردی]

🔹 **راهکار دوم: [عنوان کوتاه]**

[توضیح در ۲ جمله با مثال کاربردی]

🔹 **راهکار سوم: [عنوان کوتاه]**

[توضیح در ۲ جمله با مثال کاربردی]

💡 **نکته طلایی**

[یک بینش عمیق یا سوال تأملی در ۱ تا ۲ جمله]

قوانین نوشتاری مهم:
۱. حتماً بین هر بخش یک خط خالی بذار
۲. عنوان‌های اصلی رو با بولد بنویس
۳. ایموجی رو در ابتدای هر بخش بذار
۴. جملات کوتاه و واضح (حداکثر ۲۰ کلمه)
۵. از تو و برات استفاده کن، نه شما
۶. هرگز پاراگراف طولانی ننویس

ممنوع‌ها:
- شروع با البته یا قطعاً
- نوشتن همه چی پشت سر هم
- استفاده از کلمات غیرفارسی
- استفاده از اسم کاربر"""

DAILY_POST_PROMPT = """یک پست آموزشی برای کانال تلگرام روانشناسی ترید درباره: {topic}

قانون مطلق: فقط فارسی بنویس. هرگز از کلمات ویتنامی، چینی، ژاپنی یا غیرفارسی استفاده نکن.

ساختار دقیق پست:

🎯 **[عنوان جذاب با ایموجی]**

[یک جمله قلابی که توجه رو جلب کنه]

❌ **مشکل چیه؟**

[توضیح مشکل در ۲ جمله کوتاه]

🧠 **چرا این اتفاق می‌افته؟**

[ریشه روانشناختی در ۲ تا ۳ جمله با یک مفهوم علمی]

✅ **چطور حلش کنیم؟**

🔸 [راهکار اول در یک جمله]

🔸 [راهکار دوم در یک جمله]

🔸 [راهکار سوم در یک جمله]

💬 **سوال امروز:**

[یک سوال تعاملی که مخاطب جواب بده]

قوانین:
۱. حتماً بین بخش‌ها خط خالی بذار
۲. از بولد برای عنوان‌ها استفاده کن
۳. حداکثر ۱۵۰ کلمه
۴. زبان فارسی صمیمی
۵. فقط متن پست (بدون مقدمه)"""

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
    if not text:
        return ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def _clean_persian(text: str) -> str:
    """پاکسازی ساده و مطمئن متن با حفظ فرمت‌بندی"""
    if not text:
        return ""
    
    try:
        # جایگزینی کلمات شایع غیرفارسی
        replacements = {
            'thường': 'معمولاً',
            'often': 'اغلب',
            'usually': 'معمولاً',
            'sometimes': 'گاهی',
            'because': 'چون',
            'however': 'با این حال',
        }
        
        for foreign, persian in replacements.items():
            text = text.replace(foreign, persian)
        
        # حذف حروف زبان‌های شرقی
        cleaned_chars = []
        for char in text:
            cp = ord(char)
            # حذف چینی، ژاپنی، کره‌ای، تایلندی، هندی
            if (0x4E00 <= cp <= 0x9FFF or
                0x3040 <= cp <= 0x309F or
                0x30A0 <= cp <= 0x30FF or
                0xAC00 <= cp <= 0xD7AF or
                0x0E00 <= cp <= 0x0E7F or
                0x0900 <= cp <= 0x097F):
                continue
            cleaned_chars.append(char)
        
        text = ''.join(cleaned_chars)
        
        # پاکسازی فاصله‌های اضافی (با حفظ خط جدید)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    except Exception as e:
        logger.error(f"خطا در پاکسازی متن: {e}")
        return text  # اگه خطا داد، متن اصلی رو برگردون

def _call_groq(system_prompt: str, user_message: str) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.6,
            max_tokens=2000,
            top_p=0.9,
        )
        raw = completion.choices[0].message.content
        
        if not raw:
            logger.error("جواب خالی از Groq")
            return ""
        
        cleaned = _strip_thinking(raw)
        result = cleaned if cleaned else raw
        final = _clean_persian(result)
        
        gc.collect()
        
        return final if final else raw
    except Exception as e:
        logger.error(f"خطا در فراخوانی Groq: {e}")
        raise

async def ask_ai(system_prompt: str, user_message: str) -> str:
    for attempt in range(3):
        try:
            result = await asyncio.to_thread(_call_groq, system_prompt, user_message)
            if result:
                return result
        except Exception as e:
            logger.error(f"Groq Error (attempt {attempt+1}): {e}")
            if attempt < 2:
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
            "اینجا جاییه که روانشناسی معامله‌گری رو جدی می‌گیریم. "
            "بیشتر شکست‌های ترید از تحلیل تکنیکال ضعیف نمیاد — از *ذهنیتیه که با اون وارد بازار می‌شیم.*\n\n"
            "من کوچ شخصی توام برای شناخت و مدیریت همون الگوهای ذهنی: FOMO، انتقام‌جویی بعد از ضرر، بی‌انضباطی، ترس از ضرر، بیش‌اعتمادی و هر چیزی که نمی‌ذاره با آرامش معامله کنی.\n\n"
            "📝 *چطور کار می‌کنه؟*\n"
            "همین الان، هر چالشی که توی ترید باهاش دست‌وپنجه نرم می‌کنی رو برام بنویس. با هم ریشه‌ش رو پیدا می‌کنیم و چند قدم عملی و قابل اجرا بهت می‌دم.\n\n"
            "💬 فقط کافیه پیامت رو بفرستی!",
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
                "✅ عالی، عضویتت تایید شد!\n\n"
                "حالا هر چالشی که توی ترید باهاش دست‌وپنجه نرم می‌کنی رو برام بنویس تا با هم ریشه‌ش رو پیدا کنیم 💬"
            )
        else:
            await query.answer("هنوز عضو کانال نشدی! اول عضو شو، بعد دوباره بزن.", show_alert=True)
    except Exception as e:
        logger.error(f"خطا در check_join: {e}")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if not await is_member(ctx.bot, update.effective_user.id):
            await update.message.reply_text(JOIN_PROMPT, reply_markup=join_keyboard())
            return

        user_text = update.message.text
        
        if len(user_text) > MAX_USER_MESSAGE_LENGTH:
            await update.message.reply_text(
                f"⚠️ پیامت خیلی طولانیه! لطفاً کمتر از {MAX_USER_MESSAGE_LENGTH} کاراکتر بنویس."
            )
            return
        
        wait_msg = await update.message.reply_text(
            "🧠 در حال بررسی دقیق مشکلت هستم...\n"
            "چند لحظه صبر کن، یه پاسخ کامل و دقیق برات آماده می‌کنم ✍️"
        )
        
        reply = await ask_ai(COACH_SYSTEM_PROMPT, user_text)
        
        # اگه جواب خالی بود
        if not reply or len(reply) < 10:
            reply = "⚠️ متاسفم، نتونستم جواب مناسبی بدم. لطفاً دوباره و واضح‌تر بپرس."
        
        # تلاش برای ارسال با Markdown
        try:
            await wait_msg.edit_text(reply, parse_mode="Markdown")
        except Exception as e1:
            logger.warning(f"خطا در ارسال با Markdown: {e1}")
            try:
                # تلاش بدون Markdown
                await wait_msg.edit_text(reply)
            except Exception as e2:
                logger.warning(f"خطا در edit بدون Markdown: {e2}")
                try:
                    # ارسال پیام جدید
                    await update.message.reply_text(reply)
                except Exception as e3:
                    logger.error(f"خطا در ارسال پیام نهایی: {e3}")
        
        gc.collect()
        
    except Exception as e:
        logger.error(f"خطا کلی در handle_message: {e}")
        try:
            await update.message.reply_text("⚠️ یه مشکل پیش اومد، دوباره امتحان کن.")
        except:
            pass

async def cmd_testpost(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("⏳ در حال ساخت پست...")
        await send_daily_post(ctx)
        await update.message.reply_text("✅ پست به کانال ارسال شد.")
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
        
        gc.collect()
        
    except Exception as e:
        logger.error(f"خطا در ارسال پست به کانال: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception: {context.error}", exc_info=context.error)

# ===================== اجرا =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("testpost", cmd_testpost))
    app.add_handler(CallbackQueryHandler(handle_check_join, pattern="^check_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.add_error_handler(error_handler)

    app.job_queue.run_daily(
        send_daily_post,
        time=dtime(hour=17, minute=30, tzinfo=dt_timezone.utc)
    )

    logger.info("✅ ربات کوچ روانشناسی ترید شروع به کار کرد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
