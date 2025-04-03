from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def add_middlewares(app: FastAPI) -> None:
    origins = [
        "http://localhost:5173",
        "https://tudominio.com",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
