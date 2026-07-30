# Checklist de deploy 24/7 grátis (Turso + Render free + Vercel + GitHub Actions)

Passo a passo literal — segue na ordem, marca e vai. Detalhes/explicação de
cada item estão em `README.md` → "Deploy 24/7 (grátis)". Custo total: **US$0**.

As chaves VAPID de produção são as mesmas já usadas nos testes locais, ou
gere um par novo com `backend/scripts/generate_vapid_keys.py` — nunca
commitar as reais.

## 0. Pré-checagem (já feita, não repetir)

- [x] `npm run build` e `tsc -b` passam limpos no frontend.
- [x] `sqlalchemy-libsql` adicionado ao `requirements.txt`, `config.py` e
      `database.py` já sabem falar com Turso quando as env vars certas
      estão setadas (local dev sem elas continua caindo no SQLite de
      arquivo de sempre, sem depender de rede).
- [x] Banco local limpo — só a conta `ricardo.fipe@gmail.com` e o trade
      real (USDBRL) restaram; o resto eram contas de teste.

## 1. Migração de dados (o trade real que já existe)

- [ ] Depois de criar o banco no Turso (passo 2) e subir o backend contra
      ele pelo menos uma vez (pra `Base.metadata.create_all` criar as
      tabelas vazias lá), extrair só os dados do SQLite local:
      ```bash
      cd trading-diary/backend
      sqlite3 data/trading_diary.db ".dump users" ".dump trades" \
        ".dump risk_settings" ".dump conviction_tiers" ".dump stop_layers" \
        ".dump drawdown_phases" ".dump seasonal_postures" \
        | grep '^INSERT' > /tmp/trading_diary_inserts.sql
      ```
- [ ] Importar no Turso: `turso db shell trading-diary < /tmp/trading_diary_inserts.sql`
- [ ] Conferir: `turso db shell trading-diary "select email from users"`
      deve mostrar `ricardo.fipe@gmail.com`.

## 2. Banco no Turso

- [ ] `curl -sSfL https://get.tur.so/install.sh | bash`
- [ ] `turso auth signup` (não pede cartão).
- [ ] `turso db create trading-diary`
- [ ] `turso db show trading-diary --url` → anotar a URL, **sem** o
      prefixo `libsql://`: `_______________________.turso.io`
- [ ] `turso db tokens create trading-diary` → anotar o token:
      `_______________________________________`

## 3. Backend no Render

- [ ] Criar conta / logar em [render.com](https://render.com) (sem cartão
      pro plano free).
- [ ] **New** → **Web Service** → conectar repo `rromano33/coding-`.
- [ ] Root Directory: `trading-diary/backend`.
- [ ] Runtime: **Docker** (Dockerfile Path: `Dockerfile`).
- [ ] Plan: **Free**.
- [ ] Aba **Environment**, adicionar:
  - [ ] `SECRET_KEY` = string aleatória longa (ou deixar o Render gerar).
  - [ ] `VAPID_PUBLIC_KEY` = ______________________________
  - [ ] `VAPID_PRIVATE_KEY` = ______________________________ (**nunca commitar**)
  - [ ] `VAPID_CLAIM_EMAIL` = `ricardo.fipe@gmail.com`
  - [ ] `TURSO_DATABASE_URL` = a URL do passo 2 (sem `libsql://`)
  - [ ] `TURSO_AUTH_TOKEN` = o token do passo 2
  - [ ] `CRON_SECRET` = string aleatória longa: `_______________________`
        (vai reusar essa mesma string no passo 5)
  - [ ] `ENABLE_INTERNAL_SCHEDULER` = `false`
  - [ ] `CORS_ORIGINS` = `["*"]` por enquanto (ajustar no passo 4)
- [ ] Health Check Path: `/health`.
- [ ] Deploy → anotar a URL: `https://____________________.onrender.com`

## 4. Frontend na Vercel

- [ ] Criar conta / logar em [vercel.com](https://vercel.com).
- [ ] **New Project** → importar o mesmo repo `rromano33/coding-`.
- [ ] Root Directory: `trading-diary/frontend`.
- [ ] Environment Variables → `VITE_API_URL` = URL do Render (passo 3).
- [ ] Deploy → anotar a URL: `https://____________________.vercel.app`
- [ ] Voltar no Render → Environment → `CORS_ORIGINS` =
      `["https://____________________.vercel.app"]` (a URL real acima).
- [ ] Redeploy do backend.

## 5. Push diário via GitHub Actions

- [ ] GitHub → repo `rromano33/coding-` → **Settings** → **Secrets and
      variables** → **Actions**:
  - [ ] `CRON_SECRET` = **o mesmo valor** do passo 3.
  - [ ] `BACKEND_URL` = a URL do Render (passo 3), sem barra no final.
- [ ] **Confirmar o branch default do repo** (Settings → Branches). O
      workflow (`.github/workflows/trading-diary-daily-reminder.yml`, na
      raiz) só dispara sozinho se estiver no branch default — hoje é
      `claude/session-0asigz`. Mergear `trading-diary-app-azsjok` nele, ou
      trocar o default, antes de considerar esse passo concluído.
- [ ] Testar sem esperar 17:30: aba **Actions** → "Trading Diary —
      lembrete diário" → **Run workflow**. Deve voltar sucesso (sem
      notificação chegando ainda, porque a subscription de push é por
      dispositivo — só depois do passo 6).

## 6. Backup local no Mac (opcional, recomendado)

- [ ] `mkdir -p ~/trading-diary-backups`
- [ ] Editar `trading-diary/backend/scripts/com.ricardoromano.trading-diary-backup.plist`,
      trocar `SEU_BANCO_TURSO` por `trading-diary`.
- [ ] `cp trading-diary/backend/scripts/com.ricardoromano.trading-diary-backup.plist ~/Library/LaunchAgents/`
- [ ] `launchctl load ~/Library/LaunchAgents/com.ricardoromano.trading-diary-backup.plist`
- [ ] Testar uma vez sem esperar: `launchctl start com.ricardoromano.trading-diary-backup`
      → conferir se apareceu um `.sql` em `~/trading-diary-backups/`.

## 7. Testar no celular

- [ ] Abrir a URL da Vercel no Safari do iPhone.
- [ ] Login com `ricardo.fipe@gmail.com` (dados migrados no passo 1) — ou
      criar conta nova se preferiu não migrar.
- [ ] "Adicionar à Tela de Início".
- [ ] Abrir pelo ícone instalado (não pela aba do navegador) → Risco → ⚙
      Opções → "Ativar notificações" → aceitar permissão → "Enviar
      notificação de teste".
- [ ] Rodar de novo o `workflow_dispatch` do passo 5 → confirmar que a
      notificação chega dessa vez (agora que tem subscription cadastrada).
