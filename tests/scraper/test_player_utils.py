from backend.scraper.player_utils import (
    extract_player_id,
    extract_player_slug,
    generate_player_slug,
    slug_for_player,
)


def test_generate_player_slug_ascii_folds_accents():
    assert generate_player_slug("Alexander Zverev") == "alexander-zverev"
    assert generate_player_slug("Müller") == "muller"
    assert generate_player_slug("João Sousa") == "joao-sousa"


def test_extract_player_id_and_slug_from_href():
    href = "https://www.atptour.com/en/players/novak-djokovic/d643/overview"
    assert extract_player_id(href) == "d643"
    assert extract_player_slug(href) == "novak-djokovic"
    assert extract_player_id(None) is None
    assert extract_player_slug(["not", "a", "string"]) is None


def test_slug_for_player_prefers_href_then_stored():
    href = "https://www.atptour.com/en/players/jannik-sinner/s0ag/overview"
    assert slug_for_player("Ignored Name", href=href) == "jannik-sinner"
    assert (
        slug_for_player("Carlos Alcaraz", stored_slug="carlos-alcaraz")
        == "carlos-alcaraz"
    )
    assert slug_for_player("Test Player") == "test-player"
