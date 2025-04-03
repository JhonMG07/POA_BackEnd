from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app import models, schemas, auth
from app.database import engine, get_db
from app.scripts.init_data import seed_all_data
from app.auth import get_current_user
from passlib.context import CryptContext
import uuid
from typing import List

# Initialize the password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


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
