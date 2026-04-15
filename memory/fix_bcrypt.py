with open("agents/meta_agent/auth.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """from passlib.context import CryptContext
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")"""

new = """from jose import jwt, JWTError
import hmac

SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24"""

content = content.replace(old, new)

old2 = """def hash_password(password):
    return pwd_context.hash(password)


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)"""

new2 = """def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password[:72]).encode()).hexdigest()
    return salt + ":" + h


def verify_password(plain, hashed):
    try:
        salt, h = hashed.split(":", 1)
        return hmac.compare_digest(h, hashlib.sha256((salt + plain[:72]).encode()).hexdigest())
    except Exception:
        return False"""

content = content.replace(old2, new2)

with open("agents/meta_agent/auth.py", "w", encoding="utf-8") as f:
    f.write(content)
print("auth.py fixed — using hashlib instead of bcrypt")
