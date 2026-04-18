from utils.chemistry_rules import apply_chemistry_rules


def test_subscripts():
    assert apply_chemistry_rules("H2O") == "H_{2}O"


def test_superscripts():
    assert apply_chemistry_rules("SO4^2-") == "SO_{4}^{2-}"


def test_reaction_arrow():
    assert apply_chemistry_rules("H2 + O2 -> H2O") == "H_{2} + O_{2} \\rightarrow H_{2}O"


def test_states():
    assert apply_chemistry_rules("H2O(l)") == "H_{2}O_{(l)}"
