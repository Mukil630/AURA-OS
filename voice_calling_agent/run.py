import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure app is discoverable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import HOST, PORT
from app.api.routes import router as api_router

app = FastAPI(title="JARVIS Continuous Executive Calling Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount API routes
app.include_router(api_router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>JARVIS Calling Agent Running</h1>"

if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(f"[INFO] Starting JARVIS Calling Agent on http://{HOST}:{PORT}")
    print(f"[INFO] Mobile Access URL: http://192.168.1.8:{PORT}")
    uvicorn.run("run:app", host=HOST, port=PORT, reload=False)
