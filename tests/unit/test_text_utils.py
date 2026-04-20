"""Text cleaning and splitting utilities."""

from __future__ import annotations

import pytest

from ianuacare.ai.text import clean_text, split_sentences, split_words


class TestCleanText:
    def test_collapses_whitespace(self) -> None:
        assert clean_text("ciao\tmondo\n\ntest  ") == "ciao mondo test"

    def test_strips_edges(self) -> None:
        assert clean_text("   hello   ") == "hello"

    def test_normalizes_unicode_nfkc(self) -> None:
        # Full-width digit "１" is NFKC-normalized to ASCII "1".
        assert clean_text("caff\u00e8 \uff11") == "caff\u00e8 1"

    def test_lowercase_flag(self) -> None:
        assert clean_text("Ciao Mondo", lowercase=True) == "ciao mondo"

    def test_empty_string(self) -> None:
        assert clean_text("") == ""

    def test_whitespace_only(self) -> None:
        assert clean_text("   \n\t  ") == ""

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            clean_text(123)  # type: ignore[arg-type]


class TestSplitSentences:
    def test_basic_split(self) -> None:
        assert split_sentences("Prima frase. Seconda frase! Terza?") == [
            "Prima frase.",
            "Seconda frase!",
            "Terza?",
        ]

    def test_protects_italian_abbreviations(self) -> None:
        result = split_sentences("Il Dr. Rossi visita. Il Sig. Bianchi attende.")
        assert result == [
            "Il Dr. Rossi visita.",
            "Il Sig. Bianchi attende.",
        ]

    def test_protects_multi_dot_abbreviation(self) -> None:
        result = split_sentences("La S.p.A. ha chiuso. Nuova sede aperta.")
        assert result == [
            "La S.p.A. ha chiuso.",
            "Nuova sede aperta.",
        ]

    def test_protects_dott_ssa(self) -> None:
        result = split_sentences("La Dott.ssa Verdi opera. Paziente stabile.")
        assert result == [
            "La Dott.ssa Verdi opera.",
            "Paziente stabile.",
        ]

    def test_empty_returns_empty_list(self) -> None:
        assert split_sentences("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert split_sentences("   \n\t ") == []

    def test_single_sentence_without_terminator(self) -> None:
        assert split_sentences("una sola frase senza punto") == [
            "una sola frase senza punto"
        ]

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            split_sentences(42)  # type: ignore[arg-type]


class TestSplitWords:
    def test_basic_split(self) -> None:
        assert split_words("Ciao mondo, come va?") == ["Ciao", "mondo", "come", "va"]

    def test_unicode_aware(self) -> None:
        assert split_words("caff\u00e8 per\u00f2 citt\u00e0") == [
            "caff\u00e8",
            "per\u00f2",
            "citt\u00e0",
        ]

    def test_numbers_included(self) -> None:
        assert split_words("codice 12345 paziente") == ["codice", "12345", "paziente"]

    def test_underscore_included(self) -> None:
        assert split_words("field_one field_two") == ["field_one", "field_two"]

    def test_punctuation_excluded(self) -> None:
        assert split_words("ciao! come-va? (bene)") == ["ciao", "come", "va", "bene"]

    def test_empty_returns_empty_list(self) -> None:
        assert split_words("") == []

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            split_words(None)  # type: ignore[arg-type]
