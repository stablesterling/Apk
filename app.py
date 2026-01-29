import os
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import requests
import json
import re

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

# Use multiple public Invidious instances as fallback
INVIDIOUS_INSTANCES = [
    "https://inv.tux.pizza",
    "https://invidious.snopyta.org",
    "https://vid.puffyan.us",
    "https://yewtu.be",
    "https://inv.riverside.rocks"
]

# Cache for audio streams
stream_cache = {}

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- AUTH HELPERS ---
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- MUSIC API FUNCTIONS ---
def search_youtube_music(query: str, limit: int = 20):
    """Search YouTube Music using public APIs"""
    try:
        # Try using Invidious API
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/search?q={query}&type=video"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for item in data[:limit]:
                        if 'videoId' in item:
                            results.append({
                                'id': item['videoId'],
                                'title': item.get('title', 'Unknown'),
                                'artist': item.get('author', 'Unknown'),
                                'thumbnail': item.get('videoThumbnails', [{}])[-1].get('url', '')
                            })
                    if results:
                        return results
            except:
                continue
        
        # Fallback to ytmusicapi-like search
        return fallback_search(query, limit)
    except Exception as e:
        print(f"Search error: {e}")
        return []

def fallback_search(query: str, limit: int = 20):
    """Fallback search method"""
    try:
        # Simple search using YouTube's public endpoint
        search_url = f"https://www.youtube.com/results?search_query={query}+music"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Extract video IDs from the page (simplified approach)
        pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
        video_ids = re.findall(pattern, response.text)[:limit]
        
        # Get details for each video
        results = []
        for video_id in video_ids:
            try:
                # Use Invidious to get video details
                for instance in INVIDIOUS_INSTANCES:
                    try:
                        details_url = f"{instance}/api/v1/videos/{video_id}"
                        details_resp = requests.get(details_url, timeout=3)
                        if details_resp.status_code == 200:
                            details = details_resp.json()
                            results.append({
                                'id': video_id,
                                'title': details.get('title', 'Unknown'),
                                'artist': details.get('author', 'Unknown'),
                                'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                            })
                            break
                    except:
                        continue
            except:
                continue
        
        return results
    except Exception as e:
        print(f"Fallback search error: {e}")
        return []

def get_trending():
    """Get trending music videos"""
    try:
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/trending?type=music"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    for item in data[:15]:
                        results.append({
                            'id': item['videoId'],
                            'title': item.get('title', 'Unknown'),
                            'artist': item.get('author', 'Unknown'),
                            'thumbnail': item.get('videoThumbnails', [{}])[-1].get('url', '')
                        })
                    return results
            except:
                continue
        return []
    except Exception as e:
        print(f"Trending error: {e}")
        return []

def get_audio_stream(video_id: str):
    """Get audio stream URL for a video"""
    try:
        # Check cache first
        if video_id in stream_cache:
            return stream_cache[video_id]
        
        # Try multiple Invidious instances
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Find best audio format
                    adaptive_formats = data.get('adaptiveFormats', [])
                    audio_formats = [f for f in adaptive_formats 
                                   if f.get('type', '').startswith('audio')]
                    
                    if audio_formats:
                        # Sort by bitrate (highest first)
                        audio_formats.sort(key=lambda x: x.get('bitrate', 0), reverse=True)
                        audio_url = audio_formats[0].get('url')
                        
                        if audio_url:
                            # Cache the result for 1 hour
                            stream_cache[video_id] = audio_url
                            return audio_url
            except:
                continue
        
        # Fallback: Use YouTube's public audio stream
        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"Stream error: {e}")
        return None

# --- AUTH ROUTES ---
@app.post("/api/register")
async def register(data: dict, db: Session = Depends(get_db)):
    if not data.get('username') or not data.get('password'):
        raise HTTPException(400, "Username and password required")
    
    if db.query(User).filter(User.username == data['username']).first():
        raise HTTPException(400, "Username already exists")
    
    user = User(username=data['username'], password=hash_password(data['password']))
    db.add(user)
    db.commit()
    return {"success": True}

@app.post("/api/login")
async def login(data: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data['username']).first()
    if not user or not verify_password(data['password'], user.password):
        raise HTTPException(401, "Invalid credentials")
    return {"success": True, "user_id": user.id, "username": user.username}

# --- LIKES ROUTES ---
@app.post("/api/like")
async def toggle_like(data: dict, db: Session = Depends(get_db)):
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

@app.get("/api/liked/{user_id}")
async def get_liked(user_id: int, db: Session = Depends(get_db)):
    likes = db.query(LikedSong).filter(LikedSong.user_id == user_id).all()
    return [{"id": l.song_id, "title": l.title, "artist": l.artist, "thumbnail": l.thumbnail} for l in likes]

# --- MUSIC ROUTES ---
@app.get("/api/trending")
async def trending():
    return get_trending()

@app.get("/api/search")
async def search(q: str):
    return search_youtube_music(q)

@app.get("/api/stream/{video_id}")
async def stream(video_id: str):
    audio_url = get_audio_stream(video_id)
    if audio_url:
        return {"url": audio_url}
    raise HTTPException(404, "Stream not available")

@app.get("/api/proxy/{video_id}")
async def proxy_stream(video_id: str):
    """Proxy the audio stream to avoid CORS issues"""
    audio_url = get_audio_stream(video_id)
    if not audio_url:
        raise HTTPException(404, "Stream not available")
    
    # If it's a YouTube URL, redirect to it
    if 'youtube.com' in audio_url:
        return {"url": audio_url}
    
    # Otherwise, proxy the audio stream
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Range': 'bytes=0-',
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(audio_url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type=response.headers.get('Content-Type', 'audio/mpeg'),
                headers={
                    'Content-Type': response.headers.get('Content-Type', 'audio/mpeg'),
                    'Accept-Ranges': 'bytes',
                    'Content-Length': response.headers.get('Content-Length', ''),
                    'Cache-Control': 'public, max-age=3600'
                }
            )
    except Exception as e:
        print(f"Proxy error: {e}")
    
    # Fallback: Return the URL
    return {"url": audio_url}

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
