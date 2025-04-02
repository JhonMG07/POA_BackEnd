from app.scripts.init_data import seed_all_data
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app import models, schemas, auth
from app.database import engine, get_db
from app.models import Usuario
from app.auth import get_current_user
from passlib.context import CryptContext

# Initialize the password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


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
    print(f"Usuario encontrado: {usuario}")
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


@app.get("/perfil")
async def perfil_usuario(usuario: Usuario = Depends(get_current_user)):
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
