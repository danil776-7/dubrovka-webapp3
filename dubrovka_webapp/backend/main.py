from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import requests
import os
import threading
import time

# =====================
# DATABASE
# =====================

DATABASE_URL = "postgresql://postgres:YOhOreaGeQiTXNqnHsUACbozGqnVlQcb@postgres.railway.internal:5432/railway"

print(f"✅ Connecting to database...")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =====================
# MODEL
# =====================

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String)
    guests = Column(Integer)
    table = Column(String)
    date = Column(String)
    time = Column(String)
    status = Column(String, default="active")
    chat_id = Column(String, nullable=True)

# Создаем таблицы и проверяем наличие колонки chat_id
try:
    with engine.connect() as conn:
        try:
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='bookings' AND column_name='chat_id'
            """))
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN chat_id VARCHAR"))
                conn.commit()
                print("✅ Добавлена колонка chat_id")
            else:
                print("✅ Колонка chat_id уже существует")
        except Exception as e:
            print(f"⚠️ Ошибка при проверке колонки: {e}")
    
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
    raise

# =====================
# APP
# =====================

app = FastAPI()

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://danil776-7.github.io",
        "https://dani1776-7.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.options("/{path:path}")
async def options_handler(path: str):
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# =====================
# CONFIG
# =====================

TELEGRAM_BOT_TOKEN = "8769949339:AAFwvdkPFgj7l4BQwGfmcljauMWXRx7qves"
ADMIN_CHAT_ID = "7545540622"
TWO_GIS_REVIEW_URL = "https://2gis.ru/novokuznetsk/review/70000001067987554"

print(f"✅ Telegram configured")

# =====================
# LIMITS
# =====================

TABLE_LIMITS = {
    "1": 7,
    "2": 5,
    "3": 5,
    "4": 5,
    "5": 5,
    "6": 3,
    "VIP": 20
}

# =====================
# ХРАНИЛИЩЕ ДЛЯ ТАЙМЕРОВ
# =====================

reminder_timers = {}
completion_timers = {}

# =====================
# ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ
# =====================

def send_telegram_to_user(chat_id, text):
    """Отправка сообщения пользователю (гостю)"""
    if not chat_id or chat_id == "" or chat_id == "0" or chat_id == "None":
        print(f"⚠️ Нет chat_id, сообщение не отправлено")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Сообщение отправлено гостю {chat_id}")
            return True
        else:
            print(f"❌ Ошибка отправки гостю: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def send_telegram_to_admin(text):
    """Отправка уведомления админу"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=5
        )
        if response.status_code == 200:
            print("✅ Уведомление отправлено админу")
    except Exception as e:
        print("❌ Ошибка:", e)

def send_booking_confirmation(booking):
    """Подтверждение брони гостю"""
    message = (
        f"✅ <b>БРОНЬ ПОДТВЕРЖДЕНА!</b>\n\n"
        f"🆔 <b>ID брони:</b> {booking.id}\n"
        f"👤 <b>Имя:</b> {booking.name}\n"
        f"🪑 <b>Стол:</b> {booking.table}\n"
        f"👥 <b>Гостей:</b> {booking.guests}\n"
        f"📅 <b>Дата:</b> {booking.date}\n"
        f"⏰ <b>Время:</b> {booking.time}\n\n"
        f"🔔 <b>Напоминание:</b> Мы пришлем уведомление за 30 минут до брони.\n\n"
        f"📍 <b>Адрес:</b> Ермакова 11, Новокузнецк\n"
        f"📞 <b>Телефон:</b> +7‒913‒432‒01‒01\n\n"
        f"❤️ Ждем вас в Dubrovka!"
    )
    if booking.chat_id and booking.chat_id != "" and booking.chat_id != "0" and booking.chat_id != "None":
        send_telegram_to_user(booking.chat_id, message)
        print(f"📱 Подтверждение отправлено гостю {booking.name}")
    else:
        print(f"⚠️ У гостя {booking.name} нет chat_id, подтверждение не отправлено")

