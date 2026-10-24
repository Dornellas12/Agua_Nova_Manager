"""usuarios.py — usuário e senha (sem nada de tela). A senha é guardada só como hash PBKDF2-SHA256 com sal."""
import hashlib
import hmac
import secrets
from datetime import datetime

import banco

ITERACOES = 200_000
MIN_SENHA = 6


def criar_tabela():
    banco.executar("""CREATE TABLE IF NOT EXISTS usuarios (
        usuario TEXT PRIMARY KEY, salt TEXT NOT NULL, hash TEXT NOT NULL, criado_em TEXT)""")


def _hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), ITERACOES).hex()


def existe_usuario():
    return bool(banco.consultar("SELECT 1 FROM usuarios LIMIT 1"))


def definir_usuario(usuario, senha):
    """Cria o acesso do administrador (substitui o anterior, se existir)."""
    salt = secrets.token_hex(16)
    con = banco.conectar()
    try:
        with con:
            con.execute("DELETE FROM usuarios")
            con.execute("INSERT INTO usuarios(usuario,salt,hash,criado_em) VALUES (?,?,?,?)",
                        (usuario.strip().lower(), salt, _hash(senha, salt), datetime.now().isoformat(timespec="seconds")))
    finally:
        con.close()


def verificar(usuario, senha):
    r = banco.consultar("SELECT salt, hash FROM usuarios WHERE usuario=?", (usuario.strip().lower(),))
    salt = r[0]["salt"] if r else "00" * 16      # calcula o hash mesmo sem usuário (não revela quem existe)
    igual = hmac.compare_digest(_hash(senha, salt), r[0]["hash"] if r else "x")
    return bool(r) and igual


def alterar_senha(usuario, atual, nova):
    if not verificar(usuario, atual):
        raise ValueError("A senha atual está incorreta.")
    salt = secrets.token_hex(16)
    banco.executar("UPDATE usuarios SET salt=?, hash=? WHERE usuario=?", (salt, _hash(nova, salt), usuario))
