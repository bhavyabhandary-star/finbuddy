"""Typographic normalisation of model output (see rag_service/llm_client.py)."""

from rag_service.llm_client import normalise_typography


def test_percent_with_narrow_no_break_space_is_attached():
    assert normalise_typography("cap at 5 % of the pool") == "cap at 5% of the pool"


def test_percent_with_plain_and_no_break_space_is_attached():
    assert normalise_typography("5 % and 12 %") == "5% and 12%"


def test_other_typographic_spaces_become_plain_spaces():
    assert normalise_typography("a b c") == "a b c"


def test_text_without_figures_is_unchanged():
    assert normalise_typography("Consent must be free and specific.") == "Consent must be free and specific."


def test_percent_not_preceded_by_a_digit_is_unchanged():
    assert normalise_typography("a % sign") == "a % sign"


def test_none_passes_through():
    assert normalise_typography(None) is None
