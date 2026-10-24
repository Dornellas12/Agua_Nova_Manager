"""regras.py — regras de negócio: preços, estoque, galões, fiado e roteiro.

Aqui ficam os cálculos. A tela (app.py) só chama estas funções.
"""
from datetime import datetime, date
from urllib.parse import quote
from banco import conectar, consultar, executar

OPERACOES = ["Troca", "Compra de galão novo", "Empréstimo"]
FORMAS = ["Dinheiro", "Pix", "Cartão", "Fiado"]
# Em entregas, "A cobrar" = o entregador recebe na porta; Dinheiro/Pix/Cartão = já foi pago.
FORMAS_ENTREGA = ["A cobrar", "Dinheiro", "Pix", "Cartão", "Fiado"]


# ---------- utilidades ----------
def brl(v):
    return "R$ " + f"{(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def nome_produto(p):
    return " ".join(x for x in (p["nome"], p["marca"], p["tamanho"]) if x)


# ---------- listagens ----------
def listar_bairros(todos=False):
    return consultar("SELECT * FROM bairros" + ("" if todos else " WHERE ativo=1") + " ORDER BY zona, nome")


def listar_produtos(todos=False):
    return consultar("SELECT * FROM produtos" + ("" if todos else " WHERE ativo=1")
                     + " ORDER BY tipo DESC, nome, marca, tamanho")


def listar_clientes(todos=False):
    return consultar("""
        SELECT c.*, b.nome AS bairro, b.zona, b.frete AS frete_bairro,
               COALESCE((SELECT SUM(qtd) FROM emprestimos e WHERE e.cliente_id=c.id),0) AS emprestados
        FROM clientes c LEFT JOIN bairros b ON b.id=c.bairro_id
        """ + ("" if todos else "WHERE c.ativo=1 ") + "ORDER BY c.nome")


def emprestimos_cliente(cid=None):
    return consultar("""
        SELECT e.cliente_id, e.vasilhame_id, e.qtd, c.nome AS cliente, v.nome AS vasilhame
        FROM emprestimos e JOIN clientes c ON c.id=e.cliente_id JOIN vasilhames v ON v.id=e.vasilhame_id
        WHERE e.qtd>0 AND (? IS NULL OR e.cliente_id=?) ORDER BY c.nome""", (cid, cid))


# ---------- preços ----------
def frete_cliente(c):
    """Ordem: frete especial do cliente -> frete do bairro -> zero."""
    if c is None:
        return 0.0
    if c.get("frete_especial") is not None:
        return float(c["frete_especial"])
    return float(c.get("frete_bairro") or 0)


def preco_sugerido(p, modo, operacao, cliente, entrega):
    if p["tipo"] == "Galão":
        base = p["preco_novo"] if operacao == "Compra de galão novo" else p["preco_unit"]
        frete = frete_cliente(cliente) if entrega == "Entrega" else 0
        return base + frete
    return p["preco_fardo"] if modo == "Fardo" else p["preco_unit"]


# ---------- cadastros ----------
def salvar_bairro(d, bid=None):
    if bid:
        executar("UPDATE bairros SET nome=?, zona=?, frete=?, ativo=? WHERE id=?",
                 (d["nome"], d["zona"], d["frete"], d["ativo"], bid))
    else:
        executar("INSERT INTO bairros(nome, zona, frete) VALUES (?,?,?)", (d["nome"], d["zona"], d["frete"]))


def salvar_cliente(d, cid=None):
    v = (d["nome"], d["telefone"], d["endereco"], d["bairro_id"], d["frete_especial"], d["obs"], d["ativo"])
    if cid:
        executar("UPDATE clientes SET nome=?, telefone=?, endereco=?, bairro_id=?, frete_especial=?, obs=?, ativo=? WHERE id=?",
                 v + (cid,))
        return cid
    else:
        return executar("INSERT INTO clientes(nome,telefone,endereco,bairro_id,frete_especial,obs,ativo,criado_em) VALUES (?,?,?,?,?,?,?,?)",
                 v + (agora(),))


def salvar_produto(d, pid=None, ini_cheio=0):
    v = (d["nome"], d["marca"], d["tipo"], d["tamanho"], d["un_fardo"], d["preco_unit"],
         d["preco_fardo"], d["preco_novo"], d["est_min"], d["ativo"], d.get("vasilhame_id"))
    con = conectar()
    try:
        with con:
            if pid:
                con.execute("""UPDATE produtos SET nome=?,marca=?,tipo=?,tamanho=?,un_fardo=?,preco_unit=?,
                               preco_fardo=?,preco_novo=?,est_min=?,ativo=?,vasilhame_id=? WHERE id=?""", v + (pid,))
            else:
                pid = con.execute("""INSERT INTO produtos(nome,marca,tipo,tamanho,un_fardo,preco_unit,
                               preco_fardo,preco_novo,est_min,ativo,vasilhame_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", v).lastrowid
                if ini_cheio:
                    _mover(con, pid, ini_cheio, 0, "Estoque inicial", "")
    finally:
        con.close()
    return pid


# ---------- estoque ----------
def _mover(con, produto_id, cheio, vazio, tipo, ref, vasilhame_id=None):
    """Cheios ficam no produto; vazios ficam no VASILHAME (por tipo/tamanho, não por marca)."""
    if cheio:
        con.execute("UPDATE produtos SET est_cheio=est_cheio+? WHERE id=?", (cheio, produto_id))
    if vazio:
        if vasilhame_id is None:
            linha = con.execute("SELECT vasilhame_id FROM produtos WHERE id=?", (produto_id,)).fetchone()
            vasilhame_id = linha["vasilhame_id"] if linha else None
        if vasilhame_id is None:
            raise ValueError("Este galão ainda não tem vasilhame definido. Escolha em Cadastros > Produtos.")
        vas = con.execute("SELECT nome, est_vazio FROM vasilhames WHERE id=?", (vasilhame_id,)).fetchone()
        if vas["est_vazio"] + vazio < 0:
            raise ValueError(f"Não há vazios suficientes em {vas['nome']}: disponível {vas['est_vazio']}.")
        con.execute("UPDATE vasilhames SET est_vazio=est_vazio+? WHERE id=?", (vazio, vasilhame_id))
    con.execute("INSERT INTO movimentos(data,produto_id,tipo,d_cheio,d_vazio,ref,vasilhame_id) VALUES (?,?,?,?,?,?,?)",
                (agora(), produto_id, tipo, cheio, vazio, str(ref), vasilhame_id))


def _efeito(p, modo, operacao, qtd):
    """O que uma linha de venda faz no estoque e nos galões emprestados."""
    if p["tipo"] == "Galão":
        return dict(cheio=-qtd,
                    vazio=qtd if operacao == "Troca" else 0,          # troca: vazio volta
                    emprestimo=qtd if operacao == "Empréstimo" else 0)  # empréstimo: saldo do cliente sobe
    un = qtd * (p["un_fardo"] if modo == "Fardo" else 1)
    return dict(cheio=-un, vazio=0, emprestimo=0)


def _guardar_compra(con, cid, fornecedor, produto_id, modo, qtd, custo_unit, obs, vazios, vasilhame_id, rotulo):
    """Grava (ou atualiza) a compra e move o estoque. Devolve o id da compra."""
    p = con.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
    un = qtd * (p["un_fardo"] if p["tipo"] == "Descartável" and modo == "Fardo" else 1)
    vid = (vasilhame_id or p["vasilhame_id"]) if vazios > 0 else None
    dados = (fornecedor, produto_id, modo, qtd, custo_unit, qtd * custo_unit, obs, un, max(vazios, 0), vid)
    if cid is None:
        cid = con.execute("""INSERT INTO compras(fornecedor,produto_id,modo,qtd,custo_unit,total,obs,unidades,vazios_enviados,vasilhame_id,data)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?)""", dados + (agora(),)).lastrowid
    else:
        con.execute("""UPDATE compras SET fornecedor=?,produto_id=?,modo=?,qtd=?,custo_unit=?,total=?,obs=?,unidades=?,
                       vazios_enviados=?,vasilhame_id=? WHERE id=?""", dados + (cid,))
    _mover(con, produto_id, un, 0, rotulo, fornecedor)
    if vazios > 0:
        _mover(con, produto_id, 0, -vazios, "Vazios enviados ao fornecedor", fornecedor, vid)
    return cid


def _desfazer_compra(con, c, rotulo):
    """Reverte no estoque o efeito de uma compra (cheios e vazios enviados)."""
    _mover(con, c["produto_id"], -c["unidades"], 0, rotulo, c["fornecedor"])
    if c["vazios_enviados"]:
        p = con.execute("SELECT vasilhame_id FROM produtos WHERE id=?", (c["produto_id"],)).fetchone()
        _mover(con, c["produto_id"], 0, c["vazios_enviados"], rotulo + " (vazios)", c["fornecedor"],
               c["vasilhame_id"] or p["vasilhame_id"])


def _checar_cheio(con, produto_id):
    p = con.execute("SELECT nome, marca, tamanho, est_cheio FROM produtos WHERE id=?", (produto_id,)).fetchone()
    if p["est_cheio"] < 0:
        raise ValueError(f"Não é possível: parte dessa mercadoria ({nome_produto(p)}) já foi vendida e o estoque ficaria "
                         "negativo. Cancele as vendas ou corrija o estoque antes.")


def entrada_mercadoria(fornecedor, produto_id, modo, qtd, custo_unit, obs="", vazios_enviados=0, vasilhame_id=None):
    """Entrada de produtos. Em troca de galões, 'vazios_enviados' saem do estoque do vasilhame."""
    if qtd <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    con = conectar()
    try:
        with con:
            _guardar_compra(con, None, fornecedor, produto_id, modo, qtd, custo_unit, obs, vazios_enviados, vasilhame_id, "Entrada")
    finally:
        con.close()


def ajustar_estoque(produto_id, d_cheio, motivo):
    con = conectar()
    try:
        with con:
            p = con.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
            if p["est_cheio"] + d_cheio < 0:
                raise ValueError("Esse ajuste deixaria o estoque negativo.")
            _mover(con, produto_id, d_cheio, 0, motivo, "")
    finally:
        con.close()


def ajustar_vasilhame(vasilhame_id, delta, motivo):
    """Ajusta o estoque de galões VAZIOS de um vasilhame (estoque inicial, perda, contagem)."""
    con = conectar()
    try:
        with con:
            _mover(con, None, 0, delta, motivo, "", vasilhame_id)
    finally:
        con.close()


# ---------- vendas ----------
def registrar_venda(cliente_id, origem, entrega, pagamento, itens, obs="", data_entrega=None):
    """itens: lista de dicts com produto_id, modo, operacao, qtd, preco."""
    if not itens:
        raise ValueError("Adicione pelo menos um item ao pedido.")
    if cliente_id is None and (entrega == "Entrega" or pagamento == "Fiado"):
        raise ValueError("Cliente avulso não pode ter entrega nem fiado. Escolha um cliente cadastrado.")
    if pagamento == "A cobrar" and entrega != "Entrega":
        raise ValueError("\"A cobrar na entrega\" só vale para pedidos com entrega.")
    total = round(sum(i["qtd"] * i["preco"] for i in itens), 2)
    con = conectar()
    try:
        with con:  # tudo ou nada: se der erro, nada é gravado
            vid = con.execute(
                """INSERT INTO vendas(data,cliente_id,origem,tipo_entrega,pagamento,total,data_entrega,obs)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (agora(), cliente_id, origem, entrega, pagamento, total,
                 data_entrega if entrega == "Entrega" else None, obs)).lastrowid
            for i in itens:
                p = con.execute("SELECT * FROM produtos WHERE id=?", (i["produto_id"],)).fetchone()
                ef = _efeito(p, i["modo"], i["operacao"], i["qtd"])
                if p["tipo"] == "Galão" and p["vasilhame_id"] is None:
                    raise ValueError(f"{nome_produto(p)} não tem vasilhame definido (Cadastros > Produtos).")
                if p["est_cheio"] + ef["cheio"] < 0:
                    raise ValueError(f"Estoque insuficiente de {nome_produto(p)}: "
                                     f"disponível {p['est_cheio']}, pedido {-ef['cheio']}.")
                con.execute("INSERT INTO venda_itens(venda_id,produto_id,modo,operacao,qtd,preco) VALUES (?,?,?,?,?,?)",
                            (vid, p["id"], i["modo"], i["operacao"], i["qtd"], i["preco"]))
                _mover(con, p["id"], ef["cheio"], ef["vazio"], "Venda", f"#{vid}")
                if ef["emprestimo"] and cliente_id:
                    con.execute("""INSERT INTO emprestimos(cliente_id,vasilhame_id,qtd) VALUES (?,?,?)
                                   ON CONFLICT(cliente_id,vasilhame_id) DO UPDATE SET qtd=qtd+excluded.qtd""",
                                (cliente_id, p["vasilhame_id"], ef["emprestimo"]))
        return vid
    finally:
        con.close()


def cancelar_venda(vid):
    """Cancela e desfaz estoque e empréstimos. A venda continua no histórico."""
    con = conectar()
    try:
        with con:
            v = con.execute("SELECT * FROM vendas WHERE id=?", (vid,)).fetchone()
            if v["status"] == "Cancelada":
                raise ValueError("Esta venda já está cancelada.")
            for i in con.execute("SELECT * FROM venda_itens WHERE venda_id=?", (vid,)).fetchall():
                p = con.execute("SELECT * FROM produtos WHERE id=?", (i["produto_id"],)).fetchone()
                ef = _efeito(p, i["modo"], i["operacao"], i["qtd"])
                _mover(con, p["id"], -ef["cheio"], -ef["vazio"], "Cancelamento", f"#{vid}")
                if ef["emprestimo"] and v["cliente_id"]:
                    con.execute("UPDATE emprestimos SET qtd=MAX(qtd-?,0) WHERE cliente_id=? AND vasilhame_id=?",
                                (ef["emprestimo"], v["cliente_id"], p["vasilhame_id"]))
            con.execute("UPDATE vendas SET status='Cancelada' WHERE id=?", (vid,))
    finally:
        con.close()


def itens_da_venda(vid):
    return consultar("""SELECT i.qtd, i.modo, i.operacao, i.preco, p.nome, p.marca, p.tamanho
                        FROM venda_itens i JOIN produtos p ON p.id=i.produto_id WHERE i.venda_id=?""", (vid,))





# ---------- fiado ----------
def situacao_fiado(cid):
    """Saldo devedor. Os pagamentos quitam as vendas mais antigas primeiro."""
    vendas = consultar("SELECT id,data,total FROM vendas WHERE cliente_id=? AND pagamento='Fiado' AND status='Ativa' ORDER BY data", (cid,))
    pago = consultar("SELECT COALESCE(SUM(valor),0) s FROM pagamentos_fiado WHERE cliente_id=?", (cid,))[0]["s"]
    total = sum(v["total"] for v in vendas)
    saldo = round(total - pago, 2)
    restante, antiga = pago, None
    for v in vendas:
        if restante + 0.005 >= v["total"]:
            restante -= v["total"]
        else:
            antiga = v["data"]
            break
    dias = 0
    if antiga and saldo > 0.009:
        dias = (date.today() - datetime.strptime(antiga[:10], "%Y-%m-%d").date()).days
    return dict(total=total, pago=pago, saldo=saldo, dias=dias, vendas=vendas)


def resumo_fiado():
    ids = consultar("""SELECT DISTINCT v.cliente_id id, c.nome, c.telefone FROM vendas v
                       JOIN clientes c ON c.id=v.cliente_id
                       WHERE v.pagamento='Fiado' AND v.status='Ativa'""")
    out = []
    for c in ids:
        s = situacao_fiado(c["id"])
        if s["saldo"] > 0.009:
            out.append({**c, **s})
    return sorted(out, key=lambda x: -x["dias"])


def registrar_pagamento(cid, valor, forma, obs=""):
    if valor > situacao_fiado(cid)["saldo"] + 0.005:
        raise ValueError("O valor é maior que o saldo devedor.")
    executar("INSERT INTO pagamentos_fiado(cliente_id,data,valor,forma,obs) VALUES (?,?,?,?,?)",
             (cid, agora(), valor, forma, obs))


# ---------- roteiro de entregas ----------
def nomes_entregadores():
    r = consultar("SELECT valor FROM config WHERE chave='entregadores'")
    return r[0]["valor"].split("|") if r else ["Entregador 1", "Entregador 2"]


