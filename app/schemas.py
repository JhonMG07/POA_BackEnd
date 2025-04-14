from decimal import Decimal
from pydantic import BaseModel, condecimal
from uuid import UUID
from datetime import date, datetime
from typing import Optional,List

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

class PoaCreate(BaseModel):
    id_proyecto: UUID
    id_periodo: UUID
    codigo_poa: str
    fecha_creacion: datetime
    id_tipo_poa: UUID
    anio_ejecucion: str
    presupuesto_asignado: Decimal

class PoaOut(PoaCreate):
    id_poa: UUID
    fecha_creacion: datetime
    id_estado_poa: UUID

    class Config:
        from_attributes = True


class ProyectoCreate(BaseModel):
    codigo_proyecto: str
    titulo: str
    id_tipo_proyecto: UUID
    id_estado_proyecto: UUID
    fecha_creacion: datetime
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fecha_prorroga: Optional[date] = None
    fecha_prorroga_inicio: Optional[date] = None
    fecha_prorroga_fin: Optional[date] = None
    presupuesto_aprobado: Optional[Decimal] = None

class ProyectoOut(ProyectoCreate):
    id_proyecto: UUID
    id_director_proyecto: UUID

    class Config:
        from_attributes = True


class RolOut(BaseModel):
    id_rol: UUID
    nombre_rol: str
    descripcion: str

    class Config:
        from_attributes = True

class TipoProyectoOut(BaseModel):
    id_tipo_proyecto: UUID
    codigo_tipo: str
    nombre: str
    descripcion: str

    class Config:
        from_attributes = True

class EstadoProyectoOut(BaseModel):
    id_estado_proyecto: UUID
    nombre: str
    descripcion: str

    class Config:
        from_attributes = True


class EstadoPoaOut(BaseModel):
    id_estado_poa: UUID
    nombre: str
    descripcion: str

    class Config:
        from_attributes = True

class TipoPoaOut(BaseModel):
    id_tipo_poa: UUID
    codigo_tipo: str
    nombre: str
    descripcion: Optional[str]
    duracion_meses: int
    cantidad_periodos: int
    presupuesto_maximo: Decimal

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

class ActividadCreate(BaseModel):
    descripcion_actividad: str
    total_por_actividad: Optional[condecimal(ge=0)] = 0.00
class ActividadesBatchCreate(BaseModel):
    actividades: List[ActividadCreate]

class TareaCreate(BaseModel):
    id_detalle_tarea: UUID
    nombre: str
    detalle_descripcion: str
    cantidad: condecimal(gt=0)
    precio_unitario: condecimal(gt=0)

class TareaOut(BaseModel):
    id_tarea: UUID
    nombre: str
    detalle_descripcion: str
    cantidad: condecimal(gt=0)
    precio_unitario: condecimal(gt=0)
    total: condecimal(gt=0)
    saldo_disponible: condecimal(gt=0)

    class Config:
        from_attributes = True

class DetalleTareaOut(BaseModel):
    id_detalle_tarea: UUID
    nombre: str
    descripcion: Optional[str]

    class Config:
        from_attributes = True

class ActividadOut(BaseModel):
    id_actividad: UUID
    descripcion_actividad: str
    total_por_actividad: condecimal(max_digits=18, decimal_places=2)
    saldo_actividad: condecimal(max_digits=18, decimal_places=2)

    class Config:
        from_attributes = True

class ActividadUpdate(BaseModel):
    descripcion_actividad: str

class TareaOut(BaseModel):
    id_tarea: UUID
    nombre: str
    detalle_descripcion: Optional[str]
    cantidad: condecimal(max_digits=10, decimal_places=2)
    precio_unitario: condecimal(max_digits=18, decimal_places=2)
    total: condecimal(max_digits=18, decimal_places=2)
    saldo_disponible: condecimal(max_digits=18, decimal_places=2)

    class Config:
        from_attributes = True

class TareaUpdate(BaseModel):
    cantidad: condecimal(gt=0)
    precio_unitario: condecimal(gt=0)
