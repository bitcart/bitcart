from pwdlib import PasswordHash


class PasswordHasher:
    def __init__(self, pwd_context: PasswordHash) -> None:
        self.pwd_context = pwd_context

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)
