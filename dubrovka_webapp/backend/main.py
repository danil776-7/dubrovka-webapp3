from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timedelta
import requests
import os
import threading
import time

# =====================
# APP
# =====================

app = FastAPI()

# CORS - разрешаем все источники для теста
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# DATABASE
# =====================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found!")
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/railway"

# Фикс для Railway
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    name = Column(String(100))
    phone = Column(String(20))
    guests = Column(Integer)
    table = Column(String(10))
    date = Column(String(10))
    time = Column(String(5))
    status = Column(String(20), default="active")
    chat_id = Column(String(50), nullable=True)
    created_at = Column(String(50), nullable=True)

# Создаем таблицы
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
except Exception as e:
    print(f"❌ Error creating tables: {e}")

# =====================
# CONFIG
# =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8769949339:AAFwvdkPFgj7l4BQwGfmcljauMWXRx7qves")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "7545540622")
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
    if not chat_id or chat_id == "" or chat_id == "0" or chat_id == "None":
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def send_telegram_to_admin(text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=5
        )
        if response.status_code == 200:
            print("✅ Уведомление отправлено админу")
    except Exception as e:
        print("❌ Ошибка:", e)

def send_booking_confirmation(booking):
    message = (
        f"✅ <b>БРОНЬ ПОДТВЕРЖДЕНА!</b>\n\n"
        f"🆔 <b>ID брони:</b> {booking.id}\n"
        f"👤 <b>Имя:</b> {booking.name}\n"
        f"🪑 <b>Стол:</b> {booking.table}\n"
        f"👥 <b>Гостей:</b> {booking.guests}\n"
        f"📅 <b>Дата:</b> {booking.date}\n"
        f"⏰ <b>Время:</b> {booking.time}\n\n"
        f"📍 <b>Адрес:</b> Ермакова 11, Новокузнецк\n"
        f"📞 <b>Телефон:</b> +7‒913‒432‒01‒01\n\n"
        f"❤️ Ждем вас в Dubrovka!"
    )
    if booking.chat_id:
        send_telegram_to_user(booking.chat_id, message)

def send_reminder_to_guest(booking):
    message = (
        f"🔔 <b>НАПОМИНАНИЕ О БРОНИ!</b>\n\n"
        f"🪑 <b>Стол:</b> {booking.table}\n"
        f"📅 <b>Сегодня:</b> {booking.date}\n"
        f"⏰ <b>Через 30 минут:</b> {booking.time}\n\n"
        f"👤 <b>На имя:</b> {booking.name}\n"
        f"👥 <b>Гостей:</b> {booking.guests}\n\n"
        f"📍 <b>Ждем вас по адресу:</b> Ермакова 11\n"
        f"📞 <b>Телефон:</b> +7‒913‒432‒01‒01"
    )
    if booking.chat_id:
        send_telegram_to_user(booking.chat_id, message)

def send_thank_you_to_guest(booking):
    message = (
        f"🌟 <b>Спасибо, что посетили Dubrovka Lounge & Bar!</b> 🌟\n\n"
        f"👤 <b>{booking.name}</b>, мы благодарим вас за визит!\n\n"
        f"🍷 Надеемся, вам понравилась атмосфера, обслуживание и кухня.\n\n"
        f"📝 <b>Пожалуйста, оставьте отзыв о нашем заведении в 2ГИС</b>\n"
        f"🔗 <a href='{TWO_GIS_REVIEW_URL}'>Написать отзыв в 2ГИС</a>\n\n"
        f"❤️ Ждем вас снова!"
    )
    if booking.chat_id:
        send_telegram_to_user(booking.chat_id, message)
    else:
        send_telegram_to_admin(
            f"✅ <b>ГОСТЬ ПОСЕТИЛ (нет чата)</b>\n\n"
            f"👤 {booking.name}\n"
            f"📞 {booking.phone}\n"
            f"🪑 Стол {booking.table}\n"
            f"📅 {booking.date} {booking.time}\n\n"
            f"🔗 <b>Ссылка на отзыв:</b>\n{TWO_GIS_REVIEW_URL}"
        )

def schedule_reminder(booking):
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
            print(f"⏰ Напоминание запланировано на {reminder_time}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def schedule_auto_complete(booking):
    try:
        timer = threading.Timer(4 * 3600, auto_complete_booking, args=[booking.id])
        timer.daemon = True
        timer.start()
        completion_timers[booking.id] = timer
        print(f"🤖 Авто-завершение через 4 часа")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def auto_complete_booking(booking_id):
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
            send_thank_you_to_guest(booking)
        db.close()
    except Exception as e:
        print(f"Ошибка: {e}")
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
        print(f"❌ Ошибка: {e}")
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
        print(f"❌ Ошибка: {e}")
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
            chat_id=chat_id if chat_id and chat_id != "0" and chat_id != "None" else None,
            created_at=datetime.now().isoformat()
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        send_booking_confirmation(booking)
        schedule_reminder(booking)
        schedule_auto_complete(booking)

        print(f"✅ Новая бронь: ID={booking.id}")

        send_telegram_to_admin(
            f"🔥 <b>НОВАЯ БРОНЬ!</b>\n\n"
            f"🆔 ID: {booking.id}\n"
            f"👤 {data['name']}\n"
            f"📞 {data['phone']}\n"
            f"👥 {guests}\n"
            f"🪑 Стол {table}\n"
            f"📅 {date}\n"
            f"⏰ {time}"
        )

        return {"ok": True, "id": booking.id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
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

        if id in reminder_timers:
            reminder_timers[id].cancel()
            del reminder_timers[id]
        if id in completion_timers:
            completion_timers[id].cancel()
            del completion_timers[id]

        print(f"✅ Бронь {id} завершена")

        send_telegram_to_admin(
            f"✅ <b>ГОСТЬ УШЕЛ</b>\n\n"
            f"🆔 ID: {id}\n"
            f"👤 {booking.name}\n"
            f"📞 {booking.phone}\n"
            f"🪑 Стол {booking.table}\n"
            f"👥 {booking.guests}\n"
            f"📅 {booking.date}\n"
            f"⏰ {booking.time}"
        )
        
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

        if booking.chat_id:
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
