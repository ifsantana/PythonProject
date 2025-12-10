import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE, etc
    allow_headers=["*"],  # Qualquer header
)

class User(BaseModel):
    id: str
    name: str
    email: str
    age: int


users = [
    User(id="user1", name="user1", email="user1@mail.com", age=25),
    User(id="user2", name="user2", email="user2@mail.com", age=90),
]

@app.get("/users")
def list_users():
    return users


@app.post("/user")
def create_user(user: User):
    users.append(user)
    return user


@app.put("/user")
def update_user(user: User):
    return {"id": user.id, "name": user.name}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)