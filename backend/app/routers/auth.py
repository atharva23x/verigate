"""Auth endpoints (simple JWT login with seeded users)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit import audit
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse
from ..security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        audit(
            db,
            "LOGIN_FAILED",
            actor=body.username,
            detail={"reason": "bad credentials"},
        )
        raise HTTPException(401, "Invalid username or password")
    audit(
        db,
        "LOGIN",
        actor=user.username,
        role=user.role,
        entity_type="user",
        entity_id=user.id,
    )
    return TokenResponse(
        access_token=create_token(user),
        username=user.username,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role, "full_name": user.full_name}
