from datetime import datetime,timezone
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException,UploadFile, File, Form, Body, Query
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
import re
from fastapi.responses import JSONResponse, StreamingResponse
from app.scripts.transformador_excel import transformar_excel
from app.utils import eliminar_tareas_y_actividades
import io
import pandas as pd
import xlsxwriter
from sqlalchemy import func

from reportlab.lib.pagesizes import letter,landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
import unicodedata
from sqlalchemy.orm import selectinload

# Initialize the password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()
#middlewares
# CORS middleware
add_middlewares(app)

def quitar_tildes(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def normalizar_texto(texto):
    # Quita tildes, pasa a minúsculas, elimina espacios extra y números
    texto = quitar_tildes(texto).lower()
    texto = re.sub(r'\d+', '', texto)         # Elimina todos los números
    texto = re.sub(r'\s+', ' ', texto)        # Reemplaza múltiples espacios por uno solo
    texto = texto.strip()                     # Quita espacios al inicio y final
    return texto

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
     # Verificar si ya existe un POA con ese periodo
    result = await db.execute(
        select(models.Poa).where(models.Poa.id_periodo == data.id_periodo)
    )
    poa_existente = result.scalars().first()
    if poa_existente:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un POA asignado al periodo '{periodo.nombre_periodo}'"
        )
    
    # Validar que el tipo POA exista
    result = await db.execute(select(models.TipoPOA).where(models.TipoPOA.id_tipo_poa == data.id_tipo_poa))
    tipo_poa = result.scalars().first()
    if not tipo_poa:
        raise HTTPException(status_code=404, detail="Tipo de POA no encontrado")
    
    # Mejorar el cálculo de la duración del periodo para considerar días también
    diferencia = relativedelta(periodo.fecha_fin, periodo.fecha_inicio)
    duracion_meses = diferencia.months + diferencia.years * 12

    # Si hay días adicionales, considerar como mes adicional si es más de la mitad del mes
    if diferencia.days > 15:
        duracion_meses += 1
    
    if duracion_meses > tipo_poa.duracion_meses:
        raise HTTPException(
            status_code=400,
            detail=f"El periodo '{periodo.nombre_periodo}' tiene una duración de {duracion_meses} meses, " +
                   f"pero el tipo de POA '{tipo_poa.nombre}' permite máximo {tipo_poa.duracion_meses} meses"
        )

    result = await db.execute(select(models.EstadoPOA).where(models.EstadoPOA.nombre == "Ingresado"))
    estado = result.scalars().first()
    if not estado:
        raise HTTPException(status_code=500, detail="Estado 'Ingresado' no está definido en la base de datos")

    # Crear POA
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
     # Verificar si el nuevo periodo ya está ocupado por otro POA
    if poa.id_periodo != data.id_periodo:
        result = await db.execute(
            select(models.Poa)
            .where(models.Poa.id_periodo == data.id_periodo, models.Poa.id_poa != poa.id_poa)
        )
        otro_poa = result.scalars().first()
        if otro_poa:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un POA asignado al periodo '{periodo.nombre_periodo}'"
            )
   
    # Verificar existencia del tipo POA
    result = await db.execute(select(models.TipoPOA).where(models.TipoPOA.id_tipo_poa == data.id_tipo_poa))
    tipo_poa = result.scalars().first()

    if not tipo_poa:
        raise HTTPException(status_code=404, detail="Tipo de POA no encontrado")

    # Mejorar el cálculo de la duración del periodo para considerar días también
    diferencia = relativedelta(periodo.fecha_fin, periodo.fecha_inicio)
    duracion_meses = diferencia.months + diferencia.years * 12

    # Si hay días adicionales, considerar como mes adicional si es más de la mitad del mes
    if diferencia.days > 15:
        duracion_meses += 1
    
    if duracion_meses > tipo_poa.duracion_meses:
        raise HTTPException(
            status_code=400,
            detail=f"El periodo '{periodo.nombre_periodo}' tiene una duración de {duracion_meses} meses, " +
                   f"pero el tipo de POA '{tipo_poa.nombre}' permite máximo {tipo_poa.duracion_meses} meses"
        )

    # Estado se mantiene igual que antes
    result = await db.execute(select(models.EstadoPOA).where(models.EstadoPOA.id_estado_poa == data.id_estado_poa))
    estado = result.scalars().first()
    if not estado:
        raise HTTPException(status_code=400, detail="Estado POA no encontrado")

    # Actualizar el POA
    poa.id_proyecto = data.id_proyecto
    poa.id_periodo = data.id_periodo
    poa.codigo_poa = data.codigo_poa
    poa.fecha_creacion = data.fecha_creacion
    poa.id_tipo_poa = data.id_tipo_poa
    poa.id_estado_poa = data.id_estado_poa  # o mantener el actual si no deseas sobreescribir
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

