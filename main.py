# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from hotels.routes import router as hotels_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем статические файлы (Vue SPA) на корень "/"
# html=True — очень важно! позволяет отдавать index.html на все не-API пути
app.mount("/", StaticFiles(directory="admin", html=True), name="static-admin")

# API роуты остаются на /api/v1/...
app.include_router(
    hotels_router,
    prefix=settings.API_V1_STR,
    tags=["hotels"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )