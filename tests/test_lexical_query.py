from recallhq.retrieval.service import lexical_query


def test_lexical_query_drops_stopwords_and_ors_terms():
    assert lexical_query("Which command fixed the local 28P01 Postgres failure?") == "command | fixed | local | 28p01 | postgres | failure"


def test_lexical_query_strips_tsquery_syntax_and_dedupes():
    assert lexical_query("deploy & deploy | !rollback (prod):*") == "deploy | rollback | prod"


def test_lexical_query_returns_none_without_content_words():
    assert lexical_query("what is it?") is None