@app.get("/tipos-poa/{id}", response_model=schemas.TipoPoaOut)
async def obtener_tipo_poa(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(select(models.TipoPOA).where(models.TipoPOA.id_tipo_poa == id))
    tipo_poa = result.scalars().first()

    if not tipo_poa:
        raise HTTPException(status_code=404, detail="Tipo de POA no encontrado")

    return tipo_poa

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
        id_director_proyecto=data.id_director_proyecto,
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
    # if proyecto.id_director_proyecto != usuario.id_usuario:
    #     raise HTTPException(status_code=403, detail="Solo el director del proyecto puede editarlo")

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
    proyecto.id_director_proyecto = data.id_director_proyecto

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

#actividades
@app.post("/poas/{id_poa}/actividades")
async def crear_actividades_para_poa(
    id_poa: uuid.UUID,
    data: schemas.ActividadesBatchCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar existencia del POA
    result = await db.execute(select(models.Poa).where(models.Poa.id_poa == id_poa))
    poa = result.scalars().first()
    if not poa:
        raise HTTPException(status_code=404, detail="POA no encontrado")

    actividades = [
        models.Actividad(
            id_actividad=uuid.uuid4(),
            id_poa=id_poa,
            descripcion_actividad=act.descripcion_actividad,
            total_por_actividad=act.total_por_actividad,
            saldo_actividad=act.saldo_actividad,
        )
        for act in data.actividades
    ]

    db.add_all(actividades)
    await db.commit()

    ids_creados = [str(act.id_actividad) for act in actividades]

    return JSONResponse(
        status_code=201,
        content={
            "msg": f"{len(actividades)} actividades creadas correctamente",
            "ids_actividades": ids_creados,
        }
    )


#tareas
@app.post("/actividades/{id_actividad}/tareas", response_model=schemas.TareaOut)
async def crear_tarea(
    id_actividad: uuid.UUID,
    data: schemas.TareaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar existencia de la actividad
    result = await db.execute(select(models.Actividad).where(models.Actividad.id_actividad == id_actividad))
    actividad = result.scalars().first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    # Verificar existencia del detalle de tarea
    result = await db.execute(select(models.DetalleTarea).where(models.DetalleTarea.id_detalle_tarea == data.id_detalle_tarea))
    detalle = result.scalars().first()
    if not detalle:
        raise HTTPException(status_code=404, detail="Detalle de tarea no encontrado")

    cantidad = data.cantidad or Decimal("0")
    precio_unitario = data.precio_unitario or Decimal("0")
    total = precio_unitario * cantidad

    nueva_tarea = models.Tarea(
        id_tarea=uuid.uuid4(),
        id_actividad=id_actividad,
        id_detalle_tarea=data.id_detalle_tarea,
        nombre=data.nombre,
        detalle_descripcion=data.detalle_descripcion,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        total=total,
        saldo_disponible=total,
        lineaPaiViiv=data.lineaPaiViiv
    )

    # Actualizar montos en la actividad
    actividad.total_por_actividad += total
    actividad.saldo_actividad += total

    db.add(nueva_tarea)
    await db.commit()
    await db.refresh(nueva_tarea)

    return nueva_tarea


@app.delete("/tareas/{id_tarea}")
async def eliminar_tarea(id_tarea: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Tarea).where(models.Tarea.id_tarea == id_tarea))
    tarea = result.scalars().first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    await db.delete(tarea)
    await db.commit()
    return {"msg": "Tarea eliminada correctamente"}


@app.put("/tareas/{id_tarea}")
async def editar_tarea(
    id_tarea: uuid.UUID, 
    data: schemas.TareaUpdate, 
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
    ):
    result = await db.execute(select(models.Tarea).where(models.Tarea.id_tarea == id_tarea))
    tarea = result.scalars().first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    # Campos a actualizar y auditar
    campos_auditar = ["cantidad", "precio_unitario", "total", "saldo_disponible","lineaPaiViiv"]

    for campo in campos_auditar:
        valor_anterior = getattr(tarea, campo)
        valor_nuevo = getattr(data, campo)
        
        if valor_anterior != valor_nuevo:
            # Registrar en histórico
            historico = models.HistoricoPoa(
                id_historico=uuid.uuid4(),
                id_poa=tarea.actividad.id_poa,
                id_usuario=usuario.id_usuario,
                fecha_modificacion=datetime.utcnow(),
                campo_modificado=campo,
                valor_anterior=str(valor_anterior),
                valor_nuevo=str(valor_nuevo),
                justificacion="Actualización manual de tarea"
            )
            db.add(historico)
            setattr(tarea, campo, valor_nuevo)

    await db.commit()
    await db.refresh(tarea)

    return {"msg": "Tarea actualizada", "tarea": tarea}

#detalles tarea por poa
@app.get("/poas/{id_poa}/detalles_tarea", response_model=List[schemas.DetalleTareaOut])
async def obtener_detalles_tarea_poa(
    id_poa: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.DetalleTarea)
        .join(models.TipoPoaDetalleTarea, models.DetalleTarea.id_detalle_tarea == models.TipoPoaDetalleTarea.id_detalle_tarea)
        .join(models.Poa, models.TipoPoaDetalleTarea.id_tipo_poa == models.Poa.id_tipo_poa)
        .where(models.Poa.id_poa == id_poa)
    )
    return result.scalars().all()


#actividades por poa
@app.get("/poas/{id_poa}/actividades", response_model=List[schemas.ActividadOut])
async def obtener_actividades_de_poa(
    id_poa: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Actividad).where(models.Actividad.id_poa == id_poa)
    )
    return result.scalars().all()


@app.delete("/actividades/{id_actividad}")
async def eliminar_actividad(id_actividad: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Actividad).where(models.Actividad.id_actividad == id_actividad))
    actividad = result.scalars().first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    await db.delete(actividad)
    await db.commit()
    return {"msg": "Actividad eliminada correctamente"}


#tareas por actividad
@app.get("/actividades/{id_actividad}/tareas", response_model=List[schemas.TareaOut])
async def obtener_tareas_de_actividad(
    id_actividad: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Tarea).where(models.Tarea.id_actividad == id_actividad)
    )
    return result.scalars().all()


#editar actividad
@app.put("/actividades/{id_actividad}", response_model=schemas.ActividadOut)
async def editar_actividad(
    id_actividad: uuid.UUID,
    data: schemas.ActividadUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.Actividad).where(models.Actividad.id_actividad == id_actividad)
    )
    actividad = result.scalars().first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    actividad.descripcion_actividad = data.descripcion_actividad
    await db.commit()
    await db.refresh(actividad)

    return actividad

async def registrar_historial_poa(db, poa_id, usuario_id, campo, valor_anterior, valor_nuevo, justificacion, reforma_id=None):
    historial = models.HistoricoPoa(
        id_historico=uuid.uuid4(),
        id_poa=poa_id,
        id_usuario=usuario_id,
        fecha_modificacion=datetime.now(),
        campo_modificado=campo,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
        justificacion=justificacion,
        id_reforma=reforma_id
    )
    db.add(historial)
    await db.commit()


