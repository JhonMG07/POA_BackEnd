from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context
from dotenv import load_dotenv
import os
import sys

# Cargar variables del .env
load_dotenv()

# Configuración de Alembic
config = context.config
fileConfig(config.config_file_name)

# Agregar la ruta del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importar Base y modelos
from app.database import Base
from app.models import (
    TipoPOA,
    TipoProyecto,
    Usuario,
    Proyecto,
    EstadoProyecto,
    EstadoPOA,
    Periodo,
    Rol,
    LimiteProyectosTipo,
    Poa,
    ItemPresupuestario,
    DetalleTarea,
    TipoPoaDetalleTarea,
    LimiteActividadesTipoPoa,
    Actividad,
    Tarea,
    Permiso,
    PermisoRol,
    ReformaPoa,
    ControlPresupuestario,
    EjecucionPresupuestaria,
    HistoricoProyecto,
    HistoricoPoa,
)

# Asignar metadata de los modelos
target_metadata = Base.metadata

# 🔒 Forzar uso de psycopg2 en Alembic (modo síncrono)
url = "postgresql://postgres:postgres@db:5432/fastapidb"


def run_migrations_offline():
    """Ejecutar migraciones en modo offline"""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Ejecutar migraciones en modo online"""
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
