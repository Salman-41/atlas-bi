"""Explicit user bootstrap; no bundled account or fallback signing key."""
import os
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from atlas.models import User, session

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)

def secret():
    value = os.getenv('ATLAS_JWT_SECRET', '')
    if len(value) < 32:
        raise RuntimeError('ATLAS_JWT_SECRET must contain at least 32 characters')
    return value

def token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user.id), 'iat': now, 'exp': now + timedelta(minutes=30), 'iss': 'atlas-bi', 'aud': 'atlas-ui'}, secret(), algorithm='HS256')

def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(session)):
    try:
        if not credentials:
            raise ValueError('Missing token')
        claims = jwt.decode(credentials.credentials, secret(), algorithms=['HS256'], issuer='atlas-bi', audience='atlas-ui')
        user = db.get(User, int(claims['sub']))
        if not user:
            raise ValueError('Unknown user')
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Valid authentication required')

def roles(*allowed):
    def check(user=Depends(current_user)):
        if user.role not in allowed:
            raise HTTPException(403, 'Role is not permitted to perform this action')
        return user
    return check

def main():
    import argparse, getpass
    from pathlib import Path
    from atlas.models import Base, engine
    from sqlalchemy.orm import Session
    parser = argparse.ArgumentParser(description='Create an ATLAS BI user interactively')
    parser.add_argument('username')
    parser.add_argument('--role', choices=['admin', 'analyst', 'viewer'], default='viewer')
    args = parser.parse_args()
    Path('data').mkdir(exist_ok=True)
    password = getpass.getpass('Password (12+ characters): ')
    if len(password) < 12:
        raise SystemExit('Password must contain at least 12 characters')
    with Session(engine()) as db:
        if db.scalar(select(User).where(User.username == args.username)):
            raise SystemExit('User already exists')
        db.add(User(username=args.username, role=args.role, password_hash=hasher.hash(password)))
        db.commit()

if __name__ == '__main__':
    main()
