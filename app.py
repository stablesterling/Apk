import os
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import json

# --- DATABASE SETUP ---
DB_URL = "postgresql://vofodb_user:Y7MQfAWwEtsiHQLiGHFV7ikOI2ruTv3u@dpg-d5lm4ongi27c7390kq40-a/vofodb"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELS ---
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

app.add_middleware(CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"],
    allow_credentials=True
)

# --- AUTH HELPERS ---
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

# --- SIMPLE MUSIC DATA (No ytmusicapi for now) ---
MOCK_TRENDING = [
    {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "artist": "Rick Astley", "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
    {"id": "9bZkp7q19f0", "title": "Gangnam Style", "artist": "PSY", "thumbnail": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg"},
    {"id": "kffacxfA7G4", "title": "Baby", "artist": "Justin Bieber", "thumbnail": "https://i.ytimg.com/vi/kffacxfA7G4/hqdefault.jpg"},
    {"id": "JGwWNGJdvx8", "title": "Shape of You", "artist": "Ed Sheeran", "thumbnail": "https://i.ytimg.com/vi/JGwWNGJdvx8/hqdefault.jpg"},
    {"id": "nfs8NYg7yQM", "title": "Blinding Lights", "artist": "The Weeknd", "thumbnail": "https://i.ytimg.com/vi/nfs8NYg7yQM/hqdefault.jpg"},
]

# --- AUTH ROUTES ---
@app.post("/api/register")
async def register(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        user = User(username=username, password=hash_password(password))
        db.add(user)
        db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/login")
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        username = data.get('username')
        password = data.get('password')
        
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"success": True, "user_id": user.id, "username": user.username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- LIKES ROUTES ---
@app.post("/api/like")
async def toggle_like(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        
        existing = db.query(LikedSong).filter(
            LikedSong.user_id == data['user_id'], 
            LikedSong.song_id == data['song_id']
        ).first()
        
        if existing:
            db.delete(existing)
            db.commit()
            return {"status": "unliked"}
        
        new_like = LikedSong(
            user_id=data['user_id'], 
            song_id=data['song_id'], 
            title=data['title'], 
            artist=data['artist'], 
            thumbnail=data['thumbnail']
        )
        db.add(new_like)
        db.commit()
        return {"status": "liked"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/liked/{user_id}")
async def get_liked(user_id: int, db: Session = Depends(get_db)):
    likes = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
    return [{"id": l.song_id, "title": l.title, "artist": l.artist, "thumbnail": l.thumbnail} for l in likes]

# --- MUSIC ROUTES ---
@app.get("/api/trending")
async def trending():
    return MOCK_TRENDING

@app.get("/api/search")
async def search(q: str):
    # Simple mock search
    results = []
    for song in MOCK_TRENDING:
        if q.lower() in song['title'].lower() or q.lower() in song['artist'].lower():
            results.append(song)
    return results[:10]

@app.get("/")
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/manifest.json")
async def manifest():
    manifest_data = {
        "name": "VoFo Music",
        "short_name": "VoFo",
        "description": "Immersive Music Experience",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0d0d0d",
        "theme_color": "#c5a367",
        "orientation": "portrait",
        "icons": [
            {
                "src": "https://via.placeholder.com/192x192/c5a367/0d0d0d?text=VF",
                "sizes": "192x192",
                "type": "image/png"
            }
        ]
    }
    return JSONResponse(content=manifest_data)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "VoFo Music API is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