def salvar_nomes(nomes, telefones=None):
    """Salva nome (e WhatsApp) dos entregadores. Se um nome mudar, os pedidos dele acompanham."""
    for antigo, novo in zip(nomes_entregadores(), nomes):
        if antigo != novo:
            executar("UPDATE vendas SET entregador=? WHERE entregador=?", (novo, antigo))
    up = "INSERT INTO config(chave,valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor"
    executar(up, ("entregadores", "|".join(nomes)))
    if telefones is not None:
        executar(up, ("tel_entregadores", "|".join(telefones)))


def telefones_entregadores():
    r = consultar("SELECT valor FROM config WHERE chave='tel_entregadores'")
    return ((r[0]["valor"].split("|") if r else []) + ["", ""])[:2]


def pedidos_entrega(dia):
    """Entregas do dia + pendentes de dias anteriores."""
    return consultar("""
        SELECT v.id, v.total, v.pagamento, v.entregador, v.ordem, v.entregue, v.data_entrega, v.obs,
               c.nome AS cliente, c.telefone, c.endereco,
               COALESCE(b.nome,'—') AS bairro, COALESCE(b.zona,'Sem zona') AS zona
        FROM vendas v JOIN clientes c ON c.id=v.cliente_id LEFT JOIN bairros b ON b.id=c.bairro_id
        WHERE v.status='Ativa' AND v.tipo_entrega='Entrega'
          AND (v.data_entrega=? OR (v.entregue=0 AND v.data_entrega<?))
        ORDER BY v.ordem, v.id""", (dia, dia))


def itens_por_venda(ids):
    if not ids:
        return {}
    rows = consultar(f"""SELECT i.venda_id, i.qtd, i.modo, i.operacao, p.nome, p.marca, p.tamanho
                         FROM venda_itens i JOIN produtos p ON p.id=i.produto_id
                         WHERE i.venda_id IN ({",".join("?" * len(ids))})""", tuple(ids))
    out = {}
    for r in rows:
        extra = f" [{r['operacao']}]" if r["operacao"] else (" (fardo)" if r["modo"] == "Fardo" else "")
        out.setdefault(r["venda_id"], []).append(f"{r['qtd']}× {nome_produto(r)}{extra}")
    return {k: ", ".join(v) for k, v in out.items()}


def sugerir_divisao(pedidos, nomes):
    """Ordena por zona/bairro e divide em blocos de tamanho parecido, cortando
    de preferência na troca de zona. Devolve {id_venda: (entregador, ordem)}."""
    ordenados = sorted(pedidos, key=lambda p: (p["zona"], p["bairro"], p["cliente"]))
    n, k = len(ordenados), len(nomes)
    if n == 0:
        return {}
    limites = [j for j in range(1, n) if ordenados[j]["zona"] != ordenados[j - 1]["zona"]]
    cortes = []
    for i in range(1, k):
        alvo = round(n * i / k)
        melhor = min(limites, key=lambda j: abs(j - alvo), default=alvo)
        cortes.append(melhor if abs(melhor - alvo) <= n / 4 else alvo)
    res = {}
    for idx, p in enumerate(ordenados):
        e = sum(1 for c in cortes if idx >= c)
        inicio = cortes[e - 1] if e > 0 else 0
        res[p["id"]] = (nomes[e], idx - inicio + 1)
    return res


def aplicar_divisao(res):
    for vid, (nome, ordem) in res.items():
        executar("UPDATE vendas SET entregador=?, ordem=? WHERE id=?", (nome, ordem, vid))


def salvar_roteiro(vid, entregador, ordem, entregue, pagamento=None):
    if pagamento is not None and pagamento not in FORMAS_ENTREGA:
        raise ValueError("Forma de pagamento inválida.")
    executar("UPDATE vendas SET entregador=?, ordem=?, entregue=?, pagamento=COALESCE(?, pagamento) WHERE id=?",
             (entregador, ordem, 1 if entregue else 0, pagamento, vid))


# ---------- dados de exemplo (para testar) ----------



