import os
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from ytmusicapi import YTMusic
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

# Initialize YTMusic (anonymous)
yt = YTMusic()

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

# --- STATIC FILES ROUTES ---
@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("manifest.json")

# --- AUTH ROUTES ---
@app.post("/api/register")
async def register(username: str, password: str, db: Session = Depends(get_db)):
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(username=username, password=hash_password(password))
    db.add(user)
    db.commit()
    return {"success": True}

@app.post("/api/login")
async def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"success": True, "user_id": user.id, "username": user.username}

# --- LIKES ROUTES ---
@app.post("/api/like")
async def toggle_like(user_id: int, song_id: str, title: str, artist: str, thumbnail: str, db: Session = Depends(get_db)):
    existing = db.query(LikedSong).filter(
        LikedSong.user_id == user_id, 
        LikedSong.song_id == song_id
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unliked"}
    
    new_like = LikedSong(
        user_id=user_id, 
        song_id=song_id, 
        title=title, 
        artist=artist, 
        thumbnail=thumbnail
    )
    db.add(new_like)
    db.commit()
    return {"status": "liked"}

@app.get("/api/liked/{user_id}")
async def get_liked(user_id: int, db: Session = Depends(get_db)):
    likes = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
    return [{"id": l.song_id, "title": l.title, "artist": l.artist, "thumbnail": l.thumbnail} for l in likes]

# --- MUSIC ROUTES ---
@app.get("/api/trending")
async def trending():
    try:
        songs = yt.get_charts(country="IN")['songs']['items']
        result = []
        for s in songs[:15]:
            result.append({
                "id": s.get('videoId', ''),
                "title": s.get('title', 'Unknown'),
                "artist": s['artists'][0]['name'] if s.get('artists') else 'Unknown',
                "thumbnail": s['thumbnails'][-1]['url'] if s.get('thumbnails') else ''
            })
        return result
    except Exception as e:
        print(f"Trending error: {e}")
        return []

@app.get("/api/search")
async def search(q: str):
    try:
        results = yt.search(q, filter="songs")
        search_results = []
        for r in results[:20]:
            search_results.append({
                "id": r.get('videoId', ''),
                "title": r.get('title', 'Unknown'),
                "artist": r['artists'][0]['name'] if r.get('artists') else 'Unknown',
                "thumbnail": r['thumbnails'][-1]['url'] if r.get('thumbnails') else ''
            })
        return search_results
    except Exception as e:
        print(f"Search error: {e}")
        return []

@app.get("/")
async def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "VoFo Music API is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
