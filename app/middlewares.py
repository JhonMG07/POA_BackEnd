from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def add_middlewares(app: FastAPI) -> None:
    origins = [
        "https://poa-front.vercel.app"
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