# ======================= V2 =======================
# ---------- exclusão definitiva (só de cadastros sem movimento ativo) ----------
def _excluir(apagar, bloqueios, msg):
    for sql, params in bloqueios:
        if consultar(sql, params):
            raise ValueError(msg)
    con = conectar()
    try:
        with con:
            for sql, params in apagar:
                con.execute(sql, params)
    finally:
        con.close()


def excluir_cliente(cid):
    _excluir([("DELETE FROM venda_itens WHERE venda_id IN (SELECT id FROM vendas WHERE cliente_id=?)", (cid,)),
              ("DELETE FROM vendas WHERE cliente_id=?", (cid,)),
              ("DELETE FROM emprestimos WHERE cliente_id=?", (cid,)),
              ("DELETE FROM clientes WHERE id=?", (cid,))],
             [("SELECT 1 FROM vendas WHERE cliente_id=? AND status='Ativa' LIMIT 1", (cid,)),
              ("SELECT 1 FROM pagamentos_fiado WHERE cliente_id=? LIMIT 1", (cid,))],
             "Este cliente tem vendas ativas ou pagamentos de fiado. Cancele as vendas (Vendas > Histórico) "
             "antes de excluir, ou apenas corrija o cadastro.")


def excluir_produto(pid):
    _excluir([("DELETE FROM venda_itens WHERE produto_id=?", (pid,)),
              ("DELETE FROM movimentos WHERE produto_id=?", (pid,)),
              ("DELETE FROM produtos WHERE id=?", (pid,))],
             [("SELECT 1 FROM venda_itens i JOIN vendas v ON v.id=i.venda_id WHERE i.produto_id=? AND v.status='Ativa' LIMIT 1", (pid,)),
              ("SELECT 1 FROM compras WHERE produto_id=? LIMIT 1", (pid,))],
             "Este produto já foi vendido ou tem entradas de mercadoria. Cancele as vendas antes de excluir, "
             "ou apenas corrija o cadastro.")


def excluir_bairro(bid):
    _excluir([("DELETE FROM bairros WHERE id=?", (bid,))],
             [("SELECT 1 FROM clientes WHERE bairro_id=? LIMIT 1", (bid,))],
             "Há clientes cadastrados neste bairro. Mude o bairro deles antes de excluir.")





# ---------- despesas ----------
CATEGORIAS = ["Combustível", "Salários", "Aluguel", "Manutenção de veículos", "Energia / água / internet",
              "Impostos e taxas", "Marketing", "Outros"]


def salvar_despesa(data, categoria, descricao, valor):
    executar("INSERT INTO despesas(data,categoria,descricao,valor) VALUES (?,?,?,?)", (data, categoria, descricao, valor))


def listar_despesas(ini, fim):
    return consultar("SELECT * FROM despesas WHERE date(data) BETWEEN ? AND ? ORDER BY data DESC, id DESC", (ini, fim))


def excluir_despesa(did):
    executar("DELETE FROM despesas WHERE id=?", (did,))


# ---------- financeiro e relatórios ----------
_UN = "CASE WHEN i.modo='Fardo' THEN p.un_fardo ELSE 1 END"


def por_produto(ini, fim):
    rows = consultar(f"""SELECT p.nome, p.marca, p.tamanho, SUM(i.qtd*{_UN}) AS un, SUM(i.qtd*i.preco) AS fat
            FROM venda_itens i JOIN vendas v ON v.id=i.venda_id JOIN produtos p ON p.id=i.produto_id
            WHERE v.status='Ativa' AND date(v.data) BETWEEN ? AND ? GROUP BY p.id ORDER BY fat DESC""", (ini, fim))
    for r in rows:
        r["produto"] = nome_produto(r)
    return rows


