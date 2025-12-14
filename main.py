import sqlalchemy
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
import aio_pika
import asyncio
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = "postgresql://postgres:changeme@localhost:5432/users_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = sqlalchemy.orm.declarative_base()


# ============ MODELOS SQLALCHEMY ============

class UserDB(Base):
    """Modelo do banco de dados"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    age = Column(Integer)


class UserCreate(BaseModel):
    """Schema para criar usuário"""
    id: str
    name: str
    email: str
    age: int


class UserResponse(BaseModel):
    """Schema para resposta"""
    id: str
    name: str
    email: str
    age: int

    class ConfigDict:
        from_attributes = True



def get_db():
    """Cria sessão de banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============ VARIÁVEIS GLOBAIS ============

rabbitmq_connection = None
rabbitmq_channel = None


# ============ RABBITMQ ============

async def on_message_callback(message: aio_pika.IncomingMessage):
    """Callback quando mensagem chega"""
    async with message.process():
        print(f"[RabbitMQ] Mensagem recebida: {message.body.decode()}")


async def start_rabbitmq_consumer():
    """Conecta e consome mensagens do RabbitMQ"""
    global rabbitmq_connection, rabbitmq_channel

    try:
        # Conectar ao RabbitMQ
        rabbitmq_connection = await aio_pika.connect_robust(
            "amqp://guest:guest@localhost/"
        )

        rabbitmq_channel = await rabbitmq_connection.channel()

        # Declarar fila
        queue = await rabbitmq_channel.declare_queue(
            "hello",
            durable=True
        )

        # Consumir mensagens
        await queue.consume(on_message_callback)
        print("[RabbitMQ] Conectado e aguardando mensagens...")

    except Exception as e:
        print(f"[RabbitMQ] Erro ao conectar: {e}")


async def stop_rabbitmq_consumer():
    """Fecha conexão com RabbitMQ"""
    global rabbitmq_connection

    if rabbitmq_connection:
        await rabbitmq_connection.close()
        print("[RabbitMQ] Desconectado")


# ============ FASTAPI ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia startup e shutdown da aplicação"""
    # Startup
    print("[FastAPI] Iniciando...")
    asyncio.create_task(start_rabbitmq_consumer())

    yield  # Aplicação roda enquanto aqui

    # Shutdown
    print("[FastAPI] Encerrando...")
    await stop_rabbitmq_consumer()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ MODELOS ============

class User(BaseModel):
    id: str
    name: str
    email: str
    age: int


# ============ DADOS ============

users = [
    User(id="user1", name="user1", email="user1@mail.com", age=25),
    User(id="user2", name="user2", email="user2@mail.com", age=90),
]


# ============ ROTAS ============

@app.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    """Lista todos os usuários"""
    users = db.query(UserDB).all()
    return users


@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Cria um novo usuário"""
    # Verificar se email já existe
    existing_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email já existe")

    # Verificar se ID já existe
    existing_id = db.query(UserDB).filter(UserDB.id == user.id).first()
    if existing_id:
        raise HTTPException(status_code=400, detail="ID já existe")

    # Criar novo usuário
    new_user = UserDB(
        id=user.id,
        name=user.name,
        email=user.email,
        age=user.age
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    print(f"[DB] Usuário criado: {new_user.id}")

    return new_user


@app.put("/user")
def update_user(user: User):
    return {"id": user.id, "name": user.name}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)