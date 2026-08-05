# Diário de Trades

App para o dia a dia de mesa: diário de trades (com PnL e múltiplo R
calculados automaticamente), diário de performance, movimentos de mercado e
impressões/disciplina. Web app (PWA) — instala na tela inicial do celular,
sem loja de app.

## Estrutura

```
trading-diary/
  backend/    FastAPI + SQLite (SQLAlchemy), autenticação por JWT
  frontend/   React + Vite + TypeScript, PWA instalável, mobile-first
```

## Rodando local (dev)

Backend:

```bash
cd trading-diary/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (em outro terminal):

```bash
cd trading-diary/frontend
npm install
npm run dev
```

Abra `http://localhost:5173`, crie uma conta e comece a usar. Por padrão o
frontend fala com `http://localhost:8000` (configurável em `.env` →
`VITE_API_URL`, veja `.env.example`).

## Instalar no celular (PWA)

1. Rode o backend em algum lugar acessível pela rede do seu celular (sua
   máquina na mesma Wi-Fi, ou um deploy — ver abaixo).
2. `npm run build` no frontend gera `dist/`; sirva esse `dist/` em algum
   host (ex: Vercel, Netlify, Render, um Nginx simples) com
   `VITE_API_URL` apontando para o backend publicado.
3. No celular, abra a URL no navegador (Safari no iOS, Chrome no Android) e
   use "Adicionar à tela de início" — o app abre em tela cheia, como um
   app nativo.

Para uso 100% local (sem deploy), dá pra rodar backend + `npm run dev` na
sua máquina e acessar pelo IP dela na mesma rede Wi-Fi do celular
(`vite --host` já expõe na rede).

## O que tem no v1

- **Diário de trades**: ativo, mercado, direção, entrada/saída,
  quantidade, stop/alvo, taxas, estratégia/tags, tese de entrada, análise
  ex-post e estado emocional. PnL e múltiplo R são calculados
  automaticamente ao registrar o preço de saída.
- **Diário de performance**: PnL total, win rate, fator de lucro,
  expectativa por trade, R médio, drawdown máximo, curva de capital e
  breakdown por estratégia/ativo.
- **Movimentos de mercado**: notas datadas de leitura de mercado (macro,
  fluxo, notícias) — sem integração automática de dados de preço.
- **Impressões/disciplina**: diário de estado emocional e nota de
  disciplina (1-5) por dia.
- **Risco**: framework de risco do book, todo editável em Opções (⚙, dentro
  da aba Risco) — capital/budget, sharpe meta, stops em camadas (alerta +
  stop duro, diário/mensal/anual), risco por trade por nível de convicção,
  limites de concentração por tese/classe, regras comportamentais,
  drawdown dinâmico por fase de PnL construído e postura sazonal. A aba
  Risco calcula ao vivo: PnL dia/mês/ano vs. os stops, drawdown atual vs.
  o permitido na fase, concentração de risco aberto por tese/classe, e
  gera alertas quando algum limite é violado. O formulário de trade sugere
  quantidade de duas formas: pela distância até o stop, e pela volatilidade
  estimada do ativo (você digita a vol diária % — sem integração de
  mercado). Cada trade aberto pode ser marcado com o preço atual (manual):
  o app calcula PnL aberto e avisa quando o preço está perto do stop
  (badge amarelo) ou já cruzou (badge vermelho + alerta "stop" na aba
  Risco, com link direto pro trade).

## Notificações push

O app manda dois pushes por dia:

- **~17:30 BRT**: stop atingido, alertas de risco, ou um lembrete diário
  se não tiver nada crítico — é o momento de comentar o dia no Diário.
- **~09:00 BRT**: lembrete pra lançar o resultado oficial de **ontem**
  por classe (Rates/FX/Equities/Other) no Diário. Esse número é a única
  fonte que alimenta o motor de risco (stop diário/mensal/anual,
  drawdown, YTD) — trades individuais no app servem só de apoio (cálculo
  de PnL/R, sugestão de tamanho de posição), não entram nessa conta.

Local, os dois jobs rodam dentro do próprio processo do backend (horário
exato); em produção (Render free) são disparados de fora, por um GitHub
Actions agendado com os crons antecipados pra compensar o atraso que o
"schedule" do GitHub Actions costuma ter — ver "Deploy 24/7" abaixo.

Setup:

1. Gerar as chaves VAPID (só uma vez, não versionar):
   ```bash
   cd trading-diary/backend
   .venv/bin/python scripts/generate_vapid_keys.py
   ```
