from datetime import datetime,timezone
from fastapi import FastAPI, Depends, HTTPException,UploadFile, File, Form
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
from fastapi.responses import JSONResponse
from app.scripts.transformador_excel import transformar_excel
from app.utils import eliminar_tareas_y_actividades


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

    return {"msg": f"{len(actividades)} actividades creadas correctamente"}


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

    total = data.precio_unitario * data.cantidad

    nueva_tarea = models.Tarea(
        id_tarea=uuid.uuid4(),
        id_actividad=id_actividad,
        id_detalle_tarea=data.id_detalle_tarea,
        nombre=data.nombre,
        detalle_descripcion=data.detalle_descripcion,
        cantidad=data.cantidad,
        precio_unitario=data.precio_unitario,
        total=total,
        saldo_disponible=total
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
    campos_auditar = ["cantidad", "precio_unitario", "total", "saldo_disponible"]

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
        saldo_disponible=total
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
                        models.ItemPresupuestario.codigo == tarea["item_presupuestario"]
                        and models.ItemPresupuestario.descripcion == nombre_sin_prefijo
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
                
                # Tomar el primer id_item_presupuestario encontrado
                id_item_presupuestario = items_presupuestarios[0].id_item_presupuestario

                # Buscar el id_detalle_tarea
                result = await db.execute(
                    select(models.DetalleTarea).where(
                        models.DetalleTarea.id_item_presupuestario == id_item_presupuestario
                    )
                )
                detalles_tarea = result.scalars().all()

                if not detalles_tarea:
                    # Eliminar todo lo subido y lanzar excepción
                    await eliminar_tareas_y_actividades(id_poa, db)
                    raise HTTPException(
                        status_code=400,
                        detail=f"No se guardo nada en la base de datos debido a que: \n No se encontró detalle de tarea para el item presupuestario '{tarea['item_presupuestario']}' en la tarea '{tarea['nombre']}'"
                    )

                # Tomar el primer id_detalle_tarea encontrado
                id_detalle_tarea = detalles_tarea[0].id_detalle_tarea

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

            # Confirmar las tareas después de agregarlas
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