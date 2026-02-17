import os
import asyncio
import time
import random
import re
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp
from internetarchive import upload, configure, get_item

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
IA_EMAIL = os.getenv('IA_EMAIL')
IA_KEY = os.getenv('IA_KEY')
IA_SECRET = os.getenv('IA_SECRET')

if all([TELEGRAM_TOKEN, IA_EMAIL, IA_KEY, IA_SECRET]):
    configure(IA_EMAIL, IA_KEY, IA_SECRET)
else:
    print("Environment variables missing!")
    exit(1)

upload_queue = deque()
processing = False
app = None

async def send_status(chat_id, message):
    try:
        await app.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🔥 Terabox → Archive.org Bot

*Single:* `link | title | category`

*Multiple:*
`/queue`
`link1 | title1 | cat1`
`link2 | title2 | cat2`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing
    text = ' '.join(context.args)
    
    if not text.strip():
        msg = "❌ Links bhejiye `/queue` ke saath!

`/queue`
`https://terabox.com/xyz | Avengers | Movies`"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return
    
    lines = text.split('
')
    queued = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if 'terabox' in line.lower() and '|' in line:
            parts = [p.strip() for p in line.split('|')]
            queue_item = {
                'link': parts[0],
                'title': parts[1] if len(parts) > 1 else f'Untitled_{i+1}',
                'category': parts[2] if len(parts) > 2 else 'data',
                'chat_id': update.effective_chat.id
            }
            upload_queue.append(queue_item)
            queued += 1
    
    status = f"✅ {queued} links queued! Processing..."
    await update.message.reply_text(status, parse_mode='Markdown')
    
    if not processing:
        asyncio.create_task(process_queue())

async def process_queue():
    global processing
    processing = True
    
    total = len(upload_queue)
    current = 0
    
    while upload_queue:
        current += 1
        item = upload_queue.popleft()
        video_file = None
        
        try:
            unique_id = f"tba_{int(time.time())}_{random.randint(1000,9999)}"
            output_template = f"{unique_id}.%(ext)s"
            
            status = f"⏳ {current}/{total}: {item['title']} - Downloading..."
            await send_status(item['chat_id'], status)
            
            ydl_opts = {
                'outtmpl': output_template,
                'format': 'best[height<=1080]',
                'quiet': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['link']])
            
            files = [f for f in os.listdir('.') if f.startswith(unique_id)]
            if not files:
                raise Exception("Download failed")
            video_file = files[0]
            
            status = f"📤 {current}/{total}: {item['title']} - Uploading..."
            await send_status(item['chat_id'], status)
            
            identifier = re.sub(r'[^w-]', '-', item['title'].lower())[:40]
            if get_item(identifier).exists:
                identifier += f"_{int(time.time())%10000}"
            
            files_to_upload = [(video_file, {
                'title': item['title'],
                'creator': 'Telegram User',
                'collection': item['category']
            })]
            
            metadata = {
                'title': item['title'],
                'description': f"Terabox-Archive Bot | {item['category']}",
                'collection': item['category'],
                'mediatype': 'movies'
            }
            
            res = upload(identifier, files_to_upload, metadata=metadata, verbose=False)
            
            if res['status'] == 'ok':
                ia_url = f"https://archive.org/details/{identifier}"
                status = f"✅ {current}/{total} DONE!
{ia_url}"
                await send_status(item['chat_id'], status)
            else:
                raise Exception("Upload failed")
                
        except Exception as e:
            await send_status(item['chat_id'], f"❌ {current}/{total} Error: {str(e)[:100]}")
        
        finally:
            if video_file and os.path.exists(video_file):
                os.remove(video_file)
        
        await asyncio.sleep(45)
    
    processing = False

def main():
    global app
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('queue', queue_command))
    print("🚀 Bot LIVE!")
    app.run_polling()

if __name__ == '__main__':
    main()
