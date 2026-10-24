"""banco.py — conexão com o banco de dados SQLite e criação das tabelas.

O banco é um único arquivo (dados/agua_nova.db). Para fazer backup, basta copiá-lo.
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

DB = Path(__file__).parent / "dados" / "agua_nova.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT);

CREATE TABLE IF NOT EXISTS bairros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    zona TEXT NOT NULL DEFAULT 'Sem zona',
    frete REAL NOT NULL DEFAULT 0,          -- frete embutido por galão
    ativo INTEGER NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL, marca TEXT DEFAULT '', tamanho TEXT DEFAULT '',
    tipo TEXT NOT NULL,                      -- 'Galão' ou 'Descartável'
    un_fardo INTEGER DEFAULT 1,              -- unidades por fardo
    preco_unit REAL DEFAULT 0,               -- galão: preço da troca
    preco_fardo REAL DEFAULT 0,
    preco_novo REAL DEFAULT 0,               -- galão: preço do galão novo
    custo REAL DEFAULT 0,                    -- (não usado)
    vasilhame_id INTEGER,                    -- galão: qual vasilhame (galão vazio) ele usa
    est_min INTEGER DEFAULT 0,
    est_cheio INTEGER DEFAULT 0,             -- galão cheio / unidades descartáveis
    est_vazio INTEGER DEFAULT 0,             -- galões vazios no depósito
    ativo INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL, telefone TEXT DEFAULT '', endereco TEXT DEFAULT '',
    bairro_id INTEGER REFERENCES bairros(id),
    frete_especial REAL,                     -- NULL = usa o frete do bairro
    obs TEXT DEFAULT '', ativo INTEGER DEFAULT 1, criado_em TEXT);

CREATE TABLE IF NOT EXISTS vasilhames (      -- galão vazio: separado por tipo/tamanho, não por marca
    id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, est_vazio INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS emprestimos (     -- vasilhames emprestados a clientes
    cliente_id INTEGER, vasilhame_id INTEGER, qtd INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cliente_id, vasilhame_id));

CREATE TABLE IF NOT EXISTS vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL, cliente_id INTEGER,  -- NULL = cliente avulso
    origem TEXT, tipo_entrega TEXT, pagamento TEXT, total REAL,
    status TEXT DEFAULT 'Ativa', data_entrega TEXT,
    entregador TEXT DEFAULT '', ordem INTEGER DEFAULT 0, entregue INTEGER DEFAULT 0,
    obs TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS venda_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT, venda_id INTEGER, produto_id INTEGER,
    modo TEXT, operacao TEXT DEFAULT '', qtd INTEGER, preco REAL);

CREATE TABLE IF NOT EXISTS pagamentos_fiado (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, data TEXT,
    valor REAL, forma TEXT, obs TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, fornecedor TEXT,
    produto_id INTEGER, modo TEXT, qtd INTEGER, custo_unit REAL, total REAL, obs TEXT DEFAULT '',
    unidades INTEGER, vazios_enviados INTEGER DEFAULT 0, vasilhame_id INTEGER);

CREATE TABLE IF NOT EXISTS movimentos (      -- histórico de todo movimento de estoque
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, produto_id INTEGER,
    tipo TEXT, d_cheio INTEGER, d_vazio INTEGER, ref TEXT, vasilhame_id INTEGER);

CREATE TABLE IF NOT EXISTS despesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, categoria TEXT, descricao TEXT DEFAULT '', valor REAL);
"""


def conectar():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _colunas(con, tabela):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({tabela})")]


def _nome_vasilhame(nome):
    """Sugere o vasilhame a partir do nome do galão: Crystal e Ibirá têm o seu; o resto é 'Comum'."""
    n = unicodedata.normalize("NFD", nome.lower())
    n = "".join(ch for ch in n if unicodedata.category(ch) != "Mn")
    m = re.search(r"\b(\d+)\s*l\b", n)
    tam = f" {m.group(1)}L" if m else ""
    if "crystal" in n:
        return f"Galão Crystal{tam}"
    if "ibira" in n:
        return f"Galão Ibirá{tam}"
    return f"Galão Comum{tam}"


