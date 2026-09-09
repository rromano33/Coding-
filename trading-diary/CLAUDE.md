# Diário — contexto do projeto

Leia isto antes de mexer em qualquer coisa. Documenta o que já existe, por
quê, e o que **não** reabrir sem necessidade real.

## Pivot 2026-09-09 — virou um diário simples de texto + mood

O produto foi **totalmente repensado**: de um diário de trades completo
(trades, framework de risco, diário macro estruturado) pra um diário pessoal
simples — texto livre + 1 carinha de mood (5 pra começar, escala 1-5,
extensível) por entrada, múltiplas entradas por dia. Decisão explícita do
usuário: simplificar e só manter histórico pra olhar no futuro, não mais
operar risco pelo app.

O que isso significou na prática:

- **Novo**: `JournalEntry` (`backend/app/models.py`) + rota `/journal`
  (`backend/app/routers/journal.py`) + `frontend/src/pages/JournalPage.tsx`,
  que agora é a tela inicial (`/`) e a única aba do `BottomNav`.
- **Trades/Performance/Risco/Diário macro (`DailyNotePage`) saíram da
  navegação, mas o código e as tabelas continuam existindo** (decisão do
  usuário: reversível, não apagar código). Rotas ainda montadas em
  `App.tsx`, só sem link: `/trades`, `/trades/new`, `/trades/:id[/edit]`,
  `/performance`, `/diario-macro` (era `/diario`, renomeado pra abrir espaço
  pro novo Diário), `/risco`, `/risco/opcoes`.
- **Os dados de produção dessas tabelas foram exportados e apagados**
  (decisão explícita do usuário, não só "esconder") em 2026-09-09: `trades`
  (0 linhas — já estava zerado), `daily_notes` (162 linhas — 162 dias úteis
  distintos de jan a ago/2026 com PnL por classe lançado diariamente, quase
  todo o resto dos campos de texto vazio, só 2 dias com `comentario_geral`
  preenchido), `risk_settings`/`conviction_tiers`/`stop_layers`/
  `drawdown_phases`/`seasonal_postures` (framework de risco completo do
  usuário). Backup em dois formatos, fora do git (dado financeiro pessoal):
  `~/trading-diary-backups/pre-simplify-2026-09-09.sql` (dump completo do
  banco) e `~/trading-diary-backups/pre-simplify-export-2026-09-09.json`
  (só essas 7 tabelas, legível). `push_subscriptions` e `users` não foram
  tocados.
- Se um dia quiser reativar Trades/Risco: o código funciona, só falta
  linkar de novo no `BottomNav`/`App.tsx` — os dados antigos não voltam
  sozinhos (foram apagados), mas dá pra reimportar do JSON acima se quiser.
- **Bug real encontrado e corrigido (2026-09-09, mesmo dia do pivot)**:
  já existia uma tabela `journal_entries` em produção, órfã de uma feature
  de "diário emocional por trade" do **primeiro** commit do projeto
  (`5e9fdb5`), removida depois em `5e8aab2` — só o model foi apagado, a
  tabela nunca foi (sem Alembic, nada dropa tabela sozinho). Schema antigo:
  `date`/`mood` (texto livre)/`discipline_score`/`content`, incompatível
  com o novo `JournalEntry` (`text`/`mood` int). `create_all()` só cria
  tabela que não existe, então viu a tabela e não corrigiu nada — toda
  leitura/escrita no `/journal` novo quebrava em produção (era o que
  causava "Carregando..." travado e "Salvar" que não salvava, sem
  nenhum erro visível pro usuário — bug à parte, ver abaixo). Corrigido
  renomeando a tabela antiga pra `journal_entries_legacy_2026_08` (não
  apagada, só fora do caminho) e criando a `journal_entries` nova do
  zero. Tinha 1 linha real lá dentro — uma entrada genuína de 03/08/2026
  sobre frustração com a equipe — migrada pro schema novo (mood "frustrado"
  mapeado pra 2/😕, editável pelo usuário se achar que devia ser outro).
  Backup extra em `~/trading-diary-backups/legacy-journal-entries-2026-09-09.json`.
  Se reaproveitar `journal_entries` como nome de tabela de novo no futuro,
  **checar sempre se já existe no Turso antes de assumir que `create_all`
  vai criar do jeito certo** — esse é o tipo de bug que esse padrão sem
  migrations permite.
