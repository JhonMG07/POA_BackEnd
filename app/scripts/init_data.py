
import uuid
from app.database import SessionLocal
from app.models import Rol

async def insertar_roles():
    async with SessionLocal() as db:
        roles = [
            Rol(id_rol=uuid.uuid4(), nombre_rol="Admin", descripcion="Administrador del sistema"),
            Rol(id_rol=uuid.uuid4(), nombre_rol="Editor", descripcion="Puede editar contenidos"),
            Rol(id_rol=uuid.uuid4(), nombre_rol="Usuario", descripcion="Usuario básico del sistema"),
        ]
        db.add_all(roles)
        await db.commit()
