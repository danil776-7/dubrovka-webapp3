from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import requests
import os
import threading
import time

# =====================
# DATABASE
# =====================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is required in Railway")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =====================
# TELEGRAM
# =====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    print("⚠️ TELEGRAM_BOT_TOKEN not set")

# =====================
# MODEL
# =====================

class BookingDB(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    phone = Column(String)
    guests = Column(Integer)
    table = Column(String)
    date = Column(String)
    time = Column(String)
    chat_id = Column(String)

Base.metadata.create_all(bind=engine)

# =====================
# APP
# =====================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# HELPERS
# =====================

def send_telegram(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text
        })
    except Exception as e:
        print("Telegram error:", e)


def schedule_reminder(chat_id, text, delay):
    def task():
        time.sleep(delay)
        send_telegram(chat_id, text)

    threading.Thread(target=task).start()

# =====================
# ROUTES
# =====================

@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/busy_times")
def busy_times(date: str, table: str):
    db = SessionLocal()
    
    bookings = db.query(BookingDB).filter(
        BookingDB.date == date,
        BookingDB.table == table
    ).all()
    
    db.close()
    
    return [b.time for b in bookings]


@app.post("/booking")
def create_booking(data: dict):
    db = SessionLocal()

    # проверка занятости
    existing = db.query(BookingDB).filter(
        BookingDB.date == data["date"],
        BookingDB.table == data["table"],
        BookingDB.time == data["time"]
    ).first()

    if existing:
        db.close()
        return {"error": "busy"}

    booking = BookingDB(
        name=data["name"],
        phone=data["phone"],
        guests=data["guests"],
        table=data["table"],
        date=data["date"],
        time=data["time"],
        chat_id=str(data.get("chat_id"))
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)
    db.close()

    # =====================
    # TELEGRAM УВЕДОМЛЕНИЯ
    # =====================

    text = (
        f"📅 Новая бронь\n"
        f"👤 {booking.name}\n"
        f"📞 {booking.phone}\n"
        f"👥 {booking.guests}\n"
        f"🪑 Стол {booking.table}\n"
        f"📆 {booking.date} {booking.time}"
    )

    if ADMIN_CHAT_ID:
        send_telegram(ADMIN_CHAT_ID, text)

    if booking.chat_id:
        send_telegram(booking.chat_id, "✅ Ваша бронь подтверждена!")

        # напоминание за 1 час (3600 сек)
        schedule_reminder(
            booking.chat_id,
            f"⏰ Напоминание: бронь в {booking.time}",
            3600
        )

    return {"ok": True, "id": booking.id}


# =====================
# START (ВАЖНО ДЛЯ RAILWAY)
# =====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Server running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
