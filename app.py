import os
import bcrypt
import uvicorn
import sqlite3
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import contextmanager
from datetime import datetime

app = FastAPI(title="VoFo Music")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
DB_FILE = "vofo.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Liked songs table
    c.execute('''CREATE TABLE IF NOT EXISTS liked_songs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  song_id TEXT,
                  title TEXT,
                  artist TEXT,
                  thumbnail TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(user_id, song_id))''')
    
    conn.commit()
    conn.close()

# Initialize DB
init_db()

# DB helper
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Password
def hash_pw(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_pw(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# Mock songs
SONGS = [
    {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "artist": "Rick Astley", "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
    {"id": "9bZkp7q19f0", "title": "Gangnam Style", "artist": "PSY", "thumbnail": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg"},
    {"id": "kffacxfA7G4", "title": "Baby", "artist": "Justin Bieber", "thumbnail": "https://i.ytimg.com/vi/kffacxfA7G4/hqdefault.jpg"},
]

# Routes
@app.get("/")
async def home():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name": "VoFo",
        "short_name": "VoFo",
        "start_url": "/",
        "display": "standalone",
        "theme_color": "#c5a367"
    })

@app.post("/api/register")
async def register(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(400, "Need username and password")
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if exists
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        raise HTTPException(400, "User exists")
    
    # Create user
    hashed = hash_pw(password)
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "user_id": user_id, "username": username}

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    
    if not user or not check_pw(password, user["password"]):
        raise HTTPException(401, "Bad login")
    
    return {"success": True, "user_id": user["id"], "username": username}

@app.post("/api/like")
async def like(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    song_id = data.get("song_id")
    
    if not user_id or not song_id:
        raise HTTPException(400, "Need user_id and song_id")
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if liked
    c.execute("SELECT id FROM liked_songs WHERE user_id = ? AND song_id = ?", (user_id, song_id))
    existing = c.fetchone()
    
    if existing:
        c.execute("DELETE FROM liked_songs WHERE id = ?", (existing["id"],))
        status = "unliked"
    else:
        c.execute("""INSERT INTO liked_songs (user_id, song_id, title, artist, thumbnail) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (user_id, song_id, data.get("title", ""), data.get("artist", ""), data.get("thumbnail", "")))
        status = "liked"
    
    conn.commit()
    conn.close()
    
    return {"status": status}

@app.get("/api/liked/{user_id}")
async def liked(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT song_id, title, artist, thumbnail FROM liked_songs WHERE user_id = ? ORDER BY id DESC", (user_id,))
    songs = c.fetchall()
    conn.close()
    
    return [{"id": s["song_id"], "title": s["title"], "artist": s["artist"], "thumbnail": s["thumbnail"]} for s in songs]

@app.get("/api/trending")
async def trending():
    return SONGS

@app.get("/api/search")
async def search(q: str = ""):
    if not q:
        return SONGS
    
    q = q.lower()
    return [s for s in SONGS if q in s["title"].lower() or q in s["artist"].lower()]

@app.get("/health")
async def health():
    return {"status": "ok", "python": os.sys.version}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting on port {port}, Python {os.sys.version}")
    uvicorn.run(app, host="0.0.0.0", port=port)