def resumo_financeiro(ini, fim):
    """Faturamento bruto x despesas brutas (despesas lançadas + compras de mercadoria)."""
    p = (ini, fim)
    v = consultar("SELECT COALESCE(SUM(total),0) t, COUNT(*) n FROM vendas WHERE status='Ativa' AND date(data) BETWEEN ? AND ?", p)[0]
    fiado = consultar("SELECT COALESCE(SUM(total),0) t FROM vendas WHERE status='Ativa' AND pagamento='Fiado' AND date(data) BETWEEN ? AND ?", p)[0]["t"]
    receb = consultar("SELECT COALESCE(SUM(valor),0) t FROM pagamentos_fiado WHERE date(data) BETWEEN ? AND ?", p)[0]["t"]
    desp = consultar("SELECT COALESCE(SUM(valor),0) t FROM despesas WHERE date(data) BETWEEN ? AND ?", p)[0]["t"]
    compras = consultar("SELECT COALESCE(SUM(total),0) t FROM compras WHERE date(data) BETWEEN ? AND ?", p)[0]["t"]
    return dict(faturamento=v["t"], pedidos=v["n"], ticket=(v["t"] / v["n"] if v["n"] else 0), fiado=fiado,
                entrou=v["t"] - fiado + receb, despesas=desp, compras=compras,
                total_desp=desp + compras, lucro=v["t"] - desp - compras)


def top_clientes(ini, fim):
    return consultar("""SELECT COALESCE(c.nome,'Cliente avulso') cliente, COUNT(*) pedidos, SUM(v.total) fat
                        FROM vendas v LEFT JOIN clientes c ON c.id=v.cliente_id
                        WHERE v.status='Ativa' AND date(v.data) BETWEEN ? AND ?
                        GROUP BY v.cliente_id ORDER BY fat DESC LIMIT 15""", (ini, fim))


def por_bairro(ini, fim):
    return consultar("""SELECT COALESCE(b.nome,'Sem bairro / balcão') bairro, COUNT(*) pedidos, SUM(v.total) fat
                        FROM vendas v LEFT JOIN clientes c ON c.id=v.cliente_id LEFT JOIN bairros b ON b.id=c.bairro_id
                        WHERE v.status='Ativa' AND date(v.data) BETWEEN ? AND ?
                        GROUP BY b.id ORDER BY fat DESC""", (ini, fim))


def por_canal(ini, fim):
    return consultar("""SELECT origem, COUNT(*) pedidos, SUM(total) fat FROM vendas
                        WHERE status='Ativa' AND date(data) BETWEEN ? AND ? GROUP BY origem ORDER BY fat DESC""", (ini, fim))


def fora_do_padrao():
    return [c for c in listar_clientes() if c["frete_especial"] is not None]


def definir_emprestimo(cid, vid, qtd, devolvidos_ao_estoque=False):
    """Define o saldo de vasilhames emprestados (editar cliente). Se o saldo diminuiu e
    devolvidos_ao_estoque=True, os galões voltam como VAZIOS ao estoque (fica no histórico)."""
    qtd = max(int(qtd), 0)
    con = conectar()
    try:
        with con:
            linha = con.execute("SELECT qtd FROM emprestimos WHERE cliente_id=? AND vasilhame_id=?", (cid, vid)).fetchone()
            antes = linha["qtd"] if linha else 0
            if qtd == antes:
                return
            con.execute("""INSERT INTO emprestimos(cliente_id,vasilhame_id,qtd) VALUES (?,?,?)
                           ON CONFLICT(cliente_id,vasilhame_id) DO UPDATE SET qtd=excluded.qtd""", (cid, vid, qtd))
            if devolvidos_ao_estoque and qtd < antes:
                _mover(con, None, 0, antes - qtd, "Devolução de galão (cadastro)", f"cliente {cid}", vid)
    finally:
        con.close()


# ---------- vasilhames (galão vazio, por tipo/tamanho) ----------
def listar_vasilhames():
    return consultar("""SELECT v.*, COALESCE((SELECT SUM(qtd) FROM emprestimos e WHERE e.vasilhame_id=v.id),0) AS emprestados
                        FROM vasilhames v ORDER BY v.nome""")


def salvar_vasilhame(nome, vid=None):
    if vid:
        executar("UPDATE vasilhames SET nome=? WHERE id=?", (nome, vid))
    else:
        executar("INSERT INTO vasilhames(nome) VALUES (?)", (nome,))


def excluir_vasilhame(vid):
    _excluir([("DELETE FROM vasilhames WHERE id=?", (vid,))],
             [("SELECT 1 FROM produtos WHERE vasilhame_id=? LIMIT 1", (vid,)),
              ("SELECT 1 FROM vasilhames WHERE id=? AND est_vazio<>0", (vid,)),
              ("SELECT 1 FROM emprestimos WHERE vasilhame_id=? AND qtd>0 LIMIT 1", (vid,))],
             "Este vasilhame está em uso (produtos, vazios em estoque ou galões emprestados). Mude ou zere antes de excluir.")