2. Colar a saída em `backend/.env` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`) e
   definir `VAPID_CLAIM_EMAIL` com um e-mail de contato (veja `.env.example`).

### Testar push de verdade no iPhone

Safari só entrega push pro app **instalado na tela de início** (não pra aba
normal do navegador) e exige HTTPS — `localhost` não serve. Pra testar sem
fazer deploy, expor os dois serviços via túnel do Cloudflare
([cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)):

```bash
# 1. backend rodando normalmente
cd trading-diary/backend
.venv/bin/uvicorn app.main:app --port 8000

# 2. túnel do backend (anota a URL https gerada)
cloudflared tunnel --url http://localhost:8000

# 3. aponta o frontend pro backend do túnel e builda
#    (VITE_API_URL é embutido no build, não é runtime — precisa rebuildar
#    se a URL do túnel mudar)
cd trading-diary/frontend
echo "VITE_API_URL=https://<url-do-tunel-do-backend>" > .env
npm run build
npm run preview -- --host

# 4. túnel do frontend buildado
cloudflared tunnel --url http://localhost:4173
```

No iPhone: abra a URL https do túnel do frontend no Safari → ícone de
compartilhar → "Adicionar à Tela de Início" → abra pelo ícone instalado
(não pela aba do Safari) → Risco → ⚙ Opções → "Ativar notificações" →
aceite a permissão → "Enviar notificação de teste".

## Deploy 24/7 (grátis)

**Já está no ar:** frontend em https://coding-mbay.vercel.app, backend em
https://coding-5ahe.onrender.com. Ver `DEPLOY_CHECKLIST.md` pro registro
do que foi feito e `CLAUDE.md` → "Estado atual" pras pendências. O guia
abaixo é a referência de como foi montado (útil se precisar recriar do
zero — outra conta, outro banco, etc.).

Backend no Render (plano **free**) + [Turso](https://turso.tech) (banco
SQLite-compatível hospedado, tier free permanente, sem cartão) + frontend
no Vercel (Hobby, grátis). Custo total: **US$0**.

O tradeoff de ser grátis: o Render free hiberna após ~15min sem tráfego —
a primeira requisição depois de dormir paga o cold start inteiro
(medido em produção: ~30s+, não "alguns segundos" — na prática, telas
demorando dezenas de segundos ou minutos). Sem disco persistente no free
tier, por isso o Turso: ele é quem guarda os dados de verdade, não o
disco do Render.

Pra evitar esse cold start sem pagar nada, tem um terceiro workflow
(`.github/workflows/trading-diary-keep-alive.yml`) que faz `GET /health`
a cada ~10min — mantém o Render sempre acordado, cabendo dentro das
750h/mês grátis do plano (um serviço rodando 24/7 já usa exatamente essa
cota). Não é 100% garantido pela Render, mas na prática elimina o cold
start quase sempre. Se ainda notar lentidão apesar disso, a saída
definitiva é o plano Starter pago (~US$7/mês) — sem hibernação e com
CPU/RAM dedicados.

Os jobs de push diário (17:30 e 09:00 BRT) não podem depender do processo
do backend estar acordado nesses horários — por isso são disparados de
fora, por um único GitHub Actions agendado com dois `cron:`
(`.github/workflows/trading-diary-daily-reminder.yml` na raiz do repo)
que chama `POST /push/run-daily-reminder` ou `POST
/push/run-morning-reminder` dependendo de qual `schedule` disparou; a
própria chamada HTTP acorda o Render se estiver dormindo.

### 1. Banco → Turso

1. Instalar o CLI: `curl -sSfL https://get.tur.so/install.sh | bash`
2. `turso auth signup` (ou `login` se já tiver conta) — não pede cartão.
3. `turso db create trading-diary`
4. `turso db show trading-diary --url` → anota a URL (algo como
   `libsql://trading-diary-SEU-USUARIO.turso.io`; **tire o prefixo
   `libsql://`** — o backend usa só o host).
5. `turso db tokens create trading-diary` → anota o token.

### 2. Backend → Render