#reformas
@app.post("/poas/{id_poa}/reformas", response_model=schemas.ReformaPoaOut)
async def crear_reforma_poa(
    id_poa: uuid.UUID,
    data: schemas.ReformaPoaCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar que el POA exista
    result = await db.execute(select(models.Poa).where(models.Poa.id_poa == id_poa))
    poa = result.scalars().first()
    if not poa:
        raise HTTPException(status_code=404, detail="POA no encontrado")

    # Validar que el usuario solicitante exista
    result = await db.execute(select(models.Usuario).where(models.Usuario.id_usuario == usuario.id_usuario))
    if not result.scalars().first():
        raise HTTPException(status_code=403, detail="Usuario solicitante no válido")

    # Validar que el monto solicitado sea positivo
    if data.monto_solicitado <= 0:
        raise HTTPException(status_code=400, detail="El monto solicitado debe ser mayor a 0")

    # Validar que haya diferencia de montos
    if data.monto_solicitado == poa.presupuesto_asignado:
        raise HTTPException(status_code=400, detail="El monto solicitado debe ser diferente al monto actual del POA")

    reforma = models.ReformaPoa(
        id_reforma=uuid.uuid4(),
        id_poa=id_poa,
        fecha_solicitud=datetime.utcnow(),
        estado_reforma="Solicitada",
        monto_anterior=poa.presupuesto_asignado,
        monto_solicitado=data.monto_solicitado,
        justificacion=data.justificacion,
        id_usuario_solicita=usuario.id_usuario
    )

    db.add(reforma)
    await db.commit()
    await db.refresh(reforma)
    return reforma


@app.put("/reformas/{id_reforma}/tareas/{id_tarea}")
async def editar_tarea_en_reforma(
    id_reforma: uuid.UUID,
    id_tarea: uuid.UUID,
    data: schemas.TareaEditReforma,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    tarea = await db.get(models.Tarea, id_tarea)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    reforma = await db.get(models.ReformaPoa, id_reforma)
    if not reforma:
        raise HTTPException(status_code=404, detail="Reforma no encontrada")

    poa = await db.get(models.Poa, tarea.id_actividad)
    if not poa or poa.id_poa != reforma.id_poa:
        raise HTTPException(status_code=400, detail="Tarea no pertenece al POA de esta reforma")

    tarea.cantidad = data.cantidad
    tarea.precio_unitario = data.precio_unitario
    tarea.total = data.cantidad * data.precio_unitario
    tarea.saldo_disponible = tarea.total  # ajustar si hay lógica adicional
    if data.lineaPaiViiv is not None:
        tarea.lineaPaiViiv = data.lineaPaiViiv

    db.add(tarea)

    db.add(models.HistoricoPoa(
        id_historico=uuid.uuid4(),
        id_poa=poa.id_poa,
        id_usuario=usuario.id_usuario,
        fecha_modificacion=datetime.now(),
        campo_modificado="Tarea",
        valor_anterior=f"Cantidad: {data.anterior_cantidad}, Precio: {data.anterior_precio}",
        valor_nuevo=f"Cantidad: {data.cantidad}, Precio: {data.precio_unitario}",
        justificacion=data.justificacion,
        id_reforma=reforma.id_reforma
    ))

    await db.commit()
    return {"msg": "Tarea actualizada correctamente"}


@app.delete("/reformas/{id_reforma}/tareas/{id_tarea}")
async def eliminar_tarea_en_reforma(
    id_reforma: uuid.UUID,
    id_tarea: uuid.UUID,
    justificacion: str,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    tarea = await db.get(models.Tarea, id_tarea)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    actividad = await db.get(models.Actividad, tarea.id_actividad)
    poa = await db.get(models.Poa, actividad.id_poa)

    if not poa or poa.id_poa != (await db.get(models.ReformaPoa, id_reforma)).id_poa:
        raise HTTPException(status_code=400, detail="Tarea no corresponde a reforma")

    await db.delete(tarea)

    db.add(models.HistoricoPoa(
        id_historico=uuid.uuid4(),
        id_poa=poa.id_poa,
        id_usuario=usuario.id_usuario,
        fecha_modificacion=datetime.now(),
        campo_modificado="Tarea eliminada",
        valor_anterior=f"Tarea: {tarea.nombre} ({tarea.total})",
        valor_nuevo="Eliminada",
        justificacion=justificacion,
        id_reforma=id_reforma
    ))

    await db.commit()
    return {"msg": "Tarea eliminada correctamente"}


@app.post("/reformas/{id_reforma}/actividades/{id_actividad}/tareas")
async def agregar_tarea_en_reforma(
    id_reforma: uuid.UUID,
    id_actividad: uuid.UUID,
    data: schemas.TareaCreateReforma,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    actividad = await db.get(models.Actividad, id_actividad)
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    reforma = await db.get(models.ReformaPoa, id_reforma)
    if not reforma:
        raise HTTPException(status_code=404, detail="Reforma no encontrada")

    poa = await db.get(models.Poa, actividad.id_poa)
    if not poa or poa.id_poa != reforma.id_poa:
        raise HTTPException(status_code=400, detail="Actividad no corresponde a reforma")

    # Crear nueva tarea
    total = data.cantidad * data.precio_unitario
    nueva_tarea = models.Tarea(
        id_tarea=uuid.uuid4(),
        id_actividad=id_actividad,
        id_detalle_tarea=data.id_detalle_tarea,
        nombre=data.nombre,
        detalle_descripcion=data.detalle_descripcion,
        cantidad=data.cantidad,
        precio_unitario=data.precio_unitario,
        total=total,
        saldo_disponible=total,
        lineaPaiViiv=data.lineaPaiViiv
    )
    db.add(nueva_tarea)

    db.add(models.HistoricoPoa(
        id_historico=uuid.uuid4(),
        id_poa=poa.id_poa,
        id_usuario=usuario.id_usuario,
        fecha_modificacion=datetime.now(),
        campo_modificado="Tarea nueva",
        valor_anterior=None,
        valor_nuevo=f"Tarea: {data.nombre} - Total: {total}",
        justificacion=data.justificacion,
        id_reforma=id_reforma
    ))

    await db.commit()
    return {"msg": "Tarea agregada correctamente"}


@app.get("/poas/{id_poa}/reformas", response_model=List[schemas.ReformaOut])
async def listar_reformas_por_poa(
    id_poa: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.ReformaPoa).where(models.ReformaPoa.id_poa == id_poa)
    )
    return result.scalars().all()


@app.get("/reformas/{id_reforma}", response_model=schemas.ReformaOut)
async def obtener_reforma(
    id_reforma: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    reforma = await db.get(models.ReformaPoa, id_reforma)
    if not reforma:
        raise HTTPException(status_code=404, detail="Reforma no encontrada")
    return reforma

@app.post("/reformas/{id_reforma}/aprobar")
async def aprobar_reforma(
    id_reforma: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # # Validar rol (ejemplo: solo "Director de Investigación")
    # rol = await db.get(models.Rol, usuario.id_rol)
    # if rol.nombre_rol not in ["Director de Investigacion", "Administrador"]:
    #     raise HTTPException(status_code=403, detail="No autorizado para aprobar reformas")

    reforma = await db.get(models.ReformaPoa, id_reforma)
    if not reforma:
        raise HTTPException(status_code=404, detail="Reforma no encontrada")

    reforma.estado_reforma = "Aprobada"
    reforma.fecha_aprobacion = datetime.now()
    reforma.id_usuario_aprueba = usuario.id_usuario

    db.add(reforma)
    await db.commit()

    return {"msg": "Reforma aprobada exitosamente"}

@app.get("/poas/{id_poa}/historial", response_model=List[schemas.HistoricoPoaOut])
async def historial_poa(
    id_poa: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.HistoricoPoa).where(models.HistoricoPoa.id_poa == id_poa).order_by(models.HistoricoPoa.fecha_modificacion.desc())
    )
    return result.scalars().all()


@app.get("/proyectos/{id_proyecto}/poas", response_model=List[schemas.PoaOut])
async def obtener_poas_por_proyecto(
    id_proyecto: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar si el proyecto existe
    result = await db.execute(select(models.Proyecto).where(models.Proyecto.id_proyecto == id_proyecto))
    proyecto = result.scalars().first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Obtener los POAs asociados al proyecto
    result = await db.execute(select(models.Poa).where(models.Poa.id_proyecto == id_proyecto))
    poas = result.scalars().all()
    return poas

@app.post("/transformar_excel/")
async def transformar_archivo_excel(
    file: UploadFile = File(...),
    hoja: str = Form(...),
    db: AsyncSession = Depends(get_db),
    id_poa: uuid.UUID = Form(...),  # Recibir el ID del POA
    confirmacion: bool = Form(False),  # Confirmación del frontend
    usurio: models.Usuario = Depends(get_current_user)
):
    # Validar que el archivo tenga una extensión válida
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Archivo no soportado")

    # Validar que el POA exista
    result = await db.execute(select(models.Poa).where(models.Poa.id_poa == id_poa))
    poa = result.scalars().first()
    if not poa:
        raise HTTPException(status_code=404, detail="POA no encontrado")
    
    # Verificar si ya existen actividades asociadas al POA
    result = await db.execute(select(models.Actividad).where(models.Actividad.id_poa == id_poa))
    actividades_existentes = result.scalars().all()

    # Leer el contenido del archivo
    contenido = await file.read()
    try:
        json_result = transformar_excel(contenido, hoja)

        if actividades_existentes:
            if not confirmacion:
                # Si no hay confirmación, enviar mensaje al frontend
                return {
                    "message": "El POA ya tiene actividades asociadas. ¿Deseas eliminarlas?",
                    "requires_confirmation": True,
                }

            # Si hay confirmación, eliminar las tareas y actividades asociadas
            await eliminar_tareas_y_actividades(id_poa,db)

            # Registrar log de eliminación
            log_elim = models.LogCargaExcel(
                id_log=uuid.uuid4(),
                id_poa=id_poa,
                id_usuario=usurio.id_usuario,
                fecha_carga=datetime.now(),
                mensaje=f"Se eliminaron las actividades , sus tareas y programaciones mensuales asociadas debido a que el usuario decidió reemplazar los datos del POA con un nuevo archivo.",
                nombre_archivo=file.filename,
                hoja=hoja
            )
            db.add(log_elim)
            await db.commit()

        # Lista para registrar errores
        errores = []
        # Crear actividades y tareas en la base de datos
        for actividad in json_result["actividades"]:
            # Crear la actividad
            nueva_actividad = models.Actividad(
                id_actividad=uuid.uuid4(),
                id_poa=id_poa,
                descripcion_actividad=actividad["descripcion_actividad"],
                total_por_actividad=actividad["total_por_actividad"],
                saldo_actividad=actividad["total_por_actividad"],  # Inicialmente igual al total
            )
            db.add(nueva_actividad)
            await db.commit()
            await db.refresh(nueva_actividad)

            
            # Crear las tareas asociadas a la actividad
            for tarea in actividad["tareas"]:
                # Extraer el prefijo numérico (si existe) y el resto del nombre
                match = re.match(r"^(\d+\.\d+)\s+(.*)", tarea["nombre"])
                if match:
                    nombre_sin_prefijo = match.group(2)  # El nombre sin el prefijo (e.g., "Contratación de servicios profesionales")
                else:
                    nombre_sin_prefijo = tarea["nombre"]  # Si no hay prefijo, usar el nombre completo

                # Buscar el id_item_presupuestario
                result = await db.execute(
                    select(models.ItemPresupuestario).where(
                        (models.ItemPresupuestario.codigo == tarea["item_presupuestario"])
                    )
                )
                items_presupuestarios = result.scalars().all()

                if not items_presupuestarios:
                    # Eliminar todo lo subido y lanzar excepción
                    await eliminar_tareas_y_actividades(id_poa, db)
                    raise HTTPException(
                        status_code=400,
                        detail=f"No se guardo nada en la base de datos debido a que: \nNo se encontró el item presupuestario con código '{tarea['item_presupuestario']}' y descripción '{nombre_sin_prefijo}'"
                    )
                nombre_normalizado = normalizar_texto(nombre_sin_prefijo)
                encontrado = False
                for item in items_presupuestarios:
                     # Trae todos los detalles de tarea para ese item
                    result = await db.execute(
                        select(models.DetalleTarea).where(
                            models.DetalleTarea.id_item_presupuestario == item.id_item_presupuestario
                        )
                    )
                    detalles_tarea = result.scalars().all()
                    # Normaliza y compara en Python
                    for detalle in detalles_tarea:
                        
                        nombre_bd = normalizar_texto(detalle.nombre)
                        if nombre_bd == nombre_normalizado:
                            id_detalle_tarea = detalle.id_detalle_tarea
                            encontrado = True
                            break
                        else:
                            continue  # Sigue con el siguiente item si no encontró
                    if encontrado:
                        break
                if not encontrado:  # Si no encontró ningún detalle de tarea
                    await eliminar_tareas_y_actividades(id_poa, db)
                    db.add(log_elim)
                    await db.commit()

                    raise HTTPException(
                        status_code=400,
                        detail=f"No se guardo nada en la base de datos debido a que: \nNo se encontró detalle de tarea para el item presupuestario '{tarea['item_presupuestario']}' y descripción '{nombre_sin_prefijo}'"
                    )
               # Crear la tarea
                nueva_tarea = models.Tarea(
                    id_tarea=uuid.uuid4(),
                    id_actividad=nueva_actividad.id_actividad,
                    id_detalle_tarea=id_detalle_tarea,
                    nombre=tarea["nombre"],
                    detalle_descripcion=tarea["detalle_descripcion"],
                    cantidad=tarea["cantidad"],
                    precio_unitario=tarea["precio_unitario"],
                    total=tarea["total"],
                    saldo_disponible=tarea["total"],  # Inicialmente igual al total
                )
                db.add(nueva_tarea)

                await db.commit()
                await db.refresh(nueva_tarea)  

                # Guardar programaciones mensuales si existen y no es solo "suman"
                prog_ejec = tarea.get("programacion_ejecucion", {})
                for fecha, valor in prog_ejec.items():
                    # ...dentro del for fecha, valor in prog_ejec.items()...
                    if fecha == "suman":
                        continue
                    try:
                        # Extraer el mes y convertirlo a nombre en español
                        mes_num = int(fecha[5:7])  # "2025-03-01..." -> 3
                        meses_es = [
                            "enero", "febrero", "marzo", "abril", "mayo", "junio",
                            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
                        ]
                        mes_nombre = meses_es[mes_num - 1]
                        valor_float = float(valor)
                        nueva_prog = models.ProgramacionMensual(
                            id_programacion=uuid.uuid4(),
                            id_tarea=nueva_tarea.id_tarea,
                            mes=mes_nombre,  # Guardar el nombre del mes
                            valor=valor_float
                        )
                        db.add(nueva_prog)
                    except Exception as e:
                        continue
                await db.commit()
            # Confirmar las tareas después de agregarlas
            await db.commit()

        # Registrar log de carga
        log_crea = models.LogCargaExcel(
            id_log=uuid.uuid4(),
            id_poa=id_poa,
            id_usuario=usurio.id_usuario,
            fecha_carga=datetime.now(),
            # calcula el numero de actividades creadas y se muestra en el mensaje se cargaron ... actividades y sus tareas asociadas desde el archivo {file.filename}."
            mensaje=f"Se cargaron {len(json_result['actividades'])} actividades y sus tareas asociadas desde el archivo {file.filename}.",
            nombre_archivo=file.filename,
            hoja=hoja
        )
        db.add(log_crea)
        await db.commit()
        
        # Retornar el resultado
        if errores:
            return {
                "message": "Actividades y tareas creadas con advertencias",
                "errores": errores,
            }
        else:
            return {"message": "Actividades y tareas creadas exitosamente"}
    except ValueError as e:
        # Capturar errores de formato y lanzar una excepción HTTP
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/item-presupuestario/{id_item}", response_model=schemas.ItemPresupuestarioOut)
async def get_item_presupuestario(
    id_item: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    print(f"ID Item: {id_item}")
    result = await db.execute(select(models.ItemPresupuestario).where(models.ItemPresupuestario.id_item_presupuestario == id_item))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item presupuestario no encontrado")
    return item
  
@app.post("/reporte-poa/")
async def reporte_poa(
    anio: str = Form(...),
    tipo_proyecto: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # se agrega el o los codigos de tipo de proyecto a una lista según el tipo de proyecto 
    codigo_tipo: list[str] = []
    if tipo_proyecto == "Investigacion":
        codigo_tipo.append("PIIF")
        codigo_tipo.append("PIS")
        codigo_tipo.append("PIGR")
        codigo_tipo.append("PIM")
    elif tipo_proyecto == "Vinculacion":
        codigo_tipo.append("PVIF")
    elif tipo_proyecto == "Transferencia":
        codigo_tipo.append("PTT")
    else:
        raise HTTPException(status_code=400, detail="Tipo de proyecto no válido")
    
    # 1. Buscar los tipos de proyecto según el código_tipo
    result = await db.execute(
        select(models.TipoProyecto)
        .where(models.TipoProyecto.codigo_tipo.in_(codigo_tipo))
    )

    
    tipos_proyecto = result.scalars().all()
    ids_tipo_proyecto = [tp.id_tipo_proyecto for tp in tipos_proyecto]
    print("ids_tipo_proyecto:", ids_tipo_proyecto)
    # 2. Buscar proyectos de esos tipos
    result = await db.execute(
        select(models.Proyecto)
        .where(models.Proyecto.id_tipo_proyecto.in_(ids_tipo_proyecto))
    )
    proyectos = result.scalars().all()
    ids_proyecto = [p.id_proyecto for p in proyectos]

    # 3. Buscar POAs de esos proyectos y año
    result = await db.execute(
        select(models.Poa)
        .where(
            models.Poa.id_proyecto.in_(ids_proyecto),
            models.Poa.anio_ejecucion == anio
        )
    )
    poas = result.scalars().all()
    ids_poa = [poa.id_poa for poa in poas]

    # 4. Buscar actividades de esos POAs (total_por_actividad > 0)
    result = await db.execute(
        select(models.Actividad)
        .where(
            models.Actividad.id_poa.in_(ids_poa),
            models.Actividad.total_por_actividad > 0
        )
    )
    actividades = result.scalars().all()
    # Obtener los id_poa que tienen al menos una actividad válida
    poas_con_actividades = set(act.id_poa for act in actividades)

    # Filtrar la lista de poas para solo los que tienen actividades
    poas_filtrados = [poa for poa in poas if poa.id_poa in poas_con_actividades]

    # Agrupar actividades por descripcion_actividad
    actividades_dict = {}
    for act in actividades:
        desc = act.descripcion_actividad
        if desc not in actividades_dict:
            actividades_dict[desc] = {
                "descripcion_actividad": desc,
                "total_por_actividad": 0,
                "ids_actividad": [],
                "tareas": []
            }
        actividades_dict[desc]["total_por_actividad"] += float(act.total_por_actividad)
        actividades_dict[desc]["ids_actividad"].append(act.id_actividad)

    # 5. Buscar tareas de esas actividades (total > 0)
    ids_actividad = [id for acts in actividades_dict.values() for id in acts["ids_actividad"]]
    result = await db.execute(
        select(models.Tarea)
        .where(
            models.Tarea.id_actividad.in_(ids_actividad),
            models.Tarea.total > 0
        )
    )
    tareas = result.scalars().all()

    # Agrupar tareas por id_detalle_tarea dentro de cada actividad
    from collections import defaultdict
    for desc, act in actividades_dict.items():
        tareas_actividad = [t for t in tareas if t.id_actividad in act["ids_actividad"]]
        tareas_grouped = defaultdict(lambda: {
            "cantidad": 0, 
            "total": 0, 
            "nombres": [], 
            "id_detalle_tarea": None, 
            "detalle_descripcion": None,
            "programacion_mensual": defaultdict(float)
            })
        
        
        for tarea in tareas_actividad:
            key = tarea.id_detalle_tarea
            tareas_grouped[key]["cantidad"] += tarea.cantidad
            tareas_grouped[key]["total"] += float(tarea.total)
            tareas_grouped[key]["nombres"].append(tarea.nombre)
            tareas_grouped[key]["id_detalle_tarea"] = tarea.id_detalle_tarea
            tareas_grouped[key]["detalle_descripcion"] = tarea.detalle_descripcion

            # Obtener la programación mensual de esta tarea
            result_prog = await db.execute(
                select(models.ProgramacionMensual).where(models.ProgramacionMensual.id_tarea == tarea.id_tarea)
            )
            programaciones = result_prog.scalars().all()
            for prog in programaciones:
                mes = prog.mes
                valor = float(prog.valor)
                tareas_grouped[key]["programacion_mensual"][mes] += valor


        # Numerar las tareas agrupadas (1.1, 1.2, ...)
        tareas_final = []
        for idx, (id_detalle, datos) in enumerate(tareas_grouped.items(), start=1):
            # Buscar el item presupuestario
            result = await db.execute(
                select(models.DetalleTarea).where(models.DetalleTarea.id_detalle_tarea == id_detalle)
            )
            detalle = result.scalars().first()
            item_presupuestario = None
            if detalle:
                result = await db.execute(
                    select(models.ItemPresupuestario).where(models.ItemPresupuestario.id_item_presupuestario == detalle.id_item_presupuestario)
                )
                item = result.scalars().first()
                if item:
                    item_presupuestario = item.codigo
            # Limpiar el nombre original quitando cualquier prefijo tipo "1.3 ", "4.1 ", etc.
            nombre_original = datos['nombres'][0]
            nombre_limpio = re.sub(r"^\d+(\.\d+)?\s+", "", nombre_original).strip()
            # Extraer el número de la actividad del texto, por ejemplo "(4) ..."
            
            match_num = re.match(r"\((\d+)\)", desc.strip())
            if match_num:
                num_actividad = match_num.group(1)
            else:
                num_actividad = str(list(actividades_dict.keys()).index(desc)+1)

            nombre_tarea = f"{num_actividad}.{idx} {nombre_limpio}"
            # Convertir programacion_mensual a dict simple
            prog_mensual_dict = {mes: round(valor, 2) for mes, valor in datos["programacion_mensual"].items()}

            tareas_final.append({
                "nombre": nombre_tarea,
                "item_presupuestario": item_presupuestario,
                "cantidad": datos["cantidad"],
                "total": datos["total"],
                "programacion_mensual": prog_mensual_dict 
            })
        act["tareas"] = tareas_final

    # Agrupar POAs por codigo_tipo SOLO usando poas_filtrados
    poas_por_tipo = {}
    for tp in tipos_proyecto:
        poas_tp = [
            poa for poa in poas_filtrados
            if any(
                p.id_proyecto == poa.id_proyecto and p.id_tipo_proyecto == tp.id_tipo_proyecto
                for p in proyectos
            )
        ]
        if poas_tp:
            poas_por_tipo[tp.codigo_tipo] = {
                "nombre": tp.nombre,
                "cantidad_poas": len(poas_tp)
            }

    # Al final, antes de armar el JSON:
    def extraer_numero_actividad(desc):
        match = re.match(r"\((\d+)\)", desc.strip())
        return int(match.group(1)) if match else 9999  # 9999 para los que no tengan número
    
    # Eliminar 'ids_actividad' de cada actividad antes de devolver el JSON
    for act in actividades_dict.values():
        if "ids_actividad" in act:
            del act["ids_actividad"]

    actividades_ordenadas = sorted(
        actividades_dict.values(),
        key=lambda act: extraer_numero_actividad(act["descripcion_actividad"])
    ) 
    total_general = sum(act["total_por_actividad"] for act in actividades_ordenadas)
    tipo_proyecto_legible = {
        "Investigacion": "Proyecto de Investigación",
        "Vinculacion": "Proyecto de Vinculación",
        "Transferencia": "Proyecto de Transferencia"
    }.get(tipo_proyecto, tipo_proyecto)
    # Armar el JSON final
    reporte = {
        "anio": anio,
        "tipo_proyecto": tipo_proyecto_legible,
        "numero_poas": len(poas_filtrados), 
        "total_general": total_general,
        "tipos_proyecto_encontrados": [
            {
                "codigo_tipo": codigo,
                "nombre": datos["nombre"],
                "cantidad_poas": datos["cantidad_poas"]
            }
            for codigo, datos in poas_por_tipo.items()
        ],
        "actividades": actividades_ordenadas
    }
    return reporte

@app.post("/reporte-poa/excel/")
async def descargar_excel(
    reporte: dict = Body(...)
):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Reporte POA")
    worksheet.set_column(0, 0, 62.33)  # Columna A (Actividad o Tarea), ancho 40
    worksheet.set_column(1, 1, 22)  # Columna B (Item Presupuestario), ancho 22
    worksheet.set_column(2, 2, 13.50)  # Columna C (Cantidad), ancho 10
    worksheet.set_column(3, 3, 9)  # Columna D (Total Tarea), ancho 15

    # Formatos
    bold = workbook.add_format({'bold': True,'align': 'center', 'valign': 'vcenter'})
    header = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
    subheader = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
    border = workbook.add_format({'border': 1})
    bold_wrap = workbook.add_format({'bold': True, 'text_wrap': True,'align': 'center', 'valign': 'vcenter'})
    
    row = 0

    # Encabezados generales
    worksheet.write(row, 0, f"Año: {reporte['anio']}",bold)
    row += 1
    worksheet.write(row, 0, f"Tipo de Proyecto: {reporte['tipo_proyecto']}",bold)
    row += 1
    worksheet.write(row, 0, f"total de poas: {reporte['numero_poas']}",bold)
    row += 1
    worksheet.write(row, 0, f"total general: ${reporte['total_general']:.2f}", bold)
    row += 2

    

    # Tipos de proyecto encontrados
    worksheet.merge_range(row, 0, row, 2, "tipos_proyecto_encontrados", bold)
    row += 1
    worksheet.write_row(row, 0, ["codigo_tipo", "nombre", "cantidad de poas"], header)
    row += 1
    for tipo in reporte["tipos_proyecto_encontrados"]:
        worksheet.write_row(row, 0, [
            tipo["codigo_tipo"],
            tipo["nombre"],
            tipo["cantidad_poas"]
        ], border)
        row += 1

    row += 2

    # --- Detectar todos los meses presentes en todas las tareas ---
    meses_presentes = set()
    for actividad in reporte["actividades"]:
        for tarea in actividad["tareas"]:
            meses_presentes.update(tarea.get("programacion_mensual", {}).keys())
    # Ordenar meses según el año fiscal ecuatoriano
    meses_orden = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    meses_final = [m for m in meses_orden if m in meses_presentes]


    # --- ACTIVIDADES Y TAREAS ---
    for actividad in reporte["actividades"]:
        worksheet.merge_range(row, 0, row, 3 + len(meses_final), f"Actividad: {actividad['descripcion_actividad']}", bold_wrap)
        row += 1
        # Cabecera dinámica
        cabecera = ["Tarea", "Item Presupuestario", "Cantidad", "Total Tarea"] + [m.capitalize() for m in meses_final]
        worksheet.write_row(row, 0, cabecera, subheader)
        row += 1
        for tarea in actividad["tareas"]:
            fila = [
                tarea["nombre"],
                tarea["item_presupuestario"],
                tarea["cantidad"],
                f"${tarea['total']:.2f}"  # <-- Formato dinero
            ]
            # Agregar valores de cada mes en el orden correcto
            for mes in meses_final:
                valor_mes = tarea.get("programacion_mensual", {}).get(mes, 0)
                fila.append(f"${valor_mes:.2f}")  # <-- Formato dinero
            worksheet.write_row(row, 0, fila, border)
            row += 1
        row += 1  # Espacio entre actividades

    # --- RESUMEN MENSUAL ---
    # Sumar todos los valores de cada mes de todas las tareas
    resumen_mensual = {mes: 0 for mes in meses_final}
    for actividad in reporte["actividades"]:
        for tarea in actividad["tareas"]:
            for mes in meses_final:
                resumen_mensual[mes] += tarea.get("programacion_mensual", {}).get(mes, 0)

    # Escribir resumen mensual
    row += 1
    worksheet.write(row, 0, "RESUMEN MENSUAL", bold)
    row += 1
    worksheet.write_row(row, 0, [m.capitalize() for m in meses_final], header)
    row += 1
    worksheet.write_row(row, 0, [f"${round(resumen_mensual[mes], 2):.2f}" for mes in meses_final], border)
    workbook.close()
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reporte-poa.xlsx"}
    )

@app.post("/reporte-poa/pdf/")
async def descargar_pdf(
    reporte: dict = Body(...)
):
    output = io.BytesIO()
    custom_size = (1500, 900)  # ancho x alto en puntos

    doc = SimpleDocTemplate(output, pagesize=custom_size)
    elements = []
    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleH = styles["Heading2"]
    style_cell = ParagraphStyle('cell', fontSize=9, leading=11)  # Puedes ajustar el tamaño

    # Encabezados generales
    elements.append(Paragraph(f"<b>Año:</b> {reporte['anio']}", styleN))
    elements.append(Paragraph(f"<b>Tipo de Proyecto:</b> {reporte['tipo_proyecto']}", styleN))
    elements.append(Paragraph(f"<b>Total de POAs:</b> {reporte['numero_poas']}", styleN))
    elements.append(Paragraph(f"<b>Total general:</b> ${reporte['total_general']:.2f}", styleN))
    elements.append(Spacer(1, 12))

    # Tipos de proyecto encontrados
    elements.append(Paragraph("Tipos de proyecto encontrados", styleH))
    data = [["Código Tipo", "Nombre", "Cantidad de POAs"]]
    for tipo in reporte["tipos_proyecto_encontrados"]:
        data.append([tipo["codigo_tipo"], tipo["nombre"], tipo["cantidad_poas"]])
    table = Table(data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))
    elements.append(table)
    elements.append(Spacer(1, 16))

    # --- Detectar todos los meses presentes en todas las tareas ---
    meses_presentes = set()
    for actividad in reporte["actividades"]:
        for tarea in actividad["tareas"]:
            meses_presentes.update(tarea.get("programacion_mensual", {}).keys())
    meses_orden = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    meses_final = [m for m in meses_orden if m in meses_presentes]


    # Actividades y tareas
    for actividad in reporte["actividades"]:
        elements.append(Paragraph(f"<b>Actividad: {actividad['descripcion_actividad']}</b>", styleN))
        # Cabecera dinámica
        cabecera = [
            Paragraph("<b>Tarea</b>", style_cell),
            Paragraph("<b>Item Presupuestario</b>", style_cell),
            Paragraph("<b>Cantidad</b>", style_cell),
            Paragraph("<b>Total Tarea</b>", style_cell)
        ] + [Paragraph(f"<b>{m.capitalize()}</b>", style_cell) for m in meses_final]
        data = [cabecera]
        for tarea in actividad["tareas"]:
            fila = [
                Paragraph(str(tarea["nombre"]), style_cell),
                Paragraph(str(tarea["item_presupuestario"]), style_cell),
                Paragraph(str(tarea["cantidad"]), style_cell),
                Paragraph(f"${tarea['total']:.2f}", style_cell)  # <-- Formato dinero
            ]
            for mes in meses_final:    
                valor_mes = tarea.get("programacion_mensual", {}).get(mes, 0)
                fila.append(Paragraph(f"${valor_mes:.2f}", style_cell))  # <-- Formato dinero
            data.append(fila)
            
        table = Table(data, hAlign='LEFT', colWidths=[180, 80, 60, 60] + [50]*len(meses_final))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # --- RESUMEN MENSUAL ---
    resumen_mensual = {mes: 0 for mes in meses_final}
    for actividad in reporte["actividades"]:
        for tarea in actividad["tareas"]:
            for mes in meses_final:
                resumen_mensual[mes] += tarea.get("programacion_mensual", {}).get(mes, 0)

    elements.append(Paragraph("<b>RESUMEN MENSUAL</b>", styleH))
    resumen_data = [[Paragraph(m.capitalize(), style_cell) for m in meses_final]]
    resumen_data.append([Paragraph(f"${round(resumen_mensual[mes], 2):.2f}", style_cell) for mes in meses_final])
    resumen_table = Table(resumen_data, hAlign='LEFT', colWidths=[50]*len(meses_final))
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    elements.append(resumen_table)

    doc.build(elements)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte-poa.pdf"}
    )

@app.get("/logs-carga-excel/")
async def obtener_logs_carga_excel(
    db: AsyncSession = Depends(get_db),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
):
    try:
        query = (
            select(models.LogCargaExcel)
            .options(
                selectinload(models.LogCargaExcel.usuario),
                selectinload(models.LogCargaExcel.poa).selectinload(models.Poa.proyecto)
            )
            .join(models.Usuario)
            .join(models.Poa)
            .join(models.Proyecto)
        )
        # Validar formato de fecha y convertir a datetime
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
                query = query.where(models.LogCargaExcel.fecha_carga >= fecha_inicio_dt)
            except ValueError:
                return JSONResponse(content=[], status_code=200)
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
                # Para incluir todo el día de la fecha_fin, sumamos 1 día y restamos 1 segundo
                from datetime import timedelta
                fecha_fin_dt = fecha_fin_dt + timedelta(days=1) - timedelta(seconds=1)
                query = query.where(models.LogCargaExcel.fecha_carga <= fecha_fin_dt)
            except ValueError:
                return JSONResponse(content=[], status_code=200)
        query = query.order_by(models.LogCargaExcel.fecha_carga.desc())

        result = await db.execute(query)
        logs = result.scalars().all()

        respuesta = []
        for log in logs:
            respuesta.append({
                "fecha_carga": log.fecha_carga.strftime("%Y-%m-%d %H:%M:%S"),
                "usuario": log.usuario.nombre_usuario if log.usuario else "",
                "correo_usuario": log.usuario.email if log.usuario else "",
                "mensaje": log.mensaje,
                "nombre_archivo": log.nombre_archivo,
                "hoja": log.hoja,
                "codigo_poa": log.poa.codigo_poa if log.poa else "",
                "proyecto": log.poa.proyecto.titulo if log.poa and log.poa.proyecto else ""
            })
        return respuesta
    except Exception as e:
        print("Error en logs-carga-excel:", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)

# programacion mensual

@app.post("/programacion-mensual", response_model=schemas.ProgramacionMensualOut)
async def crear_programacion_mensual(
    data: schemas.ProgramacionMensualCreate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    nueva = models.ProgramacionMensual(**data.dict())
    db.add(nueva)
    try:
        await db.commit()
        await db.refresh(nueva)
        return nueva
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Ya existe programación para ese mes y tarea.")

@app.put("/programacion-mensual/{id_programacion}", response_model=schemas.ProgramacionMensualOut)
async def actualizar_programacion_mensual(
    id_programacion: uuid.UUID,
    data: schemas.ProgramacionMensualUpdate,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    result = await db.execute(
        select(models.ProgramacionMensual).where(models.ProgramacionMensual.id_programacion == id_programacion)
    )
    programacion = result.scalars().first()
    if not programacion:
        raise HTTPException(status_code=404, detail="Programación no encontrada")

    programacion.valor = data.valor
    await db.commit()
    await db.refresh(programacion)
    return programacion

@app.get("/tareas/{id_tarea}/programacion-mensual", response_model=List[schemas.ProgramacionMensualOut])
async def obtener_programacion_por_tarea(
    id_tarea: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user)
):
    # Verificar que la tarea exista
    result = await db.execute(select(models.Tarea).where(models.Tarea.id_tarea == id_tarea))
    tarea = result.scalars().first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    result = await db.execute(
        select(models.ProgramacionMensual).where(models.ProgramacionMensual.id_tarea == id_tarea)
    )
    return result.scalars().all()
