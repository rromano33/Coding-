# Checklist de deploy 24/7 grátis (Turso + Render free + Vercel + GitHub Actions)

**✅ Concluído em 2026-08-01 — isto está em produção, não é mais um plano.**
Ver `CLAUDE.md` → "Estado atual" pra URLs reais e pendências não-bloqueantes.
Este arquivo fica como registro do que foi feito (e serve de referência se
precisar recriar do zero um dia — banco novo, conta nova, etc.).

Custo total: **US$0**.

## 0. Pré-checagem

- [x] `npm run build` e `tsc -b` passam limpos no frontend.
- [x] `sqlalchemy-libsql` no `requirements.txt`, `config.py`/`database.py`
      falam com Turso via `connect_args={"auth_token": ...}` (não via URL —
      bug real da lib, ver `CLAUDE.md`).
- [x] Banco local limpo — só a conta `ricardo.fipe@gmail.com` e o trade
      real (USDBRL) restaram antes de migrar.

## 1. Migração de dados

- [x] `INSERT`s extraídos do SQLite local (`users`, `trades`,
      `risk_settings`, `conviction_tiers`, `stop_layers`, `drawdown_phases`,
      `seasonal_postures`) e importados no Turso via `turso db shell
      trading-diary < inserts.sql`.
- [x] Confirmado: `ricardo.fipe@gmail.com` presente no Turso, 17 linhas no
      total (1 user + 1 trade + resto do framework de risco).

## 2. Banco no Turso

- [x] Turso CLI instalado (`~/.turso/turso`, adicionado ao PATH via
      `.bash_profile`).
- [x] Conta criada (`turso auth signup`, usuário `ricardoromano33`).
- [x] Banco criado: `trading-diary`.
- [x] URL: `trading-diary-ricardoromano33.aws-us-east-1.turso.io`.
- [x] Token gerado (`turso db tokens create trading-diary`) e configurado
      no Render (não fica salvo em nenhum arquivo do repo).

## 3. Backend no Render

- [x] Serviço criado: `Coding-` (Render detectou Python nativo, não
      Docker — funciona igual, `Build Command: pip install -r
      requirements.txt`, `Start Command: uvicorn app.main:app --host
      0.0.0.0 --port $PORT`).
- [x] Root Directory: `trading-diary/backend`.
- [x] Plan: **Free**.
- [x] Branch: `claude/trading-diary-app-azsjok` (correção necessária — o
      Render conectou por padrão no branch errado, `claude/session-0asigz`,
      que não tem a pasta `trading-diary`).
- [x] `PYTHON_VERSION=3.11.9` (Render caiu em Python 3.14 por padrão, sem
      wheel pronta pra `pydantic-core` — precisou fixar a versão).
- [x] Env vars: `SECRET_KEY`, `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/
      `VAPID_CLAIM_EMAIL`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`,
      `CRON_SECRET`, `ENABLE_INTERNAL_SCHEDULER=false`, `CORS_ORIGINS`
      (ajustado no passo 4).
- [x] Health Check Path: `/health`.
- [x] URL: **https://coding-5ahe.onrender.com**

## 4. Frontend na Vercel

- [x] Projeto criado: `coding-mbay`.
- [x] Root Directory: `trading-diary/frontend`.
- [x] Branch: `claude/trading-diary-app-azsjok` (mesmo problema do Render
      — a tela inicial de import não deixa trocar branch facilmente;
      corrigido depois via Project Settings, ou direto pela API com o
      token do Vercel CLI já cacheado em
      `~/Library/Application Support/com.vercel.cli/auth.json`).
- [x] Framework preset corrigido pra **Vite** (Vercel detectou "Python"
      por causa do outro projeto que existe na raiz do monorepo).
- [x] `VITE_API_URL=https://coding-5ahe.onrender.com`.
- [x] URL: **https://coding-mbay.vercel.app**
- [x] `CORS_ORIGINS` no Render atualizado pra
      `["https://coding-mbay.vercel.app"]` e confirmado via curl (origem
      não autorizada não recebe mais o header `Access-Control-Allow-Origin`).

## 5. Push diário via GitHub Actions

- [x] Secrets criados no repo: `CRON_SECRET` (mesmo valor do Render),
      `BACKEND_URL=https://coding-5ahe.onrender.com`.
- [x] **Branch default do repositório trocado** de `claude/session-0asigz`
      pra `claude/trading-diary-app-azsjok` (necessário pro `schedule:`
      funcionar sozinho).
- [x] Testado via `workflow_dispatch` (2x — uma antes e uma depois de ter
      uma subscription cadastrada): [run 1](https://github.com/rromano33/Coding-/actions/runs/30723392302)
      sucesso sem subscription ativa, [run 2](https://github.com/rromano33/Coding-/actions/runs/30723683954)
      sucesso **com** notificação chegando de verdade no iPhone.

## 6. Backup local no Mac

- [x] `~/trading-diary-backups/` criado.
- [x] `.plist` copiado pra `~/Library/LaunchAgents/` com `trading-diary`
      no lugar do placeholder.
- [x] `launchctl load` + `launchctl start` manual pra testar — gerou dump
      real (17 linhas, `.sql` de ~7KB). Roda sozinho 1x/dia às 22h daqui
      pra frente.
- [x] Bug corrigido: o script original não achava o `turso` CLI quando
      rodado via `launchd` (que não carrega `.bash_profile`) — corrigido
      pra exportar o PATH explicitamente dentro do próprio script
      (commit `63308b1`, **ainda não empurrado pro GitHub** — sem
      credencial de git disponível na sessão que fez isso; rodar `git
      push origin claude/trading-diary-app-azsjok` quando puder).

## 7. Testado no celular

- [x] Login com `ricardo.fipe@gmail.com` na URL real da Vercel (dados
      migrados no passo 1, nada perdido).
- [x] "Adicionar à Tela de Início" → aberto pelo ícone instalado.
- [x] Notificações ativadas em Opções.
- [x] Push de teste (via `workflow_dispatch` do GitHub Actions) **confirmado
      chegando no iPhone real**.
