import uuid
from app import models
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession


async def eliminar_tareas_y_actividades(id_poa: uuid.UUID, db: AsyncSession):
    """
    Elimina todas las tareas y actividades asociadas a un POA.
    """
    # Obtener las actividades asociadas al POA
    result = await db.execute(select(models.Actividad).where(models.Actividad.id_poa == id_poa))
    actividades = result.scalars().all()
    for actividad in actividades:
        # Eliminar tareas asociadas a la actividad
        result = await db.execute(select(models.Tarea).where(models.Tarea.id_actividad == actividad.id_actividad))
        tareas = result.scalars().all()
        for tarea in tareas:
            await db.delete(tarea)

        # Eliminar la actividad
        await db.delete(actividad)

    # Confirmar los cambios en la base de datos
    await db.commit()