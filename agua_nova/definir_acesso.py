"""Cria ou redefine o usuário e a senha do sistema. Seus dados NÃO são apagados.

Como usar (Terminal, dentro da pasta agua_nova, com o sistema fechado):
    python3 definir_acesso.py          (no Windows: python definir_acesso.py)
Só quem tem acesso ao computador consegue rodar isto — é isso que protege o acesso.
"""
import getpass

import banco
import usuarios

banco.iniciar()
usuarios.criar_tabela()
print("=== Acesso ao sistema Água Nova ===")
if usuarios.existe_usuario():
    if input("Já existe um acesso. Digite SIM para substituir por um novo: ").strip().upper() != "SIM":
        raise SystemExit("Nada foi alterado.")
usuario = input("Novo usuário: ").strip()
if len(usuario) < 3:
    raise SystemExit("O usuário precisa ter pelo menos 3 caracteres.")
senha = getpass.getpass("Nova senha (não aparece enquanto você digita): ")
if len(senha) < usuarios.MIN_SENHA:
    raise SystemExit(f"A senha precisa ter pelo menos {usuarios.MIN_SENHA} caracteres.")
if senha != getpass.getpass("Repita a senha: "):
    raise SystemExit("As senhas não conferem. Nada foi alterado.")
usuarios.definir_usuario(usuario, senha)
print("Pronto! Abra o sistema e entre com o novo usuário e senha.")
