from datetime import datetime,timezone
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
from dateutil.relativedelta import relativedelta
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


@app.get("/periodos/{id}", response_model=schemas.PeriodoOut)
async def obtener_periodo(id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Periodo).where(models.Periodo.id_periodo == id))
    periodo = result.scalars().first()

    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    return periodo


#POA

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

    diferencia = relativedelta(periodo.fecha_fin, periodo.fecha_inicio)
    duracion_meses = diferencia.months + diferencia.years * 12

    if duracion_meses > tipo_poa.duracion_meses:
        raise HTTPException(
            status_code=400,
            detail="El periodo excede la duración permitida por el tipo de POA"
        )

    result = await db.execute(select(models.EstadoPOA).where(models.EstadoPOA.nombre == "Ingresado"))
    estado = result.scalars().first()
    if not estado:
        raise HTTPException(status_code=500, detail="Estado 'Ingresado' no está definido en la base de datos")

    nuevo_poa = models.Poa(
        id_poa=uuid.uuid4(),
        id_proyecto=data.id_proyecto,
        id_periodo=data.id_periodo,
        codigo_poa=data.codigo_poa,
        fecha_creacion=data.fecha_creacion,
        id_estado_poa=estado.id_estado_poa,
        id_tipo_poa=data.id_tipo_poa,
        anio_ejecucion=data.anio_ejecucion,
        presupuesto_asignado=data.presupuesto_asignado
    )

    db.add(nuevo_poa)
    await db.commit()
    await db.refresh(nuevo_poa)

    return nuevo_poa

from dateutil.relativedelta import relativedelta

