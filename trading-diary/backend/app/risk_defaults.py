"""Valores default de risco, usados para popular a conta na primeira vez que
o usuário acessa /risk-settings. Espelham o framework de risco de referência
(planilha "Framework de Risco — Parâmetros do Book"); tudo é editável depois."""

DEFAULT_SETTINGS = {
    "capital_alocado": 250_000_000.0,
    "budget_anual_pnl": 25_000_000.0,
    "sharpe_meta": 1.20,
    "stop_loss_anual": 12_500_000.0,
    "stop_loss_mensal": 6_250_000.0,
    "stop_loss_diario": 1_750_000.0,
    "risco_max_tese": 5_000_000.0,
    "risco_max_classe": 7_500_000.0,
    "max_trades_simultaneos": 5,
    "max_teses_simultaneas": 3,
}

DEFAULT_BEHAVIORAL_RULES = [
    "Toda posição deve ter STOP, TARGET e CATALISADOR escritos ANTES de entrar.",
    "Sizing é função de (Risco por trade) + (distância até stop). Não é 'feeling'.",
    "Não realizo lucro antes do target a menos que a TESE tenha mudado (não o preço).",
    "Não movo stop contra a posição. Posso reduzir, nunca afrouxar.",
    "Se atingir stop diário, encerro o dia. Sem 'recuperar'.",
    "Toda violação de regra é registrada no Journal com motivo. Sem exceção.",
    "Revisão semanal de 30min toda sexta: processo > resultado.",
]

DEFAULT_CONVICTION_TIERS = [
    {"label": "baixa", "pct_of_stop_anual": 0.05, "notes": "Tese nova, pouca evidência. Sizing pequeno para testar.", "order_index": 0},
    {"label": "media", "pct_of_stop_anual": 0.10, "notes": "Tese clara mas sem catalisador iminente.", "order_index": 1},
    {"label": "alta", "pct_of_stop_anual": 0.20, "notes": "Tese clara + catalisador definido + assimetria favorável.", "order_index": 2},
    {"label": "extrema", "pct_of_stop_anual": 0.30, "notes": "Convicção máxima. Documentar justificativa.", "order_index": 3},
]

DEFAULT_STOP_LAYERS = [
    {
        "level": "diario",
        "alerta_amarelo": 1_750_000.0,
        "stop_duro": 3_500_000.0,
        "motivo": "Um único dia ruim não pode comprometer o mês.",
        "order_index": 0,
    },
    {
        "level": "mensal",
        "alerta_amarelo": 3_000_000.0,
        "stop_duro": 6_500_000.0,
        "motivo": "-R$3M no mês reduz risco em 30%. -R$5M reduz 50%. -R$6,5M fecha o mês.",
        "order_index": 1,
    },
]

DEFAULT_DRAWDOWN_PHASES = [
    {"pnl_min": 0.0, "pnl_max": 15_000_000.0, "drawdown_max_pct": 0.35, "floor_minimo": 4_000_000.0, "order_index": 0},
    {"pnl_min": 15_000_000.0, "pnl_max": 35_000_000.0, "drawdown_max_pct": 0.30, "floor_minimo": 5_000_000.0, "order_index": 1},
    {"pnl_min": 35_000_000.0, "pnl_max": None, "drawdown_max_pct": 0.20, "floor_minimo": 6_500_000.0, "order_index": 2},
]

DEFAULT_SEASONAL_POSTURES = [
    {"periodo": "Jan–Jun", "situacao_pnl": "Qualquer", "postura": "Full risk budget", "order_index": 0},
    {"periodo": "Jul–Set", "situacao_pnl": "Abaixo de 40% da meta", "postura": "Manter risco, buscar recuperação", "order_index": 1},
    {"periodo": "Jul–Set", "situacao_pnl": "Acima de 60% da meta", "postura": "Reduz novo risco 20%, protege drawdown", "order_index": 2},
    {"periodo": "Out–Nov", "situacao_pnl": "Acima de 80% da meta", "postura": "Modo defensivo, só alta convicção", "order_index": 3},
    {"periodo": "Dezembro", "situacao_pnl": "Qualquer", "postura": "Gestão do aberto, sem risco novo relevante", "order_index": 4},
]
