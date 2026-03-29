from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "database": "checking"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/bookings_by_date")
def bookings_by_date(date: str):
    return []

@app.get("/busy_times")
def busy_times(date: str, table: str):
    return []

@app.post("/booking")
def create_booking(data: dict):
    return {"ok": True, "id": 1, "message": "Test booking"}
