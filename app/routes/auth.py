from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.auth.security import verify_password, hash_password, create_token
from app.auth.dependencies import get_current_user

router = APIRouter()

class LoginRequest(BaseModel):
    usuario: str   # email del usuario
    password: str

@router.post("/login")
def login(body: LoginRequest):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, org_id, email, name, role, password_hash, is_active FROM users WHERE username = %s",
            (body.usuario,),
        )
        user = cur.fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    token = create_token({
        "sub":    str(user["id"]),
        "org_id": str(user["org_id"]),
        "role":   user["role"],
        "name":   user["name"],
        "email":  user["email"],
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id":     str(user["id"]),
            "org_id": str(user["org_id"]),
            "name":   user["name"],
            "email":  user["email"],
            "role":   user["role"],
        },
    }

@router.get("/me")
def me(user=Depends(get_current_user)):
    return user


class PasswordChange(BaseModel):
    password_actual: str
    password_nuevo:  str

@router.put("/me/password")
def cambiar_mi_password(body: PasswordChange, user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (user["sub"],))
        row = cur.fetchone()
        if not row or not verify_password(body.password_actual, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hash_password(body.password_nuevo), user["sub"]),
        )
    return {"ok": True}
