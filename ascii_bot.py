import telebot
from flask import Flask, request
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import io
import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

TOKEN = '7034087598:AAHJosYC4uU5oSjT4c28xqn3DVeTNU2oFao'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASCII_CHARS = "@%#&8BWMm0OZ$QUXYIlov1x[]{}()+=|;:,. "
file_storage = {}

def frame_to_ascii(frame, width=50, color=False):
    height = int((frame.shape[0] / frame.shape[1]) * width)
    small_frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    if color:
        small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)  # BGR в RGB
        ascii_frame = []
        for i in range(height):
            row = []
            for j in range(width):
                pixel = small_frame[i, j].astype(float)
                pixel = np.clip(pixel, 0, 255)
                brightness = sum(pixel) / 3 / 255.0
                index = int(brightness * (len(ASCII_CHARS) - 1))
                row.append((ASCII_CHARS[index], tuple(pixel)))
            ascii_frame.append(row)
        return ascii_frame
    else:
        ascii_frame = []
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        normalized = gray / 255.0
        for i in range(height):
            row = []
            for j in range(width):
                brightness = normalized[i, j]
                pixel_color = (255, 255, 255) if brightness > 0.5 else (0, 0, 0)
                index = int(brightness * (len(ASCII_CHARS) - 1))
                row.append((ASCII_CHARS[index], pixel_color))
            ascii_frame.append(row)
        return ascii_frame

def ascii_to_image(ascii_data, width=50, color=False, symbol_size="small"):
    font_size = 12 if symbol_size == "small" else 24
    try:
        font = ImageFont.truetype("cour.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    bbox = font.getbbox("A")
    char_width = bbox[2] - bbox[0]
    ascent, descent = font.getmetrics()
    char_height = ascent + descent
    
    if color:
        height = len(ascii_data)
        img_width = width * char_width
        img_height = height * char_height
        img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
        d = ImageDraw.Draw(img)
        for i, row in enumerate(ascii_data):
            for j, (char, pixel_color) in enumerate(row):
                rgb_color = (int(pixel_color[0]), int(pixel_color[1]), int(pixel_color[2]))
                d.text((j * char_width, i * char_height), char, font=font, fill=rgb_color)
        return img
    else:
        height = len(ascii_data)
        img_width = width * char_width
        img_height = height * char_height
        img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        for i, row in enumerate(ascii_data):
            for j, (char, pixel_color) in enumerate(row):
                rgb_color = (int(pixel_color[0]), int(pixel_color[1]), int(pixel_color[2]))
                d.text((j * char_width, i * char_height), char, font=font, fill=rgb_color)
        return img

def video_to_ascii(input_path, output_path, color=False, symbol_size="small", max_duration=5):
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return False, "Не удалось открыть файл"
    
    fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 24
    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    width = 60 if symbol_size == "small" else 30
    height = int((orig_height / orig_width) * width)
    
    font_size = 12 if symbol_size == "small" else 24
    try:
        font = ImageFont.truetype("cour.ttf", font_size)
    except:
        font = ImageFont.load_default()
    bbox = font.getbbox("A")
    char_width = bbox[2] - bbox[0]
    ascent, descent = font.getmetrics()
    char_height = ascent + descent
    
    base_width = width * char_width
    out_width = base_width * 2
    out_height = int(out_width * (orig_height / orig_width))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height))
    
    frame_count = 0
    max_frames = int(fps * max_duration)
    frame_skip = 0
    
    while cap.isOpened() and frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_skip += 1
        if frame_skip % 3 == 0:
            ascii_data = frame_to_ascii(frame, width, color)
            img = ascii_to_image(ascii_data, width, color, symbol_size)
            img_resized = img.resize((out_width, out_height), Image.Resampling.BILINEAR)
            frame_out = np.array(img_resized)
            out.write(frame_out)
            frame_count += 1
    
    cap.release()
    out.release()
    
    if not os.path.exists(output_path):
        return False, "Файл вывода не создан"
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Video size: {file_size_mb:.2f} MB")
    if file_size_mb > 50:
        os.remove(output_path)
        return False, "Файл слишком большой (>50 МБ)"
    return True, None

def process_photo(image, color=False, symbol_size="small"):
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    orig_width, orig_height = image.size
    
    width = 60 if symbol_size == "small" else 30
    height = int((orig_height / orig_width) * width)
    
    font_size = 12 if symbol_size == "small" else 24
    try:
        font = ImageFont.truetype("cour.ttf", font_size)
    except:
        font = ImageFont.load_default()
    bbox = font.getbbox("A")
    char_width = bbox[2] - bbox[0]
    ascent, descent = font.getmetrics()
    char_height = ascent + descent
    
    ascii_data = frame_to_ascii(frame, width, color)
    ascii_img = ascii_to_image(ascii_data, width, color, symbol_size)
    ascii_img_resized = ascii_img.resize((orig_width, orig_height), Image.Resampling.BILINEAR)
    
    return ascii_img_resized

