from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, DECIMAL, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from datetime import datetime,timezone
# se puede mejorar la legibilidad del archivo separando los modelos en diferentes archivos
# y luego importarlos aquí, pero por simplicidad los mantendremos en un solo archivo

# Definición de los modelos de la base de datos utilizando SQLAlchemy

class TipoPOA(Base):
    __tablename__ = "TIPO_POA"

    id_tipo_poa = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_tipo = Column(String(20), nullable=False)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(500))
    duracion_meses = Column(Integer, nullable=False)
    cantidad_periodos = Column(Integer, nullable=False)
    presupuesto_maximo = Column(DECIMAL(18, 2), nullable=False)

class TipoProyecto(Base):
    __tablename__ = "TIPO_PROYECTO"

    id_tipo_proyecto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_tipo = Column(String(20), nullable=False)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(String(500))
    duracion_meses = Column(Integer, nullable=False)
    cantidad_periodos = Column(Integer, nullable=False)
    presupuesto_maximo = Column(DECIMAL(18, 2), nullable=False)
class EstadoProyecto(Base):
    __tablename__ = "ESTADO_PROYECTO"

    id_estado_proyecto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(String(500))
    permite_edicion = Column(Boolean, nullable=False, default=True)


class Rol(Base):
    __tablename__ = "ROL"

    id_rol = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_rol = Column(String(50), nullable=False)
    descripcion = Column(String(200))

    usuarios = relationship("Usuario", back_populates="rol")

class Usuario(Base):
    __tablename__ = "USUARIO"

    id_usuario = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_usuario = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    id_rol = Column(UUID(as_uuid=True), ForeignKey("ROL.id_rol"), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    rol = relationship("Rol", back_populates="usuarios")

class Proyecto(Base):
    __tablename__ = "PROYECTO"

    id_proyecto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_proyecto = Column(String(50), nullable=False)
    titulo = Column(String(2000), nullable=False)
    id_tipo_proyecto = Column(UUID(as_uuid=True), ForeignKey("TIPO_PROYECTO.id_tipo_proyecto"), nullable=False)
    id_estado_proyecto = Column(UUID(as_uuid=True), ForeignKey("ESTADO_PROYECTO.id_estado_proyecto"), nullable=False)
    id_director_proyecto = Column(String(200), nullable=True)
    presupuesto_aprobado = Column(DECIMAL(18, 2))
    fecha_creacion = Column(DateTime, nullable=False)
    fecha_inicio = Column(Date)
    fecha_fin = Column(Date)
    fecha_prorroga = Column(Date)  # fecha de solicitud de prórroga
    fecha_prorroga_inicio = Column(Date, nullable= True)  # nueva fecha de inicio aprobada
    fecha_prorroga_fin = Column(Date)     # nueva fecha de fin aprobada

    tipo_proyecto = relationship("TipoProyecto")
    estado_proyecto = relationship("EstadoProyecto")
    # director = relationship("Usuario", back_populates="proyectos_dirigidos", foreign_keys=[id_director_proyecto])

class Periodo(Base):
    __tablename__ = "PERIODO"

    id_periodo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_periodo = Column(String(150), nullable=False)
    nombre_periodo = Column(String(180), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    anio = Column(String(4), nullable=True)
    mes = Column(String(35), nullable=True)


class EstadoPOA(Base):
    __tablename__ = "ESTADO_POA"

    id_estado_poa = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(String(500))

class LimiteProyectosTipo(Base):
    __tablename__ = "LIMITE_PROYECTOS_TIPO"

    id_limite = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_tipo_proyecto = Column(UUID(as_uuid=True), ForeignKey("TIPO_PROYECTO.id_tipo_proyecto"), nullable=False)
    limite_proyectos = Column(Integer, nullable=False, default=1)
    descripcion = Column(String(200))

    tipo_proyecto = relationship("TipoProyecto")

class Poa(Base):
    __tablename__ = "POA"

    id_poa = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("PROYECTO.id_proyecto"), nullable=False)
    id_periodo = Column(UUID(as_uuid=True), ForeignKey("PERIODO.id_periodo"), nullable=False)
    codigo_poa = Column(String(50), nullable=False)
    fecha_creacion = Column(DateTime, nullable=False)
    id_estado_poa = Column(UUID(as_uuid=True), ForeignKey("ESTADO_POA.id_estado_poa"), nullable=False)
    id_tipo_poa = Column(UUID(as_uuid=True), ForeignKey("TIPO_POA.id_tipo_poa"), nullable=False)
    anio_ejecucion = Column(String(4), nullable=False)
    presupuesto_asignado = Column(DECIMAL(18, 2), nullable=False)

    proyecto = relationship("Proyecto")
    periodo = relationship("Periodo")
    estado_poa = relationship("EstadoPOA")

    tipo_poa = relationship("TipoPOA")

class ItemPresupuestario(Base):
    __tablename__ = "ITEM_PRESUPUESTARIO"

    id_item_presupuestario = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(20), nullable=False)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(500))

    detalles_tarea = relationship("DetalleTarea", back_populates="item_presupuestario")