1. [render.com](https://render.com) → **New** → **Web Service** → conecte o
   repo `rromano33/coding-`.
2. **Root Directory**: `trading-diary/backend`.
3. **Runtime**: Docker (Dockerfile Path: `Dockerfile`).
4. **Plan**: Free.
5. Aba **Environment** → adicionar:
   - `SECRET_KEY`: qualquer string aleatória longa.
   - `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL`: as
     mesmas chaves geradas pra push (veja seção acima) — **não** as chaves
     de teste deste repo, gere um par novo pra produção.
   - `TURSO_DATABASE_URL`: o host do passo 1.4 (sem `libsql://`).
   - `TURSO_AUTH_TOKEN`: o token do passo 1.5.
   - `CRON_SECRET`: qualquer string aleatória longa (vai ser reusada no
     GitHub Actions, passo 4).
   - `ENABLE_INTERNAL_SCHEDULER`: `false` (o gatilho real é o GitHub
     Actions, ver passo 4 — deixar o scheduler in-process ligado aqui só
     arriscaria mandar push duplicado nos dias em que o Render por acaso
     já estiver acordado no horário).
   - `CORS_ORIGINS`: por ora deixe `["*"]`; depois do passo 3 (Vercel),
     volte aqui e troque pelo domínio real, ex.
     `["https://seu-app.vercel.app"]`.
6. **Health Check Path**: `/health`.
7. Deploy. Anota a URL gerada (`https://trading-diary-backend-xxxx.onrender.com`).

Há um `render.yaml` em `trading-diary/backend/` com essa configuração como
Blueprint — pode tentar usá-lo direto (**New** → **Blueprint**, apontando
pro arquivo), mas como o repo tem outros projetos na raiz o auto-detect do
Render pode não achá-lo; se não achar, siga os passos manuais acima.

### 3. Frontend → Vercel

1. [vercel.com](https://vercel.com) → **New Project** → importe o mesmo
   repo `rromano33/coding-`.
2. **Root Directory**: `trading-diary/frontend` (framework Vite é
   auto-detectado).
3. **Environment Variables** → `VITE_API_URL` = a URL do Render do passo 2
   (ex. `https://trading-diary-backend-xxxx.onrender.com`). É embutida no
   build, então qualquer mudança nessa variável exige um redeploy.
4. Deploy. Anota a URL gerada (`https://seu-app.vercel.app`).
5. Volte no Render e atualize `CORS_ORIGINS` com essa URL, redeploy o
   backend.

O `vercel.json` já incluído faz o rewrite de todas as rotas pra
`index.html` (necessário porque o app usa `react-router-dom` com histórico
de navegador — sem isso, atualizar a página numa rota tipo `/trades/5` dá
404).

### 4. Push diário → GitHub Actions

1. No GitHub, repo `rromano33/coding-` → **Settings** → **Secrets and
   variables** → **Actions** → adicionar:
   - `CRON_SECRET`: o mesmo valor que você colocou no Render (passo 2).
   - `BACKEND_URL`: a URL do Render (passo 2), sem barra no final.
2. **Importante**: gatilhos `schedule:` do GitHub Actions só rodam no
   **branch default** do repositório. Se este workflow ainda estiver só
   no branch `claude/trading-diary-app-azsjok`, mergeie pro branch default
   (ou troque o default nas configurações do repo) — senão o cron nunca
   dispara sozinho.
3. Pra testar sem esperar o horário: aba **Actions** do GitHub → o
   workflow "Trading Diary — lembretes diários" → **Run workflow**
   (`workflow_dispatch`), escolhendo "fim-de-dia" ou "manha".

### 5. Keep-alive → GitHub Actions

Reusa os mesmos secrets do passo 4 (`BACKEND_URL`). Não precisa configurar
nada além disso — o workflow `trading-diary-keep-alive.yml` já faz `GET
/health` a cada ~10min sozinho, desde que esteja no branch default (mesma
observação do passo 4.2 sobre `schedule:`).

### 5. Backup local no Mac (opcional, recomendado)

Rede de segurança extra além do Turso — `trading-diary/backend/scripts/`
tem `backup_turso.sh` (dump diário via Turso CLI) e um `.plist` de
exemplo pra rodar via `launchd` 1x/dia. Ver comentários nesses dois
arquivos pra instalar.

### 6. Testar

Abra a URL do Vercel no celular, crie a conta (ou migre o trade real que
já existia localmente — ver "Migração de dados" no `DEPLOY_CHECKLIST.md`,
**este deploy começa com banco vazio** por padrão), adicione à tela de
início e ative as notificações em Opções.

## Próximos passos possíveis

- Anexar prints/screenshots do gráfico a cada trade.
- Editar trade fechado ainda parcialmente (hoje dá pra editar tudo via
  `PUT /trades/{id}`, mas a UI de edição é a mesma tela de criação —
  pode valer separar fluxos de "fechar trade" vs "editar trade").