- **Bug de UX corrigido junto**: `JournalPage` não tinha `.catch` nas
  chamadas de API — uma falha (como a acima) deixava "Carregando..." pra
  sempre e o botão "Salvar" voltava ao normal sem nenhuma mensagem,
  parecendo que "não salvou" sem pista nenhuma do motivo. Agora tem estado
  de erro visível com botão de retry no load e mensagem inline no form.
- **Pushes diários mantidos, repurposed** (decisão explícita do usuário:
  "mantenha, porque isso me lembra de preencher o diário, mas não precisa
  de resultados"). `push_service.py`: `send_daily_reminder` (~17:30) e
  `send_morning_reminder` (~9h, era `send_yesterday_result_reminder`)
  agora mandam só um lembrete genérico de escrever no diário — nada de
  resultado por classe/risco. `send_morning_reminder` pula o usuário se
  ele já criou uma `JournalEntry` hoje (mesma lógica de "pular se já
  preenchido" de antes, só que contra o diário novo). Ver "Push
  notifications" abaixo pra infra (scheduler, GitHub Actions, VAPID) —
  isso não mudou, só o conteúdo/gatilho de completude dos dois jobs.

## Objetivo do produto (histórico — trades/risco, ver pivot acima)

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
    models.py            SQLAlchemy: User, Trade, DailyNote,
                          RiskSettings, ConvictionTier, StopLayer,
                          DrawdownPhase, SeasonalPosture
    schemas.py            Pydantic (request/response)
    auth.py                hashing + JWT + get_current_user
    calculations.py        fonte única da matemática de dinheiro: gross_pnl,
                           compute_pnl/compute_r_multiple (fechamento do
                           trade), position_risk_brl (usado por risk.py tb)
    types_labels.py        rótulos PT (MARKET_LABELS/RISK_CLASS_LABELS) pro
                           texto gerado em daily_notes.py
    risk_defaults.py       valores default de risco (seed on first access)
    routers/
      auth.py, trades.py, daily_notes.py, stats.py, journal.py
      risk_settings.py     CRUD dos parâmetros de risco
      risk.py               GET /risk/status (calculado, ver abaixo)
  frontend/src/
    api/{client,endpoints}.ts
    auth/{AuthContext,LoginPage,RegisterPage}.tsx
    components/{Layout,BottomNav,ProtectedRoute,StatCard}.tsx
    pages/
      JournalPage (tela inicial atual, ver "Pivot 2026-09-09" acima —
        histórico agrupado por mês/ano, com busca por data exata)
      TradesPage, TradeFormPage, TradeDetailPage (legado, sem link no nav)
      PerformancePage (legado, sem link no nav)
      DailyNotePage (legado, `/diario-macro`, sem link no nav)
      RiskStatusPage, RiskSettingsPage (legado, sem link no nav)
    types.ts, utils/format.ts
```

## O que já está implementado

- **Auth**: registro/login, JWT em `localStorage`, `ProtectedRoute`.
- **Trades**: CRUD completo. `pnl`/`r_multiple` calculados automaticamente
  ao registrar `exit_price` (`calculations.py:apply_computed_fields`).
  Campos: asset, market, direction, status, entry/exit date+price,
  quantity, stop/target, fees, strategy, tags, thesis, notes, emotions,
  conviction, vol_diaria_pct, current_price (+ current_price_updated_at),
  currency, fx_rate_to_brl, contract_multiplier, risk_class,
  manual_adjustment.
  `unrealized_pnl` e `stop_alert` (`"perto"` | `"atingido"` | `None`) são
  **properties Python no modelo `Trade`**, não colunas — calculadas a
  partir de `current_price` vs. `entry_price`/`stop_price`/`direction`.
  Endpoint dedicado `PATCH /trades/{id}/price` pra marcar preço sem passar
  pelo form de edição completo.
  - **PnL multi-moeda/multi-classe**: `entry_price`/`exit_price`/`quantity`
    mudam de significado por `market` — FX é notional na moeda base +
    taxa do par, futuros/opções são pontos/prêmio × `contract_multiplier`.
    O resultado bruto é convertido pra R$ via `fx_rate_to_brl` (taxa única,
    aplicada no momento do fechamento — não separa efeito cambial de
    efeito de preço, decisão deliberada, ver abaixo) e somado a
    `manual_adjustment` (ajuste manual em R$ pra scaling intraday: o
    usuário aumenta/diminui posição ao longo do dia sem abrir trade novo).
    `TradeFormPage` troca os rótulos e mostra/esconde Moeda, Taxa de
    conversão e Multiplicador conforme o `market` selecionado.
  - **`risk_class`** (`rates`/`fx`/`equities`/`other`) é **independente**
    de `market` — existe só pra alimentar o P&L por classe do Diário
    (ver abaixo), pré-selecionado por `market`
    (`DEFAULT_RISK_CLASS_BY_MARKET` em `types.ts`) mas editável, porque um
    "futuros" pode ser tanto um future de juro (RATES) quanto de índice
    (EQUITIES) e isso não dá pra inferir do `market` sozinho.
- **Performance**: `/stats/summary`, `/stats/equity-curve`,
  `/stats/by-strategy`, `/stats/by-asset`, `/stats/by-market`. Tudo
  calculado em Python a partir dos trades fechados (dataset pessoal,
  pequeno — não precisou de agregação SQL).
- **Diário** (`DailyNote`, substitui os antigos `MarketNote`/`JournalEntry`):
  segue a estrutura real do diário macro diário do usuário (Ontem,
  Comentário geral, Oil/Commodities, Bolsas, Juros DM, Pricing DM, DXY/
  DMFX, Moedas EM, BRL, Rates EM, Pricing EM, Meu book, **resultado
  oficial do dia por classe** (`pnl_rates`/`pnl_fx`/`pnl_equities`/
  `pnl_other`, floats nullable — ver "Risco é top-down" abaixo),
  Posições, O que espero de amanhã, Vol total USD/BRL, Risco de
  portfólio). CRUD simples (`routers/daily_notes.py`), mais
  `GET /daily-notes/prefill?date=` que **só sugere** valores iniciais
  (não é dashboard ao vivo): "Ontem" vem do `espero_amanha` do registro
  anterior, "Posições" lista os trades `status=="open"` no momento —
  isso vira texto editável no form, o registro salvo é sempre o texto
  final (congelado). O resultado por classe é **sempre digitado à mão**
  (não tem prefill a partir de trades — decisão deliberada, ver abaixo).
  `pnl_por_classe` (texto) continua existindo só como string de exibição
  gerada no frontend a partir dos 4 campos numéricos antes de salvar —
  não é mais fonte de nada, é só pra manter o histórico legível na lista.
  `pricing_dm`/`pricing_em`/`vol_total_*`/`risco_portfolio` continuam
  texto livre ou manual — estruturar isso (por banco central, por
  metodologia de VaR) é escopo grande, não fiz agora.
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
  - **Risco é top-down, não vem de trades** (decisão deliberada do
    usuário, 2026-08-04): PnL hoje/mês/ano e a curva de drawdown vêm de
    `risk.py::_daily_official_pnl`, que soma `DailyNote.pnl_rates` +
    `pnl_fx` + `pnl_equities` + `pnl_other` por dia (um dia só entra na
    conta se pelo menos uma classe foi preenchida). `Trade.pnl` **não**
    entra nessa soma — trades no app servem só de apoio (calcular PnL/R
    individual, sugerir tamanho de posição), o usuário lança o resultado
    oficial do book separadamente todo dia (via push das ~9h, ver
    "Push notifications" abaixo) e é isso que baliza stop/drawdown/YTD.
    Concentração de risco por tese/classe e alertas de stop individual
    continuam vindo de trades **abertos** (isso é exposição atual, não
    PnL realizado — não muda com essa decisão).
- **Sizing sugerido** no form de trade: duas sugestões lado a lado —
  por distância ao stop (`risco_maximo / |entry - stop|`) e por
  volatilidade do ativo (`risco_maximo / (entry_price × vol_diaria_pct)`,
  assumindo 1× vol diária como referência de risco). Ambas agora dividem
  também por `contract_multiplier` e multiplicam pela `fx_rate_to_brl`
  quando a moeda não é BRL, senão o sizing sugerido saía errado pros
  mesmos casos que quebravam o PnL (FX/futuros/opções). Mesma correção
  aplicada em `risk.py::_position_risk` → `calculations.position_risk_brl`
  (usado no sizing sugerido *e* na concentração de risco por
  tese/classe em `GET /risk/status`).
- **Push notifications (web push)**: dois lembretes diários, horários e
  propósitos diferentes — não reabrir sem pedido novo.
  - `PushSubscription` (modelo novo): `endpoint`/`p256dh`/`auth` por usuário,
    N por usuário (um por dispositivo/navegador instalado).
  - `app/push_service.py`:
    - `send_push` (pywebpush + VAPID, remove a subscription do banco se o
      endpoint responder 404/410).
    - `send_daily_reminder` (~17:30) e `send_morning_reminder` (~09:00):
      descrição original abaixo (histórico, de quando ainda calculavam
      `risk/status`/`pnl_por_classe`) — **repurposed no pivot 2026-09-09**,
      ver seção "Pivot" no topo deste arquivo. Hoje os dois só mandam um
      lembrete genérico de escrever no diário, sem nenhum dado financeiro.
    - ~~`send_daily_reminder` (~17:30): varre usuários com subscription
      ativa, calcula `risk/status` de cada um e manda push — prioriza
      stop > alerta > lembrete genérico de trades abertos. É o momento
      de comentar o dia (diário de fim de dia).~~
    - ~~`send_yesterday_result_reminder` (~09:00): lembra de lançar o
      resultado oficial de ontem por classe no Diário
      (`pnl_rates`/`pnl_fx`/`pnl_equities`/`pnl_other`) — pula o usuário
      se esse dia já tiver alguma classe preenchida. Esse número é a
      única fonte do motor de risco (ver "Risco é top-down" acima), então
      esse push é estrutural, não cosmético: sem ele (ou sem o usuário
      responder), o dia fica de fora do drawdown/YTD.
  - `app/routers/push.py`: `GET /push/public-key`, `POST /push/subscribe`,
    `POST /push/unsubscribe`, `POST /push/test`, `POST
    /push/run-daily-reminder` (fim de dia), `POST /push/run-morning-reminder`
    (resultado oficial de ontem) — ambos protegidos por `X-Cron-Secret`.
  - Dois jobs via APScheduler (`BackgroundScheduler`) registrados no
    `lifespan` do `main.py`: `daily_reminder` (17:30) e `morning_reminder`
    (09:00), ambos `America/Sao_Paulo` — rodam em thread própria dentro do
    próprio processo do backend (não é um worker separado). Em produção
    (Render free) esse scheduler in-process fica desligado
    (`ENABLE_INTERNAL_SCHEDULER=false`) e o gatilho real é o GitHub
    Actions (ver "Deploy 24/7" no README) batendo nos dois endpoints em
    horários compensados.
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

- **Conversão FX pra R$ é uma taxa única aplicada no fechamento**
  (`fx_rate_to_brl`), não taxas separadas de entrada/saída. Decisão
  explícita do usuário: mais simples, não separa efeito cambial de
  efeito de preço. Se um dia isso incomodar, é campo novo + mudança na
  fórmula de `calculations.compute_pnl`, não mudança de conceito.
- **`risk_class` é campo separado de `market`**, não derivado dele — ver
  "O que já está implementado" acima. Não tentar inferir `risk_class` a
  partir de `market`/`asset` automaticamente; é decisão do usuário por
  trade.
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
- **Deploy: Render free + Turso, não Render Starter pago + disco.**
  Superseder de uma decisão anterior — motivo novo e explícito: usuário
  não quer gastar nada com o app. Render free não tem disco persistente
  (dado se perde a cada redeploy/restart) e hiberna após inatividade —
  **medido em produção (2026-08-05): cold start real de ~30s+ na primeira
  requisição depois de dormir**, não "alguns segundos" como se assumiu
  originalmente aqui (afetava tanto abertura do app quanto troca de tela,
  já que o usuário costuma levar mais que a janela de inatividade do
  Render lendo cada tela). Isolado com um probe direto no driver libsql
  (sem picos mesmo após 40s idle) — descartou bug no driver/Turso,
  confirmando que é especificamente o Render dormindo. Mitigado sem custo
  por `.github/workflows/trading-diary-keep-alive.yml`: `GET /health` a
  cada ~10min, mantendo o serviço sempre acordado (cabe nas 750h/mês
  grátis do plano — um serviço 24/7 já usa exatamente essa cota). Se
  ainda notar lentidão apesar disso, a saída definitiva é o Starter pago
  (~US$7/mês, sem hibernação + CPU/RAM dedicados) — usuário já foi
  avisado, decisão dele se/quando migrar. Turso (SQLite-compatível hospedado,
  tier free permanente, sem cartão) resolve o disco: `config.py` monta
  `resolved_database_url` (`sqlite+libsql://...`) quando
  `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` estão setados (só em produção —
  local dev continua 100% SQLite de arquivo, sem depender de rede).
  `database.py` tem um branch específico pra isso (`sqlite:///` = arquivo
  local com mkdir; Turso = engine com `connect_args={"auth_token": ...}`;
  qualquer outra coisa = genérico).
  - **Bug real encontrado e corrigido**: `sqlalchemy-libsql==0.2.0` deixa
    embutir `authToken` na query string da URL (`?authToken=...`), mas o
    driver `libsql_experimental` por baixo **ignora isso** — só lê o
    token via kwarg `auth_token=` passado em `connect_args`. Com o token
    na URL dá 401 "empty JWT token" mesmo com o token certo. Testado
    contra o Turso de produção real pra confirmar a correção (commit
    `25035dd`). Se um dia atualizar essa lib, testar de novo — pode ter
    sido corrigido upstream.
  - **Push num backend que hiberna**: o `BackgroundScheduler` in-process
    (`main.py`) só roda se `ENABLE_INTERNAL_SCHEDULER` não for `"false"`
    (default `true` — fica ligado local; no Render está `false`, ver
    `render.yaml`). O gatilho real de produção é externo: um GitHub
    Actions agendado (`.github/workflows/trading-diary-daily-reminder.yml`
    — **na raiz do repo**, não em `trading-diary/`, GitHub Actions não lê
    workflow de subpasta) chama `POST /push/run-daily-reminder`
    (protegido por header `X-Cron-Secret` == `settings.cron_secret`).
    Alvo: notificação às 17:30 BRT. **GitHub Actions não executa
    `schedule:` no horário exato** — observado chegando depois das 18:00
    com cron em 20:30 UTC — então o cron está em **20:00 UTC** (17:00
    BRT), 30min antecipado como margem de compensação. Se seguir
    atrasando, antecipar mais (não tem garantia formal de precisão do
    GitHub, só ajuste empírico). A própria chamada HTTP acorda o Render se
    estiver dormindo. Gatilhos `schedule:` do GitHub Actions só rodam no
    branch default do repo — **já trocado** pro `claude/trading-diary-app-azsjok`
    (era `claude/session-0asigz`). Testado via `workflow_dispatch` e
    confirmado: notificação chegou no iPhone real do usuário.
  - **Backup extra pro Mac**: `backend/scripts/backup_turso.sh` (usa
    `turso db shell <db> .dump`) + `~/Library/LaunchAgents/com.ricardoromano.
    trading-diary-backup.plist` (cópia local do `.plist` do repo, com
    `SEU_BANCO_TURSO` já trocado por `trading-diary`) — **já instalado e
    rodando** via `launchd`, 1x/dia às 22h. Salva dumps em
    `~/trading-diary-backups/` (fora do repo, dado financeiro pessoal não
    vai pro git), mantendo os últimos 30 dias. Testado manualmente
    (`launchctl start com.ricardoromano.trading-diary-backup`): gerou
    dump real com as 17 linhas de dado do usuário. Rede de segurança, não
    a defesa principal — a principal é o próprio Turso.
  - Frontend continua no Vercel (`vercel.json`, rewrite de SPA por causa
    do `BrowserRouter`) — isso não mudou, Vercel Hobby já era grátis.
  - `render.yaml` atualizado: `plan: free`, sem bloco `disk:`, com as
    env vars novas (`TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`,
    `CRON_SECRET`, `ENABLE_INTERNAL_SCHEDULER=false`).

## Estado atual — **já está em produção, no ar, testado**

Não é mais um plano — isso está rodando de verdade desde 2026-08-01:

- **Frontend**: https://coding-mbay.vercel.app (Vercel, projeto `coding-mbay`)
- **Backend**: https://coding-5ahe.onrender.com (Render free, serviço `Coding-`)
- **Banco**: Turso, banco `trading-diary` (conta `ricardoromano33`, org
  `aws-us-east-1`). Dados reais do usuário (conta `ricardo.fipe@gmail.com`
  + o trade USDBRL + framework de risco completo) foram migrados do
  SQLite local pra lá — o SQLite local (`backend/data/trading_diary.db`)
  foi limpo de contas de teste antes da migração e continua existindo só
  como banco de **dev local**, não é mais a fonte de dados real.
  `CORS_ORIGINS` no Render já apertado só pra URL da Vercel (não é mais
  `["*"]`).
- **Push diário**: GitHub Actions rodando no branch default (ver acima),
  testado e confirmado entregando notificação real no iPhone do usuário.
- **Backup**: `launchd` rodando local no Mac do usuário, testado.
- Local (`uvicorn`/`vite dev`) continua funcionando normalmente pra
  desenvolvimento — não precisa de Turso nem de nada em produção pra
  iterar localmente, só cai no SQLite de arquivo de sempre.

**Pendências não-bloqueantes:**
- Commits locais não empurrados pro remoto (`63308b1` fix do
  `backup_turso.sh`, e o commit que adiciona PnL multi-moeda/multi-classe
  + Diário macro, ver "O que já está implementado") — sem credencial de
  git disponível nas sessões que fizeram isso. Rodar
  `git push origin claude/trading-diary-app-azsjok` quando tiver como.
- **Antes de fazer deploy do commit de PnL/Diário em produção**: `Trade`
  ganhou colunas novas (`currency`, `fx_rate_to_brl`, `contract_multiplier`,
  `risk_class`, `manual_adjustment`) e existe uma tabela nova
  (`daily_notes`). Sem Alembic, `create_all` cria a tabela nova sozinho,
  mas **não adiciona colunas na tabela `trades` já existente no Turso** —
  precisa rodar manualmente algo como
  `ALTER TABLE trades ADD COLUMN currency TEXT;` (e as outras 4) via
  `turso db shell trading-diary` antes de subir esse backend, senão os
  requests que leem/escrevem `Trade` vão quebrar em produção. Baixo risco
  (colunas nullable/com default, só 1 trade real no banco), mas é passo
  manual — não fazer sem confirmar com o usuário na hora do deploy.
- **Bug conhecido, não corrigido**: `RiskSettings.get_or_create` (em
  `routers/risk_settings.py`) tem race condition — a página de Opções
  dispara 5 GETs em paralelo na primeira visita de um usuário
  **totalmente novo**, e duas requisições podem tentar criar a mesma
  linha singleton ao mesmo tempo, batendo em `UNIQUE constraint failed`
  (vira 500, que sem headers de CORS aparece como falso erro de CORS no
  navegador). Baixo risco pro usuário real (já semeado), mas afeta
  qualquer conta nova. Não precisa nem git — só cria uma conta e visita
  `/risco/opcoes` rapidinho pra reproduzir.
- **Credenciais usadas neste deploy não ficaram salvas em lugar nenhum
  meu** (nem deveriam) — se uma sessão futura precisar mexer em
  Render/Vercel/GitHub programaticamente: (1) Vercel CLI tem token
  cacheado em `~/Library/Application Support/com.vercel.cli/auth.json`
  (`npx vercel whoami` confirma) — dá pra usar a API REST da Vercel
  direto com esse token, sem pedir nada ao usuário; (2) Render e GitHub
  **não têm** credencial cacheada — GitHub em particular só aceita
  Personal Access Token (login é via Google, sem senha tradicional); se
  precisar, pedir um token novo ao usuário (ele já fez isso duas vezes
  nesta sessão, sabe o caminho: github.com/settings/tokens).

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

Todo o trabalho está no branch `claude/trading-diary-app-azsjok` do repo
`rromano33/Coding-` (que também contém um projeto Python não-relacionado
na raiz — `Data/`, `config/`, `scripts/`, `src/`, `tests/` — não mexer
nele por engano). **Esse branch é o branch default do repositório**
(trocado de `claude/session-0asigz` pra este, necessário pro cron do
GitHub Actions funcionar — ver "Estado atual" acima). Uma sessão nova do
Claude Code que abrir este repo do zero deve cair aqui automaticamente.

## Ideias de próximos passos (não compromissos, só notas)

- Corrigir a race condition do `RiskSettings.get_or_create` (ver
  "Pendências" acima) — baixo esforço, é só serializar as 5 chamadas da
  RiskSettingsPage ou fazer um `get_or_create` atômico (`INSERT OR
  IGNORE` + `SELECT`).
- Alembic, se o schema for mudar de novo com dados reais já no banco
  (agora que tem deploy 24/7 com dados reais, vale mais a pena que antes).
- Separar "tese" de `strategy` se a sobreposição atrapalhar na prática.
- Anexar screenshots de gráfico a um trade.
- Fluxo de "fechar trade" separado do formulário de edição genérico.
- Layout mais "profissional" (visual) — motivação original da conversa
  que levou ao push notification; ainda não endereçado especificamente,
  a UI atual é funcional mas básica (Tailwind puro, sem design system).
