# emrates — precificação de BCs e PnL de swaps (LatAm + CEMEA)

Ferramentas para a mesa: (1) o que a curva de juros está precificando para
cada Banco Central, reunião a reunião, com simulação de cenários; (2) PnL
de posições abertas em swap, decomposto em carry/roll-down vs. movimento
de curva.

Países: Brasil, México, Chile, Colômbia, África do Sul, Polônia, República
Tcheca, Hungria.

## Isso roda local, não na nuvem

Este projeto foi montado num ambiente de nuvem, mas **precisa rodar na sua
máquina** (VS Code local) porque depende de:
- xbbg + Bloomberg Terminal/BBComm ativo (dados de mercado)
- `Data/Input_BCs.xlsx`, seu arquivo local

Clone/copie este repositório para `C:\Users\RRZBCSH\Projects\meu-projeto\`
— a pasta `Data/` do repo já bate com o caminho que você usa hoje, então o
arquivo `Input_BCs.xlsx` que já existe aí não precisa mudar de lugar.

## Setup

```bash
pip install -e .
pip install -r requirements.txt
```

## Passo 0 — calibrar o leitor da planilha

Eu não tenho acesso ao seu `Input_BCs.xlsx` real, então `excel_loader.py`
assume nomes de coluna (ver `config/settings.yaml`) que são um chute a
partir da sua descrição. Rode:

```bash
python scripts/inspect_inputs.py
```

e me mande o output (nomes de aba, colunas, primeiras linhas) — ajusto
`tickers_columns` / `dates_columns` / `positions_columns` em
`config/settings.yaml` para bater exatamente com o arquivo.

## Passo 1 — aba "Posições" (ainda não existe na sua planilha)

Adicione uma aba `Posições` em `Input_BCs.xlsx` com estas colunas
(nomes configuráveis em `config/settings.yaml` → `positions_columns` se
preferir nomes diferentes):

| Coluna | Descrição |
|---|---|
| TradeID | identificador único da operação |
| Country | brazil / mexico / chile / colombia / south_africa / poland / czech / hungary |
| TradeDate | data de fechamento |
| StartDate | data de início de acumulação |
| MaturityDate | data de vencimento |
| PayReceive | `pay` (pagando fixo/tomado) ou `receive` (recebendo fixo/aplicado) |
| Notional | notional da operação |
| FixedRate | taxa fixa contratada (decimal, ex: 0.1075) |
| Currency | moeda do notional |

## Uso diário

```bash
python scripts/run_daily_pricing.py   # precifica todos os países E já regenera Data/processed/dashboard.html
python scripts/run_pnl.py             # compara com a curva do dia anterior salva, gera Data/processed/pnl_<data>.csv
```

`run_daily_pricing.py` chama `build_dashboard.py` sozinho no final — não
precisa rodar os dois. Se quiser só reconstruir o dashboard a partir dos
dados já salvos (sem bater na Bloomberg de novo), rode
`python scripts/build_dashboard.py` isolado.

O dashboard inclui uma aba "Cenários interativos" por país — você digita
até 4 cenários alternativos (caminho absoluto de bps por reunião, não um
choque relativo ao mercado) e o navegador recalcula o impacto por vértice
na hora, sem precisar rodar nada de novo em Python.

## VaR e vol de portfólio (`riskvar/`)

Projeto separado dentro do mesmo repo: lê uma planilha de posições
(ativo, ticker BBG, tipo Notional/DV01, valor da posição — aba "Summary")
e o histórico diário de preços/taxas de outra aba da mesma planilha
("Preços", preenchida no Excel via `=BDH(...)` da própria Bloomberg — ver
`config/portfolio_risk.yaml`), e calcula, usando janelas de estimação de
3M (63 dias úteis) e 12M (252 dias úteis):

- **VaR** histórico e paramétrico (confiança configurável — `confidence_levels`
  no config, por padrão 95% e 99% lado a lado).
- **Expected Shortfall (ES/CVaR)** — perda média ALÉM do VaR, não só o
  ponto de corte; padrão de referência do FRTB (Basel).
- **Backtest em-amostra**: quantos dias, na própria amostra, a perda real
  ultrapassou o VaR estimado, vs. o esperado só pela confiança escolhida
  — mais informativo pro VaR paramétrico (estouros bem acima do esperado
  indicam caudas mais gordas que a Normal assume).
- **VaR individual por posição**: VaR histórico de cada posição como se
  fosse sozinha o portfólio inteiro (janela/confiança primárias) — coluna
  própria na tabela de ativos, antes da contribuição %.
- **Benefício de diversificação**: soma dos VaRs de cada posição isolada
  vs. o VaR real do portfólio (net) — os dois valores em $ aparecem lado
  a lado, seguidos do % que resume a diferença.
- **Correlação entre ativos**: matriz de correlação de Pearson do P&L
  diário, par a par — a base numérica do benefício de diversificação
  acima (pares com correlação baixa/negativa são hedges de verdade).
- **Piores dias**: as 10 piores datas de P&L da janela mais longa.
- Vol diária e anualizada.

Os tiles de VaR, ES e vol ficam em três linhas separadas por métrica (uma
linha só de VaR — todas as janelas/confianças juntas —, uma só de ES,
uma só de vol), não misturadas por janela.

O VaR/ES em si são sempre de 1 dia — o que muda entre as janelas é
quanto histórico entra na amostra, não o horizonte projetado.

Opcionalmente, um **stress test por sensibilidade a fatores macro** (ex:
"S&P -5%", "UST10y +20bps", "Brent +20%") — regressão linear do P&L do
portfólio contra fatores configurados em `stress_factors`/
`stress_scenarios` (cada fator precisa do próprio histórico como mais uma
coluna na aba "Preços", mesmo mecanismo `=BDH(...)`). Isso é sensibilidade
estatística contínua, não cenários de eventos históricos reais (Taper
Tantrum, COVID etc.) — aqueles ainda não estão implementados, exigem
pesquisa própria pra fixar magnitude/data certa por evento. Sem essas duas
chaves no config, a seção é pulada sem erro.

Não depende de sessão Bloomberg em Python (BBComm/xbbg) — só lê a
planilha. Células `#N/A N/A` (sem cotação naquele dia) são descartadas
automaticamente por ativo.

