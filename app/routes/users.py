"""
users.py — CRUD de usuarios
Acceso: solo roles admin y super_admin
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.auth.dependencies import require_roles
from app.auth.security import hash_password

router = APIRouter()

ROLES_VALIDOS = ['super_admin', 'admin', 'supervisor', 'operator', 'lab', 'readonly']

# ─── Modelos ──────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username:  str
    email:     str
    name:      str
    role:      str
    password:  str
    is_active: bool = True

class UserUpdate(BaseModel):
    username:  Optional[str]  = None
    email:     Optional[str]  = None
    name:      Optional[str]  = None
    role:      Optional[str]  = None
    is_active: Optional[bool] = None
    password:  Optional[str]  = None  # vacío = no cambiar

# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def listar_usuarios(user=Depends(require_roles("super_admin", "admin"))):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, username, email, name, role, is_active, created_at
            FROM users
            WHERE org_id = %s
            ORDER BY name
            """,
            (user["org_id"],),
        )
        return cur.fetchall()


@router.post("", status_code=201)
def crear_usuario(body: UserCreate, user=Depends(require_roles("super_admin", "admin"))):
    if body.role not in ROLES_VALIDOS:
        raise HTTPException(400, detail="Rol inválido")
    # Un admin no puede crear super_admin
    if user["role"] == "admin" and body.role == "super_admin":
        raise HTTPException(403, detail="Un admin no puede crear usuarios super_admin")

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO users (org_id, username, email, name, role, password_hash, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, username, email, name, role, is_active
                """,
                (
                    user["org_id"], body.username, body.email, body.name,
                    body.role, hash_password(body.password), body.is_active,
                ),
            )
            return cur.fetchone()
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(409, detail="El usuario o email ya existe")
            raise


@router.put("/{user_id}")
def actualizar_usuario(
    user_id: str,
    body: UserUpdate,
    user=Depends(require_roles("super_admin", "admin")),
):
    if body.role and body.role not in ROLES_VALIDOS:
        raise HTTPException(400, detail="Rol inválido")
    if user["role"] == "admin" and body.role == "super_admin":
        raise HTTPException(403, detail="Un admin no puede asignar rol super_admin")

    # Construir SET dinámico — los nombres de campo son hardcoded, no vienen del usuario
    sets, vals = [], []
    if body.username  is not None: sets.append("username = %s");      vals.append(body.username)
    if body.email     is not None: sets.append("email = %s");         vals.append(body.email)
    if body.name      is not None: sets.append("name = %s");          vals.append(body.name)
    if body.role      is not None: sets.append("role = %s");          vals.append(body.role)
    if body.is_active is not None: sets.append("is_active = %s");     vals.append(body.is_active)
    if body.password:               sets.append("password_hash = %s"); vals.append(hash_password(body.password))

    if not sets:
        raise HTTPException(400, detail="Nada que actualizar")

    vals += [user["org_id"], user_id]
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE org_id = %s AND id = %s "
                "RETURNING id, username, email, name, role, is_active",
                vals,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, detail="Usuario no encontrado")
            return row
        except HTTPException:
            raise
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(409, detail="El usuario o email ya existe")
            raise


@router.delete("/{user_id}", status_code=204)
def eliminar_usuario(user_id: str, user=Depends(require_roles("super_admin", "admin"))):
    if user_id == user["sub"]:
        raise HTTPException(400, detail="No puedes eliminarte a ti mismo")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM users WHERE org_id = %s AND id = %s RETURNING id",
            (user["org_id"], user_id),
        )
        if not cur.fetchone():
            raise HTTPException(404, detail="Usuario no encontrado")
