"""app.py — telas do sistema Distribuidora Água Nova (Streamlit).

Para rodar:  streamlit run app.py
"""
import html
import sqlite3
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import acesso
import banco
import regras
from regras import brl

st.set_page_config(page_title="Água Nova", page_icon="💧", layout="wide")
banco.iniciar()

GOTA = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24"><path d="M12 2C12 2 5 10 5 15a7 7 0 0014 0C19 10 12 2 12 2z" '
        'fill="#fff"/><path d="M9 15a3 3 0 003 3" stroke="#0E7FA8" stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>')

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Nunito', 'Segoe UI', sans-serif; }
.block-container { padding-top: 1.2rem; max-width: 1250px; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stSidebar"] { background: linear-gradient(185deg, #063B57 0%, #0E7FA8 100%); }
[data-testid="stSidebar"] * { color: #fff !important; }
[data-testid="stSidebar"] label[data-baseweb="radio"] { padding: .55rem .8rem; border-radius: 10px; width: 100%; transition: background .15s; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover { background: rgba(255,255,255,.15); }
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child { display: none; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) { background: rgba(255,255,255,.24); font-weight: 800; }
.marca { display:flex; gap:.7rem; align-items:center; padding:.4rem .4rem 1.2rem; }
.marca b { font-size:1.25rem; line-height:1.1; font-weight:800; }
.marca small { opacity:.8; }

.hero { background: linear-gradient(110deg, #063B57 0%, #0E7FA8 60%, #3FC1D9 100%); color:#fff; border-radius:18px;
        padding:1.2rem 1.6rem; display:flex; align-items:center; gap:1rem; margin-bottom:1.2rem; }
.hero h1 { margin:0; font-size:1.9rem; font-weight:800; color:#fff; padding:0; }
.hero p { margin:0; opacity:.85; }
.titulo h2 { margin:.2rem 0 0; font-weight:800; color:#063B57; padding:0; }
.titulo p { margin:0 0 .8rem; color:#5A7A8C; }

.card { background:#fff; border-radius:16px; padding:1rem 1.2rem; border:1px solid #DDEBF2; border-left:6px solid #0E7FA8; margin-bottom:.6rem; }
.card .r { color:#5A7A8C; font-size:.85rem; font-weight:600; }
.card .v { color:#063B57; font-size:1.7rem; font-weight:800; line-height:1.2; }
.card .s { color:#5A7A8C; font-size:.8rem; }
.card.verde { border-left-color:#1E9E6A; } .card.laranja { border-left-color:#E8912D; } .card.vermelho { border-left-color:#D64545; }

.total { background:#063B57; color:#fff; border-radius:14px; padding:.8rem 1.2rem; font-size:1.5rem; font-weight:800; text-align:right; margin:.6rem 0; }
.entrega { background:#fff; border:1px solid #DDEBF2; border-radius:14px; padding:.8rem 1rem; margin-bottom:.6rem; }
.entrega.feita { opacity:.55; background:#EAF6EF; }
.entrega .n { display:inline-block; background:#0E7FA8; color:#fff; border-radius:50%; width:1.7rem; height:1.7rem; text-align:center;
              line-height:1.7rem; font-weight:800; margin-right:.5rem; }
.entrega .l { color:#43606F; font-size:.92rem; }
.entrega .valor { font-weight:800; color:#063B57; }
.fiado { background:#FDEBD3; color:#8A4B00; border-radius:8px; padding:0 .4rem; font-size:.8rem; font-weight:700; }
.cobrar { background:#DDF0FA; color:#075985; border-radius:8px; padding:0 .4rem; font-size:.8rem; font-weight:700; }
.pago { background:#DDF3E6; color:#146C43; border-radius:8px; padding:0 .4rem; font-size:.8rem; font-weight:700; }

.stButton > button[kind="primary"] { background:#0E7FA8; border:0; border-radius:10px; font-weight:700; }
.stButton > button { border-radius:10px; }
[data-testid="stSidebar"] .stButton > button { background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.45); }
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,.25); }
[data-testid="stForm"] { background:#fff; border-radius:16px; border:1px solid #DDEBF2; }
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] { background:#F2F8FB !important; border:1px solid #B9D4E2 !important; border-radius:10px !important; }
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea { background:transparent !important; }
</style>
"""


# ---------- componentes visuais ----------
def card(rotulo, valor, sub="", cor=""):
    st.markdown(f"<div class='card {cor}'><div class='r'>{rotulo}</div><div class='v'>{valor}</div>"
                f"<div class='s'>{sub}</div></div>", unsafe_allow_html=True)


def titulo(t, sub=""):
    st.markdown(f"<div class='titulo'><h2>{t}</h2><p>{sub}</p></div>", unsafe_allow_html=True)


def tabela(rows, colunas):
    if not rows:
        st.info("Nada por aqui ainda.")
        return
    d = pd.DataFrame(rows)[list(colunas)].rename(columns=colunas)
    st.dataframe(d, use_container_width=True, hide_index=True)


def ok_msg():
    if "ok" in st.session_state:
        st.success(st.session_state.pop("ok"))


def tentar_excluir(fn, id_, conf, msg):
    if not conf:
        st.error("Marque a caixa de confirmação para excluir.")
        return
    try:
        fn(id_)
        st.session_state.ok = msg
        st.rerun()
    except ValueError as e:
        st.error(str(e))


# ---------- PAINEL ----------
def pg_inicio():
    titulo("Painel", "Como está o dia na Água Nova")
    hoje = date.today().isoformat()
    v = banco.consultar("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM vendas WHERE status='Ativa' AND date(data)=?", (hoje,))[0]
    ent = banco.consultar("SELECT COUNT(*) n FROM vendas WHERE status='Ativa' AND tipo_entrega='Entrega' AND entregue=0 AND data_entrega<=?", (hoje,))[0]["n"]
    fiado = regras.resumo_fiado()
    na_rua = banco.consultar("SELECT COALESCE(SUM(qtd),0) n FROM emprestimos")[0]["n"]
    c = st.columns(4)
    with c[0]: card("Vendas de hoje", brl(v["t"]), f"{v['n']} pedidos")
    with c[1]: card("Entregas pendentes", ent, "para hoje ou atrasadas", "laranja")
    with c[2]: card("A receber (fiado)", brl(sum(f["saldo"] for f in fiado)), f"{len(fiado)} clientes devendo", "vermelho")
    with c[3]: card("Galões emprestados", na_rua, "com clientes", "verde")

    esq, dir_ = st.columns([3, 2])
    with esq:
        st.markdown("##### Vendas dos últimos 7 dias")
        dias = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        rows = banco.consultar("SELECT date(data) d, SUM(total) t FROM vendas WHERE status='Ativa' AND date(data)>=? GROUP BY date(data)", (dias[0],))
        mapa = {r["d"]: r["t"] for r in rows}
        barras([{"dia": d[8:10] + "/" + d[5:7], "v": mapa.get(d, 0)} for d in dias], "dia", "v")
    with dir_:
        st.markdown("##### Estoque baixo")
        baixos = banco.consultar("SELECT * FROM produtos WHERE ativo=1 AND est_min>0 AND est_cheio<=est_min ORDER BY nome")
        if not baixos:
            st.success("Tudo acima do mínimo ✅")
        for p in baixos:
            st.warning(f"**{regras.nome_produto(p)}**: {p['est_cheio']} em estoque (mínimo {p['est_min']})")


# ---------- VENDAS ----------
def pg_vendas():
    titulo("Vendas", "Pedidos de WhatsApp, telefone e balcão")
    aba1, aba2 = st.tabs(["🛒 Nova venda", "📋 Histórico"])
    with aba1:
        nova_venda()
    with aba2:
        historico()


def nova_venda():
    st.session_state.setdefault("carrinho", [])
    produtos = regras.listar_produtos()
    if not produtos:
        st.warning("Cadastre os produtos em ⚙️ Cadastros antes de vender.")
        return
    opcoes = {"👤 Cliente avulso (balcão)": None}
    for c in regras.listar_clientes():
        rot = f"{c['nome']} — {c['telefone'] or 'sem telefone'}"
        opcoes[rot if rot not in opcoes else f"{rot} (#{c['id']})"] = c

    a, b = st.columns([2, 1])
    cliente = opcoes[a.selectbox("Cliente (digite nome ou telefone para buscar)", list(opcoes))]
    origem = b.selectbox("Origem do pedido", ["WhatsApp", "Telefone", "Balcão"])
    if cliente:
        emp = regras.emprestimos_cliente(cliente["id"])
        emp_txt = ", ".join(f"{e['qtd']}× {e['vasilhame']}" for e in emp) or "nenhum"
        deve = regras.situacao_fiado(cliente["id"])["saldo"]
        st.caption(f"📍 {cliente['endereco'] or 'sem endereço'} · {cliente['bairro'] or 'sem bairro'} · "
                   f"frete {brl(regras.frete_cliente(cliente))}/galão · galões emprestados: {emp_txt} · "
                   f"deve: {brl(max(deve, 0))}")

    c3, c4, c5 = st.columns(3)
    entrega = c3.radio("Tipo", ["Entrega", "Retirada"], horizontal=True, index=1 if cliente is None else 0)
    if entrega == "Entrega":
        rotulos = {"A cobrar na entrega": "A cobrar", "Já pago – Pix": "Pix", "Já pago – Dinheiro": "Dinheiro",
                   "Já pago – Cartão": "Cartão", "Fiado": "Fiado"}
        pagamento = rotulos[c4.selectbox("Pagamento", list(rotulos))]
    else:
        pagamento = c4.selectbox("Pagamento", regras.FORMAS)
    data_ent = c5.date_input("Data da entrega", date.today()) if entrega == "Entrega" else None
    if cliente is None and (entrega == "Entrega" or pagamento == "Fiado"):
        st.warning("Cliente avulso não pode ter entrega nem fiado. Escolha um cliente cadastrado.")

    with st.container(border=True):
        st.markdown("**Adicionar item**")
        pmap = {regras.nome_produto(p): p for p in produtos}
        x1, x2, x3, x4 = st.columns([3, 2, 1, 2])
        p = pmap[x1.selectbox("Produto", list(pmap))]
        if p["tipo"] == "Galão":
            operacao, modo = x2.selectbox("Operação", regras.OPERACOES), "Unidade"
        else:
            operacao = ""
            modo = x2.selectbox("Vender por", ["Unidade", "Fardo"] if p["preco_fardo"] > 0 else ["Unidade"])
        qtd = x3.number_input("Qtd", 1, 999, 1)
        sug = regras.preco_sugerido(p, modo, operacao, cliente, entrega)
        preco = x4.number_input("Preço unitário (R$)", 0.0, value=float(sug), step=0.5, format="%.2f",
                                key=f"pr_{p['id']}_{modo}_{operacao}_{cliente['id'] if cliente else 0}_{entrega}")
        st.caption(f"Em estoque: {p['est_cheio']} {'galões cheios' if p['tipo'] == 'Galão' else 'unidades'}"
                   + (f" · {p['un_fardo']} un/fardo" if modo == "Fardo" else ""))
        if st.button("➕ Adicionar ao pedido"):
            st.session_state.carrinho.append(dict(produto_id=p["id"], nome=regras.nome_produto(p), modo=modo,
                                                  operacao=operacao, qtd=int(qtd), preco=float(preco)))
            st.rerun()

    st.markdown("##### Itens do pedido")
    total = 0.0
    if not st.session_state.carrinho:
        st.info("Nenhum item ainda.")
    for i, it in enumerate(st.session_state.carrinho):
        sub = it["qtd"] * it["preco"]
        total += sub
        r1, r2 = st.columns([8, 1])
        det = it["operacao"] or it["modo"]
        r1.markdown(f"**{it['qtd']}×** {it['nome']} ({det}) — {brl(it['preco'])} = **{brl(sub)}**")
        if r2.button("✖", key=f"rm{i}"):
            st.session_state.carrinho.pop(i)
            st.rerun()
    st.markdown(f"<div class='total'>Total: {brl(total)}</div>", unsafe_allow_html=True)
    obs = st.text_input("Observações do pedido")
    if st.button("✅ Finalizar venda", type="primary", disabled=not st.session_state.carrinho):
        try:
            vid = regras.registrar_venda(cliente["id"] if cliente else None, origem, entrega, pagamento,
                                         st.session_state.carrinho, obs, data_ent.isoformat() if data_ent else None)
            st.session_state.carrinho = []
            st.session_state.ok = f"Venda #{vid} registrada: {brl(total)} ({pagamento})."
            st.rerun()
        except ValueError as e:
            st.error(str(e))


def historico():
    rows = banco.consultar("""SELECT v.id, v.data, COALESCE(c.nome,'Cliente avulso') cliente, v.origem, v.tipo_entrega,
                              v.pagamento, v.total, v.status FROM vendas v LEFT JOIN clientes c ON c.id=v.cliente_id
                              ORDER BY v.id DESC LIMIT 200""")
    if not rows:
        st.info("Nenhuma venda registrada ainda.")
        return
    mostra = [{**r, "data": r["data"][:16], "total": brl(r["total"])} for r in rows]
    tabela(mostra, {"id": "Nº", "data": "Data", "cliente": "Cliente", "origem": "Origem", "tipo_entrega": "Tipo",
                    "pagamento": "Pagamento", "total": "Total", "status": "Status"})
    st.markdown("##### Ver itens ou cancelar uma venda")
    mapa = {f"#{r['id']} · {r['data'][:16]} · {r['cliente']} · {brl(r['total'])} · {r['status']}": r for r in rows}
    sel = mapa[st.selectbox("Venda", list(mapa))]
    tabela([{"i": f"{i['qtd']}× {regras.nome_produto(i)}", "o": i["operacao"] or i["modo"], "p": brl(i["preco"])}
            for i in regras.itens_da_venda(sel["id"])], {"i": "Item", "o": "Operação", "p": "Preço unit."})
    if sel["status"] == "Ativa":
        conf = st.checkbox("Confirmo o cancelamento (o estoque e os galões emprestados voltam ao que eram)")
        if st.button("Cancelar venda", disabled=not conf):
            regras.cancelar_venda(sel["id"])
            st.session_state.ok = f"Venda #{sel['id']} cancelada."
            st.rerun()


# ---------- ROTEIRO ----------
def selo_pagamento(p):
    if p["pagamento"] == "Fiado":
        return "<span class='fiado'>FIADO – não cobrar</span>"
    if p["pagamento"] == "A cobrar":
        return "<span class='cobrar'>💵 COBRAR</span>"
    return f"<span class='pago'>✅ JÁ PAGO ({html.escape(p['pagamento'])})</span>"


def html_roteiro(dia, grupos):
    """Página para imprimir (Cmd+P / Ctrl+P): uma folha por entregador, com caixinha para marcar 'entregue'."""
    css = ("<style>@page{margin:12mm} body{font-family:Arial,Helvetica,sans-serif;color:#0B2A3C;margin:0;padding:18px}"
           "header{border-bottom:4px solid #0E7FA8;padding-bottom:8px;margin-bottom:14px}"
           "h1{margin:0;font-size:22px;color:#063B57} h2{margin:4px 0 0;font-size:16px;color:#0E7FA8}"
           "table{width:100%;border-collapse:collapse;font-size:13px} th{background:#EAF3F8;text-align:left}"
           "th,td{border:1px solid #9DB8C7;padding:6px 8px;vertical-align:top}"
           ".box{display:inline-block;width:16px;height:16px;border:2px solid #063B57;border-radius:3px}"
           ".tot{margin-top:10px;font-weight:bold;text-align:right;font-size:15px}"
           "section{page-break-after:always} section:last-child{page-break-after:auto}"
           "@media print{body{padding:0}}</style>")
    h = []
    for nome, lista in grupos:
        lista = [p for p in lista if not p["entregue"]]
        if not lista:
            continue
        h.append(f"<section><header><h1>💧 Distribuidora Água Nova</h1><h2>Roteiro de {dia:%d/%m/%Y} · "
                 f"{html.escape(nome or 'Sem entregador')} · {len(lista)} entregas</h2></header>"
                 "<table><tr><th>✔</th><th>#</th><th>Cliente</th><th>Endereço</th><th>Itens</th><th>Cobrança</th></tr>")
        for i, p in enumerate(lista, 1):
            obs = f"<br><i>Obs.: {html.escape(p['obs'])}</i>" if p.get("obs") else ""
            h.append(f"<tr><td><span class='box'></span></td><td>{i}</td>"
                     f"<td><b>{html.escape(p['cliente'])}</b><br>{html.escape(p['telefone'] or '')}</td>"
                     f"<td>{html.escape(p['endereco'] or '')}<br>{html.escape(p['bairro'])}</td>"
                     f"<td>{html.escape(p['itens'])}{obs}</td><td>{html.escape(regras.texto_cobranca(p, emoji=False))}</td></tr>")
        total = sum(p["total"] for p in lista if p["pagamento"] == "A cobrar")
        h.append(f"</table><div class='tot'>Total a cobrar: {brl(total)}</div></section>")
    if not h:
        h.append("<p>Nenhuma entrega pendente.</p>")
    return f"<html><head><meta charset='utf-8'><title>Roteiro {dia:%d/%m/%Y}</title>{css}</head><body>" + "".join(h) + "</body></html>"


def pg_roteiro():
    titulo("Roteiro de Entregas", "Sequência, cliente, endereço, itens e valor")
    nomes = regras.nomes_entregadores()
    tels = regras.telefones_entregadores()
    with st.expander("✏️ Entregadores (nome e WhatsApp)"):
        c1, c2 = st.columns(2)
        n1 = c1.text_input("Entregador 1", nomes[0])
        t1 = c1.text_input("WhatsApp do entregador 1 (opcional)", tels[0], placeholder="(19) 99999-0000")
        n2 = c2.text_input("Entregador 2", nomes[1])
        t2 = c2.text_input("WhatsApp do entregador 2 (opcional)", tels[1], placeholder="(19) 99999-0000")
        if st.button("Salvar entregadores"):
            regras.salvar_nomes([n1.strip() or "Entregador 1", n2.strip() or "Entregador 2"], [t1.strip(), t2.strip()])
            st.rerun()
    dia = st.date_input("Data das entregas", date.today())
    pedidos = regras.pedidos_entrega(dia.isoformat())
    if not pedidos:
        st.info("Nenhuma entrega para esta data.")
        return
    itens = regras.itens_por_venda([p["id"] for p in pedidos])
    for p in pedidos:
        p["itens"] = itens.get(p["id"], "")
    rv = st.session_state.setdefault("rv", 0)

    if st.button("🪄 Sugerir divisão entre os entregadores"):
        regras.aplicar_divisao(regras.sugerir_divisao([p for p in pedidos if not p["entregue"]], nomes))
        st.session_state.rv += 1
        st.rerun()
    st.caption("A sugestão agrupa por zona e divide as entregas em partes iguais. Ajuste o entregador e a ordem na tabela e clique em salvar. "
               "**A cobrar** = o entregador recebe na porta. Depois de entregar, troque para como o cliente pagou (Dinheiro, Pix, Cartão) ou Fiado.")
    d = pd.DataFrame([{"ID": p["id"], "Entregador": p["entregador"] or None, "Ordem": p["ordem"],
                       "Entregue": bool(p["entregue"]), "Cliente": p["cliente"], "Bairro": p["bairro"],
                       "Zona": p["zona"], "Endereço": p["endereco"], "Itens": p["itens"],
                       "Valor": brl(p["total"]), "Pgto": p["pagamento"]} for p in pedidos])
    ed = st.data_editor(d, hide_index=True, use_container_width=True, key=f"ed_{dia}_{rv}",
                        disabled=["ID", "Cliente", "Bairro", "Zona", "Endereço", "Itens", "Valor"],
                        column_config={"Entregador": st.column_config.SelectboxColumn(options=nomes),
                                       "Ordem": st.column_config.NumberColumn(min_value=0, step=1),
                                       "Pgto": st.column_config.SelectboxColumn("Pagamento", options=regras.FORMAS_ENTREGA)})
    if st.button("💾 Salvar roteiro", type="primary"):
        for _, r in ed.iterrows():
            regras.salvar_roteiro(int(r["ID"]), r["Entregador"] if pd.notna(r["Entregador"]) else "",
                                  int(r["Ordem"]), bool(r["Entregue"]), r["Pgto"])
        st.session_state.rv += 1
        st.session_state.ok = "Roteiro salvo."
        st.rerun()

    st.markdown("##### Resumo para os entregadores")
    grupos = [(n, sorted([p for p in pedidos if p["entregador"] == n], key=lambda p: p["ordem"])) for n in nomes]
    grupos.append(("", [p for p in pedidos if p["entregador"] not in nomes]))
    cols = st.columns(2)
    for idx, (nome, lista) in enumerate(grupos):
        alvo = cols[idx] if idx < 2 else st.container()
        with alvo:
            st.markdown(f"**{nome or 'Sem entregador'}** · {len(lista)} entregas")
            for p in lista:
                st.markdown(
                    f"<div class='entrega {'feita' if p['entregue'] else ''}'>"
                    f"<span class='n'>{p['ordem'] or '·'}</span><b>{html.escape(p['cliente'])}</b><br>"
                    f"<span class='l'>📍 {html.escape(p['endereco'] or 'sem endereço')} — {html.escape(p['bairro'])}<br>"
                    f"📦 {html.escape(p['itens'])}</span><br>"
                    f"<span class='valor'>{brl(p['total'])}</span> · {selo_pagamento(p)}</div>", unsafe_allow_html=True)

    st.markdown("##### 📲 Mensagem para o WhatsApp dos entregadores")
    st.caption("Só as entregas ainda não marcadas como entregues. Use o botão de copiar no canto da caixa e cole no WhatsApp, "
               "ou abra direto pelo botão (em roteiros muito longos, prefira copiar).")
    algum = False
    for idx, (nome, lista) in enumerate(grupos[:len(nomes)]):
        pend = [p for p in lista if not p["entregue"]]
        if not pend:
            continue
        algum = True
        msg = regras.mensagem_whatsapp(dia, nome, pend)
        with st.expander(f"{nome} · {len(pend)} entregas", expanded=True):
            st.code(msg, language=None, wrap_lines=True)
            st.link_button("📲 Abrir no WhatsApp", regras.link_whatsapp(tels[idx], msg))
    sem = [p for p in grupos[-1][1] if not p["entregue"]]
    if sem:
        st.info(f"{len(sem)} entrega(s) ainda sem entregador. Defina na tabela acima para gerar a mensagem.")
    elif not algum:
        st.info("Nenhuma entrega pendente para enviar.")
    st.download_button("🖨️ Baixar roteiro para imprimir", html_roteiro(dia, grupos),
                       file_name=f"roteiro_{dia.isoformat()}.html", mime="text/html")
    st.caption("Abra o arquivo baixado e imprima com Cmd + P (Ctrl + P no Windows). Sai uma folha por entregador.")


# ---------- CLIENTES ----------
def form_cliente(c=None):
    bairros = regras.listar_bairros()
    if not bairros:
        st.warning("Cadastre os bairros primeiro em ⚙️ Cadastros.")
    bmap = {"(sem bairro)": None}
    bmap.update({f"{b['nome']} ({b['zona']}) · frete {brl(b['frete'])}": b["id"] for b in bairros})
    rotulos = list(bmap)
    idx = next((i for i, v in enumerate(bmap.values()) if c and v == c["bairro_id"]), 0)
    with st.form(f"form_cliente_{c['id'] if c else 0}", clear_on_submit=c is None):
        nome = st.text_input("Nome *", c["nome"] if c else "")
        tel = st.text_input("Telefone / WhatsApp", c["telefone"] if c else "")
        end = st.text_input("Endereço (rua e número)", c["endereco"] if c else "")
        bairro = st.selectbox("Bairro", rotulos, index=idx)
        esp = st.checkbox("Cliente com frete especial", value=bool(c and c["frete_especial"] is not None))
        val = st.number_input("Frete especial por galão (R$)", 0.0, value=float(c["frete_especial"] or 0) if c else 0.0, step=0.5)
        galoes = regras.listar_vasilhames()
        atual = {e["vasilhame_id"]: e["qtd"] for e in regras.emprestimos_cliente(c["id"])} if c else {}
        if galoes:
            st.markdown("**Galões emprestados a este cliente** (altere para corrigir o saldo)")
        saldos = {g["id"]: st.number_input(g["nome"], 0, 999, int(atual.get(g["id"], 0))) for g in galoes}
        volta = st.checkbox("Se o saldo diminuiu, os galões voltaram vazios ao depósito (somar ao estoque de vazios). "
                            "Desmarque se for só correção de digitação.", value=True) if (c and galoes) else False
        obs = st.text_area("Observações", c["obs"] if c else "")
        conf = st.checkbox("Marque para confirmar a exclusão deste cliente") if c else False
        salvar = st.form_submit_button("💾 Salvar cliente", type="primary")
        excluir = st.form_submit_button("🗑️ Excluir cliente") if c else False
        if excluir:
            tentar_excluir(regras.excluir_cliente, c["id"], conf, "Cliente excluído.")
        if salvar:
            if not nome.strip():
                st.error("Informe o nome do cliente.")
            else:
                cid = regras.salvar_cliente(dict(nome=nome.strip(), telefone=tel.strip(), endereco=end.strip(),
                                           bairro_id=bmap[bairro], frete_especial=val if esp else None,
                                           obs=obs, ativo=1), c["id"] if c else None)
                for gid, q in saldos.items():
                    regras.definir_emprestimo(cid, gid, int(q), volta)
                st.session_state.ok = f"Cliente {nome.strip()} salvo."
                st.rerun()


def pg_clientes():
    titulo("Clientes", "Cadastro, frete especial e galões emprestados")
    aba1, aba2, aba3 = st.tabs(["🔎 Buscar e editar", "➕ Novo cliente", "🫙 Resumo de galões emprestados"])
    with aba1:
        busca = st.text_input("Buscar por nome ou telefone").strip().lower()
        clientes = [c for c in regras.listar_clientes(todos=True)
                    if not busca or busca in c["nome"].lower() or busca in (c["telefone"] or "").lower()]
        tabela([{"n": c["nome"], "t": c["telefone"], "e": c["endereco"],
                 "b": c["bairro"] or "—",
                 "f": brl(regras.frete_cliente(c)) + (" ★" if c["frete_especial"] is not None else ""),
                 "g": c["emprestados"]} for c in clientes],
               {"n": "Nome", "t": "Telefone", "e": "Endereço", "b": "Bairro", "f": "Frete/galão", "g": "Galões emprestados"})
        st.caption("★ = frete especial")
        if clientes:
            mapa = {f"{c['nome']} — {c['telefone'] or 'sem telefone'} (#{c['id']})": c for c in clientes}
            st.markdown("##### Editar cliente")
            form_cliente(mapa[st.selectbox("Cliente", list(mapa))])
    with aba2:
        form_cliente(None)
    with aba3:
        emp = regras.emprestimos_cliente()
        totais = {}
        for e in emp:
            totais[e["vasilhame"]] = totais.get(e["vasilhame"], 0) + e["qtd"]
        if totais:
            for col, (n, q) in zip(st.columns(len(totais)), totais.items()):
                with col:
                    card(n, q, "galões na rua", "verde")
        tabela([{"c": e["cliente"], "p": e["vasilhame"], "q": e["qtd"]} for e in emp],
               {"c": "Cliente", "p": "Vasilhame", "q": "Quantidade"})
        st.caption("Para alterar o saldo de um cliente, edite o cadastro dele na aba Buscar e editar.")


# ---------- ESTOQUE ----------
def pg_estoque():
    titulo("Estoque", "Produtos cheios, galões vazios, entradas e perdas")
    produtos = regras.listar_produtos()
    if not produtos:
        st.warning("Cadastre os produtos em ⚙️ Cadastros.")
        return
    vasilhames = regras.listar_vasilhames()
    aba1, aba2, aba3, aba4 = st.tabs(["📦 Estoque atual", "⬇️ Entrada de mercadoria", "🛠️ Ajuste / perdas", "🧾 Movimentações"])
    pmap = {regras.nome_produto(p): p for p in produtos}
    vmap = {v["nome"]: v["id"] for v in vasilhames}
    with aba1:
        rows = []
        for p in produtos:
            g = p["tipo"] == "Galão"
            baixo = p["est_min"] > 0 and p["est_cheio"] <= p["est_min"]
            rows.append({"p": regras.nome_produto(p), "c": p["est_cheio"],
                         "f": "—" if g else p["est_cheio"] // max(p["un_fardo"], 1),
                         "m": p["est_min"], "s": "⚠️ Baixo" if baixo else "✅ Ok"})
        tabela(rows, {"p": "Produto", "c": "Cheios / unidades", "f": "Fardos completos", "m": "Mínimo", "s": "Situação"})
        st.markdown("##### Galões vazios (por vasilhame, sem separar por marca)")
        tabela([{"n": v["nome"], "e": v["est_vazio"], "r": v["emprestados"]} for v in vasilhames],
               {"n": "Vasilhame", "e": "Vazios no depósito", "r": "Emprestados a clientes"})
    with aba2:
        with st.form("entrada", clear_on_submit=True):
            forn = st.text_input("Fornecedor")
            p = pmap[st.selectbox("Produto", list(pmap))]
            c1, c2, c3 = st.columns(3)
            modo = c1.selectbox("Entrada por", ["Unidade", "Fardo"])
            qtd = c2.number_input("Quantidade", 1, 99999, 1)
            custo = c3.number_input("Valor pago por unidade/fardo (R$)", 0.0, step=0.5, format="%.2f")
            st.caption("Galões entram como galões cheios. O valor pago entra automaticamente nas despesas do Financeiro.")
            st.markdown("**Troca de galões no fornecedor** (só para galões)")
            c4, c5 = st.columns(2)
            env = c4.number_input("Galões vazios enviados ao fornecedor", 0, 99999, 0)
            opcoes_v = {"Automático (o vasilhame do produto)": None, **vmap}
            vas = opcoes_v[c5.selectbox("Vasilhame enviado", list(opcoes_v))]
            if st.form_submit_button("Registrar entrada", type="primary"):
                try:
                    regras.entrada_mercadoria(forn, p["id"], modo, int(qtd), custo, vazios_enviados=int(env), vasilhame_id=vas)
                    st.session_state.ok = "Entrada registrada e estoque atualizado."
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        compras = regras.listar_compras()
        tabela([{**x, "data": x["data"][:16], "total": brl(x["total"])} for x in compras[:30]],
               {"id": "Nº", "data": "Data", "fornecedor": "Fornecedor", "prod": "Produto", "qtd": "Qtd", "modo": "Por",
                "total": "Total", "vazios_enviados": "Vazios enviados"})
        if compras:
            st.markdown("##### ✏️ Corrigir ou excluir um lançamento de entrada")
            st.caption("O estoque e as despesas do Financeiro se ajustam sozinhos, e o estorno fica no histórico de movimentações.")
            cmap = {f"#{x['id']} · {x['data'][:16]} · {x['fornecedor']} · {x['prod']} · {x['qtd']} ({x['modo']}) · {brl(x['total'])}": x
                    for x in compras}
            ce = cmap[st.selectbox("Lançamento", list(cmap))]
            pnomes = list(pmap)
            ip = next((i for i, n in enumerate(pnomes) if pmap[n]["id"] == ce["produto_id"]), 0)
            op_v = {"Automático (o vasilhame do produto)": None, **vmap}
            iv = next((i for i, v in enumerate(op_v.values()) if v == ce["vasilhame_id"]), 0)
            with st.form(f"fedit_{ce['id']}"):
                e1, e2 = st.columns(2)
                ef = e1.text_input("Fornecedor", ce["fornecedor"], key=f"ef_{ce['id']}")
                ep = pmap[e2.selectbox("Produto", pnomes, index=ip, key=f"ep_{ce['id']}")]
                e3, e4, e5 = st.columns(3)
                em = e3.selectbox("Entrada por", ["Unidade", "Fardo"], index=0 if ce["modo"] == "Unidade" else 1, key=f"em_{ce['id']}")
                eq = e4.number_input("Quantidade", 1, 99999, int(ce["qtd"]), key=f"eq_{ce['id']}")
                ec = e5.number_input("Valor pago por unidade/fardo (R$)", 0.0, value=float(ce["custo_unit"]), step=0.5,
                                     format="%.2f", key=f"ec_{ce['id']}")
                e6, e7 = st.columns(2)
                ev = e6.number_input("Galões vazios enviados", 0, 99999, int(ce["vazios_enviados"]), key=f"ev_{ce['id']}")
                evs = op_v[e7.selectbox("Vasilhame enviado", list(op_v), index=iv, key=f"evs_{ce['id']}")]
                conf = st.checkbox("Marque para confirmar a exclusão deste lançamento", key=f"cf_{ce['id']}")
                salvar = st.form_submit_button("💾 Salvar correção", type="primary")
                excluir = st.form_submit_button("🗑️ Excluir lançamento")
                if excluir:
                    tentar_excluir(regras.excluir_compra, ce["id"], conf, "Lançamento excluído. Estoque e despesas foram ajustados.")
                if salvar:
                    try:
                        regras.editar_compra(ce["id"], ef, ep["id"], em, int(eq), ec, int(ev), evs)
                        st.session_state.ok = "Lançamento corrigido. Estoque e despesas foram ajustados."
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))
    with aba3:
        st.markdown("##### Produtos cheios")
        with st.form("ajuste", clear_on_submit=True):
            p = pmap[st.selectbox("Produto", list(pmap), key="aj_prod")]
            motivo = st.selectbox("Motivo", ["Estoque inicial", "Perda / quebra", "Correção de contagem", "Outro"])
            dc = st.number_input("Cheios / unidades (use negativo para reduzir)", value=0, step=1)
            if st.form_submit_button("Aplicar ajuste", type="primary"):
                try:
                    regras.ajustar_estoque(p["id"], int(dc), motivo)
                    st.session_state.ok = "Ajuste aplicado."
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        st.markdown("##### Galões vazios (informe o estoque inicial aqui)")
        if not vasilhames:
            st.info("Cadastre os vasilhames em ⚙️ Cadastros > Vasilhames.")
        else:
            with st.form("ajuste_vas", clear_on_submit=True):
                vn = st.selectbox("Vasilhame", list(vmap))
                motivo_v = st.selectbox("Motivo ", ["Estoque inicial", "Correção de contagem", "Perda / quebra", "Outro"])
                dv = st.number_input("Vazios (use negativo para reduzir)", value=0, step=1)
                if st.form_submit_button("Aplicar ajuste de vazios", type="primary"):
                    try:
                        regras.ajustar_vasilhame(vmap[vn], int(dv), motivo_v)
                        st.session_state.ok = "Ajuste de vazios aplicado."
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
    with aba4:
        rows = banco.consultar("""SELECT m.data, COALESCE(TRIM(p.nome||' '||p.marca||' '||p.tamanho),'—') prod,
                                  COALESCE(v.nome,'—') vas, m.tipo, m.d_cheio, m.d_vazio, m.ref
                                  FROM movimentos m LEFT JOIN produtos p ON p.id=m.produto_id
                                  LEFT JOIN vasilhames v ON v.id=m.vasilhame_id ORDER BY m.id DESC LIMIT 150""")
        tabela([{**r, "data": r["data"][:16]} for r in rows],
               {"data": "Data", "prod": "Produto", "vas": "Vasilhame", "tipo": "Tipo", "d_cheio": "Δ Cheios",
                "d_vazio": "Δ Vazios", "ref": "Ref."})


# ---------- FIADO ----------
def pg_fiado():
    titulo("Fiado", "Quem está devendo e há quanto tempo")
    dev = regras.resumo_fiado()
    card("Total a receber", brl(sum(d["saldo"] for d in dev)), f"{len(dev)} clientes", "vermelho")
    if not dev:
        st.success("Nenhum cliente devendo 🎉")
        return
    tabela([{"c": d["nome"], "t": d["telefone"], "s": brl(d["saldo"]), "d": d["dias"]} for d in dev],
           {"c": "Cliente", "t": "Telefone", "s": "Deve", "d": "Dias em aberto"})
    mapa = {f"{d['nome']} — {brl(d['saldo'])}": d for d in dev}
    sel = mapa[st.selectbox("Registrar pagamento de", list(mapa))]
    st.caption(f"Total comprado fiado: {brl(sel['total'])} · já pago: {brl(sel['pago'])} · saldo: {brl(sel['saldo'])}")
    with st.form("pag", clear_on_submit=True):
        valor = st.number_input("Valor pago (R$)", 0.01, max(float(sel["saldo"]), 0.01), float(sel["saldo"]), step=1.0, format="%.2f")
        forma = st.selectbox("Forma de pagamento", ["Dinheiro", "Pix", "Cartão"])
        obs = st.text_input("Observação")
        if st.form_submit_button("Registrar pagamento", type="primary"):
            try:
                regras.registrar_pagamento(sel["id"], float(valor), forma, obs)
                st.session_state.ok = f"Pagamento de {brl(valor)} registrado para {sel['nome']}."
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ---------- FINANCEIRO E RELATÓRIOS ----------
def periodo(chave):
    hoje = date.today()
    op = st.radio("Período", ["Este mês", "Mês passado", "Últimos 30 dias", "Personalizado"], horizontal=True, key=f"per_{chave}")
    if op == "Este mês":
        ini, fim = hoje.replace(day=1), hoje
    elif op == "Mês passado":
        fim = hoje.replace(day=1) - timedelta(days=1)
        ini = fim.replace(day=1)
    elif op == "Últimos 30 dias":
        ini, fim = hoje - timedelta(days=29), hoje
    else:
        c1, c2 = st.columns(2)
        ini = c1.date_input("De", hoje.replace(day=1), key=f"di_{chave}")
        fim = c2.date_input("Até", hoje, key=f"df_{chave}")
    st.caption(f"Período: {ini:%d/%m/%Y} a {fim:%d/%m/%Y}")
    return ini.isoformat(), fim.isoformat()


def barras(rows, rotulo, valor, horizontal=False):
    """Gráfico de barras com o valor (R$) escrito em cada barra."""
    if not rows:
        return
    d = pd.DataFrame(rows)[[rotulo, valor]]
    d.columns = ["item", "valor"]
    d["texto"] = [brl(v) if v else "" for v in d["valor"]]
    topo = max(float(d["valor"].max()) * 1.25, 1.0)
    escala = alt.Scale(domain=[0, topo])
    cor, tinta = "#0E7FA8", "#063B57"
    if horizontal:
        base = alt.Chart(d).encode(y=alt.Y("item:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
                                   x=alt.X("valor:Q", scale=escala, axis=None))
        barra = base.mark_bar(color=cor, cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
        texto = base.mark_text(align="left", dx=6, fontWeight="bold", color=tinta).encode(text="texto:N")
        altura = max(120, 36 * len(d))
    else:
        base = alt.Chart(d).encode(x=alt.X("item:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                                   y=alt.Y("valor:Q", scale=escala, axis=None))
        barra = base.mark_bar(color=cor, cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        texto = base.mark_text(dy=-8, fontWeight="bold", color=tinta).encode(text="texto:N")
        altura = 300
    st.altair_chart((barra + texto).properties(height=altura), use_container_width=True)


def grafico(rows, rotulo, valor):
    barras(rows, rotulo, valor, horizontal=True)


def pg_financeiro():
    titulo("Financeiro", "Faturamento bruto x despesas = lucro ou prejuízo")
    ini, fim = periodo("fin")
    aba1, aba2 = st.tabs(["📈 Resumo", "🧾 Despesas"])
    with aba1:
        r = regras.resumo_financeiro(ini, fim)
        c = st.columns(3)
        with c[0]: card("Faturamento bruto", brl(r["faturamento"]), f"{r['pedidos']} vendas")
        with c[1]: card("Despesas", brl(r["total_desp"]), "lançadas + compras de mercadoria", "laranja")
        with c[2]: card("Lucro" if r["lucro"] >= 0 else "Prejuízo", brl(abs(r["lucro"])), "faturamento − despesas",
                        "verde" if r["lucro"] >= 0 else "vermelho")
        st.caption(f"Despesas = {brl(r['despesas'])} lançadas na aba Despesas + {brl(r['compras'])} em compras de mercadoria "
                   "(entradas no estoque). Não lance compra de mercadoria duas vezes.")
        st.caption(f"Entrou em caixa no período: {brl(r['entrou'])} · Vendido no fiado no período: {brl(r['fiado'])}.")
    with aba2:
        with st.form("desp", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            data = c1.date_input("Data", date.today())
            cat = c2.selectbox("Categoria", regras.CATEGORIAS)
            valor = c3.number_input("Valor (R$)", 0.0, step=10.0, format="%.2f")
            desc = st.text_input("Descrição (opcional)")
            if st.form_submit_button("➕ Registrar despesa", type="primary"):
                if valor <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    regras.salvar_despesa(data.isoformat(), cat, desc, valor)
                    st.session_state.ok = "Despesa registrada."
                    st.rerun()
        lista = regras.listar_despesas(ini, fim)
        tabela([{**d, "data": d["data"][:10], "valor": brl(d["valor"])} for d in lista],
               {"data": "Data", "categoria": "Categoria", "descricao": "Descrição", "valor": "Valor"})
        if lista:
            cats = {}
            for d in lista:
                cats[d["categoria"]] = cats.get(d["categoria"], 0) + d["valor"]
            grafico([{"cat": k, "v": v} for k, v in cats.items()], "cat", "v")
            mapa = {f"{d['data'][:10]} · {d['categoria']} · {brl(d['valor'])} · {d['descricao']} (#{d['id']})": d["id"] for d in lista}
            sel = st.selectbox("Excluir uma despesa lançada errada", list(mapa))
            if st.button("🗑️ Excluir despesa"):
                regras.excluir_despesa(mapa[sel])
                st.session_state.ok = "Despesa excluída."
                st.rerun()


def pg_relatorios():
    titulo("Relatórios", "O que vende, quem compra e onde")
    ini, fim = periodo("rel")
    r = regras.resumo_financeiro(ini, fim)
    c = st.columns(3)
    with c[0]: card("Faturamento", brl(r["faturamento"]))
    with c[1]: card("Vendas", r["pedidos"], "pedidos no período", "verde")
    with c[2]: card("Ticket médio", brl(r["ticket"]), "valor médio por pedido", "laranja")
    aba1, aba2, aba3, aba4 = st.tabs(["🏆 Produtos", "👥 Clientes", "📍 Bairros e canais", "⭐ Frete fora do padrão"])
    with aba1:
        rows = regras.por_produto(ini, fim)
        tabela([{"p": x["produto"], "u": x["un"], "f": brl(x["fat"])} for x in rows],
               {"p": "Produto", "u": "Unidades vendidas", "f": "Faturamento"})
        grafico([{"p": x["produto"], "f": x["fat"]} for x in rows[:10]], "p", "f")
    with aba2:
        rows = regras.top_clientes(ini, fim)
        tabela([{**x, "fat": brl(x["fat"])} for x in rows], {"cliente": "Cliente", "pedidos": "Pedidos", "fat": "Faturamento"})
    with aba3:
        rows = regras.por_bairro(ini, fim)
        st.markdown("**Vendas por bairro**")
        tabela([{**x, "fat": brl(x["fat"])} for x in rows], {"bairro": "Bairro", "pedidos": "Pedidos", "fat": "Faturamento"})
        grafico(rows[:10], "bairro", "fat")
        st.markdown("**Vendas por canal**")
        rows = regras.por_canal(ini, fim)
        tabela([{**x, "fat": brl(x["fat"])} for x in rows], {"origem": "Canal", "pedidos": "Pedidos", "fat": "Faturamento"})
    with aba4:
        st.caption("Clientes com frete diferente do padrão do bairro. Útil para decidir se vale padronizar.")
        tabela([{"c": x["nome"], "b": x["bairro"] or "—", "p": brl(x["frete_bairro"]), "e": brl(x["frete_especial"]),
                 "d": brl(x["frete_especial"] - (x["frete_bairro"] or 0))} for x in regras.fora_do_padrao()],
               {"c": "Cliente", "b": "Bairro", "p": "Frete do bairro", "e": "Frete especial", "d": "Diferença por galão"})


# ---------- CADASTROS ----------
def pg_cadastros():
    titulo("Cadastros", "Produtos, bairros e zonas de entrega")
    aba1, aba2, aba3, aba4 = st.tabs(["🧴 Produtos", "🫙 Vasilhames", "📍 Bairros e fretes", "🔐 Acesso"])
    with aba1:
        todos = regras.listar_produtos(todos=True)
        vas = regras.listar_vasilhames()
        vmap = {x["nome"]: x["id"] for x in vas}
        vnome = {x["id"]: x["nome"] for x in vas}
        tabela([{"p": regras.nome_produto(p), "t": p["tipo"], "u": brl(p["preco_unit"]),
                 "f": brl(p["preco_fardo"]) if p["tipo"] == "Descartável" else "—",
                 "n": brl(p["preco_novo"]) if p["tipo"] == "Galão" else "—",
                 "v": vnome.get(p["vasilhame_id"], "—") if p["tipo"] == "Galão" else "—",
                 "m": p["est_min"]} for p in todos],
               {"p": "Produto", "t": "Tipo", "u": "Preço unit./troca", "f": "Preço fardo", "n": "Galão novo",
                "v": "Vasilhame", "m": "Mín."})
        mapa = {"➕ Novo produto": None}
        mapa.update({regras.nome_produto(p): p for p in todos})
        p = mapa[st.selectbox("Cadastrar ou editar", list(mapa))]
        pid = p["id"] if p else 0
        tipo = st.radio("Tipo de produto", ["Galão", "Descartável"], horizontal=True,
                        index=0 if not p or p["tipo"] == "Galão" else 1, key=f"tipo_{pid}")
        with st.form(f"fprod_{pid}_{tipo}", clear_on_submit=p is None):
            g = tipo == "Galão"
            nome = st.text_input("Nome (ex.: Galão 20L)" if g else "Nome (ex.: Água Mineral)", p["nome"] if p else "")
            marca = tamanho = ""
            un_fardo, pf, pn = 1, 0.0, 0.0
            vas_sel = None
            if not g:
                c1, c2 = st.columns(2)
                marca = c1.text_input("Marca", p["marca"] if p else "")
                tamanho = c2.text_input("Tamanho (ex.: 500ml)", p["tamanho"] if p else "")
                un_fardo = st.number_input("Unidades por fardo", 1, 999, int(p["un_fardo"]) if p else 12)
                c3, c4 = st.columns(2)
                pu = c3.number_input("Preço da unidade (R$)", 0.0, value=float(p["preco_unit"]) if p else 0.0, step=0.5)
                pf = c4.number_input("Preço do fardo (R$)", 0.0, value=float(p["preco_fardo"]) if p else 0.0, step=0.5)
            else:
                c3, c4 = st.columns(2)
                pu = c3.number_input("Preço base da troca (R$, sem frete)", 0.0, value=float(p["preco_unit"]) if p else 0.0, step=0.5)
                pn = c4.number_input("Preço do galão novo (R$, sem frete)", 0.0, value=float(p["preco_novo"]) if p else 0.0, step=0.5)
                if vmap:
                    nomes_v = list(vmap)
                    atual_v = next((n for n, i in vmap.items() if p and i == p["vasilhame_id"]), nomes_v[0])
                    vas_sel = st.selectbox("Vasilhame (o galão vazio que ele usa)", nomes_v, index=nomes_v.index(atual_v))
                else:
                    st.warning("Cadastre primeiro os vasilhames na aba 🫙 Vasilhames.")
            em = st.number_input("Estoque mínimo (gera alerta)", 0, 99999, int(p["est_min"]) if p else 0)
            ic = 0
            if not p:
                ic = st.number_input("Estoque inicial (cheios/unidades)", 0, 99999, 0)
            conf = st.checkbox("Marque para confirmar a exclusão deste produto") if p else False
            salvar = st.form_submit_button("💾 Salvar produto", type="primary")
            excluir = st.form_submit_button("🗑️ Excluir produto") if p else False
            if excluir:
                tentar_excluir(regras.excluir_produto, p["id"], conf, "Produto excluído.")
            if salvar:
                if not nome.strip():
                    st.error("Informe o nome do produto.")
                elif g and vas_sel is None:
                    st.error("Escolha o vasilhame do galão.")
                else:
                    regras.salvar_produto(dict(nome=nome.strip(), marca=marca.strip(), tipo=tipo, tamanho=tamanho.strip(),
                                               un_fardo=int(un_fardo), preco_unit=pu, preco_fardo=pf, preco_novo=pn,
                                               est_min=int(em), ativo=1,
                                               vasilhame_id=vmap.get(vas_sel)), p["id"] if p else None, int(ic))
                    st.session_state.ok = "Produto salvo."
                    st.rerun()
    with aba2:
        vas = regras.listar_vasilhames()
        tabela([{"n": x["nome"], "e": x["est_vazio"], "r": x["emprestados"]} for x in vas],
               {"n": "Vasilhame", "e": "Vazios no depósito", "r": "Emprestados"})
        st.caption("O galão vazio não tem marca: é separado só por tipo/tamanho (ex.: Galão Comum 20L, Galão Ibirá 20L). "
                   "Para informar a quantidade de vazios, use Estoque > Ajuste / perdas.")
        mapa = {"➕ Novo vasilhame": None}
        mapa.update({x["nome"]: x for x in vas})
        vs = mapa[st.selectbox("Cadastrar ou editar vasilhame", list(mapa))]
        with st.form(f"fvas_{vs['id'] if vs else 0}", clear_on_submit=vs is None):
            nome = st.text_input("Nome do vasilhame (ex.: Galão Comum 20L)", vs["nome"] if vs else "")
            conf = st.checkbox("Marque para confirmar a exclusão deste vasilhame") if vs else False
            salvar = st.form_submit_button("💾 Salvar vasilhame", type="primary")
            excluir = st.form_submit_button("🗑️ Excluir vasilhame") if vs else False
            if excluir:
                tentar_excluir(regras.excluir_vasilhame, vs["id"], conf, "Vasilhame excluído.")
            if salvar:
                if not nome.strip():
                    st.error("Informe o nome do vasilhame.")
                else:
                    try:
                        regras.salvar_vasilhame(nome.strip(), vs["id"] if vs else None)
                        st.session_state.ok = "Vasilhame salvo."
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Já existe um vasilhame com esse nome.")
    with aba3:
        todos = regras.listar_bairros(todos=True)
        tabela([{"n": b["nome"], "z": b["zona"], "f": brl(b["frete"])} for b in todos],
               {"n": "Bairro", "z": "Zona", "f": "Frete por galão"})
        mapa = {"➕ Novo bairro": None}
        mapa.update({b["nome"]: b for b in todos})
        b = mapa[st.selectbox("Cadastrar ou editar bairro", list(mapa))]
        zonas = sorted({x["zona"] for x in todos})
        with st.form(f"fbairro_{b['id'] if b else 0}", clear_on_submit=b is None):
            nome = st.text_input("Nome do bairro", b["nome"] if b else "")
            zona = st.text_input("Zona de entrega", b["zona"] if b else "")
            if zonas:
                st.caption("Zonas já usadas: " + ", ".join(zonas))
            frete = st.number_input("Frete embutido por galão (R$)", 0.0, value=float(b["frete"]) if b else 0.0, step=0.5)
            conf = st.checkbox("Marque para confirmar a exclusão deste bairro") if b else False
            salvar = st.form_submit_button("💾 Salvar bairro", type="primary")
            excluir = st.form_submit_button("🗑️ Excluir bairro") if b else False
            if excluir:
                tentar_excluir(regras.excluir_bairro, b["id"], conf, "Bairro excluído.")
            if salvar:
                if not nome.strip():
                    st.error("Informe o nome do bairro.")
                else:
                    try:
                        regras.salvar_bairro(dict(nome=nome.strip(), zona=zona.strip() or "Sem zona", frete=frete,
                                                  ativo=1), b["id"] if b else None)
                        st.session_state.ok = "Bairro salvo."
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Já existe um bairro com esse nome.")
    with aba4:
        acesso.tela_alterar_senha()



# ---------- NAVEGAÇÃO ----------
PAGINAS = {"🏠  Painel": pg_inicio, "🛒  Vendas": pg_vendas, "🚚  Roteiro de entregas": pg_roteiro,
           "👥  Clientes": pg_clientes, "📦  Estoque": pg_estoque, "💰  Fiado": pg_fiado,
           "💹  Financeiro": pg_financeiro, "📊  Relatórios": pg_relatorios, "⚙️  Cadastros": pg_cadastros}


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    if not acesso.exigir_login(GOTA.format(s=64)):
        return
    with st.sidebar:
        st.markdown(f"<div class='marca'>{GOTA.format(s=40)}<div><b>Água Nova</b><br><small>Distribuidora</small></div></div>",
                    unsafe_allow_html=True)
        escolha = st.radio("Menu", list(PAGINAS), label_visibility="collapsed")
        st.caption("Versão 1.0")
        st.caption("Desenvolvido por Brunno Dornelas")
        st.markdown("<hr style='opacity:.25'>", unsafe_allow_html=True)
        acesso.painel_sessao()
    st.markdown(f"<div class='hero'>{GOTA.format(s=54)}<div><h1>Distribuidora Água Nova</h1>"
                f"<p>Estoque, vendas e entregas · {datetime.now():%d/%m/%Y}</p></div></div>", unsafe_allow_html=True)
    ok_msg()
    PAGINAS[escolha]()


main()
