"""acesso.py — login, senha e desconexão automática por inatividade.

- A senha NUNCA é guardada em texto: fica só um "hash" (PBKDF2-SHA256 com sal).
- Depois de TEMPO_LIMITE segundos sem usar o sistema, a sessão é encerrada.
- Após MAX_FALHAS senhas erradas, o login fica bloqueado por BLOQUEIO segundos.
- O acesso NÃO é criado pelo navegador: o dono roda  python3 definir_acesso.py  no computador.
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime

import streamlit as st

import usuarios

TEMPO_LIMITE = 5 * 60   # segundos sem uso até sair sozinho
MAX_FALHAS = 5          # tentativas erradas antes do bloqueio
BLOQUEIO = 60           # segundos de bloqueio

CSS_LOGIN = """
<style>
.stApp { background: radial-gradient(900px 500px at 15% 0%, rgba(63,193,217,.55), rgba(63,193,217,0) 65%),
                     linear-gradient(160deg, #063B57 0%, #0E7FA8 100%); }
[data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] { display: none; }
header[data-testid="stHeader"] { background: transparent; }
.lg-marca { text-align: center; color: #fff; margin: 5vh 0 1.2rem; }
.lg-marca h1 { color: #fff; font-size: 1.9rem; font-weight: 800; margin: .7rem 0 0; padding: 0; }
.lg-marca p { opacity: .88; margin: .3rem 0 0; }
.lg-card { background:#fff; border-radius:16px; padding:1.4rem 1.6rem; color:#0B2A3C; box-shadow:0 24px 60px rgba(6,59,87,.40); }
[data-testid="stForm"] { padding: 1.6rem 1.6rem .8rem; border: 0; box-shadow: 0 24px 60px rgba(6,59,87,.40); }
.lg-rodape { text-align: center; color: rgba(255,255,255,.78); font-size: .8rem; margin-top: 1.2rem; }
</style>
"""


@st.cache_resource
def _controle():
    """Contador de falhas compartilhado por todas as abas (atualizar a página não zera)."""
    return {"falhas": 0, "ate": 0.0}


# ---------- tela de login ----------
def _form_login():
    ctl = _controle()
    espera = ctl["ate"] - time.time()
    with st.form("login"):
        st.markdown("##### Bem-vindo de volta")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True, disabled=espera > 0)
    if espera > 0:
        st.error(f"Muitas tentativas incorretas. Aguarde {int(espera) + 1} segundos.")
    elif entrar:
        if usuarios.verificar(usuario, senha):
            ctl["falhas"] = 0
            st.session_state["auth_user"] = usuario.strip().lower()
            st.session_state["auth_ultima"] = time.time()
            st.rerun()
        else:
            ctl["falhas"] += 1
            if ctl["falhas"] >= MAX_FALHAS:
                ctl["falhas"], ctl["ate"] = 0, time.time() + BLOQUEIO
                st.error(f"Muitas tentativas incorretas. Login bloqueado por {BLOQUEIO} segundos.")
            else:
                st.error("Usuário ou senha incorretos.")


def _aviso_sem_acesso():
    st.markdown("<div class='lg-card'><b>🔧 Acesso ainda não configurado</b><br><br>"
                "Para criar o usuário e a senha, feche o sistema e rode no Terminal, dentro da pasta do projeto:<br>"
                "<code>python3 definir_acesso.py</code><br><br>Depois, abra o sistema novamente.</div>",
                unsafe_allow_html=True)


def _tela_login(logo):
    sem_acesso = not usuarios.existe_usuario()
    st.markdown(CSS_LOGIN, unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        sub = "Configuração necessária" if sem_acesso else "Acesso ao sistema"
        st.markdown(f"<div class='lg-marca'>{logo}<h1>Distribuidora Água Nova</h1><p>{sub}</p></div>",
                    unsafe_allow_html=True)
        if "aviso_login" in st.session_state:
            st.warning(st.session_state.pop("aviso_login"))
        _aviso_sem_acesso() if sem_acesso else _form_login()
        st.markdown("<div class='lg-rodape'>🔒 Acesso protegido · Desenvolvido por Brunno Dornelas · Versão 1.0</div>",
                    unsafe_allow_html=True)


# ---------- controle de sessão ----------
def exigir_login(logo):
    """Chame no começo do app. Devolve True se a pessoa está logada; senão mostra o login."""
    usuarios.criar_tabela()
    agora = time.time()
    if st.session_state.get("auth_user"):
        if agora - st.session_state.get("auth_ultima", 0) > TEMPO_LIMITE:
            pedido = st.session_state.get("carrinho")  # o pedido em andamento não se perde
            st.session_state.clear()
            st.session_state["aviso_login"] = "Sessão encerrada após 5 minutos sem uso. Entre novamente."
            if pedido:
                st.session_state["carrinho"] = pedido
                st.session_state["aviso_login"] += " O pedido que você estava montando foi mantido."
        else:
            st.session_state["auth_ultima"] = agora  # cada clique/ação renova o tempo
            return True
    _tela_login(logo)
    return False


def sair():
    st.session_state.clear()
    st.rerun()


@st.fragment(run_every="10s")
def _relogio():
    """Roda sozinho a cada 10s (sem contar como atividade) e derruba a sessão quando o tempo acaba."""
    resta = TEMPO_LIMITE - (time.time() - st.session_state.get("auth_ultima", 0))
    if resta <= 0:
        st.rerun()
    m, s = divmod(int(resta), 60)
    st.caption(f"⏱️ Desconecta em {m}:{s:02d} sem uso")


def painel_sessao():
    """Mostra usuário, contagem regressiva e botão Sair (use dentro da barra lateral)."""
    st.caption(f"👤 {st.session_state.get('auth_user', '')}")
    _relogio()
    if st.button("🔒 Sair", use_container_width=True):
        sair()


def tela_alterar_senha():
    st.markdown("##### Alterar senha de acesso")
    with st.form("trocar_senha", clear_on_submit=True):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password")
        conf = st.text_input("Repita a nova senha", type="password")
        if st.form_submit_button("Salvar nova senha", type="primary"):
            if len(nova) < usuarios.MIN_SENHA:
                st.error(f"A nova senha precisa ter pelo menos {usuarios.MIN_SENHA} caracteres.")
            elif nova != conf:
                st.error("As senhas não conferem.")
            else:
                try:
                    usuarios.alterar_senha(st.session_state["auth_user"], atual, nova)
                    st.success("Senha alterada com sucesso.")
                except ValueError as e:
                    st.error(str(e))
    st.caption("Esqueceu a senha? Feche o sistema e rode no Terminal: python3 definir_acesso.py")