class DetalleTarea(Base):
    __tablename__ = "DETALLE_TAREA"

    id_detalle_tarea = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_item_presupuestario = Column(UUID(as_uuid=True), ForeignKey("ITEM_PRESUPUESTARIO.id_item_presupuestario"), nullable=False)
    nombre = Column(String(500), nullable=False)
    descripcion = Column(String(500))
    caracteristicas = Column(String(500))

    item_presupuestario = relationship("ItemPresupuestario", back_populates="detalles_tarea")

class TipoPoaDetalleTarea(Base):
    __tablename__ = "TIPO_POA_DETALLE_TAREA"

    id_tipo_poa_detalle_tarea = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_tipo_poa = Column(UUID(as_uuid=True), ForeignKey("TIPO_POA.id_tipo_poa"), nullable=False)
    id_detalle_tarea = Column(UUID(as_uuid=True), ForeignKey("DETALLE_TAREA.id_detalle_tarea"), nullable=False)

    tipo_poa = relationship("TipoPOA")
    detalle_tarea = relationship("DetalleTarea")

class LimiteActividadesTipoPoa(Base):
    __tablename__ = "LIMITE_ACTIVIDADES_TIPO_POA"

    id_limite = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_tipo_poa = Column(UUID(as_uuid=True), ForeignKey("TIPO_POA.id_tipo_poa"), nullable=False)
    limite_actividades = Column(Integer, nullable=False, default=10)
    descripcion = Column(String(200))

    tipo_poa = relationship("TipoPOA")

class Actividad(Base):
    __tablename__ = "ACTIVIDAD"

    id_actividad = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_poa = Column(UUID(as_uuid=True), ForeignKey("POA.id_poa"), nullable=False)
    descripcion_actividad = Column(String(500), nullable=False)
    total_por_actividad = Column(DECIMAL(18, 2), nullable=False)
    saldo_actividad = Column(DECIMAL(18, 2), nullable=False)

    poa = relationship("Poa")
    tareas = relationship("Tarea", back_populates="actividad")

class Tarea(Base):
    __tablename__ = "TAREA"

    id_tarea = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_actividad = Column(UUID(as_uuid=True), ForeignKey("ACTIVIDAD.id_actividad"), nullable=False)
    id_detalle_tarea = Column(UUID(as_uuid=True), ForeignKey("DETALLE_TAREA.id_detalle_tarea"), nullable=True)
    nombre = Column(String(200))

    detalle_descripcion = Column(String(5000))
    cantidad = Column(DECIMAL(10, 2), nullable=True, default=0)
    precio_unitario = Column(DECIMAL(18, 2), nullable=True, default=0)
    total = Column(DECIMAL(18, 2), nullable=True, default=0)
    saldo_disponible = Column(DECIMAL(18, 2), nullable=True, default=0)
    lineaPaiViiv = Column(Integer, nullable=True)

    actividad = relationship("Actividad", back_populates="tareas")
    detalle_tarea = relationship("DetalleTarea")
    programacion_mensual = relationship("ProgramacionMensual", back_populates="tarea", cascade="all, delete-orphan")


class ProgramacionMensual(Base):
    __tablename__ = "PROGRAMACION_MENSUAL"

    id_programacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_tarea = Column(UUID(as_uuid=True), ForeignKey("TAREA.id_tarea"), nullable=False)
    mes = Column(String(15), nullable=False)  # Formato: '01-2026', '02-2026', etc.
    valor = Column(DECIMAL(18, 2), nullable=False)

    tarea = relationship("Tarea", back_populates="programacion_mensual")

    __table_args__ = (
        UniqueConstraint('id_tarea', 'mes', name='uq_tarea_mes'),
    )


class Permiso(Base):
    __tablename__ = "PERMISO"

    id_permiso = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_permiso = Column(String(50), nullable=False)
    descripcion = Column(String(200))
    modulo = Column(String(50), nullable=False)
    accion = Column(String(50), nullable=False)

    roles = relationship("PermisoRol", back_populates="permiso")

class PermisoRol(Base):
    __tablename__ = "PERMISO_ROL"

    id_permiso_rol = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_rol = Column(UUID(as_uuid=True), ForeignKey("ROL.id_rol"), nullable=False)
    id_permiso = Column(UUID(as_uuid=True), ForeignKey("PERMISO.id_permiso"), nullable=False)

    permiso = relationship("Permiso", back_populates="roles")
    rol = relationship("Rol")

