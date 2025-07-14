from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import ssl

DATABASE_URL = os.getenv("DATABASE_URL")
ssl_context = ssl.create_default_context()

engine = create_async_engine(
    DATABASE_URL.replace("?sslmode=require", ""),  # limpia la URL
    echo=True,
    connect_args={"ssl": ssl_context}
)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with SessionLocal() as session:
        yield session