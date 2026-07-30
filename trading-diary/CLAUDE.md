# Diário de Trades — contexto do projeto

Leia isto antes de mexer em qualquer coisa. Documenta o que já existe, por
quê, e o que **não** reabrir sem necessidade real.

## Objetivo do produto

App pessoal (dono: um trader de mesa de operações) para três coisas:

1. Diário de trades com dados suficientes para análise ex-post, consolidado
   num diário de performance.
2. Pautar a tomada de risco em dados: sizing de posição relativo à
   volatilidade do ativo e ao resultado YTD vs. metas do book.
3. Alertar sobre os stops previamente definidos (tanto no nível do book —
   PnL dia/mês/ano vs. limites — quanto por posição individual).

Uso pessoal, single-tenant por conta (cada usuário só vê os próprios
dados). Não é um produto multi-cliente.

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite, autenticação JWT (`python-jose`
  + `passlib[bcrypt]`).
- **Frontend**: React + Vite + TypeScript, PWA (`vite-plugin-pwa`),
  Tailwind v4, `react-router-dom`, `recharts`. Mobile-first, pensado pra
  instalar na tela inicial do celular.
- Sem framework de state management além de Context (auth) + fetch direto
  por página. Sem testes automatizados formais — validação até agora foi
  via `curl` (backend) e scripts Playwright ad-hoc descartáveis (não
  commitados no repo).

## Estrutura

```
trading-diary/
  backend/app/
    models.py            SQLAlchemy: User, Trade, MarketNote, JournalEntry,
                          RiskSettings, ConvictionTier, StopLayer,
                          DrawdownPhase, SeasonalPosture
    schemas.py            Pydantic (request/response)
    auth.py                hashing + JWT + get_current_user
    calculations.py        pnl/r_multiple no fechamento do trade
    risk_defaults.py       valores default de risco (seed on first access)
    routers/
      auth.py, trades.py, market_notes.py, journal.py, stats.py
      risk_settings.py     CRUD dos parâmetros de risco
      risk.py               GET /risk/status (calculado, ver abaixo)
  frontend/src/
    api/{client,endpoints}.ts
    auth/{AuthContext,LoginPage,RegisterPage}.tsx
    components/{Layout,BottomNav,ProtectedRoute,StatCard}.tsx
    pages/
      TradesPage, TradeFormPage, TradeDetailPage
      PerformancePage
      MarketNotesPage
      JournalPage
      RiskStatusPage (aba "Risco"), RiskSettingsPage (Opções, /risco/opcoes)
    types.ts, utils/format.ts
```

## O que já está implementado

- **Auth**: registro/login, JWT em `localStorage`, `ProtectedRoute`.
- **Trades**: CRUD completo. `pnl`/`r_multiple` calculados automaticamente
  ao registrar `exit_price` (`calculations.py:apply_computed_fields`).
  Campos: asset, market, direction, status, entry/exit date+price,
  quantity, stop/target, fees, strategy, tags, thesis, notes, emotions,
  conviction, vol_diaria_pct, current_price (+ current_price_updated_at).
  `unrealized_pnl` e `stop_alert` (`"perto"` | `"atingido"` | `None`) são
  **properties Python no modelo `Trade`**, não colunas — calculadas a
  partir de `current_price` vs. `entry_price`/`stop_price`/`direction`.
  Endpoint dedicado `PATCH /trades/{id}/price` pra marcar preço sem passar
  pelo form de edição completo.
- **Performance**: `/stats/summary`, `/stats/equity-curve`,
  `/stats/by-strategy`, `/stats/by-asset`, `/stats/by-market`. Tudo
  calculado em Python a partir dos trades fechados (dataset pessoal,
  pequeno — não precisou de agregação SQL).
- **Movimentos de mercado** e **Diário/Impressões**: CRUD simples, sem
  lógica especial.
