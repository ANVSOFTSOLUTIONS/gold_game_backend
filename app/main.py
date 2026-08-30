import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_indexes
from .game_engine import round_loop
from .routers import auth, game, wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_indexes()
    task = asyncio.create_task(round_loop())
    yield
    task.cancel()


app = FastAPI(title="NineBox API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(game.router)


@app.get("/health")
def health():
    return {"status": "ok"}
