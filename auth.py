"""
Authentification : mots de passe hachés (PBKDF2-SHA256) et jetons JWT.
"""

import base64
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import db
from config import JWT_HOURS, JWT_SECRET

PBKDF2_ITERATIONS = 240_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_bearer = HTTPBearer(auto_error=False)


# ----------------------------------------------------------------------
# Mots de passe
# ----------------------------------------------------------------------

def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password, stored):
    try:
        _, iterations, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def validate_registration(name, email, password):
    if len(name.strip()) < 2:
        raise HTTPException(422, "Le nom doit contenir au moins 2 caractères.")
    if not EMAIL_RE.match(email.strip()):
        raise HTTPException(422, "Adresse e-mail invalide.")
    if len(password) < 8:
        raise HTTPException(422, "Le mot de passe doit contenir au moins 8 caractères.")


# ----------------------------------------------------------------------
# Jetons
# ----------------------------------------------------------------------

def create_token(user):
    payload = {
        "sub": user["id"],
        "name": user["name"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    """Dépendance FastAPI : renvoie l'utilisateur connecté ou une erreur 401."""
    if credentials is None:
        raise HTTPException(401, "Connexion requise.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(401, "Session expirée, reconnecte-toi.") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(401, "Jeton invalide.") from error
    user = db.get_user(payload["sub"])
    if user is None:
        raise HTTPException(401, "Compte introuvable.")
    return user
