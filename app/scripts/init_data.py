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
        {"nombre": "Aprobado", "desc": "El proyecto ha sido revisado y validado por las instancias correspondientes, y está autorizado para iniciar su ejecución.", "edita": True},
        {"nombre": "En Ejecución", "desc": "El proyecto está actualmente en desarrollo, cumpliendo con las actividades planificadas dentro de los plazos establecidos.", "edita": True},
        {"nombre": "En Ejecución-Prorroga técnica", "desc": "El proyecto sigue en ejecución, pero se le ha otorgado una extensión de tiempo debido a causas justificadas de tipo técnico.", "edita": True},
        {"nombre": "Suspendido", "desc": "La ejecución del proyecto ha sido detenida temporalmente por motivos administrativos, financieros o técnicos, y está a la espera de una resolución.", "edita": False},
        {"nombre": "Cerrado", "desc": "El proyecto ha finalizado completamente, cumpliendo con los objetivos y requisitos establecidos sin observaciones relevantes.", "edita": False},
        {"nombre": "Cerrado con Observaciones", "desc": "El proyecto fue finalizado, pero durante su ejecución se identificaron observaciones menores que no comprometieron gravemente sus resultados.", "edita": False},
        {"nombre": "Cerrado con Incumplimiento", "desc": "El proyecto fue finalizado, pero no cumplió con los objetivos, metas o requerimientos establecidos, y presenta fallas sustanciales.", "edita": False},
        {"nombre": "No Ejecutado", "desc": "El proyecto fue aprobado, pero no se inició su ejecución por falta de recursos, cambios de prioridades u otras razones justificadas.", "edita": False},
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

    # Verificar que todos los ítems presupuestarios tengan asignada una tarea
    # nombre: PIM; PTT; PVIF (resto de POA's)
    items_codigo = [
        {"codigo": "730606", "nombre": "1.1; 1.1; 1.1", "descripcion": "Codigo único"},
        {"codigo": "710502", "nombre": "2.1; 0; 2.1", "descripcion": "Codigo único"},
        {"codigo": "710601", "nombre": "2.2; 0; 2.2", "descripcion": "Codigo único"},
        {"codigo": "840107", "nombre": "3.1; 7.1; 3.1", "descripcion": "Depende de una condición"},
        {"codigo": "731407", "nombre": "3.1; 7.1; 3.1", "descripcion": "Depende de una condición"},
        {"codigo": "840104", "nombre": "4.1; 2.1; 4.1", "descripcion": "Depende de una condición"},
        {"codigo": "731404", "nombre": "4.1; 2.1; 4.1", "descripcion": "Depende de una condición"},
        {"codigo": "730829", "nombre": "5.1; 3.1; 5.1", "descripcion": "Codigo único"},
        {"codigo": "730819", "nombre": "5.2; 0; 5.2", "descripcion": "Codigo único"},
        {"codigo": "730204", "nombre": "6.1; 4.1; 6.1", "descripcion": "Codigo único"},
        {"codigo": "730612", "nombre": "7.1; 0; 7.1", "descripcion": "Codigo único"},
        {"codigo": "730303", "nombre": "8.1; 5.1; 8.1", "descripcion": "Codigo único"},
        {"codigo": "730301", "nombre": "(8.2 8.3); 5.2; 8.2", "descripcion": "Aplica en 2 tareas del mismo POA"},
        {"codigo": "730609", "nombre": "9.1; 0; 0", "descripcion": "Codigo único"},
        {"codigo": "840109", "nombre": "10.1; 0; 0", "descripcion": "Depende de una condición"},
        {"codigo": "731409", "nombre": "10.1; 0; 0", "descripcion": "Depende de una condición"},
        {"codigo": "730304", "nombre": "11.1; 0; 0", "descripcion": "Codigo único"},
        {"codigo": "730302", "nombre": "(11.2 11.3 12.1); 0; 0", "descripcion": "Aplica en 3 tareas del mismo POA"},
        {"codigo": "730307", "nombre": "12.2; 0; 0", "descripcion": "Codigo único"},
        {"codigo": "770102", "nombre": "0; 8.1; 0", "descripcion": "Codigo único"},
        {"codigo": "730601", "nombre": "0; 6.1; 0", "descripcion": "Codigo único"},
        {"codigo": "730207", "nombre": "0; 0; 6.2", "descripcion": "Codigo único"},
    ]

    nuevos_items = []

    for item in items_codigo:
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
        # Detalles para PIM
        {
            "codigo": "730606",
            "nombre": "Contratación de servicios profesionales",
            "descripcion": "Asistente de investigación",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730606",
            "nombre": "Contratación de servicios profesionales",
            "descripcion": "Servicios profesionales 1",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730606",
            "nombre": "Contratación de servicios profesionales",
            "descripcion": "Servicios profesionales 2",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730606",
            "nombre": "Contratación de servicios profesionales",
            "descripcion": "Servicios profesionales 3",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "710502",
            "nombre": "Contratación de ayudantes de investigación RMU",
            "descripcion": "",
            "tipos_poa": ["PIM", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "710601",
            "nombre": "Contratación de ayudantes de investigación IESS",
            "descripcion": "",
            "tipos_poa": ["PIM", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        # Casos #ojo - equipos informáticos (dos códigos alternativos)
        {
            "codigo": "840107",
            "nombre": "Adquisición de equipos informáticos",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "731407",
            "nombre": "Adquisición de equipos informáticos", 
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        # Casos #ojo - equipos especializados (dos códigos alternativos)
        {
            "codigo": "840104",
            "nombre": "Adquisición de equipos especializados y maquinaria",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "731404",
            "nombre": "Adquisición de equipos especializados y maquinaria",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730829",
            "nombre": "Adquisición de insumos",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730819",
            "nombre": "Adquisición de reactivos",
            "descripcion": "",
            "tipos_poa": ["PIM", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730204",
            "nombre": "Solicitud de autorización para el pago de publicaciones",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "730612",
            "nombre": "Solicitud de pago de inscripción para participación en eventos académicos",
            "descripcion": "",
            "tipos_poa": ["PIM", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730303",
            "nombre": "Viáticos al interior",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730301",
            "nombre": "Pasajes aéreos al interior",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730301",
            "nombre": "Movilización al interior",
            "descripcion": "",
            "tipos_poa": ["PIM", "PTT", "PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730609",
            "nombre": "Análisis de laboratorios",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        # Casos #ojo - literatura especializada
        {
            "codigo": "840109",
            "nombre": "Adquisición de literatura especializada",
            "descripcion": "(valor mas de 100 y durabilidad)",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "731409",
            "nombre": "Adquisición de literatura especializada",
            "descripcion": "(valor mas de 100 y durabilidad)",
            "tipos_poa": ["PIM"]
        },
        # Detalles específicos para PIM
        {
            "codigo": "730304",
            "nombre": "Viáticos al exterior",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "730302",
            "nombre": "Pasajes aéreos al exterior",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "730302",
            "nombre": "Movilización al exterior",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "730302",
            "nombre": "Pasajes aéreos para atención a delegados (investigadores colaboradores externos)",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        {
            "codigo": "730307",
            "nombre": "Servicio de hospedaje y alimentación para atención a delegados (investigadores colaboradores externos)",
            "descripcion": "",
            "tipos_poa": ["PIM"]
        },
        # Detalles específicos para PTT
        {
            "codigo": "730204",
            "nombre": "Servicio de edición, impresión y reproducción (Impresión 3D)",
            "descripcion": "",
            "tipos_poa": ["PTT"]
        },
        {
            "codigo": "730601",
            "nombre": "Contratación de servicios técnicos especializados para la elaboración de diseño, construcción, implementación, seguimiento y mejora contínua de los prototipos",
            "descripcion": "Contratación de servicios técnicos especializados (Consultoría), para la adquisición de muestras de campo",
            "tipos_poa": ["PTT"]
        },
        {
            "codigo": "770102",
            "nombre": "Propiedad intelectual",
            "descripcion": "",
            "tipos_poa": ["PTT"]
        },
        # Detalles específicos para PVIF, PVIS, PIGR, PIS, PIIF
        {
            "codigo": "730204",
            "nombre": "Servicio de edición, impresión y reproducción (copias)",
            "descripcion": "",
            "tipos_poa": ["PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
        {
            "codigo": "730207",
            "nombre": "Servicio de difusion informacion y publicidad (banner, plotter, pancarta, afiches)",
            "descripcion": "",
            "tipos_poa": ["PVIF", "PVIS", "PIGR", "PIS", "PIIF"]
        },
    ]

    # Función para obtener ItemPresupuestario por código
    async def obtener_item_presupuestario(db, codigo):
        result = await db.execute(
            select(ItemPresupuestario).where(ItemPresupuestario.codigo == codigo)
        )
        return result.scalars().first()

    # Función para crear DetalleTarea si no existe
    async def crear_detalle_tarea_si_no_existe(db, item_presupuestario, nombre, descripcion):
        # Verificar si ya existe el detalle exacto (incluyendo nombre Y descripción)
        result = await db.execute(
            select(DetalleTarea).where(
                and_(
                    DetalleTarea.id_item_presupuestario == item_presupuestario.id_item_presupuestario,
                    DetalleTarea.nombre == nombre,
                    DetalleTarea.descripcion == descripcion  # ← AGREGAR ESTA LÍNEA
                )
            )
        )
        detalle_existente = result.scalars().first()
        
        if not detalle_existente:
            nuevo_detalle = DetalleTarea(
                id_detalle_tarea=uuid.uuid4(),
                id_item_presupuestario=item_presupuestario.id_item_presupuestario,
                nombre=nombre,
                descripcion=descripcion,
                caracteristicas=None
            )
            db.add(nuevo_detalle)
            await db.flush()  # Para obtener el ID sin hacer commit
            return nuevo_detalle
        
        return detalle_existente

    # Procesar todos los detalles
    detalles_creados = []
    for detalle_info in detalles:
        # Obtener el item presupuestario
        item_presupuestario = await obtener_item_presupuestario(db, detalle_info["codigo"])
        
        if not item_presupuestario:
            print(f"❌ No se encontró ItemPresupuestario con código: {detalle_info['codigo']}")
            continue
        
        # Crear o obtener el DetalleTarea
        detalle_tarea = await crear_detalle_tarea_si_no_existe(
            db, 
            item_presupuestario, 
            detalle_info["nombre"], 
            detalle_info["descripcion"]
        )
        
        # Guardar información para asociaciones posteriores
        detalles_creados.append({
            "detalle_tarea": detalle_tarea,
            "tipos_poa": detalle_info["tipos_poa"]
        })

    await db.commit()
    print(f"✅ Se procesaron {len(detalles_creados)} detalles de tarea.")

    # ─────────────────────────────────────────────────────────────────────────────
    # Insertar relaciones TIPO_POA_DETALLE_TAREA
    # ─────────────────────────────────────────────────────────────────────────────

    async def asociar_detalles_a_tipos_poa(db, detalles_creados):
        # Mapear los códigos reales de TipoPOA
        tipos_poa_map = {}
        codigos_tipo = ["PIM", "PTT", "PVIF", "PIIF", "PIS", "PIGR", "PVIS"]
        
        for codigo in codigos_tipo:
            result = await db.execute(select(TipoPOA).where(TipoPOA.codigo_tipo == codigo))
            tipo_poa = result.scalars().first()
            if tipo_poa:
                tipos_poa_map[codigo] = tipo_poa
            else:
                print(f"⚠️ No se encontró TipoPOA con código: {codigo}")

        asociaciones_realizadas = 0
        
        for detalle_info in detalles_creados:
            detalle_tarea = detalle_info["detalle_tarea"]
            tipos_poa_codigos = detalle_info["tipos_poa"]
            
            for codigo_tipo in tipos_poa_codigos:
                tipo_poa = tipos_poa_map.get(codigo_tipo)
                if not tipo_poa:
                    continue
                    
                # Verificar si la asociación ya existe
                result = await db.execute(
                    select(TipoPoaDetalleTarea).where(
                        and_(
                            TipoPoaDetalleTarea.id_tipo_poa == tipo_poa.id_tipo_poa,
                            TipoPoaDetalleTarea.id_detalle_tarea == detalle_tarea.id_detalle_tarea
                        )
                    )
                )
                
                if not result.scalars().first():
                    nueva_asociacion = TipoPoaDetalleTarea(
                        id_tipo_poa_detalle_tarea=uuid.uuid4(),
                        id_tipo_poa=tipo_poa.id_tipo_poa,
                        id_detalle_tarea=detalle_tarea.id_detalle_tarea
                    )
                    db.add(nueva_asociacion)
                    asociaciones_realizadas += 1

        await db.commit()
        print(f"✅ Se crearon {asociaciones_realizadas} asociaciones nuevas entre TipoPOA y DetalleTarea.")

    # Ejecutar las asociaciones
    await asociar_detalles_a_tipos_poa(db, detalles_creados)