- **Framework de risco** (espelha uma planilha de referência do usuário —
  "Framework de Risco — Parâmetros do Book"):
  - `RiskSettings` (singleton por usuário): capital alocado, budget anual
    de PnL, sharpe meta, stop_loss anual/mensal/diário (valores flat),
    risco máx. por tese/classe, nº máx. de trades/teses simultâneas,
    regras comportamentais (lista, guardada como JSON em `Text`).
  - `ConvictionTier`: baixa/média/alta/extrema → % do stop anual → risco
    máximo em R$.
  - `StopLayer`: por nível (`diario`/`mensal`) → `alerta_amarelo` +
    `stop_duro`, com motivo em texto livre.
  - `DrawdownPhase`: faixas de PnL construído no ano → % de drawdown
    permitido + floor mínimo em R$.
  - `SeasonalPosture`: tabela de referência (período, situação de PnL,
    postura) — **só exibida, nunca usada em lógica automática** (decisão
    deliberada, ver abaixo).
  - Tudo seedado com os defaults de `risk_defaults.py` na primeira vez que
    o usuário acessa `/risk-settings` (`get_or_create_settings`), e
    totalmente editável depois em Opções.
  - `GET /risk/status`: calcula PnL hoje/mês/ano, compara com os
    `StopLayer`/`stop_loss_*`, drawdown atual do ano vs. permitido pela
    fase, concentração de risco aberto (por `strategy`="tese" e por
    `market`="classe") vs. limites, contagem de trades/teses abertas vs.
    limites, e alertas por posição (proximidade/rompimento de stop
    individual, risco acima do permitido pra convicção). Alertas de
    posição carregam `trade_id` pra a UI linkar direto ao trade.
- **Sizing sugerido** no form de trade: duas sugestões lado a lado —
  por distância ao stop (`risco_maximo / |entry - stop|`) e por
  volatilidade do ativo (`risco_maximo / (entry_price × vol_diaria_pct)`,
  assumindo 1× vol diária como referência de risco).