class ReformaPoa(Base):
    __tablename__ = "REFORMA_POA"

    id_reforma = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_poa = Column(UUID(as_uuid=True), ForeignKey("POA.id_poa"), nullable=False)
    fecha_solicitud = Column(DateTime, nullable=False)
    fecha_aprobacion = Column(DateTime)
    estado_reforma = Column(String(50), nullable=False)
    monto_anterior = Column(DECIMAL(18, 2), nullable=False)
    monto_solicitado = Column(DECIMAL(18, 2), nullable=False)
    justificacion = Column(String(500), nullable=False)
    id_usuario_solicita = Column(UUID(as_uuid=True), ForeignKey("USUARIO.id_usuario"), nullable=False)
    id_usuario_aprueba = Column(UUID(as_uuid=True), ForeignKey("USUARIO.id_usuario"))

    poa = relationship("Poa")
    usuario_solicita = relationship("Usuario", foreign_keys=[id_usuario_solicita])
    usuario_aprueba = relationship("Usuario", foreign_keys=[id_usuario_aprueba])

class ControlPresupuestario(Base):
    __tablename__ = "CONTROL_PRESUPUESTARIO"

    id_control = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_poa = Column(UUID(as_uuid=True), ForeignKey("POA.id_poa"), nullable=False)
    id_tarea = Column(UUID(as_uuid=True), ForeignKey("TAREA.id_tarea"), nullable=False)
    fecha_registro = Column(DateTime, nullable=False)
    monto_certificado = Column(DECIMAL(18, 2), nullable=False)
    monto_comprometido = Column(DECIMAL(18, 2), nullable=False)
    monto_devengado = Column(DECIMAL(18, 2), nullable=False, default=0)
    saldo_disponible = Column(DECIMAL(18, 2), nullable=False)
    id_reforma = Column(UUID(as_uuid=True), ForeignKey("REFORMA_POA.id_reforma"))
    justificacion = Column(String(500))
    referencia_documento = Column(String(100))

    poa = relationship("Poa")
    tarea = relationship("Tarea")
    reforma = relationship("ReformaPoa")

class EjecucionPresupuestaria(Base):
    __tablename__ = "EJECUCION_PRESUPUESTARIA"

    id_ejecucion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_tarea = Column(UUID(as_uuid=True), ForeignKey("TAREA.id_tarea"), nullable=False)
    id_poa = Column(UUID(as_uuid=True), ForeignKey("POA.id_poa"), nullable=False)
    monto_ejecutado = Column(DECIMAL(18, 2), nullable=False)
    fecha_ejecucion = Column(DateTime, nullable=False)
    descripcion_ejecucion = Column(String(500))
    referencia_documento = Column(String(100))
    bloqueado = Column(Boolean, nullable=False, default=False)
    id_control_presupuestario = Column(UUID(as_uuid=True), ForeignKey("CONTROL_PRESUPUESTARIO.id_control"))

    tarea = relationship("Tarea")
    poa = relationship("Poa")
    control_presupuestario = relationship("ControlPresupuestario")

class HistoricoProyecto(Base):
    __tablename__ = "HISTORICO_PROYECTO"

    id_historico = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("PROYECTO.id_proyecto"), nullable=False)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey("USUARIO.id_usuario"), nullable=False)
    fecha_modificacion = Column(DateTime, nullable=False)
    campo_modificado = Column(String(100), nullable=False)
    valor_anterior = Column(Text)
    valor_nuevo = Column(Text)
    justificacion = Column(String(500), nullable=False)

    proyecto = relationship("Proyecto")
    usuario = relationship("Usuario")

class HistoricoPoa(Base):
    __tablename__ = "HISTORICO_POA"

    id_historico = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_poa = Column(UUID(as_uuid=True), ForeignKey("POA.id_poa"), nullable=False)
    id_usuario = Column(UUID(as_uuid=True), ForeignKey("USUARIO.id_usuario"), nullable=False)
    fecha_modificacion = Column(DateTime, nullable=False)
    campo_modificado = Column(String(100), nullable=False)
    valor_anterior = Column(Text)
    valor_nuevo = Column(Text)
    justificacion = Column(String(500), nullable=False)
    id_reforma = Column(UUID(as_uuid=True), ForeignKey("REFORMA_POA.id_reforma"))

    poa = relationship("Poa")
    usuario = relationship("Usuario")
    reforma = relationship("ReformaPoa")

class LogCargaExcel(Base):
    __tablename__ = "LOG_CARGA_EXCEL"
    id_log = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_poa = Column(String(36), nullable=True)              # UUID del POA como string
    codigo_poa = Column(String(100), nullable=True)         # Código POA visible
    id_usuario = Column(String(36), nullable=True)          # UUID del usuario como string
    usuario_nombre = Column(String(100), nullable=True)     # Nombre del usuario
    usuario_email = Column(String(100), nullable=True)      # Email del usuario
    proyecto_nombre = Column(String(200), nullable=True)    # Nombre del proyecto
    fecha_carga = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # Fecha
    nombre_archivo = Column(String(200), nullable=False)    # Archivo
    hoja = Column(String(100), nullable=False)              # Hoja
    mensaje = Column(String(500), nullable=False)           # Mensaje