# ---------- corrigir / excluir lançamentos de entrada ----------
def listar_compras(limite=60):
    rows = consultar("""SELECT c.id, c.data, c.fornecedor, c.produto_id, c.modo, c.qtd, c.custo_unit, c.total,
                               COALESCE(c.vazios_enviados,0) AS vazios_enviados, c.vasilhame_id,
                               p.nome, p.marca, p.tamanho
                        FROM compras c JOIN produtos p ON p.id=c.produto_id ORDER BY c.id DESC LIMIT ?""", (limite,))
    for x in rows:
        x["prod"] = nome_produto(x)
    return rows


def editar_compra(cid, fornecedor, produto_id, modo, qtd, custo_unit, vazios_enviados=0, vasilhame_id=None):
    """Corrige um lançamento: estorna o efeito antigo e aplica o novo, tudo ou nada."""
    if qtd <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    con = conectar()
    try:
        with con:
            c = con.execute("SELECT * FROM compras WHERE id=?", (cid,)).fetchone()
            if not c:
                raise ValueError("Lançamento não encontrado.")
            _desfazer_compra(con, c, "Estorno (entrada corrigida)")
            _guardar_compra(con, cid, fornecedor, produto_id, modo, qtd, custo_unit, c["obs"], vazios_enviados,
                            vasilhame_id, "Entrada (corrigida)")
            for pid in {c["produto_id"], produto_id}:
                _checar_cheio(con, pid)
    finally:
        con.close()


def excluir_compra(cid):
    """Exclui o lançamento: o estoque volta ao que era e a despesa deixa de contar."""
    con = conectar()
    try:
        with con:
            c = con.execute("SELECT * FROM compras WHERE id=?", (cid,)).fetchone()
            if not c:
                raise ValueError("Lançamento não encontrado.")
            _desfazer_compra(con, c, "Estorno (entrada excluída)")
            con.execute("DELETE FROM compras WHERE id=?", (cid,))
            _checar_cheio(con, c["produto_id"])
    finally:
        con.close()



# ---------- mensagem de WhatsApp e cobrança ----------
def texto_cobranca(p, emoji=True):
    v = brl(p["total"])
    pg = p["pagamento"]
    if pg == "Fiado":
        e, t = "📒", f"FIADO (não cobrar) – {v}"
    elif pg == "A cobrar":
        e, t = "💵", f"COBRAR {v}"
    else:
        e, t = "✅", f"JÁ PAGO ({pg}) – {v} (não cobrar)"
    return f"{e} {t}" if emoji else t


def mensagem_whatsapp(dia, nome, pedidos):
    """Texto pronto para colar no WhatsApp (*negrito* é a formatação do próprio WhatsApp)."""
    lista = sorted(pedidos, key=lambda p: (p["ordem"] or 999, p["id"]))
    n = len(lista)
    linhas = [f"*ROTEIRO DE ENTREGAS – {dia:%d/%m/%Y}*", f"*Entregador: {nome}* ({n} {'entrega' if n == 1 else 'entregas'})", ""]
    for i, p in enumerate(lista, 1):
        tel = f" – {p['telefone']}" if p["telefone"] else ""
        linhas += [f"*{i}) {p['cliente']}*{tel}", f"📍 {p['endereco'] or 'sem endereço'} – {p['bairro']}", f"📦 {p.get('itens', '')}"]
        if p.get("obs"):
            linhas.append(f"📝 {p['obs']}")
        linhas += [texto_cobranca(p), ""]
    total = sum(p["total"] for p in lista if p["pagamento"] == "A cobrar")
    linhas.append(f"💰 *Total a cobrar: {brl(total)}*")
    return "\n".join(linhas)


def link_whatsapp(telefone, texto):
    """Abre o WhatsApp com a mensagem pronta (direto no entregador, se o telefone estiver salvo)."""
    d = "".join(ch for ch in (telefone or "") if ch.isdigit())
    if d and not d.startswith("55") and len(d) in (10, 11):
        d = "55" + d
    return f"https://wa.me/{d}?text={quote(texto)}"
