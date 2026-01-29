import os
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database
DB_URL = "postgresql://vofodb_user:Y7MQfAWwEtsiHQLiGHFV7ikOI2ruTv3u@dpg-d5lm4ongi27c7390kq40-a/vofodb"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

class LikedSong(Base):
    __tablename__ = "liked_songs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    song_id = Column(String)
    title = Column(String)
    artist = Column(String)
    thumbnail = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# Routes
@app.get("/")
async def home():
    with open("index.html", "r") as f:
        return HTMLResponse(f.read())

@app.get("/manifest.json")
async def get_manifest():
    return JSONResponse({
        "name": "VoFo Music",
        "short_name": "VoFo",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0d0d0d",
        "theme_color": "#c5a367"
    })

@app.post("/api/register")
async def register(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        raise HTTPException(400, "Missing username or password")
    
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username exists")
    
    user = User(username=username, password=hash_password(password))
    db.add(user)
    db.commit()
    return {"success": True}

@app.post("/api/login")
async def login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(401, "Invalid credentials")
    
    return {"success": True, "user_id": user.id, "username": user.username}

@app.post("/api/like")
async def like_song(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    existing = db.query(LikedSong).filter(
        LikedSong.user_id == data["user_id"],
        LikedSong.song_id == data["song_id"]
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unliked"}
    
    song = LikedSong(
        user_id=data["user_id"],
        song_id=data["song_id"],
        title=data.get("title", ""),
        artist=data.get("artist", ""),
        thumbnail=data.get("thumbnail", "")
    )
    db.add(song)
    db.commit()
    return {"status": "liked"}

@app.get("/api/liked/{user_id}")
async def get_liked(user_id: int, db: Session = Depends(get_db)):
    songs = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
    return [{"id": s.song_id, "title": s.title, "artist": s.artist, "thumbnail": s.thumbnail} for s in songs]

@app.get("/api/trending")
async def trending():
    return [
        {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "artist": "Rick Astley", "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
        {"id": "9bZkp7q19f0", "title": "Gangnam Style", "artist": "PSY", "thumbnail": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg"},
    ]

@app.get("/api/search")
async def search(q: str = ""):
    songs = [
        {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "artist": "Rick Astley", "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
        {"id": "9bZkp7q19f0", "title": "Gangnam Style", "artist": "PSY", "thumbnail": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg"},
        {"id": "kffacxfA7G4", "title": "Baby", "artist": "Justin Bieber", "thumbnail": "https://i.ytimg.com/vi/kffacxfA7G4/hqdefault.jpg"},
    ]
    if not q:
        return songs
    
    return [s for s in songs if q.lower() in s["title"].lower() or q.lower() in s["artist"].lower()]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
