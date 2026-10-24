# Sistema Distribuidora Água Nova — Versão 1

## Rodar no MacBook (primeira vez)
1. Instale o Python 3.12 em python.org/downloads
2. Abra o Terminal e entre na pasta:  cd caminho/para/agua_nova
3. python3 -m venv .venv
4. source .venv/bin/activate
5. pip install -r requirements.txt
6. streamlit run app.py   (abre em http://localhost:8501)

Nas próximas vezes: dois cliques em iniciar.command
(se o Mac bloquear: botão direito > Abrir; ou no Terminal: chmod +x iniciar.command)

## Rodar no Windows
1. Instale o Python 3.12 marcando "Add Python to PATH"
2. Abra o Prompt de Comando na pasta e rode: pip install -r requirements.txt
3. Dois cliques em iniciar.bat

## Importante
- Copie para o Windows só os arquivos de código. NÃO copie a pasta "dados" (banco de testes) nem ".venv".
- Backup: copie o arquivo dados/agua_nova.db.
