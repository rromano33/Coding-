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

## Próximos passos possíveis

- Deploy do backend (Render/Fly/Railway) + Postgres gerenciado no lugar do
  SQLite, se quiser sincronizar entre vários dispositivos de forma mais
  robusta.
- Anexar prints/screenshots do gráfico a cada trade.
- Editar trade fechado ainda parcialmente (hoje dá pra editar tudo via
  `PUT /trades/{id}`, mas a UI de edição é a mesma tela de criação —
  pode valer separar fluxos de "fechar trade" vs "editar trade").
