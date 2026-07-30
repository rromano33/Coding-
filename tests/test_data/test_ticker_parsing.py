from datetime import date

from emrates.data.calendars import Calendar
from emrates.data.ticker_parsing import brazil_di1_label, brazil_di1_maturity


def test_brazil_di1_label_known_examples():
    assert brazil_di1_label(date(2027, 1, 4)) == "DIF27"
    assert brazil_di1_label(date(2028, 7, 3)) == "DIN28"
    assert brazil_di1_label(date(2026, 12, 1)) == "DIZ26"


def test_brazil_di1_label_round_trips_with_maturity_for_every_month():
    """brazil_di1_label deve reconstruir o mesmo código do ticker original a
    partir do vencimento resolvido por brazil_di1_maturity (Ricardo,
    29/07/2026: quer o código do DI1 -- tipo DIF27 -- ao lado do vencimento
    na tabela de impacto por vértice)."""
    calendar = Calendar("brazil", holidays=set())
    for letter_year in ["F27", "G27", "H27", "J27", "K27", "M27", "N28", "Q28", "U28", "V28", "X28", "Z26"]:
        ticker = f"OD{letter_year} Comdty"
        maturity = brazil_di1_maturity(ticker, calendar)
        assert brazil_di1_label(maturity) == f"DI{letter_year}"