def get_style_keyboard(message_id, content_type):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Цветное", callback_data=f"color_{content_type}_{message_id}"),
        InlineKeyboardButton("Монохромное", callback_data=f"mono_{content_type}_{message_id}")
    )
    return keyboard

def get_size_keyboard(message_id, content_type, color):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Мелкие символы", callback_data=f"small_{content_type}_{message_id}_{color}"),
        InlineKeyboardButton("Крупные символы", callback_data=f"large_{content_type}_{message_id}_{color}")
    )
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "Привет! Я преобразую фото, видео и GIF в ASCII-арт.\n\n"
        "Как использовать:\n"
        "1. Отправь мне медиа.\n"
        "2. Выбери стиль (цветной или монохромный).\n"
        "3. Выбери размер символов (мелкие или крупные).\n\n"
        "Ограничения:\n"
        "- Видео: до 5 секунд.\n"
        "- Максимальный размер файла: 50 МБ.\n"
        "- Возможны задержки из-за бесплатного хостинга."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    file_id = message.video.file_id
    file_storage[message.message_id] = {"file_id": file_id}
    bot.reply_to(message, "Выбери стиль ASCII:", reply_markup=get_style_keyboard(message.message_id, "video"))

@bot.message_handler(content_types=['animation'])
def handle_gif(message):
    file_id = message.animation.file_id
    file_storage[message.message_id] = {"file_id": file_id}
    bot.reply_to(message, "Выбери стиль ASCII:", reply_markup=get_style_keyboard(message.message_id, "animation"))

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id
    file_storage[message.message_id] = {"file_id": file_id}
    bot.reply_to(message, "Выбери стиль ASCII:", reply_markup=get_style_keyboard(message.message_id, "photo"))

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(Exception))
def send_video_with_retry(chat_id, video):
    logger.info(f"Sending video to chat_id={chat_id}")
    bot.send_video(chat_id, video)

@bot.callback_query_handler(func=lambda call: True)
def handle_choice(call):
    try:
        data = call.data.split('_')
        if len(data) == 3:
            style, content_type, message_id = data
            message_id = int(message_id)
            file_data = file_storage.get(message_id)
            if not file_data:
                bot.send_message(call.message.chat.id, "Ошибка: файл не найден.")
                return
            
            color = (style == "color")
            file_storage[message_id]["color"] = color
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                text="Выбери размер символов:", reply_markup=get_size_keyboard(message_id, content_type, color))
        
        elif len(data) == 4:
            symbol_size, content_type, message_id, color = data
            message_id = int(message_id)
            file_data = file_storage.get(message_id)
            if not file_data:
                bot.send_message(call.message.chat.id, "Ошибка: файл не найден.")
                return
            
            file_id = file_data["file_id"]
            color = (color == "True")
            
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            if content_type in ["video", "animation"]:
                input_path = f"input_{content_type}.mp4"
                with open(input_path, 'wb') as f:
                    f.write(downloaded_file)
                
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                    text=f"Обрабатываю {content_type}, подожди немного...")
                
                output_path = "output_ascii.mp4"
                success, error = video_to_ascii(input_path, output_path, color, symbol_size)
                
                if success:
                    if os.path.exists(output_path):
                        with open(output_path, 'rb') as video:
                            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                            if file_size_mb > 50:
                                bot.send_message(call.message.chat.id, "Ошибка: файл слишком большой (>50 МБ).")
                            else:
                                send_video_with_retry(call.message.chat.id, video)
                        os.remove(output_path)
                    else:
                        bot.send_message(call.message.chat.id, "Ошибка: файл вывода не найден.")
                    os.remove(input_path)
                else:
                    bot.send_message(call.message.chat.id, f"Ошибка: {error or 'не удалось обработать'}.")
            
            elif content_type == "photo":
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                    text="Обрабатываю фото, подожди немного...")
                
                img = Image.open(io.BytesIO(downloaded_file))
                ascii_img = process_photo(img, color=color, symbol_size=symbol_size)
                
                img_byte_arr = io.BytesIO()
                ascii_img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                file_size_mb = img_byte_arr.getbuffer().nbytes / (1024 * 1024)
                if file_size_mb > 50:
                    bot.send_message(call.message.chat.id, "Ошибка: фото слишком большое (>50 МБ).")
                else:
                    bot.send_photo(call.message.chat.id, img_byte_arr)
            
            if message_id in file_storage:
                del file_storage[message_id]
                
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        bot.send_message(call.message.chat.id, f"Произошла ошибка: {str(e)}")

@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    logger.info("Received POST from Telegram")
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def webhook():
    logger.info("Setting webhook")
    bot.remove_webhook()
    bot.set_webhook(url='https://asciivideobot.onrender.com/' + TOKEN)
    logger.info("Webhook set")
    return "Webhook set", 200

if __name__ == "__main__":
    logger.info("Starting Flask app")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))