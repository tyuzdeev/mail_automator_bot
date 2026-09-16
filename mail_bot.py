import time
import threading
import os
import hashlib
import telebot
from imap_tools import MailBox, AND

# --- Настройки ---
IMAP_SERVER = "imap.mail.ru"  
EMAIL_LOGIN = "YOUR_EMAIL@bk.ru" # Вставь свою почту
EMAIL_PASSWORD = "YOUR_APP_PASSWORD" # Пароль для внешних приложений

TARGET_SENDERS = ["target_1@mail.ru", "target_2@gmail.com"] # От кого ждем письма
TG_TOKEN = "YOUR_BOT_TOKEN_HERE"
TG_CHAT_ID = "YOUR_CHAT_ID" 

HISTORY_FILE = "processed_hashes.txt"
bot = telebot.TeleBot(TG_TOKEN)


def is_already_processed(file_hash):
    # Проверяем, есть ли такой хэш в файле
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            # Читаем весь файл и ищем вхождение (простой и рабочий способ)
            text = f.read()
            if file_hash in text:
                return True
    return False

def save_processed_hash(file_hash):
    # Записываем хэш в файл с новой строки, чтобы не отправить дубликат потом
    with open(HISTORY_FILE, "a") as f:
        f.write(file_hash + "\n")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Бот на связи! Мониторинг почты запущен 🤖")

def check_email_loop():
    print("Начинаю мониторить почту...")
    while True:
        try:
            with MailBox(IMAP_SERVER).login(EMAIL_LOGIN, EMAIL_PASSWORD) as mailbox:
                # Ищем только непрочитанные
                for msg in mailbox.fetch(AND(seen=False)):
                    sender_email = msg.from_.lower()
                    
                    if any(target in sender_email for target in TARGET_SENDERS):
                        for att in msg.attachments:
                            if att.filename.lower().endswith('.pdf'):
                                # Создаем уникальный отпечаток файла
                                data_to_hash = sender_email.encode() + att.payload
                                file_signature = hashlib.md5(data_to_hash).hexdigest()
                                
                                # Если файл уже есть в истории — пропускаем
                                if is_already_processed(file_signature):
                                    try:
                                        if "target_1@mail.ru" in sender_email:
                                            mailbox.move(msg.uid, "Нужная_папка")
                                        else:
                                            mailbox.flag(msg.uid, '\\Seen', True)
                                    except:
                                        pass
                                    continue
                                
                                print(f"Найден новый PDF от {msg.from_}: {att.filename}. Отправляю...")
                                
                                # 1. Отправляем в Телеграм
                                caption_text = f"📄 Письмо от {msg.from_}"
                                bot.send_document(
                                    chat_id=TG_CHAT_ID,
                                    document=(att.filename, att.payload),
                                    caption=caption_text
                                )
                                
                                # 2. Сохраняем хэш, чтобы больше не отправлять
                                save_processed_hash(file_signature)
                                
                                # 3. Наводим порядок на почте
                                try:
                                    if "target_1@mail.ru" in sender_email:
                                        mailbox.move(msg.uid, "Нужная_папка")
                                        print("✅ Отправлено в ТГ и перенесено в папку!")
                                    else:
                                        mailbox.flag(msg.uid, '\\Seen', True)
                                        print("✅ Отправлено в ТГ (письмо помечено прочитанным)!")
                                except Exception as e:
                                    print(f"⚠️ Ошибка обработки на сервере: {e}")
                                    mailbox.flag(msg.uid, '\\Seen', True)
                                    
        except Exception as e:
            print(f"⚠️ Ошибка проверки почты: {e}")
        
        # Ждем 5 секунд перед следующей проверкой
        time.sleep(5)


if __name__ == "__main__":
    # Запускаем проверку почты в отдельном потоке, чтобы бот не зависал
    email_thread = threading.Thread(target=check_email_loop)
    email_thread.daemon = True
    email_thread.start()
    
    print("🤖 Бот запущен!")
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=60)
        except Exception as e:
            time.sleep(5)