@app.put("/poas/{id}", response_model=schemas.PoaOut)
async def editar_poa(
    id: uuid.UUID,
    data: schemas.PoaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar que el POA exista
    result = await db.execute(select(models.Poa).where(models.Poa.id_poa == id))
    poa = result.scalars().first()
    if not poa:
        raise HTTPException(status_code=404, detail="POA no encontrado")

    # Verificar existencia del proyecto
    result = await db.execute(select(models.Proyecto).where(models.Proyecto.id_proyecto == data.id_proyecto))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Verificar existencia del periodo
    result = await db.execute(select(models.Periodo).where(models.Periodo.id_periodo == data.id_periodo))
    periodo = result.scalars().first()
    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    # Verificar existencia del tipo POA
    result = await db.execute(select(models.TipoPOA).where(models.TipoPOA.id_tipo_poa == data.id_tipo_poa))
    tipo_poa = result.scalars().first()
    if not tipo_poa:
        raise HTTPException(status_code=404, detail="Tipo de POA no encontrado")

    # Validar duración del periodo usando relativedelta
    diferencia = relativedelta(periodo.fecha_fin, periodo.fecha_inicio)
    duracion_meses = diferencia.months + diferencia.years * 12
    if duracion_meses != tipo_poa.duracion_meses:
        raise HTTPException(
            status_code=400,
            detail="La duración del periodo no coincide con el tipo de POA seleccionado"
        )

    # Estado se mantiene igual que antes
    result = await db.execute(select(models.EstadoPOA).where(models.EstadoPOA.nombre == "Ingresado"))
    estado = result.scalars().first()
    if not estado:
        raise HTTPException(status_code=500, detail="Estado 'Ingresado' no está definido")

    # Actualizar el POA
    poa.id_proyecto = data.id_proyecto
    poa.id_periodo = data.id_periodo
    poa.codigo_poa = data.codigo_poa
    poa.fecha_creacion = data.fecha_creacion
    poa.id_tipo_poa = data.id_tipo_poa
    poa.id_estado_poa = estado.id_estado_poa  # o mantener el actual si no deseas sobreescribir
    poa.anio_ejecucion = data.anio_ejecucion
    poa.presupuesto_asignado = data.presupuesto_asignado

    await db.commit()
    await db.refresh(poa)
    return poa

@app.get("/poas/", response_model=List[schemas.PoaOut])
async def listar_poas(
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(select(models.Poa))
    return result.scalars().all()

@app.get("/poas/{id}", response_model=schemas.PoaOut)
async def obtener_poa(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(select(models.Poa).where(models.Poa.id_poa == id))
    poa = result.scalars().first()

    if not poa:
        raise HTTPException(status_code=404, detail="POA no encontrado")

    return poa

@app.get("/estados-poa/", response_model=List[schemas.EstadoPoaOut])
async def listar_estados_poa(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.EstadoPOA))
    return result.scalars().all()

@app.get("/tipos-poa/", response_model=List[schemas.TipoPoaOut])
async def listar_tipos_poa(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TipoPOA))

    return result.scalars().all()

@app.post("/periodos/", response_model=schemas.PeriodoOut)
async def crear_periodo(
    data: schemas.PeriodoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    nuevo = models.Periodo(
        id_periodo=uuid.uuid4(),
        **data.dict()
    )
    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo

@app.put("/periodos/{id}", response_model=schemas.PeriodoOut)
async def editar_periodo(
    id: uuid.UUID,
    data: schemas.PeriodoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(select(models.Periodo).where(models.Periodo.id_periodo == id))
    periodo = result.scalars().first()

    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")

    for key, value in data.dict().items():
        setattr(periodo, key, value)

    await db.commit()
    await db.refresh(periodo)
    return periodo

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
        fecha_prorroga_inicio=data.fecha_prorroga_inicio,
        fecha_prorroga_fin=data.fecha_prorroga_fin,
        presupuesto_aprobado=data.presupuesto_aprobado
    )

    db.add(nuevo)
    await db.commit()
    await db.refresh(nuevo)
    return nuevo

@app.put("/proyectos/{id}", response_model=schemas.ProyectoOut)
async def editar_proyecto(
    id: uuid.UUID,
    data: schemas.ProyectoCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Validar que el proyecto exista
    result = await db.execute(select(models.Proyecto).where(models.Proyecto.id_proyecto == id))
    proyecto = result.scalars().first()

    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Validar que el usuario sea el director del proyecto
    if proyecto.id_director_proyecto != usuario.id_usuario:
        raise HTTPException(status_code=403, detail="Solo el director del proyecto puede editarlo")

    # Validar tipo y estado
    tipo = await db.execute(select(models.TipoProyecto).where(models.TipoProyecto.id_tipo_proyecto == data.id_tipo_proyecto))
    if not tipo.scalars().first():
        raise HTTPException(status_code=404, detail="Tipo de proyecto no encontrado")

    estado = await db.execute(select(models.EstadoProyecto).where(models.EstadoProyecto.id_estado_proyecto == data.id_estado_proyecto))
    if not estado.scalars().first():
        raise HTTPException(status_code=404, detail="Estado de proyecto no encontrado")

    # Actualizar campos
    proyecto.codigo_proyecto = data.codigo_proyecto
    proyecto.titulo = data.titulo
    proyecto.id_tipo_proyecto = data.id_tipo_proyecto
    proyecto.id_estado_proyecto = data.id_estado_proyecto
    proyecto.fecha_creacion = data.fecha_creacion
    proyecto.fecha_inicio = data.fecha_inicio
    proyecto.fecha_fin = data.fecha_fin
    proyecto.fecha_prorroga = data.fecha_prorroga
    proyecto.fecha_prorroga_inicio = data.fecha_prorroga_inicio
    proyecto.fecha_prorroga_fin = data.fecha_prorroga_fin
    proyecto.presupuesto_aprobado = data.presupuesto_aprobado

    await db.commit()
    await db.refresh(proyecto)
    return proyecto


@app.get("/proyectos/", response_model=List[schemas.ProyectoOut])
async def listar_proyectos(
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Proyecto)
    )
    proyectos = result.scalars().all()
    return proyectos

@app.get("/proyectos/{id}", response_model=schemas.ProyectoOut)
async def obtener_proyecto(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Proyecto).where(models.Proyecto.id_proyecto == id)
    )
    proyecto = result.scalars().first()

    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # if proyecto.id_director_proyecto != usuario.id_usuario:
    #     raise HTTPException(status_code=403, detail="No tienes acceso a este proyecto")

    return proyecto

@app.get("/roles/", response_model=List[schemas.RolOut])
async def listar_roles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Rol))
    return result.scalars().all()

@app.get("/tipos-proyecto/", response_model=List[schemas.TipoProyectoOut])
async def listar_tipos_proyecto(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TipoProyecto))
    return result.scalars().all()

@app.get("/estados-proyecto/", response_model=List[schemas.EstadoProyectoOut])
async def listar_estados_proyecto(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.EstadoProyecto))
    return result.scalars().all()

