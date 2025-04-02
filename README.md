# 🚀 FastAPI + PostgreSQL + Alembic API

Este proyecto es una API construida con **FastAPI**, **SQLAlchemy (async)**, y **PostgreSQL**, gestionado con **Docker** y migraciones controladas por **Alembic**.

---

## 📦 Tecnologías utilizadas

- FastAPI
- SQLAlchemy (async)
- Alembic
- PostgreSQL
- Docker & Docker Compose

---

## 🐳 Cómo ejecutar el proyecto

### 🔹 Levantar los contenedores

```bash
docker-compose up -d
```

Esto construirá la imagen de la API y levantará los servicios `web` (FastAPI) y `db` (PostgreSQL).

### 🔹 Detener los contenedores

```bash
docker-compose down
```

---

## 📂 Migraciones con Alembic

Utiliza **Alembic** para gestionar cambios en los modelos y mantener sincronizada la base de datos.

### ➕ Crear nueva migración

```bash
docker exec -it fastapi_app alembic revision --autogenerate -m "descripcion"
```

**Ejemplos:**

```bash
docker exec -it fastapi_app alembic revision --autogenerate -m "initial"
docker exec -it fastapi_app alembic revision --autogenerate -m "Agrego nuevo_monto_comprometido a ControlPresupuestario"
```

### ⬆️ Aplicar migraciones

```bash
docker exec -it fastapi_app alembic upgrade head
```

---

## 🧪 Datos iniciales

El proyecto inserta automáticamente datos iniciales al iniciar el servidor (por ejemplo, roles predefinidos como `"Admin"`, `"Editor"`, `"Usuario"`).

Esto se hace desde el archivo:

```
app/scripts/init_data.py
```

Y se ejecuta al arrancar la aplicación mediante el evento `@app.on_event("startup")` en `main.py`:

```python
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    # llenar la base de datos con datos iniciales
    print("Insertando roles iniciales...")
    await insertar_roles()
```

---

## 📬 Endpoints principales

| Método | Ruta        | Descripción                          |
|--------|-------------|--------------------------------------|
| POST   | `/register` | Crea un nuevo usuario                |
| POST   | `/login`    | Autentica y retorna un JWT           |
| GET    | `/perfil`   | Devuelve el perfil del usuario logueado |

> Recuerda enviar el token en rutas protegidas usando el header:  
> `Authorization: Bearer <token>`

---

## ✅ Requisitos

- Docker y Docker Compose
- Python 3.11 (solo si deseas correr cosas fuera del contenedor)

---

## 📝 Licencia

Este proyecto es de uso libre y puede ser modificado según las necesidades de tu organización o equipo.
