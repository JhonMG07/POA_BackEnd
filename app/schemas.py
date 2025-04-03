from pydantic import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    nombre_usuario: str
    email: str
    password: str
    id_rol: UUID

class UserOut(BaseModel):
    id_usuario: UUID
    nombre_usuario: str
    email: str
    id_rol: UUID
    activo: bool

    class Config:
        from_attributes = True


class PeriodoCreate(BaseModel):
    codigo_periodo: str
    nombre_periodo: str
    fecha_inicio: date
    fecha_fin: date
    anio: Optional[str] = None
    mes: Optional[str] = None

class PeriodoOut(PeriodoCreate):
    id_periodo: UUID

    class Config:
        from_attributes = True