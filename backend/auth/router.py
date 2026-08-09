from fastapi import APIRouter, Depends, Response, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.auth.magic_link import request_magic_link, verify_magic_link
from backend.auth.session import create_session
from backend.db.session import get_db

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr


@router.post("/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # Always return the same response whether or not the email is recognized,
    # so the endpoint can't be used to enumerate valid accounts.
    request_magic_link(db, body.email)
    return {"status": "if_that_email_is_registered_a_link_has_been_sent"}


@router.get("/auth/verify")
def verify(token: str, response: Response, db: Session = Depends(get_db)):
    email = verify_magic_link(db, token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired link")

    redirect = RedirectResponse(url="/")
    create_session(db, redirect, email)
    return redirect
