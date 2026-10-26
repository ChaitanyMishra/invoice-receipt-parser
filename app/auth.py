import datetime
import os

import jwt
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv()
password_hash = PasswordHash.recommended()


def get_password_hash(password:str):
    if not password:
        return None
    hashed_password =password_hash.hash(password)
    return hashed_password


def verify_hash_password(password:str , hashed_password):
    if not password:
        return None
    if not hashed_password:
        return None

    try:
        verified_password =  password_hash.verify(password,hashed_password)
        return verified_password
    except Exception as e:  # noqa: BLE001
        return None

def create_access_token(data:dict):
    SECRET_KEY = os.getenv("SECRET_KEY")
    algorithm = "HS256"
    to_encode = data.copy()
    ACCESS_TOKEN_EXPIRE_MINUTES=datetime.datetime.now(datetime.UTC)+datetime.timedelta(minutes=30)
    to_encode.update({"exp":ACCESS_TOKEN_EXPIRE_MINUTES})
    access_token = jwt.encode(to_encode ,SECRET_KEY, algorithm=algorithm)
    return access_token

def decode_access_token(token_string:str):
    algorithm =  "HS256"
    SECRET_KEY=os.getenv("SECRET_KEY")
    try:
        decoded_payload =  jwt.decode(token_string,SECRET_KEY,algorithms=[algorithm])
        return decoded_payload
    except jwt.PyJWTError:
        return None
