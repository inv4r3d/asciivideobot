import telebot
from flask import Flask, request
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import io
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Вставьте ваш токен от BotFather
TOKEN = '7034087598:AAHJosYC4uU5oSjT4c28xqn3DVeTNU2oFao'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Символы для ASCII-арта (от темного к светлому)
ASCII_CHARS = "@%#*+=-:. "

# Словарь для хранения file_id и настроек
file_storage = {}

# Функция для преобразования кадра в ASCII (цветной или монохромный)
def frame_to_ascii(frame, width=50, color=False):
    height = int((frame.shape[0] / frame.shape[1]) * width)
    small_frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    if color:
        ascii_frame = []
        for i in range(height):
            row = []
            for j in range(width):
                pixel = small_frame[i, j]  # BGR формат
                brightness = sum(pixel) / 3 / 255.0
                index = int(brightness * (len(ASCII_CHARS) - 1))
                row.append((ASCII_CHARS[index], tuple(pixel)))
            ascii_frame.append(row)
        return ascii_frame
    else:
        # Монохромный режим: только два цвета (черный и белый)
        ascii_frame = []
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)  # Преобразуем в градации серого
        normalized = gray / 255.0  # Нормализуем от 0 до 1
        for i in range(height):
            row = []
            for j in range(width):
                brightness = normalized[i, j]  # Яркость от 0 (черный) до 1 (белый)
                pixel_color = (255, 255, 255) if brightness > 0.5 else (0, 0, 0)
                index = int(brightness * (len(ASCII_CHARS) - 1))
                row.append((ASCII_CHARS[index], pixel_color))
            ascii_frame.append(row)
        return ascii_frame

# Функция для создания изображения из ASCII
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
        img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))  # Черный фон для "цветного"
        d = ImageDraw.Draw(img)
        for i, row in enumerate(ascii_data):
            for j, (char, pixel_color) in enumerate(row):
                rgb_color = (int(pixel_color[2]), int(pixel_color[1]), int(pixel_color[0]))
                d.text((j * char_width, i * char_height), char, font=font, fill=rgb_color)
        return img
    else:
        height = len(ascii_data)
        img_width = width * char_width
        img_height = height * char_height
        img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))  # Белый фон
        d = ImageDraw.Draw(img)
        for i, row in enumerate(ascii_data):
            for j, (char, pixel_color) in enumerate(row):
                rgb_color = (int(pixel_color[0]), int(pixel_color[1]), int(pixel_color[2]))
                d.text((j * char_width, i * char_height), char, font=font, fill=rgb_color)
        return img

# Функция для создания видео из ASCII с сохранением пропорций
def video_to_ascii(input_path, output_path, color=False, symbol_size="small", max_duration=10):
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return False, "Не удалось открыть файл"
    
    fps = cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 24
    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    width = 50 if symbol_size == "small" else 25
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
    out_width = base_width
    out_height = int(out_width * (orig_height / orig_width))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (out_width, out_height))
    
    frame_count = 0
    max_frames = int(fps * max_duration)
    
    while cap.isOpened() and frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        ascii_data = frame_to_ascii(frame, width, color)
        img = ascii_to_image(ascii_data, width, color, symbol_size)
        img_resized = img.resize((out_width, out_height), Image.Resampling.LANCZOS)
        frame_out = np.array(img_resized)
        out.write(frame_out)
        frame_count += 1
    
    cap.release()
    out.release()
    
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if file_size_mb > 50:
        os.remove(output_path)
        return False, "Файл слишком большой (>50 МБ)"
    return True, None

# Функция для обработки фото с сохранением исходного размера
def process_photo(image, color=False, symbol_size="small"):
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    orig_width, orig_height = image.size
    
    width = 50 if symbol_size == "small" else 25
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
    ascii_img_resized = ascii_img.resize((orig_width, orig_height), Image.Resampling.LANCZOS)
    
    return ascii_img_resized

# Создание клавиатуры для выбора стиля
def get_style_keyboard(message_id, content_type):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Цветное", callback_data=f"color_{content_type}_{message_id}"),
        InlineKeyboardButton("Монохромное", callback_data=f"mono_{content_type}_{message_id}")
    )
    return keyboard

# Создание клавиатуры для выбора размера символов
def get_size_keyboard(message_id, content_type, color):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Мелкие символы", callback_data=f"small_{content_type}_{message_id}_{color}"),
        InlineKeyboardButton("Крупные символы", callback_data=f"large_{content_type}_{message_id}_{color}")
    )
    return keyboard

# Обработчики сообщений
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне фото, видео или GIF для обработки в ASCII.")

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

# Обработчик выбора стиля и размера
@bot.callback_query_handler(func=lambda call: True)
def handle_choice(call):
    try:
        data = call.data.split('_')
        if len(data) == 3:  # Выбор стиля
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
        
        elif len(data) == 4:  # Выбор размера
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
                    with open(output_path, 'rb') as video:
                        bot.send_video(call.message.chat.id, video)
                    os.remove(input_path)
                    os.remove(output_path)
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
        bot.send_message(call.message.chat.id, f"Произошла ошибка: {str(e)}")

# Webhook маршруты для Flask
@app.route('/' + TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://asciivideobot.onrender.com/' + TOKEN)
    return "Webhook set", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))