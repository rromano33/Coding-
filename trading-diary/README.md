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

O app manda push notifications (stop atingido, alertas de risco, ou um
lembrete diário se não tiver nada crítico) — um job roda 1x/dia (9h) no
próprio backend.

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

## Deploy 24/7

Backend no Render (Docker + disco persistente, sem precisar trocar de
SQLite) e frontend no Vercel. Estimativa de custo: Render "Starter"
(instância que não hiberna e suporta disco) fica em torno de US$7/mês;
Vercel no plano Hobby é gratuito pra esse tamanho de app.

### 1. Backend → Render

1. [render.com](https://render.com) → **New** → **Web Service** → conecte o
   repo `rromano33/coding-`.
2. **Root Directory**: `trading-diary/backend`.
3. **Runtime**: Docker (Dockerfile Path: `Dockerfile`, já que o root
   directory acima já aponta pra pasta certa).
4. **Plan**: Starter (o free tier hiberna e não tem disco persistente —
   não serve pra manter o SQLite entre reinícios).
5. Aba **Disks** → adicionar disco: mount path `/app/data`, 1 GB (o
   `DATABASE_URL` padrão do app já aponta pra esse caminho, não precisa
   sobrescrever).
6. Aba **Environment** → adicionar:
   - `SECRET_KEY`: qualquer string aleatória longa.
   - `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CLAIM_EMAIL`: as
     mesmas chaves geradas pra push (veja seção acima) — **não** as chaves
     de teste deste repo, gere um par novo pra produção.
   - `CORS_ORIGINS`: por ora deixe `["*"]`; depois do passo 2 (Vercel),
     volte aqui e troque pelo domínio real, ex.
     `["https://seu-app.vercel.app"]`.
7. **Health Check Path**: `/health`.
8. Deploy. Anota a URL gerada (`https://trading-diary-backend-xxxx.onrender.com`).

Há um `render.yaml` em `trading-diary/backend/` com essa configuração como
Blueprint — pode tentar usá-lo direto (**New** → **Blueprint**, apontando
pro arquivo), mas como o repo tem outros projetos na raiz o auto-detect do
Render pode não achá-lo; se não achar, siga os passos manuais acima.

### 2. Frontend → Vercel

1. [vercel.com](https://vercel.com) → **New Project** → importe o mesmo
   repo `rromano33/coding-`.
2. **Root Directory**: `trading-diary/frontend` (framework Vite é
   auto-detectado).
3. **Environment Variables** → `VITE_API_URL` = a URL do Render do passo 1
   (ex. `https://trading-diary-backend-xxxx.onrender.com`). É embutida no
   build, então qualquer mudança nessa variável exige um redeploy.
4. Deploy. Anota a URL gerada (`https://seu-app.vercel.app`).
5. Volte no Render e atualize `CORS_ORIGINS` com essa URL, redeploy o
   backend.

O `vercel.json` já incluído faz o rewrite de todas as rotas pra
`index.html` (necessário porque o app usa `react-router-dom` com histórico
de navegador — sem isso, atualizar a página numa rota tipo `/trades/5` dá
404).

### 3. Testar

Abra a URL do Vercel no celular, crie a conta (ou reaproveite se migrou
dados manualmente — **este deploy começa com banco vazio**, os trades
salvos localmente não são migrados automaticamente), adicione à tela de
início e ative as notificações em Opções.

## Próximos passos possíveis

- Anexar prints/screenshots do gráfico a cada trade.
- Editar trade fechado ainda parcialmente (hoje dá pra editar tudo via
  `PUT /trades/{id}`, mas a UI de edição é a mesma tela de criação —
  pode valer separar fluxos de "fechar trade" vs "editar trade").
