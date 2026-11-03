import pytest

from emporio_agent.retrieval.policy_search import PolicySearch, tokenize


@pytest.fixture(scope="module")
def ps():
    return PolicySearch()


def test_chunks_follow_manual_structure(ps):
    sections = [c.section for c in ps.chunks]
    assert len(sections) == len(set(sections))            # no duplicated sections
    assert {"2", "3.1", "4.1", "5.2", "8.1", "9"} <= set(sections)
    assert all(c.text for c in ps.chunks)                 # no empty chunks


def test_numbered_list_items_are_not_sections(ps):
    # Section 7.2 contains a list "1. Saudação ... 5. Fechamento": must stay inside 7.2.
    c72 = next(c for c in ps.chunks if c.section == "7.2")
    assert "Fechamento" in c72.text


def test_tokenize_ignores_accents_and_stems():
    assert tokenize("Devolução") == tokenize("devolver")


@pytest.mark.parametrize(
    "query, expected",
    [
        ("posso devolver um produto? em quantos dias", "4.1"),
        ("qual o horário de funcionamento no sábado", "2"),
        ("como funciona o rastreamento do pedido", "5.3"),
        ("quantos dias de garantia legal", "8.1"),
        ("quero excluir meus dados", "9"),
        ("quais itens não podem ser trocados", "4.4"),
    ],
)
def test_top_hit(ps, query, expected):
    assert ps.search(query, top_k=1)[0].section == expected


def test_gibberish_returns_nothing(ps):
    assert ps.search("zzzz qwerty") == []


def test_shipping_question_retrieves_both_shipping_rules(ps):
    # BM25 is lexical: it cannot know Dourados is outside Campo Grande.
    # That decision belongs to rules/shipping.py; retrieval just returns both sections.
    hits = {h.section for h in ps.search("quanto é o frete para Dourados", top_k=2)}
    assert hits == {"5.1", "5.2"}


def test_installment_question_matches_payment_rules(ps):
    hits = {h.section for h in ps.search("posso pagar em 10x?", top_k=2)}
    assert hits & {"3", "3.1"}


def test_comprehensive_return_question_returns_both_modalities():
    sections = {
        hit.section
        for hit in PolicySearch().search(
            "troca devolução arrependimento defeito garantia prazo", top_k=3
        )
    }
    assert {"4.1", "4.2"} <= sections