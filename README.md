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
python scripts/run_daily_pricing.py   # gera Data/processed/priced_bc_<país>_<data>.csv e salva a curva do dia
python scripts/run_pnl.py             # compara com a curva do dia anterior salva, gera Data/processed/pnl_<data>.csv
```

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