def _migrar(con):
    """Atualiza bancos de versões anteriores. Roda sozinho e não perde dados."""
    if "custo" not in _colunas(con, "produtos"):
        con.execute("ALTER TABLE produtos ADD COLUMN custo REAL DEFAULT 0")
    if "vasilhame_id" not in _colunas(con, "produtos"):
        con.execute("ALTER TABLE produtos ADD COLUMN vasilhame_id INTEGER")
    if "vasilhame_id" not in _colunas(con, "movimentos"):
        con.execute("ALTER TABLE movimentos ADD COLUMN vasilhame_id INTEGER")
    antigos = []
    if "produto_id" in _colunas(con, "emprestimos"):      # saldo por produto -> saldo por vasilhame
        antigos = con.execute("SELECT cliente_id, produto_id, qtd FROM emprestimos").fetchall()
        con.execute("DROP TABLE emprestimos")
        con.execute("""CREATE TABLE emprestimos (cliente_id INTEGER, vasilhame_id INTEGER,
                       qtd INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (cliente_id, vasilhame_id))""")
    for p in con.execute("SELECT id, nome, est_vazio FROM produtos WHERE tipo='Galão' AND vasilhame_id IS NULL").fetchall():
        nome = _nome_vasilhame(p["nome"])
        con.execute("INSERT OR IGNORE INTO vasilhames(nome) VALUES (?)", (nome,))
        vid = con.execute("SELECT id FROM vasilhames WHERE nome=?", (nome,)).fetchone()["id"]
        con.execute("UPDATE produtos SET vasilhame_id=?, est_vazio=0 WHERE id=?", (vid, p["id"]))
        if p["est_vazio"]:
            con.execute("UPDATE vasilhames SET est_vazio=est_vazio+? WHERE id=?", (p["est_vazio"], vid))
    for a in antigos:
        r = con.execute("SELECT vasilhame_id FROM produtos WHERE id=?", (a["produto_id"],)).fetchone()
        if r and r["vasilhame_id"] and a["qtd"] > 0:
            con.execute("""INSERT INTO emprestimos(cliente_id,vasilhame_id,qtd) VALUES (?,?,?)
                           ON CONFLICT(cliente_id,vasilhame_id) DO UPDATE SET qtd=qtd+excluded.qtd""",
                        (a["cliente_id"], r["vasilhame_id"], a["qtd"]))


def _migrar_compras(con):
    """Guarda em cada compra as unidades e os vazios enviados (necessário para corrigir/excluir)."""
    if "unidades" in _colunas(con, "compras"):
        return
    for col in ("unidades INTEGER", "vazios_enviados INTEGER DEFAULT 0", "vasilhame_id INTEGER"):
        con.execute(f"ALTER TABLE compras ADD COLUMN {col}")
    con.execute("""UPDATE compras SET unidades = qtd * CASE WHEN modo='Fardo' AND
                   (SELECT tipo FROM produtos p WHERE p.id=compras.produto_id)='Descartável'
                   THEN (SELECT un_fardo FROM produtos p WHERE p.id=compras.produto_id) ELSE 1 END""")
    # recupera os vazios enviados a partir do histórico de movimentações
    cond = """m.tipo='Vazios enviados ao fornecedor' AND m.produto_id=compras.produto_id
              AND m.data=compras.data AND m.ref=compras.fornecedor"""
    con.execute(f"""UPDATE compras SET
        vazios_enviados = COALESCE((SELECT -SUM(m.d_vazio) FROM movimentos m WHERE {cond}), 0),
        vasilhame_id = (SELECT m.vasilhame_id FROM movimentos m WHERE {cond} LIMIT 1)
        WHERE (SELECT COUNT(*) FROM compras c2 WHERE c2.produto_id=compras.produto_id
               AND c2.data=compras.data AND c2.fornecedor=compras.fornecedor) = 1""")


def iniciar():
    con = conectar()
    try:
        with con:
            con.executescript(SCHEMA)
            _migrar(con)
            _migrar_compras(con)
    finally:
        con.close()


def consultar(sql, params=()):
    """Executa um SELECT e devolve uma lista de dicionários."""
    con = conectar()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def executar(sql, params=()):
    """Executa INSERT/UPDATE/DELETE e devolve o id criado."""
    con = conectar()
    try:
        with con:
            return con.execute(sql, params).lastrowid
    finally:
        con.close()
