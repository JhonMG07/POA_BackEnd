from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app import models, schemas, auth
from app.database import engine, get_db
from app.middlewares import add_middlewares
from app.scripts.init_data import seed_all_data
from app.auth import get_current_user
from passlib.context import CryptContext
import uuid
from typing import List

# Initialize the password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()
#middlewares
# CORS middleware
add_middlewares(app)

@app.on_event("startup")
async def on_startup():

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    # llenar la base de datos con datos iniciales
    print("Insertando roles iniciales...")
    await seed_all_data()


@app.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(models.Usuario).filter(models.Usuario.email == form_data.username)
    )
    usuario = result.scalars().first()
    print(f"Usuario encontrado: {usuario}")
    if not usuario or not auth.verificar_password(
        form_data.password, usuario.password_hash
    ):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not usuario.activo:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    access_token = auth.crear_token_acceso(
        data={"sub": str(usuario.id_usuario), "id_rol": str(usuario.id_rol)}
    )
    return {"access_token": access_token, "token_type": "bearer"}

#Usar para validar el usuario
@app.get("/perfil")
async def perfil_usuario(usuario: models.Usuario = Depends(get_current_user)):
    return {
        "id": usuario.id_usuario,
        "nombre": usuario.nombre_usuario,
        "rol": usuario.id_rol,
    }


@app.post("/register", response_model=schemas.UserOut)
async def register_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Usuario).where(models.Usuario.email == user.email)
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    hashed_final = pwd_context.hash(user.password)

    nuevo_usuario = models.Usuario(
        nombre_usuario=user.nombre_usuario,
        email=user.email,
        password_hash=hashed_final,
        id_rol=user.id_rol,
        activo=True,
    )

    db.add(nuevo_usuario)
    await db.commit()
    await db.refresh(nuevo_usuario)
    return nuevo_usuario

#Periodos

@app.post("/periodos/", response_model=schemas.PeriodoOut)
async def crear_periodo(data: schemas.PeriodoCreate, db: AsyncSession = Depends(get_db),usuario: models.Usuario = Depends(get_current_user)):
    
    # Obtener el rol del usuario
    result = await db.execute(select(models.Rol).where(models.Rol.id_rol == usuario.id_rol))
    rol = result.scalars().first()

    if not rol or rol.nombre_rol not in ["Administrador", "Director de Investigacion"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear periodos")
    
    # Validar que no exista ya el código
    result = await db.execute(select(models.Periodo).where(models.Periodo.codigo_periodo == data.codigo_periodo))
    existente = result.scalars().first()

    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un periodo con ese código")

    nuevo = models.Periodo(
        id_periodo=uuid.uuid4(),
        codigo_periodo=data.codigo_periodo,
        nombre_periodo=data.nombre_periodo,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        anio=data.anio,
        mes=data.mes
    )

    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)

    return nuevo

@app.put("/periodos/{id}", response_model=schemas.PeriodoOut)
async def editar_periodo_completo(
    id: uuid.UUID,
    data: schemas.PeriodoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result_rol = await db.execute(select(models.Rol).where(models.Rol.id_rol == usuario.id_rol))
    rol = result_rol.scalars().first()
    if not rol or rol.nombre_rol not in ["Administrador", "Director de Investigacion"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para editar periodos")

    result = await db.execute(select(models.Periodo).where(models.Periodo.id_periodo == id))
    periodo = result.scalars().first()

    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    # Reemplazar todos los campos
    periodo.codigo_periodo = data.codigo_periodo
    periodo.nombre_periodo = data.nombre_periodo
    periodo.fecha_inicio = data.fecha_inicio
    periodo.fecha_fin = data.fecha_fin
    periodo.anio = data.anio
    periodo.mes = data.mes

    await db.commit()
    await db.refresh(periodo)
    return periodo

@app.get("/periodos/", response_model=List[schemas.PeriodoOut])
async def listar_periodos(
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(select(models.Periodo))
    periodos = result.scalars().all()
    return periodos

#POA

from datetime import datetime
from app.models import Poa, EstadoPOA

@app.post("/poas/", response_model=schemas.PoaOut)
async def crear_poa(
    data: schemas.PoaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Validar que el proyecto exista
    result = await db.execute(select(models.Proyecto).where(models.Proyecto.id_proyecto == data.id_proyecto))
    proyecto = result.scalars().first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Validar que el periodo exista
    result = await db.execute(select(models.Periodo).where(models.Periodo.id_periodo == data.id_periodo))
    periodo = result.scalars().first()
    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    # Validar que el tipo POA exista
    result = await db.execute(select(models.TipoPOA).where(models.TipoPOA.id_tipo_poa == data.id_tipo_poa))
    tipo_poa = result.scalars().first()
    if not tipo_poa:
        raise HTTPException(status_code=404, detail="Tipo de POA no encontrado")

    # Obtener el estado "Ingresado"
    result = await db.execute(select(EstadoPOA).where(EstadoPOA.nombre == "Ingresado"))
    estado = result.scalars().first()
    if not estado:
        raise HTTPException(status_code=500, detail="Estado 'Ingresado' no está definido en la base de datos")

    nuevo_poa = Poa(
        id_poa=uuid.uuid4(),
        id_proyecto=data.id_proyecto,
        id_periodo=data.id_periodo,
        codigo_poa=data.codigo_poa,
        fecha_creacion=datetime.now(datetime.timezone.utc),
        id_estado_poa=estado.id_estado_poa,
        id_tipo_poa=data.id_tipo_poa,
        anio_ejecucion=data.anio_ejecucion,
        presupuesto_asignado=data.presupuesto_asignado
    )

    db.add(nuevo_poa)
    await db.commit()
    await db.refresh(nuevo_poa)

    return nuevo_poa



#Proyecto

@app.post("/proyectos/", response_model=schemas.ProyectoOut)
async def crear_proyecto(
    data: schemas.ProyectoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Validar existencia de tipo de proyecto
    result = await db.execute(select(models.TipoProyecto).where(models.TipoProyecto.id_tipo_proyecto == data.id_tipo_proyecto))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Tipo de proyecto no encontrado")

    # Validar existencia de estado de proyecto
    result = await db.execute(select(models.EstadoProyecto).where(models.EstadoProyecto.id_estado_proyecto == data.id_estado_proyecto))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Estado de proyecto no encontrado")

    nuevo = models.Proyecto(
        id_proyecto=uuid.uuid4(),
        codigo_proyecto=data.codigo_proyecto,
        titulo=data.titulo,
        id_tipo_proyecto=data.id_tipo_proyecto,
        id_estado_proyecto=data.id_estado_proyecto,
        id_director_proyecto=usuario.id_usuario,
        fecha_creacion=data.fecha_creacion,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        fecha_prorroga=data.fecha_prorroga,
        tiempo_prorroga_meses=data.tiempo_prorroga_meses,
        presupuesto_aprobado=data.presupuesto_aprobado
    )

    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo