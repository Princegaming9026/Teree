import os
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

configure(IA_EMAIL, IA_KEY, IA_SECRET)
upload_queue = deque()
app = None

def send_status(chat_id, message):
    try:
        asyncio.create_task(app.bot.send_message(chat_id=chat_id, text=message))
    except:
        pass

async def start(update, context):
    await update.message.reply_text("Terabox Archive Bot. Send: link | title | category")

async def queue_command(update, context):
    global app
    text = ' '.join(context.args)
    
    if not text:
        await update.message.reply_text("Send /queue with links")
        return
    
    lines = text.split('
')
    queued = 0
    
    for i, line in enumerate(lines):
        line = line.strip()
        if 'terabox' in line and '|' in line:
            parts = [p.strip() for p in line.split('|')]
            queue_item = {
                'link': parts[0],
                'title': parts[1] if len(parts) > 1 else f'Untitled_{i}',
                'category': parts[2] if len(parts) > 2 else 'data',
                'chat_id': update.effective_chat.id
            }
            upload_queue.append(queue_item)
            queued += 1
    
    await update.message.reply_text(f"Queued {queued} links")
    process_queue()

def process_queue():
    total = len(upload_queue)
    current = 0
    
    while upload_queue:
        current += 1
        item = upload_queue.popleft()
        video_file = None
        
        try:
            unique_id = f"tba_{int(time.time())}_{random.randint(1000,9999)}"
            ydl_opts = {'outtmpl': f'{unique_id}.%(ext)s'}
            
            send_status(item['chat_id'], f"{current}/{total}: Downloading {item['title']}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item['link']])
            
            files = [f for f in os.listdir('.') if f.startswith(unique_id)]
            if files:
                video_file = files[0]
                
                send_status(item['chat_id'], f"{current}/{total}: Uploading")
                
                identifier = re.sub(r'[^a-z0-9]', '-', item['title'].lower())[:40]
                files_to_upload = [(video_file, {'title': item['title']})]
                metadata = {'title': item['title'], 'mediatype': 'movies'}
                
                res = upload(identifier, files_to_upload, metadata=metadata)
                
                if res['status'] == 'ok':
                    url = f"https://archive.org/details/{identifier}"
                    send_status(item['chat_id'], f"DONE: {url}")
            
        except Exception as e:
            send_status(item['chat_id'], f"Error: {str(e)}")
        
        finally:
            if video_file and os.path.exists(video_file):
                os.remove(video_file)
        
        time.sleep(30)

async def handle_message(update, context):
    text = update.message.text
    if 'terabox' in text and '|' in text:
        parts = [p.strip() for p in text.split('|')]
        queue_item = {
            'link': parts[0],
            'title': parts[1] if len(parts) > 1 else 'Untitled',
            'category': parts[2] if len(parts) > 2 else 'data',
            'chat_id': update.effective_chat.id
        }
        upload_queue.append(queue_item)
        await update.message.reply_text("Added to queue")
        process_queue()

def main():
    global app
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('queue', queue_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    print("Bot started")
    app.run_polling()

if __name__ == '__main__':
    main()
