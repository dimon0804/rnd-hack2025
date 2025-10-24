from fastapi import FastAPI
from .routers.api import api_router
from .db.session import Base, engine
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="HackRTC API")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(api_router)