def send_reminder_to_guest(booking):
    """Напоминание гостю за 30 минут"""
    message = (
        f"🔔 <b>НАПОМИНАНИЕ О БРОНИ!</b>\n\n"
        f"🪑 <b>Стол:</b> {booking.table}\n"
        f"📅 <b>Сегодня:</b> {booking.date}\n"
        f"⏰ <b>Через 30 минут:</b> {booking.time}\n\n"
        f"👤 <b>На имя:</b> {booking.name}\n"
        f"👥 <b>Гостей:</b> {booking.guests}\n\n"
        f"📍 <b>Ждем вас по адресу:</b> Ермакова 11\n"
        f"📞 <b>По вопросам:</b> +7‒913‒432‒01‒01\n\n"
        f"🌟 Пожалуйста, не опаздывайте!"
    )
    if booking.chat_id and booking.chat_id != "" and booking.chat_id != "0" and booking.chat_id != "None":
        send_telegram_to_user(booking.chat_id, message)
        print(f"⏰ Напоминание отправлено гостю {booking.name} для брони {booking.id}")
    else:
        # Если нет chat_id, отправляем админу напоминание что нужно позвонить
        send_telegram_to_admin(
            f"🔔 <b>НАПОМИНАНИЕ (позвонить гостю)</b>\n\n"
            f"🪑 Стол {booking.table}\n"
            f"👤 {booking.name}\n"
            f"📞 {booking.phone}\n"
            f"📅 {booking.date} {booking.time}"
        )

def send_thank_you_to_guest(booking):
    """Благодарность гостю после посещения"""
    message = (
        f"🌟 <b>Спасибо, что посетили Dubrovka Lounge & Bar!</b> 🌟\n\n"
        f"👤 <b>{booking.name}</b>, мы благодарим вас за визит!\n\n"
        f"🍷 Надеемся, вам понравилась атмосфера, обслуживание и кухня.\n\n"
        f"📝 <b>Пожалуйста, оставьте отзыв о нашем заведении в 2ГИС</b>\n"
        f"Ваше мнение очень важно для нас!\n\n"
        f"🔗 <a href='{TWO_GIS_REVIEW_URL}'>Написать отзыв в 2ГИС</a>\n\n"
        f"❤️ Ждем вас снова в Dubrovka!"
    )
    if booking.chat_id and booking.chat_id != "" and booking.chat_id != "0" and booking.chat_id != "None":
        send_telegram_to_user(booking.chat_id, message)
        print(f"📱 Благодарность отправлена гостю {booking.name}")
    else:
        # Если нет chat_id, отправляем админу ссылку для отзыва
        send_telegram_to_admin(
            f"✅ <b>ГОСТЬ ПОСЕТИЛ (нет чата)</b>\n\n"
            f"👤 {booking.name}\n"
            f"📞 {booking.phone}\n"
            f"🪑 Стол {booking.table}\n"
            f"📅 {booking.date} {booking.time}\n\n"
            f"🔗 <b>Ссылка на отзыв для гостя:</b>\n"
            f"{TWO_GIS_REVIEW_URL}"
        )

def schedule_reminder(booking):
    """Запланировать напоминание за 30 минут"""
    try:
        booking_datetime = datetime.strptime(f"{booking.date} {booking.time}", "%Y-%m-%d %H:%M")
        reminder_time = booking_datetime - timedelta(minutes=30)
        now = datetime.now()
        
        if reminder_time > now:
            delay = (reminder_time - now).total_seconds()
            timer = threading.Timer(delay, send_reminder_to_guest, args=[booking])
            timer.daemon = True
            timer.start()
            reminder_timers[booking.id] = timer
            print(f"⏰ Напоминание запланировано на {reminder_time} для брони {booking.id}")
        else:
            print(f"⚠️ Время напоминания уже прошло для брони {booking.id}")
    except Exception as e:
        print(f"❌ Ошибка планирования: {e}")

def schedule_auto_complete(booking):
    """Запланировать автоматическое завершение через 4 часа"""
    try:
        timer = threading.Timer(4 * 3600, auto_complete_booking, args=[booking.id])
        timer.daemon = True
        timer.start()
        completion_timers[booking.id] = timer
        print(f"🤖 Авто-завершение через 4 часа для брони {booking.id}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def auto_complete_booking(booking_id):
    """Автоматическое завершение брони через 4 часа"""
    try:
        time.sleep(4 * 3600)
        db = SessionLocal()
        booking = db.query(Booking).filter(
            Booking.id == booking_id,
            Booking.status == "active"
        ).first()
        
        if booking:
            booking.status = "completed"
            db.commit()
            print(f"🤖 Авто-завершение брони {booking_id}")
            
            send_telegram_to_admin(
                f"🤖 <b>АВТО-ЗАВЕРШЕНИЕ</b>\n\n"
                f"🆔 ID: {booking_id}\n"
                f"👤 {booking.name}\n"
                f"📞 {booking.phone}\n"
                f"🪑 Стол {booking.table}\n"
                f"📅 {booking.date} {booking.time}"
            )
            
            # Отправляем благодарность гостю
            send_thank_you_to_guest(booking)
            
        db.close()
    except Exception as e:
        print(f"Ошибка авто-завершения: {e}")
    finally:
        if booking_id in completion_timers:
            del completion_timers[booking_id]

# =====================
# HELPERS
# =====================

def normalize_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Invalid date")

# =====================
# ЭНДПОИНТЫ
# =====================

@app.get("/")
def root():
    return {"status": "ok", "database": "connected"}

@app.get("/health")
def health():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/bookings_by_date")
def bookings_by_date(date: str):
    db = SessionLocal()
    try:
        print(f"📅 Запрос броней на дату: {date}")
        date = normalize_date(date)
        data = db.query(Booking).filter(
            Booking.date == date,
            Booking.status == "active"
        ).all()
        print(f"✅ Найдено броней: {len(data)}")
        return [
            {
                "id": b.id,
                "name": b.name,
                "phone": b.phone,
                "guests": b.guests,
                "table": b.table,
                "date": b.date,
                "time": b.time,
                "status": b.status
            }
            for b in data
        ]
    except Exception as e:
        print(f"❌ Ошибка в bookings_by_date: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/busy_times")
def busy_times(date: str, table: str):
    db = SessionLocal()
    try:
        date = normalize_date(date)
        data = db.query(Booking).filter(
            Booking.date == date,
            Booking.table == table,
            Booking.status == "active"
        ).all()
        return [b.time for b in data]
    except Exception as e:
        print(f"❌ Ошибка в busy_times: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/booking")
def create_booking(data: dict):
    db = SessionLocal()
    try:
        print(f"📝 Создание брони: {data}")
        
        required = ["name", "phone", "guests", "table", "date", "time"]
        for field in required:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing field: {field}")

        date = normalize_date(data["date"])
        table = str(data["table"])
        time = data["time"]
        guests = int(data["guests"])
        chat_id = str(data.get("chat_id", ""))

        if table not in TABLE_LIMITS:
            raise HTTPException(status_code=400, detail=f"Table {table} does not exist")

        if guests > TABLE_LIMITS[table]:
            raise HTTPException(
                status_code=400, 
                detail=f"Too many guests. Max for table {table} is {TABLE_LIMITS[table]}"
            )

        exists = db.query(Booking).filter(
            Booking.date == date,
            Booking.time == time,
            Booking.table == table,
            Booking.status == "active"
        ).first()

        if exists:
            raise HTTPException(status_code=409, detail="Time slot already booked")

        booking = Booking(
            name=data["name"],
            phone=data["phone"],
            guests=guests,
            table=table,
            date=date,
            time=time,
            status="active",
            chat_id=chat_id if chat_id and chat_id != "0" and chat_id != "None" else None
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        # 🔥 Отправляем подтверждение брони гостю
        send_booking_confirmation(booking)
        
        # 🔥 Планируем напоминание за 30 минут
        schedule_reminder(booking)
        
        # Планируем авто-завершение через 4 часа
        schedule_auto_complete(booking)

        print(f"✅ Новая бронь: ID={booking.id}")

        # Отправляем уведомление админу
        send_telegram_to_admin(
            f"🔥 <b>НОВАЯ БРОНЬ!</b>\n\n"
            f"🆔 <b>ID:</b> {booking.id}\n"
            f"👤 <b>Имя:</b> {data['name']}\n"
            f"📞 <b>Телефон:</b> {data['phone']}\n"
            f"👥 <b>Гостей:</b> {guests}\n"
            f"🪑 <b>Стол:</b> {table}\n"
            f"📅 <b>Дата:</b> {date}\n"
            f"⏰ <b>Время:</b> {time}\n"
            f"📱 <b>Telegram ID:</b> {chat_id if chat_id and chat_id != '0' else 'нет'}"
        )

        return {"ok": True, "id": booking.id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка создания брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/done/{id}")
def done(id: int):
    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(
            Booking.id == id,
            Booking.status == "active"
        ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Active booking not found")

        booking.status = "completed"
        db.commit()

        # Останавливаем таймеры
        if id in reminder_timers:
            reminder_timers[id].cancel()
            del reminder_timers[id]
        if id in completion_timers:
            completion_timers[id].cancel()
            del completion_timers[id]

        print(f"✅ Бронь {id} завершена")

        # Отправляем уведомление админу
        send_telegram_to_admin(
            f"✅ <b>ГОСТЬ УШЕЛ</b>\n\n"
            f"🆔 <b>ID:</b> {id}\n"
            f"👤 <b>Имя:</b> {booking.name}\n"
            f"📞 <b>Телефон:</b> {booking.phone}\n"
            f"🪑 <b>Стол:</b> {booking.table}\n"
            f"👥 <b>Гостей:</b> {booking.guests}\n"
            f"📅 <b>Дата:</b> {booking.date}\n"
            f"⏰ <b>Время:</b> {booking.time}"
        )
        
        # 🔥 Отправляем благодарность гостю со ссылкой на отзыв
        send_thank_you_to_guest(booking)

        return {"ok": True, "message": "Booking completed"}

    except HTTPException:
        raise
    finally:
        db.close()

@app.post("/cancel/{id}")
def cancel(id: int):
    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(
            Booking.id == id,
            Booking.status == "active"
        ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Active booking not found")

        booking.status = "cancelled"
        db.commit()

        if id in reminder_timers:
            reminder_timers[id].cancel()
            del reminder_timers[id]
        if id in completion_timers:
            completion_timers[id].cancel()
            del completion_timers[id]

        print(f"❌ Бронь {id} отменена")

        send_telegram_to_admin(
            f"❌ <b>БРОНЬ ОТМЕНЕНА</b>\n\n"
            f"🆔 ID: {id}\n"
            f"👤 {booking.name}\n"
            f"📞 {booking.phone}\n"
            f"🪑 Стол {booking.table}\n"
            f"📅 {booking.date} {booking.time}"
        )
        
        # Уведомляем гостя об отмене
        if booking.chat_id and booking.chat_id != "" and booking.chat_id != "0" and booking.chat_id != "None":
            cancel_message = (
                f"❌ <b>Бронь отменена</b>\n\n"
                f"Уважаемый(ая) {booking.name},\n\n"
                f"Ваша бронь в Dubrovka на {booking.date} {booking.time} (стол {booking.table}) была отменена администратором.\n\n"
                f"Если у вас есть вопросы, звоните: 📞 +7‒913‒432‒01‒01"
            )
            send_telegram_to_user(booking.chat_id, cancel_message)

        return {"ok": True, "message": "Booking cancelled"}

    except HTTPException:
        raise
    finally:
        db.close()

@app.get("/all_bookings")
def all_bookings():
    db = SessionLocal()
    try:
        data = db.query(Booking).all()
        return [
            {
                "id": b.id,
                "name": b.name,
                "phone": b.phone,
                "guests": b.guests,
                "table": b.table,
                "date": b.date,
                "time": b.time,
                "status": b.status
            }
            for b in data
        ]
    finally:
        db.close()
