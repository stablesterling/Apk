import os
import bcrypt
import uvicorn
import json
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Use SQLite for now (compatible with Python 3.13)
# PostgreSQL psycopg2 has issues with Python 3.13
DB_URL = "sqlite:///./vofo.db"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
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

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="VoFo Music API")

# Serve static files for PWA
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password helpers
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Mock music data (you can replace this with real API later)
MOCK_TRENDING = [
    {"id": "dQw4w9WgXcQ", "title": "Never Gonna Give You Up", "artist": "Rick Astley", "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
    {"id": "9bZkp7q19f0", "title": "Gangnam Style", "artist": "PSY", "thumbnail": "https://i.ytimg.com/vi/9bZkp7q19f0/hqdefault.jpg"},
    {"id": "kffacxfA7G4", "title": "Baby", "artist": "Justin Bieber", "thumbnail": "https://i.ytimg.com/vi/kffacxfA7G4/hqdefault.jpg"},
    {"id": "JGwWNGJdvx8", "title": "Shape of You", "artist": "Ed Sheeran", "thumbnail": "https://i.ytimg.com/vi/JGwWNGJdvx8/hqdefault.jpg"},
    {"id": "nfs8NYg7yQM", "title": "Blinding Lights", "artist": "The Weeknd", "thumbnail": "https://i.ytimg.com/vi/nfs8NYg7yQM/hqdefault.jpg"},
    {"id": "5qm8PH4xAss", "title": "Uptown Funk", "artist": "Mark Ronson ft. Bruno Mars", "thumbnail": "https://i.ytimg.com/vi/5qm8PH4xAss/hqdefault.jpg"},
    {"id": "OPf0YbXqDm0", "title": "Bad Guy", "artist": "Billie Eilish", "thumbnail": "https://i.ytimg.com/vi/OPf0YbXqDm0/hqdefault.jpg"},
    {"id": "8UVNT4wvIGY", "title": "Someone Like You", "artist": "Adele", "thumbnail": "https://i.ytimg.com/vi/8UVNT4wvIGY/hqdefault.jpg"},
    {"id": "kJQP7kiw5Fk", "title": "Despacito", "artist": "Luis Fonsi ft. Daddy Yankee", "thumbnail": "https://i.ytimg.com/vi/kJQP7kiw5Fk/hqdefault.jpg"},
    {"id": "09R8_2nJtjg", "title": "Sugar", "artist": "Maroon 5", "thumbnail": "https://i.ytimg.com/vi/09R8_2nJtjg/hqdefault.jpg"},
]

# --- STATIC FILES ---
@app.get("/")
async def serve_home():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/manifest.json")
async def serve_manifest():
    return JSONResponse({
        "name": "VoFo Music",
        "short_name": "VoFo",
        "description": "Immersive Music Streaming",
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
            },
            {
                "src": "https://via.placeholder.com/512x512/c5a367/0d0d0d?text=VoFo",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.get("/service-worker.js")
async def serve_service_worker():
    return FileResponse("service-worker.js")

@app.get("/offline.html")
async def serve_offline():
    return FileResponse("offline.html")

# --- AUTH ROUTES ---
@app.post("/api/register")
async def register(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        # Check if user exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create new user
        hashed_password = hash_password(password)
        new_user = User(username=username, password=hashed_password)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "success": True,
            "message": "Registration successful",
            "user_id": new_user.id,
            "username": new_user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/login")
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        user = db.query(User).filter(User.username == username).first()
        
        if not user or not verify_password(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        return {
            "success": True,
            "message": "Login successful",
            "user_id": user.id,
            "username": user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# --- LIKES ROUTES ---
@app.post("/api/like")
async def toggle_like(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        song_id = data.get("song_id")
        title = data.get("title", "")
        artist = data.get("artist", "")
        thumbnail = data.get("thumbnail", "")
        
        if not user_id or not song_id:
            raise HTTPException(status_code=400, detail="User ID and Song ID required")
        
        # Check if already liked
        existing_like = db.query(LikedSong).filter(
            LikedSong.user_id == user_id,
            LikedSong.song_id == song_id
        ).first()
        
        if existing_like:
            # Unlike
            db.delete(existing_like)
            db.commit()
            return {
                "success": True,
                "status": "unliked",
                "message": "Song removed from liked"
            }
        else:
            # Like
            new_like = LikedSong(
                user_id=user_id,
                song_id=song_id,
                title=title,
                artist=artist,
                thumbnail=thumbnail
            )
            db.add(new_like)
            db.commit()
            return {
                "success": True,
                "status": "liked",
                "message": "Song added to liked"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Like operation failed: {str(e)}")

@app.get("/api/liked/{user_id}")
async def get_liked_songs(user_id: int, db: Session = Depends(get_db)):
    try:
        liked_songs = db.query(LikedSong).filter(
            LikedSong.user_id == user_id
        ).order_by(LikedSong.id.desc()).all()
        
        return [
            {
                "id": song.song_id,
                "title": song.title,
                "artist": song.artist,
                "thumbnail": song.thumbnail
            }
            for song in liked_songs
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch liked songs: {str(e)}")

# --- MUSIC ROUTES ---
@app.get("/api/trending")
async def get_trending():
    try:
        return MOCK_TRENDING[:15]
    except Exception as e:
        print(f"Trending error: {e}")
        return []

@app.get("/api/search")
async def search_music(q: str = ""):
    try:
        if not q or q.strip() == "":
            return MOCK_TRENDING[:10]
        
        search_term = q.lower().strip()
        results = []
        
        for song in MOCK_TRENDING:
            if (search_term in song["title"].lower() or 
                search_term in song["artist"].lower() or
                search_term in song["id"].lower()):
                results.append(song)
        
        return results[:20]
        
    except Exception as e:
        print(f"Search error: {e}")
        return []

@app.get("/api/song/{song_id}")
async def get_song_info(song_id: str):
    try:
        # Find song in mock data
        for song in MOCK_TRENDING:
            if song["id"] == song_id:
                return {
                    "success": True,
                    "song": song
                }
        
        # If not found, return a default
        return {
            "success": True,
            "song": {
                "id": song_id,
                "title": "Unknown Song",
                "artist": "Unknown Artist",
                "thumbnail": "https://via.placeholder.com/300x300/333/ccc?text=🎵"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# --- UTILITY ROUTES ---
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "VoFo Music API",
        "version": "1.0.0",
        "database": "connected"
    }

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    try:
        user_count = db.query(User).count()
        like_count = db.query(LikedSong).count()
        
        return {
            "users": user_count,
            "liked_songs": like_count,
            "available_songs": len(MOCK_TRENDING)
        }
    except Exception as e:
        return {
            "users": 0,
            "liked_songs": 0,
            "available_songs": len(MOCK_TRENDING),
            "error": str(e)
        }

# --- ERROR HANDLERS ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") else None
        }
    )

# --- STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    print("🚀 VoFo Music API starting up...")
    print(f"📊 Using database: {DB_URL}")
    print(f"🎵 Mock songs loaded: {len(MOCK_TRENDING)}")

# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🌍 Starting server on port {port}...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Set to True for development
        log_level="info"
    )
