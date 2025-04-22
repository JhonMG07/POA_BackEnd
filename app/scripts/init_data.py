import uuid
from app.database import SessionLocal
from app.models import (
    Rol, 
    Permiso, 
    PermisoRol, 
    TipoPOA, 
    TipoProyecto, 
    EstadoProyecto, 
    EstadoPOA, 
    LimiteProyectosTipo,
    ItemPresupuestario,
    DetalleTarea,
    TipoPoaDetalleTarea
    )

from sqlalchemy.future import select
from sqlalchemy import and_

# Esta función sirve para llenar la base de datos con datos iniciales
async def seed_all_data():
    async with SessionLocal() as db:
        """
        Llenar roles deseados
        """
        # Verificar roles existentes
        result = await db.execute(select(Rol.nombre_rol))
        roles_existentes = set(result.scalars().all())

        roles_deseados = [
            {"nombre_rol": "Administrador", "descripcion": "Acceso completo al sistema"},
            {"nombre_rol": "Director de Investigacion", "descripcion": "Director de investigacion con permisos para gestionar proyectos y POAs"},
            {"nombre_rol": "Director de Proyecto", "descripcion": "Director de proyecto con permisos para gestionar POAs"},
            {"nombre_rol": "Director de reformas", "descripcion": "Usuario encargado de aprobación de presupuestos y reformas"},
        ]

        nuevos_roles = [
            Rol(id_rol=uuid.uuid4(), nombre_rol=r["nombre_rol"], descripcion=r["descripcion"])
            for r in roles_deseados if r["nombre_rol"] not in roles_existentes
        ]

        if nuevos_roles:
            db.add_all(nuevos_roles)

        """
        Llenar permisos deseados
        """
        # Verificar permisos existentes
        result = await db.execute(select(Permiso.codigo_permiso))
        codigos_existentes = set(result.scalars().all())
        permisos_deseados = [
            {"codigo": "PROY_CREATE", "desc": "Crear proyectos", "modulo": "Proyectos", "accion": "Crear"},
            {"codigo": "PROY_READ", "desc": "Ver proyectos", "modulo": "Proyectos", "accion": "Leer"},
            {"codigo": "PROY_UPDATE", "desc": "Modificar proyectos", "modulo": "Proyectos", "accion": "Actualizar"},
            {"codigo": "PROY_DELETE", "desc": "Eliminar proyectos", "modulo": "Proyectos", "accion": "Eliminar"},
            {"codigo": "POA_CREATE", "desc": "Crear POAs", "modulo": "POA", "accion": "Crear"},
            {"codigo": "POA_READ", "desc": "Ver POAs", "modulo": "POA", "accion": "Leer"},
            {"codigo": "POA_UPDATE", "desc": "Modificar POAs", "modulo": "POA", "accion": "Actualizar"},
            {"codigo": "POA_DELETE", "desc": "Eliminar POAs", "modulo": "POA", "accion": "Eliminar"},
            {"codigo": "REFORM_APPROVE", "desc": "Aprobar reformas", "modulo": "Reformas", "accion": "Aprobar"},
            {"codigo": "BUDGET_EXEC", "desc": "Registrar ejecución presupuestaria", "modulo": "Presupuesto", "accion": "Ejecutar"},
        ]

        nuevos_permisos = [
            Permiso(
                id_permiso=uuid.uuid4(),
                codigo_permiso=p["codigo"],
                descripcion=p["desc"],
                modulo=p["modulo"],
                accion=p["accion"]
            )
            for p in permisos_deseados if p["codigo"] not in codigos_existentes
        ]

        if nuevos_permisos:
            db.add_all(nuevos_permisos)

        await db.commit()  # Importante antes de buscar datos recién insertados

        """
        Asignar permisos al rol "Administrador"
        Se le asignaron todos los permisos al rol "Administrador" para que tenga acceso completo al sistema.
        """

        # Obtener el rol "Administrador"
        result_rol = await db.execute(select(Rol).where(Rol.nombre_rol == "Administrador"))
        rol_admin = result_rol.scalars().first()

        # Obtener todos los permisos
        result_permisos = await db.execute(select(Permiso))
        todos_los_permisos = result_permisos.scalars().all()

        # Verificar permisos ya asignados al rol administrador
        result_asignados = await db.execute(select(PermisoRol.id_permiso, PermisoRol.id_rol))
        ya_asignados = {(r.id_permiso, r.id_rol) for r in result_asignados.all()}

        nuevos_permisos_rol = [
            PermisoRol(
                id_permiso_rol=uuid.uuid4(),
                id_rol=rol_admin.id_rol,
                id_permiso=permiso.id_permiso
            )
            for permiso in todos_los_permisos
            if (permiso.id_permiso, rol_admin.id_rol) not in ya_asignados
        ]

        if nuevos_permisos_rol:
            db.add_all(nuevos_permisos_rol)

        await db.commit()
    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar registros en TIPO_POA si no existen
    # ─────────────────────────────────────────────────────────────────────────────
    result = await db.execute(select(TipoPOA.codigo_tipo))
    poas_existentes = set(result.scalars().all())

    tipos_poa = [
        {"codigo": "PIIF", "nombre": "Interno con financiamiento", "desc": "Proyectos internos que requieren cierto monto de dinero", "duracion": 12, "periodos": 1, "presupuesto": 6000},
        {"codigo": "PIS", "nombre": "Semilla con financiamiento", "desc": "Proyectos semilla que requieren cierto monto de dinero", "duracion": 18, "periodos": 2, "presupuesto": 15000},
        {"codigo": "PIGR", "nombre": "Grupales", "desc": "Proyectos grupales que requieren cierto monto de dinero", "duracion": 24, "periodos": 2, "presupuesto": 60000},
        {"codigo": "PIM", "nombre": "Multidisciplinarios", "desc": "Proyectos que incluyen varias disciplinas que requieren cierto monto de dinero", "duracion": 36, "periodos": 3, "presupuesto": 120000},
        {"codigo": "PVIF", "nombre": "Vinculación con financiaminento", "desc": "Proyectos de vinculación con la sociedad que requieren cierto monto de dinero", "duracion": 18, "periodos": 2, "presupuesto": 6000},
        {"codigo": "PTT", "nombre": "Transferencia tecnológica", "desc": "Proyectos de transferencia tecnológica y uso de equipamiento", "duracion": 18, "periodos": 2, "presupuesto": 15000},
        {"codigo": "PVIS", "nombre": "Vinculación sin financiaminento", "desc": "Proyectos de vinculación con la sociedad sin necesidad de dinero", "duracion": 12, "periodos": 1, "presupuesto": 0},
    ]

    nuevos_poa = [
        TipoPOA(
            id_tipo_poa=uuid.uuid4(),
            codigo_tipo=poa["codigo"],
            nombre=poa["nombre"],
            descripcion=poa["desc"],
            duracion_meses=poa["duracion"],
            cantidad_periodos=poa["periodos"],
            presupuesto_maximo=poa["presupuesto"],
        )
        for poa in tipos_poa if poa["codigo"] not in poas_existentes
    ]

    if nuevos_poa:
        db.add_all(nuevos_poa)
        await db.commit()

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar en TIPO_PROYECTO duplicando de TIPO_POA
    # ─────────────────────────────────────────────────────────────────────────────
    result = await db.execute(select(TipoProyecto.codigo_tipo))
    proyectos_existentes = set(result.scalars().all())

    result = await db.execute(select(TipoPOA))
    tipos_poa_guardados = result.scalars().all()

    nuevos_proyectos = [
        TipoProyecto(
            id_tipo_proyecto=poa.id_tipo_poa,
            codigo_tipo=poa.codigo_tipo,
            nombre=poa.nombre,
            descripcion=poa.descripcion,
            duracion_meses=poa.duracion_meses,
            cantidad_periodos=poa.cantidad_periodos,
            presupuesto_maximo=poa.presupuesto_maximo,
        )
        for poa in tipos_poa_guardados if poa.codigo_tipo not in proyectos_existentes
    ]

    if nuevos_proyectos:
        db.add_all(nuevos_proyectos)
        await db.commit()

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar en ESTADO_PROYECTO
    # ─────────────────────────────────────────────────────────────────────────────
    result = await db.execute(select(EstadoProyecto.nombre))
    estados_existentes = set(result.scalars().all())

    estados = [
        {"nombre": "Planificación", "desc": "Proyecto en fase de planificación inicial", "edita": True},
        {"nombre": "En Ejecución", "desc": "Proyecto en desarrollo activo", "edita": True},
        {"nombre": "Suspendido", "desc": "Proyecto temporalmente detenido", "edita": False},
        {"nombre": "Completado", "desc": "Proyecto finalizado exitosamente", "edita": False},
        {"nombre": "Cancelado", "desc": "Proyecto interrumpido antes de su conclusión", "edita": False},
    ]

    nuevos_estados = [
        EstadoProyecto(
            id_estado_proyecto=uuid.uuid4(),
            nombre=e["nombre"],
            descripcion=e["desc"],
            permite_edicion=e["edita"]
        )
        for e in estados if e["nombre"] not in estados_existentes
    ]

    if nuevos_estados:
        db.add_all(nuevos_estados)
        await db.commit()

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar en ESTADO_POA
    # ─────────────────────────────────────────────────────────────────────────────
    result = await db.execute(select(EstadoPOA.nombre))
    estado_poa_existentes = set(result.scalars().all())

    estado_poas = [
        {"nombre": "Ingresado", "desc": "El director del proyecto ingresa el POA, en este estado todavía se puede editarlo"},
        {"nombre": "Validado", "desc": "El director de investigación emite comentarios correctivos del POA y es enviado a Ejecucion o denuevo a Ingresado"},
        {"nombre": "Ejecucion", "desc": "El POA a sido aprobado para ejecución y todos puede leerlo, el sistema controla los saldos, el siguinete paso es Reforma o Finalizado"},
        {"nombre": "En Reforma", "desc": "El director del proyecto solicita una reforma de tareas o actividades que todavia tienen saldo y es enviado a Validado"},
        {"nombre": "Finalizado", "desc": "POA finalizado y cerrado"}
    ]

    nuevos_estado_poas = [
        EstadoPOA(
            id_estado_poa=uuid.uuid4(),
            nombre=p["nombre"],
            descripcion=p["desc"]
        )
        for p in estado_poas if p["nombre"] not in estado_poa_existentes
    ]

    if nuevos_estado_poas:
        db.add_all(nuevos_estado_poas)
        await db.commit()

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar en LIMITE_PROYECTOS_TIPO para 'Vinculación sin financiaminento'
    # ─────────────────────────────────────────────────────────────────────────────

    # Validar si ya existe
    subquery = select(TipoProyecto.id_tipo_proyecto).where(TipoProyecto.nombre == "Vinculación sin financiaminento")
    tipo_proyecto_id = (await db.execute(subquery)).scalar_one_or_none()

    if tipo_proyecto_id:
        result = await db.execute(
            select(LimiteProyectosTipo).where(LimiteProyectosTipo.id_tipo_proyecto == tipo_proyecto_id)
        )
        ya_existe = result.scalars().first()

        if not ya_existe:
            limite = LimiteProyectosTipo(
                id_limite=uuid.uuid4(),
                id_tipo_proyecto=tipo_proyecto_id,
                limite_proyectos=2,
                descripcion="Máximo 2 proyectos de vinculación sin financiamiento simultáneos"
            )
            db.add(limite)
            await db.commit()

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar en ITEM_PRESUPUESTARIO (permitiendo duplicidad de código con distintas descripciones)
    # ─────────────────────────────────────────────────────────────────────────────


    items = [
        {"codigo": "730606", "nombre": "Asistente de investigación", "descripcion": "Contratación de servicios profesionales"},
        {"codigo": "710502", "nombre": "Ayudante de investigación - RMU", "descripcion": "Contratación de ayudantes de investigación RMU"},
        {"codigo": "710601", "nombre": "Ayudante de investigación - IESS", "descripcion": "Contratación de ayudantes de investigación IESS"},
        {"codigo": "840107", "nombre": "Equipo informático", "descripcion": "Adquisición de equipos informáticos"},
        {"codigo": "840104", "nombre": "Equipo especializado / maquinaria", "descripcion": "Adquisición de equipos especializados y maquinaria"},
        {"codigo": "730829", "nombre": "Insumos", "descripcion": "Adquisición de insumos"},
        {"codigo": "730819", "nombre": "Reactivos", "descripcion": "Adquisición de reactivos"},
        {"codigo": "730204", "nombre": "Publicaciones / impresión", "descripcion": "Pago de publicaciones o impresión 3D"},
        {"codigo": "730612", "nombre": "Inscripción eventos", "descripcion": "Pago de inscripción para eventos académicos"},
        {"codigo": "730303", "nombre": "Viáticos - interior", "descripcion": "Viáticos a nivel nacional"},
        {"codigo": "730301", "nombre": "Pasajes interior", "descripcion": "Pasajes aéreos al interior"},
        {"codigo": "730301", "nombre": "Movilización interior", "descripcion": "Movilización terrestre al interior"},
        {"codigo": "730609", "nombre": "Laboratorios", "descripcion": "Análisis en laboratorios"},
        {"codigo": "840109", "nombre": "Literatura", "descripcion": "Adquisición de literatura especializada"},
        {"codigo": "730304", "nombre": "Viáticos - exterior", "descripcion": "Viáticos a nivel internacional"},
        {"codigo": "730302", "nombre": "Pasajes exterior", "descripcion": "Pasajes aéreos al exterior"},
        {"codigo": "730302", "nombre": "Movilización exterior", "descripcion": "Movilización terrestre al exterior"},
        {"codigo": "730302", "nombre": "Pasajes para delegados", "descripcion": "Pasajes aéreos para atencion de delegados"},
        {"codigo": "730307", "nombre": "Hospedaje delegados", "descripcion": "Hospedaje y alimentación para atención a delegados"},
        {"codigo": "770102", "nombre": "Viáticos al interior", "descripcion": "Viáticos al interior"},
        {"codigo": "730601", "nombre": "Servicios profesionales", "descripcion": "Contratación de servicios profesionales para la elaboracion de diseño, construccion, implementacion, seguimiento y mejora continua de prototipos"},

    ]

    nuevos_items = []

    for item in items:
        result = await db.execute(
            select(ItemPresupuestario).where(
                and_(
                    ItemPresupuestario.codigo == item["codigo"],
                    ItemPresupuestario.descripcion == item["descripcion"]
                )
            )
        )
        existente = result.scalars().first()
        if not existente:
            nuevos_items.append(
                ItemPresupuestario(
                    id_item_presupuestario=uuid.uuid4(),
                    codigo=item["codigo"],
                    nombre=item["nombre"],
                    descripcion=item["descripcion"]
                )
            )

    if nuevos_items:
        db.add_all(nuevos_items)
        await db.commit()
        print(f"Se insertaron {len(nuevos_items)} ítems presupuestarios nuevos.")
    else:
        print("Todos los ítems presupuestarios ya existen con su descripción.")

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar DETALLE_TAREA asociados a los ITEM_PRESUPUESTARIO ya existentes
    # ─────────────────────────────────────────────────────────────────────────────


    detalles = [
        {"codigo": "730606", "nombre": "Contratación de servicios profesionales", "descripcion": "Asistente de investigación"},
        {"codigo": "710502", "nombre": "RMU 1", "descripcion": "Ayudante de investigación con RMU"},
        {"codigo": "710601", "nombre": "IESS 1", "descripcion": "Ayudante de investigación con IESS"},
        {"codigo": "840107", "nombre": "Equipos informáticos", "descripcion": "Compra de laptops y PCs"},
        {"codigo": "840104", "nombre": "Equipos especializados", "descripcion": "Maquinaria y herramientas especializadas"},
        {"codigo": "730829", "nombre": "Insumos varios", "descripcion": "Materiales consumibles"},
        {"codigo": "730819", "nombre": "Reactivos químicos", "descripcion": "Reactivos de laboratorio"},
        {"codigo": "730204", "nombre": "Pago publicaciones", "descripcion": "Gastos por publicación de artículos"},
        {"codigo": "730612", "nombre": "Pago inscripción", "descripcion": "Inscripciones a congresos o eventos"},
        {"codigo": "730303", "nombre": "Viáticos internos", "descripcion": "Viáticos dentro del país"},
        {"codigo": "730301", "nombre": "Pasajes interiores", "descripcion": "Pasajes aéreos dentro del país"},
        {"codigo": "730301", "nombre": "Movilización interna", "descripcion": "Transporte terrestre nacional"},
        {"codigo": "730609", "nombre": "Análisis laboratorio", "descripcion": "Pruebas en laboratorios externos"},
        {"codigo": "840109", "nombre": "Compra de libros", "descripcion": "Literatura técnica especializada"},
        {"codigo": "730304", "nombre": "Viáticos al exterior", "descripcion": "Viáticos para viajes internacionales"},
        {"codigo": "730302", "nombre": "Pasajes exteriores", "descripcion": "Pasajes aéreos internacionales"},
        {"codigo": "730302", "nombre": "Movilización exterior", "descripcion": "Transporte terrestre internacional"},
        {"codigo": "730302", "nombre": "Pasajes delegados", "descripcion": "Pasajes para investigadores externos"},
        {"codigo": "730307", "nombre": "Hospedaje delegados", "descripcion": "Hospedaje y comida para delegados"},
        {"codigo": "770102", "nombre": "Viáticos al interior", "descripcion": "Viáticos al interior"},
        {"codigo": "730601", "nombre": "Servicios profesionales", "descripcion": "Contratación de servicios profesionales para la elaboracion de diseño, construccion, implementacion, seguimiento y mejora continua de prototipos"},
    ]

    nuevos_detalles = []

    for d in detalles:
        # Buscar el ítem presupuestario asociado
        result = await db.execute(
            select(ItemPresupuestario).where(
                and_(
                    ItemPresupuestario.codigo == d["codigo"],
                )
            )
        )
        item = result.scalars().first()
        if item:
            # Verificar si ya existe el detalle
            result = await db.execute(
                select(DetalleTarea).where(
                    and_(
                        DetalleTarea.id_item_presupuestario == item.id_item_presupuestario,
                        DetalleTarea.nombre == d["nombre"]
                    )
                )
            )
            existe = result.scalars().first()
            if not existe:
                nuevos_detalles.append(
                    DetalleTarea(
                        id_detalle_tarea=uuid.uuid4(),
                        id_item_presupuestario=item.id_item_presupuestario,
                        nombre=d["nombre"],
                        descripcion=d["descripcion"],
                        caracteristicas=None
                    )
                )

    if nuevos_detalles:
        db.add_all(nuevos_detalles)
        await db.commit()
        print(f"Se insertaron {len(nuevos_detalles)} DETALLE_TAREA.")
    else:
        print("Todos los DETALLE_TAREA ya existen.")


    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar relaciones TIPO_POA_DETALLE_TAREA
    # ─────────────────────────────────────────────────────────────────────────────

    # Obtener el tipo POA por nombre -> PIM
    result = await db.execute(select(TipoPOA).where(TipoPOA.codigo_tipo == "PIM"))
    tipo_poa = result.scalars().first()
    detalles_PIM = [
        {"codigo": "730606", "nombre": "Contratación de servicios profesionales", "descripcion": "Asistente de investigación"},
        {"codigo": "710502", "nombre": "RMU 1", "descripcion": "Ayudante de investigación con RMU"},
        {"codigo": "710601", "nombre": "IESS 1", "descripcion": "Ayudante de investigación con IESS"},
        {"codigo": "840107", "nombre": "Equipos informáticos", "descripcion": "Compra de laptops y PCs"},
        {"codigo": "840104", "nombre": "Equipos especializados", "descripcion": "Maquinaria y herramientas especializadas"},
        {"codigo": "730829", "nombre": "Insumos varios", "descripcion": "Materiales consumibles"},
        {"codigo": "730819", "nombre": "Reactivos químicos", "descripcion": "Reactivos de laboratorio"},
        {"codigo": "730204", "nombre": "Pago publicaciones", "descripcion": "Gastos por publicación de artículos"},
        {"codigo": "730612", "nombre": "Pago inscripción", "descripcion": "Inscripciones a congresos o eventos"},
        {"codigo": "730303", "nombre": "Viáticos internos", "descripcion": "Viáticos dentro del país"},
        {"codigo": "730301", "nombre": "Pasajes interiores", "descripcion": "Pasajes aéreos dentro del país"},
        {"codigo": "730301", "nombre": "Movilización interna", "descripcion": "Transporte terrestre nacional"},
        {"codigo": "730609", "nombre": "Análisis laboratorio", "descripcion": "Pruebas en laboratorios externos"},
        {"codigo": "840109", "nombre": "Compra de libros", "descripcion": "Literatura técnica especializada"},
        {"codigo": "730304", "nombre": "Viáticos al exterior", "descripcion": "Viáticos para viajes internacionales"},
        {"codigo": "730302", "nombre": "Pasajes exteriores", "descripcion": "Pasajes aéreos internacionales"},
        {"codigo": "730302", "nombre": "Movilización exterior", "descripcion": "Transporte terrestre internacional"},
        {"codigo": "730302", "nombre": "Pasajes delegados", "descripcion": "Pasajes para investigadores externos"},
        {"codigo": "730601", "nombre": "Servicios profesionales", "descripcion": "Contratación de servicios profesionales para la elaboracion de diseño, construccion, implementacion, seguimiento y mejora continua de prototipos"},
        
    ]
    if tipo_poa:
        nuevos = 0
        for detalle in detalles_PIM:
            result = await db.execute(
                select(DetalleTarea)
                .join(ItemPresupuestario)
                .where(
                    ItemPresupuestario.codigo == detalle["codigo"],
                    DetalleTarea.nombre == detalle["nombre"]
                )
            )
            detalle_obj = result.scalars().first()

            if not detalle_obj:
                print(f"No se encontró DetalleTarea con código {detalle['codigo']} y nombre {detalle['nombre']}")
                continue

            result = await db.execute(
                select(TipoPoaDetalleTarea).where(
                    TipoPoaDetalleTarea.id_tipo_poa == tipo_poa.id_tipo_poa,
                    TipoPoaDetalleTarea.id_detalle_tarea == detalle_obj.id_detalle_tarea
                )
            )
            ya_existe = result.scalars().first()

            if not ya_existe:
                relacion = TipoPoaDetalleTarea(
                    id_tipo_poa_detalle_tarea=uuid.uuid4(),
                    id_tipo_poa=tipo_poa.id_tipo_poa,
                    id_detalle_tarea=detalle_obj.id_detalle_tarea
                )
                db.add(relacion)
                nuevos += 1

        await db.commit()
        print(f"Asociaciones nuevas: {nuevos}")
    else:
        print("No se encontró el TIPO_POA con código 'PIM'")

    # Obtener el tipo POA por nombre -> PTT
    result = await db.execute(select(TipoPOA).where(TipoPOA.codigo_tipo == "PTT"))
    tipo_poa = result.scalars().first()
    detalles_PTT = [
        {"codigo": "730606", "nombre": "Contratación de servicios profesionales", "descripcion": "Asistente de investigación"},
        {"codigo": "840104", "nombre": "Equipos especializados", "descripcion": "Maquinaria y herramientas especializadas"},
        {"codigo": "730829", "nombre": "Insumos varios", "descripcion": "Materiales consumibles"},
        {"codigo": "730204", "nombre": "Pago publicaciones", "descripcion": "Gastos por publicación de artículos"},
        {"codigo": "730303", "nombre": "Viáticos internos", "descripcion": "Viáticos dentro del país"},
        {"codigo": "730301", "nombre": "Pasajes interiores", "descripcion": "Pasajes aéreos dentro del país"},
        {"codigo": "730301", "nombre": "Movilización interna", "descripcion": "Transporte terrestre nacional"},
        {"codigo": "770102", "nombre": "Viáticos al interior", "descripcion": "Viáticos al interior"},
        {"codigo": "730601", "nombre": "Servicios profesionales", "descripcion": "Contratación de servicios profesionales para la elaboracion de diseño, construccion, implementacion, seguimiento y mejora continua de prototipos"},
    ]
    if tipo_poa:
        nuevos = 0
        for detalle in detalles_PTT:
            result = await db.execute(
                select(DetalleTarea)
                .join(ItemPresupuestario)
                .where(
                    ItemPresupuestario.codigo == detalle["codigo"],
                    DetalleTarea.nombre == detalle["nombre"]
                )
            )
            detalle_obj = result.scalars().first()

            if not detalle_obj:
                print(f"No se encontró DetalleTarea con código {detalle['codigo']} y nombre {detalle['nombre']}")
                continue

            result = await db.execute(
                select(TipoPoaDetalleTarea).where(
                    TipoPoaDetalleTarea.id_tipo_poa == tipo_poa.id_tipo_poa,
                    TipoPoaDetalleTarea.id_detalle_tarea == detalle_obj.id_detalle_tarea
                )
            )
            ya_existe = result.scalars().first()

            if not ya_existe:
                relacion = TipoPoaDetalleTarea(
                    id_tipo_poa_detalle_tarea=uuid.uuid4(),
                    id_tipo_poa=tipo_poa.id_tipo_poa,
                    id_detalle_tarea=detalle_obj.id_detalle_tarea
                )
                db.add(relacion)
                nuevos += 1

        await db.commit()
        print(f"Asociaciones nuevas: {nuevos}")
    else:
        print("No se encontró el TIPO_POA con código 'PIM'")
