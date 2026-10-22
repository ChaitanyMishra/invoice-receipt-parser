from app.models import User
from app.database import engine
from sqlmodel import Session,select
from app.auth import get_password_hash

def create_user(email:str,hashed_password:str):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user:
            return None

        new_user = User(email=email,hashed_password=hashed_password)
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user

def get_user_by_email(email:str):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            return None
        return user


