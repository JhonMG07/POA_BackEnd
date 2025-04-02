import uuid
from app.database import SessionLocal
from app.models import Rol, Permiso, PermisoRol
from sqlalchemy.future import select

# Esta función sirve para llenar la base de datos con datos iniciales
async def seed_all_data():
    async with SessionLocal() as db:
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