```bash
python scripts/run_var.py             # gera Data/processed/var_report_<data>.csv e .html
```

### Compartilhando com a mesa

O motor de cálculo é o mesmo pra todo mundo — só o caminho/aba/colunas da
planilha de cada trader muda, e isso fica num arquivo separado do código
de propósito, pra ninguém sobrescrever o config de outra pessoa:

1. Copie `config/portfolio_risk.example.yaml` (versionado, igual pra
   todo mundo) para `config/portfolio_risk.yaml` (pessoal — no
   `.gitignore`, nunca commitado).
2. Edite `paths.portfolio_xlsx` em `config/portfolio_risk.yaml` pro
   caminho real da SUA planilha, e os nomes de aba/coluna se a sua
   planilha usar nomes diferentes (já vem configurado com o layout
   confirmado: aba "Summary" com Classe | Ativo | BBG | Tipo | Posição,
   aba "Preços" com Classe/Ativo/BBG nas linhas e uma data por linha
   depois).
3. Rode `python scripts/run_var.py` normalmente.

Se o arquivo pessoal ainda não existir, `run_var.py` avisa exatamente
esses passos antes de sair. Convenção de sinal do DV01: valor da posição
para uma **alta** de 1bp na taxa (mesma convenção de
`emrates.portfolio.risk.dv01`) — se a posição ganha quando a taxa sobe
(ex: pagador em swap), o DV01 informado deve ser positivo.

Além do CSV, o script gera um relatório HTML autocontido (abre offline, em
qualquer navegador, sem precisar de internet) com os números principais em
destaque, a tabela completa (VaR/ES/vol/estouros por janela e confiança),
piores dias, benefício de diversificação, stress test (se configurado) e
um gráfico de P&L acumulado dos últimos 12 meses, com crosshair/tooltip ao
passar o mouse e uma vista em tabela alternativa.

### Versão interativa (cada trader digita as próprias posições)

`scripts/run_var.py` gera o relatório oficial a partir da SUA planilha —
posições e tudo. Pra distribuir pra mesa sem que cada pessoa precise
mexer com Python/config/planilha, existe uma segunda ferramenta:

