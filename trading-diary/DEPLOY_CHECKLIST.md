# Checklist de deploy 24/7 (Render + Vercel)

Passo a passo literal — segue na ordem, marca e vai. Detalhes/explicação de
cada item estão em `README.md` → "Deploy 24/7". As chaves VAPID de produção
foram geradas numa conversa anterior com o Claude (não estão neste
repositório, nem devem entrar em nenhum commit) — se você não as tem
salvas, gere um par novo com `backend/scripts/generate_vapid_keys.py`.

## 0. Pré-checagem (já feita, não repetir)

- [x] Dockerfile do backend testado (simulação local de disco persistente:
      dado sobrevive a restart do processo).
- [x] `render.yaml` validado como YAML.
- [x] `vercel.json` com rewrite de SPA (`BrowserRouter`).
- [x] `npm run build` e `tsc -b` passam limpos no frontend.

## 1. Backend no Render

- [ ] Criar conta / logar em [render.com](https://render.com).
- [ ] **New** → **Web Service** → conectar repo `rromano33/coding-`.
- [ ] Root Directory: `trading-diary/backend`.
- [ ] Runtime: **Docker** (Dockerfile Path: `Dockerfile`).
- [ ] Plan: **Starter** (free tier hiberna e não tem disco — não serve).
- [ ] Aba **Disks**: mount path `/app/data`, tamanho `1 GB`.
- [ ] Aba **Environment**, adicionar:
  - [ ] `SECRET_KEY` = string aleatória longa (ou deixar o Render gerar).
  - [ ] `VAPID_PUBLIC_KEY` = (par de produção, gerado na conversa/script)
  - [ ] `VAPID_PRIVATE_KEY` = (idem — **nunca commitar**)
  - [ ] `VAPID_CLAIM_EMAIL` = `ricardo.fipe@gmail.com` (ou outro e-mail seu)
  - [ ] `CORS_ORIGINS` = `["*"]` por enquanto (ajustar no passo 3)
- [ ] Health Check Path: `/health`.
- [ ] Deploy → anotar a URL: `https://____________________.onrender.com`

## 2. Frontend na Vercel

- [ ] Criar conta / logar em [vercel.com](https://vercel.com).
- [ ] **New Project** → importar o mesmo repo `rromano33/coding-`.
- [ ] Root Directory: `trading-diary/frontend`.
- [ ] Environment Variables → `VITE_API_URL` = URL do Render (passo 1).
- [ ] Deploy → anotar a URL: `https://____________________.vercel.app`

## 3. Fechar o CORS

- [ ] Voltar no Render → Environment → `CORS_ORIGINS` =
      `["https://____________________.vercel.app"]` (a URL real do passo 2).
- [ ] Redeploy do backend.

## 4. Testar no celular

- [ ] Abrir a URL da Vercel no Safari/Chrome do celular.
- [ ] Criar conta (banco começa vazio — trades salvos localmente antes do
      deploy não migram sozinhos).
- [ ] "Adicionar à Tela de Início".
- [ ] Abrir pelo ícone instalado (não pela aba do navegador) → Risco → ⚙
      Opções → "Ativar notificações" → aceitar permissão → "Enviar
      notificação de teste".
