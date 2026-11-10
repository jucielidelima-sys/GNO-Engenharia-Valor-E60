# GNO — Engenharia de Valor E60

Versão com visual branco/laranja GNO e salvamento persistente no Supabase.

## 1. Criar tabela no Supabase

Abra o **SQL Editor** do projeto `engenharia-valor-e60`, cole `supabase_setup.sql` e clique **Run**. A tabela `e60_snapshots` armazena versões completas das simulações. As quatro tabelas anteriores permanecem inalteradas.

## 2. Publicar no GitHub

Crie um repositório **privado** e envie `app.py`, `requirements.txt`, `assets/logo_gno.png`, `supabase_setup.sql` e `.gitignore`. **Não envie** `secrets.toml`, banco SQLite, senhas ou chaves.

## 3. Publicar no Streamlit Community Cloud

Crie o app a partir do repositório, arquivo principal `app.py`. Em **Advanced settings / Secrets**, cole as três variáveis do exemplo `.streamlit/secrets.toml.example` com seus valores reais. Use a chave secreta do Supabase **somente no servidor**, nunca no front-end. Defina uma senha forte `APP_PASSWORD` e restrinja o acesso ao app.

## 4. Testar

Entre com a senha, registre uma simulação e confira o horário de salvamento em **Salvamento e cópias de segurança**. Feche o navegador, abra novamente e verifique a simulação. No Supabase, confira as linhas em `e60_snapshots`.

## Avisos

- A aplicação usa um **estado compartilhado**; não foi projetada para edição simultânea. Dois usuários podem gerar versões concorrentes. Para colaboração multiusuário, é necessário controle de versão/conflitos e autenticação individual.
- O histórico append-only facilita recuperação, mas **não substitui backups externos**. Exporte JSON periodicamente e guarde fora do Supabase.
- Sem credenciais Supabase, o app usa SQLite **somente para testes locais**. SQLite não é persistente no Streamlit Community Cloud.
- O login por senha única é uma barreira inicial, não identifica individualmente os autores das alterações. Para equipes, implementar login individual e autorização.
- Não publicar com segredos ausentes: configure os Secrets antes de liberar acesso ao link do app.