```bash
python scripts/build_interactive_var.py   # gera Data/processed/var_interativo_<data>.html
```

Gera um HTML autocontido diferente: embute só o **histórico de
preços/taxas** (mesma aba "Preços", mesmos tickers) — nenhuma posição sua
vai pro arquivo. Quem abrir digita as próprias posições (ticker, tipo,
valor) direto no navegador e todos os números (VaR histórico/paramétrico,
ES, vol, VaR individual por posição, contribuição %, correlação entre
ativos, diversificação, piores dias, stress test) recalculam na hora, em
JavaScript puro — sem Python, sem sessão Bloomberg, sem enviar planilha
nenhuma. As posições digitadas não são salvas em lugar nenhum: ficam só
na aba do navegador enquanto ela estiver aberta.

Como o arquivo não tem como se conectar à Bloomberg depois de gerado, ele
é uma **foto do mercado** presa na data em que rodou — o próprio HTML
mostra isso num banner explícito no topo ("Dados de mercado até
DD/MM/AAAA"). Pra atualizar os preços, rode o script nesse arquivo de novo
e redistribua.

A matemática em JS é uma tradução direta de `riskvar/var_metrics.py`,
`riskvar/pnl_series.py` e `riskvar/stress.py` — qualquer mudança de
fórmula precisa ser replicada nos dois lados e reverificada com:

```bash
python scripts/verify_interactive_var.py   # compara JS (via Playwright) vs Python num dataset sintético
```

## Sizing Tool (`streamlit_app/`)

App **Streamlit** (roda local, não é um arquivo gerado/distribuído como os
relatórios acima) que calcula o tamanho de posição (Notional ou DV01)
ajustado pela volatilidade REALIZADA do ativo: você escolhe um múltiplo de
desvio-padrão pro stop (ex: 1.5σ) em vez de um % fixo arbitrário, informa a
perda máxima aceita em $ e o R/R desejado, e a ferramenta back-calcula o
tamanho, o preço de stop e o preço-alvo. Mostra também a distribuição de
retornos, o preço com as bandas de entrada/stop/alvo, vol realizada por
janela (7D/15D/30D/60D) e vol móvel anualizada.

Lê o histórico de preços do MESMO `config/portfolio_risk.yaml` que
`run_var.py`/`build_interactive_var.py` usam (aba "Preços") — sem sessão
Bloomberg em Python, mesmo motivo de sempre. Se a Bloomberg atualizar a
planilha enquanto o app estiver rodando, use o botão "🔄 Recarregar
preços" (o app cacheia a leitura, não fica relendo o Excel a cada clique).

```bash
pip install -r requirements.txt        # inclui streamlit + plotly agora
streamlit run streamlit_app/sizing_tool.py
```

Abre sozinho no navegador em `http://localhost:8501`. `Ctrl+C` no
terminal pra parar o servidor.

A matemática (vol realizada, distância do stop, tamanho da posição) mora
em `riskvar/sizing.py` -- funções puras, sem nada de Streamlit, testadas
em `tests/test_riskvar/test_sizing.py`. `tests/test_streamlit_app/` testa
o app de verdade (via `streamlit.testing.v1.AppTest`, sem navegador) contra
uma planilha sintética, pra pegar erro de wiring de UI que só aparece
rodando o app.

## Book de FX individual — trend + carry (`fxstrategy/`)

Projeto novo, ainda em construção (só a perna de carry existe por
enquanto): sinais de trend following (G10) e carry (BRL/MXN/ZAR
financiado em USD ou JPY) pra um book individual, com stop por vol como
peça central (reaproveita `riskvar/sizing.py` quando chegar nessa parte).

Mesmo padrão de sempre pra dado: aba **"Preços FX"** do mesmo
`Portfolio.xlsx` que já alimenta o `riskvar` (`config/fx_strategy.yaml` —
copie de `config/fx_strategy.example.yaml`), separada da aba "Preços" de
EM Rates pra não misturar os dois universos nem arriscar mexer no que os
outros scripts já leem. Sem sessão Bloomberg em Python — mesmo mecanismo
`=BDH(...)` no Excel.

**Carry por forward points** (decisão explícita — não por diferencial de
taxa curta, porque forward points embutem prêmio de risco/liquidez que a
taxa pura não capta). Tickers e escalas de cada perna foram confirmados
direto na tela `DES` do terminal Bloomberg (não são uniformes entre
moedas — JPY usa escala ÷100, BRL/MXN/ZAR usam ÷10.000; BRL especificamente
não segue o padrão simples `BRL1M Curncy` por ser NDF, o ticker certo é
`BCN1M`/`BCN3M Curncy`). Fórmula e convenção de sinal em
`fxstrategy/carry.py`:

```
premium(CCY) = (forward_points / escala) / spot * (365 / tenor_dias)   # ≈ r_CCY - r_USD, via paridade de juros coberta
carry(EM financiado em Y) = premium(EM) - premium(Y)                    # Y="USD" é o caso trivial (premium(USD)=0)
```

Testado em `tests/test_fxstrategy/` — inclusive um teste de sinal
(financiar em JPY, que rende menos que USD, dá carry maior que financiar
em USD direto) e um teste que confere o `config/fx_strategy.example.yaml`
contra as escalas/tenores confirmados no terminal, pra pegar deriva se um
lado mudar sem o outro.

```bash
python scripts/run_fx_carry.py   # carry atual (e médio 60d/full) de cada moeda EM x cada moeda de financiamento
```

Gera `Data/processed/fx_carry_<data>.csv` — bom pra conferir rapidamente
que os dados da aba "Preços FX" e a fórmula batem com o esperado antes de
avançar pra sinal/backtest.

**Ainda não implementado**: sinal de trend, backtest, e o sizing/stop do
book (a parte que motivou o projeto todo). Próximos passos, nessa ordem.

## Arquitetura

```
config/
  settings.yaml           caminhos e mapeamento de colunas da planilha
  countries/*.yaml         convenções por país (day count, composição, tipo de pilar, etc.)
src/emrates/
  data/                    Bloomberg (xbbg), leitor da planilha, calendários, snapshot de curvas
  conventions/             day count, composição, geração de schedule, parsing de tenor
  curves/                  bootstrap de curva de desconto (dois estilos, ver abaixo)
  central_banks/           meeting-dated stripping + simulação de cenários de BC
  pricing/                 valuation de swap e decomposição de PnL (carry vs. curve move)
  portfolio/               book de posições, DV01, PnL agregado
  reports/                 formatação dos dois relatórios finais
scripts/                   orquestração (rodar localmente)
tests/                     valida a matemática do engine com casos sintéticos (`pytest`)
```

### Por que dois estilos de curva

- **`zero_rate`** (Brasil DI1, Chile Cámara/SPC, Colômbia IBR): o
  instrumento não tem cupom intermediário — é economicamente uma taxa zero
  até o vencimento. Cada pilar vira um discount factor direto, sem
  bootstrap iterativo.
- **`par_swap`** (México TIIE de Fondeo, África do Sul JIBAR, Polônia
  WIBOR, Rep. Tcheca PRIBOR, Hungria BUBOR): swap com cupom periódico.
  Bootstrap sequencial — cada pilar resolve seu discount factor via uma
  iteração secante contra a estrutura já construída (não é uma fórmula
  fechada de um passo só, porque datas de cupom intermediárias entre dois
  pilares dependem do próprio pilar sendo resolvido).

Qual estilo usar por país é config (`pillar_type` em `config/countries/*.yaml`),
não código.

### Meeting-dated stripping (o "quanto está precificado")

`central_banks/stripper.py` monta os intervalos `[hoje, reunião_1,
reunião_2, ...]`, lê a taxa forward implícita da curva em cada intervalo
e reporta o salto entre níveis consecutivos como os bps precificados para
aquela reunião. Para saber quanto está precificado na ÚLTIMA reunião de
uma lista, inclua também a reunião seguinte na chamada (senão o método não
tem de onde tirar o "nível depois" daquela última reunião).

México usa uma curva à parte só pro relatório de reuniões:
`curves/linear_rate.py` interpola a taxa cotada de cada pilar TIIE
linearmente (sem bootstrap de cupom, sem NSS) — comparado contra a curva
de TIIE real no Bloomberg (Ricardo, 29/07/2026), essa é a versão que mais
se aproxima da referência dele (NSS divergia ~26bps acumulados até
~17 meses à frente, essa versão fica em ~14bps). A curva usada pra
precificar posições/PnL de México continua com bootstrap de cupom, sem
mudança — só o relatório de "quanto está precificado" foi trocado.

Brasil usa leitura direta dos pilares reais + split 65/35 (mesmo método
da Colômbia, `strip_meeting_path_from_pillars`) em vez de NSS desde
03/08/2026: quando o DI1 front-month vence no próprio dia da rodada (algo
que acontece mensalmente — ver o skip de pilar degenerado em
`run_daily_pricing.py`), o pilar real mais próximo fica bem mais longe do
que a próxima reunião do Copom, criando um "gap" largo com só 1 reunião
dentro. Suavização (NSS ou a interpolação cúbica da curva exata) trata
esse gap como transição gradual em vez de concentrar o corte/alta na
própria reunião — comparado contra a calculadora de CDI da Bloomberg
(Ricardo, 03/08/2026), a leitura direta com split chegou bem mais perto
(~22bps vs. os ~25bps da Bloomberg, contra ~6-11bps que a suavização
mostrava).

### Cenários de BC

`central_banks/scenarios.py` recebe choques (em bps) em uma ou mais
reuniões e reconstrói a curva inteira consistente com esse novo caminho —
o choque se propaga de forma persistente a partir da reunião escolhida
(reprecificação de path completo, como combinado). A ponta longa, além do
horizonte de reuniões informado, é carregada junto pelo mesmo fator de
deslocamento cumulativo, preservando o formato original da curva lá na
frente. Qualquer posição pode então ser reprecificada nessa curva
hipotética (`pricing/discounting.py`) para obter o PnL do cenário,
vértice a vértice.

## O que falta confirmar (marcado "VERIFICAR" nos yaml)

A pesquisa dos agentes (fontes: bancos centrais, bolsas, ISDA — ver `sources`
em cada yaml) fechou a maior parte das convenções, mas alguns pontos só dá
para confirmar no terminal Bloomberg ou com a mesa local:
- **Tickers Bloomberg exatos** das famílias de curva OTC (nenhum mnemônico
  de swap OTC — BRSW, MPSW, curva do Chile/Colômbia — foi confirmado em
  fonte pública; DI1 futuro do Brasil é o único 100% confirmado).
- **Frequência de cupom para tenores longos** no Chile (SPC >18m) e
  Colômbia (IBR 1Y+) — pode não ser bullet como os tenores curtos.
- **Day count exato** do JIBAR sul-africano (ACT/365 é o mais citado, mas
  não universal) e se BUBOR/PRIBOR precisam de day count diferente por
  perna (Hungria confirmadamente tem: BUBOR ACT/360, BIRS ACT/365).
- **Polônia é o país de maior risco de mudança de convenção no curto
  prazo**: WIBOR será descontinuado para novos contratos a partir de
  01/01/2027, substituto é POLSTR (não WIRON, como se cogitou antes) —
  mercado de POLSTR OIS ainda imaturo em jul/2026. África do Sul também
  está em transição (JIBAR → ZARONIA, JIBAR cessa definitivamente em
  31/12/2026).

## Limitação conhecida — swaps já em curso

`pricing/discounting.py` valoriza a perna flutuante inteira (de
`start_date` até `maturity_date`) usando a curva de hoje, mesmo quando
`start_date` já passou. Isso é exatamente certo para trades ainda não
iniciados, e é a prática comum de marcação suja para o dia a dia — mas,
para uma posição que já começou a acumular (a maioria do book real),
o correto é separar em (a) acumulação já REALIZADA desde `start_date` até
hoje, usando os fixings históricos reais do índice (CDI/ICP/IBR/TIIE de
Fondeo/JIBAR/WIBOR/PRIBOR/BUBOR), e (b) acumulação futura ainda
implícita na curva. Isso requer puxar histórico do índice via
`bbg_client.history()` e um pequeno motor de acumulação — deixei de fora
deste primeiro corte para não represar a entrega; é o próximo passo mais
importante para a precisão do PnL de posições reais.