- **Push notifications (web push)**:
  - `PushSubscription` (modelo novo): `endpoint`/`p256dh`/`auth` por usuário,
    N por usuário (um por dispositivo/navegador instalado).
  - `app/push_service.py`: `send_push` (pywebpush + VAPID, remove a
    subscription do banco se o endpoint responder 404/410) e
    `send_daily_reminder` (varre usuários com subscription ativa, calcula
    `risk/status` de cada um e manda push — prioriza stop > alerta > lembrete
    genérico de trades abertos).
  - `app/routers/push.py`: `GET /push/public-key`, `POST /push/subscribe`,
    `POST /push/unsubscribe`, `POST /push/test`.
  - Job diário agendado via APScheduler (`BackgroundScheduler`, cron
    9h todo dia) registrado no `lifespan` do `main.py` — roda em thread própria
    dentro do próprio processo do backend (não é um worker separado).
  - Chaves VAPID em `.env` (`VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/
    `VAPID_CLAIM_EMAIL`), geradas com
    `backend/scripts/generate_vapid_keys.py`. **Nunca commitar as chaves
    reais** — só `.env.example` vazio vai pro repo.
  - Frontend: `vite-plugin-pwa` trocado de `generateSW` pra
    `strategies: "injectManifest"` (precisava de um service worker
    customizado pra lidar com os eventos `push`/`notificationclick`).
    `src/sw.ts` faz precache via `workbox-precaching` e mostra a notificação
    com o payload JSON mandado pelo backend (`title`/`body`/`url`).
    `src/sw.ts` é **excluído do `tsc -b`** (ver `tsconfig.json`) porque usa
    globais de `webworker`, incompatíveis com o `lib: DOM` do resto do app;
    o `vite build` bundla e type-checa o service worker separadamente.
  - `src/push.ts`: helpers `enablePushNotifications`/
    `disablePushNotifications`/`getPushSubscriptionStatus`. UI em
    `RiskSettingsPage` (seção "Notificações": ativar/desativar + botão de
    teste).
  - No iPhone (Safari), push só funciona com o site **instalado na tela
    inicial** (PWA standalone) — Safari não dá push pra aba de navegador
    comum. Testar isso é passo manual do usuário, não dá pra validar numa
    sessão remota.

## Decisões deliberadas — não reabrir sem motivo novo

- **"Tese" reaproveita o campo `Trade.strategy`** em vez de ter um campo
  dedicado. Foi uma decisão consciente pra não explodir o schema; o
  usuário está ciente. Se isso incomodar na prática, é uma migração
  pequena (campo novo + endpoint de concentração lendo o campo novo).
- **`current_price` é 100% manual** — o usuário escolheu explicitamente
  não integrar feed de mercado (Bloomberg não dá pra chamar de um app
  assim; alternativas tipo Alpha Vantage têm cobertura ruim pra ativos
  BR). Se um dia quiser automatizar, é endpoint novo + alguma API de
  cotação, mas isso é escopo grande.
- **`vol_diaria_pct` é estimativa digitada pelo usuário**, não calculada a
  partir de histórico de preços — decisão explícita pra não depender de
  acumular marcações antes do sizing funcionar.
- **`SeasonalPosture` é só informativo.** Decisão explícita de não
  parsear o texto livre de período/situação pra dirigir sizing
  automaticamente — regra frágil em cima de texto editável. Se quiser
  automatizar isso, precisa estruturar a tabela com mês/threshold
  numérico primeiro (mudança de schema, não só de lógica).
- **Sem Alembic/migrations.** Schema evolui via `Base.metadata.create_all`,
  que só cria tabelas que não existem — **não adiciona colunas em tabelas
  já existentes**. Toda vez que `models.py` ganha um campo novo num
  modelo existente, o banco local (`trading-diary/backend/data/trading_diary.db`)
  precisa ser apagado e recriado (perde dados). Isso é aceitável enquanto
  for ambiente de teste pessoal; se virar produção com dados que
  importam, configurar Alembic antes de continuar.
- **CORS liberado (`allow_origins=["*"]`)** — ok pra dev local, revisar
  antes de expor o backend publicamente.
- **SQLite, não Postgres** — suficiente pro volume de dados de uma pessoa;
  trocar é só mudar `DATABASE_URL` (já abstraído em `config.py`).
- **Deploy: Render (Docker + disco persistente) em vez de migrar pra
  Postgres.** Decisão deliberada pra manter o SQLite (ver ponto acima) —
  monta um disco em `/app/data` (mesmo caminho que `config.py` já usa por
  default) no plano Starter do Render, que não hiberna e mantém o disco
  entre deploys/restarts. Testado localmente (fora do Render) apontando
  `DATABASE_URL` pra um caminho fixo, matando e subindo o processo de novo:
  dado sobrevive. Frontend no Vercel (`vercel.json` com rewrite de SPA,
  necessário por causa do `BrowserRouter`). Ver README.md → "Deploy 24/7"
  pro passo a passo completo (inclui os campos exatos do dashboard do
  Render/Vercel). `CORS_ORIGINS` no Render precisa ser atualizado pro
  domínio real do Vercel depois do primeiro deploy do frontend.

## Como rodar

```bash
# backend
cd trading-diary/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (outro terminal)
cd trading-diary/frontend
npm install
npm run dev
```

Frontend em `http://localhost:5173`, fala com `http://localhost:8000` por
padrão (`VITE_API_URL` em `.env`, ver `.env.example`).

## Branch

Todo o trabalho até agora está no branch `claude/trading-diary-app-azsjok`
do repo `rromano33/coding-` (que também contém um projeto Python
não-relacionado, `emrates`, na raiz — não mexer nele por engano).

## Ideias de próximos passos (não compromissos, só notas)

- Alembic, se o schema for mudar de novo com dados reais já no banco
  (agora que tem deploy 24/7 com dados reais, vale mais a pena que antes).
- Separar "tese" de `strategy` se a sobreposição atrapalhar na prática.
- Anexar screenshots de gráfico a um trade.
- Fluxo de "fechar trade" separado do formulário de edição genérico.
