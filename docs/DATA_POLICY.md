# Data Policy (Draft)

## Cel przetwarzania

Przetwarzanie publicznie dostepnych tresci z X w celu:
- analizy merytorycznej tresci edukacyjnych/tradingowych,
- oceny jakosci i spojnosci przekazu,
- budowy ustrukturyzowanego zbioru danych do dalszej analizy badawczej.

## Minimalizacja danych

Zbierane pola (MVP):
- `post_id`, `author_handle`, `published_at`, `url`
- tekst posta
- `hashtags` / etykiety wykryte lub pobrane z posta (jezeli dostepne)
- obrazy powiazane z postem (lub ich referencje)
- metadane przetwarzania (`scraped_at`, `processed_at`)
- kontekst pobrania (`filter_context`: tryb `all`/`filtered`, tagi/frazy)

Nie zbieramy danych prywatnych ani nieautoryzowanych.

## Retencja (propozycja)

1. Dane surowe (`data/raw`) - krotsza retencja, np. 30-180 dni (do ustalenia).
2. Dane przetworzone (`data/processed`) - retencja projektowa.
3. Eksporty (`data/exports`) - wersjonowane/oznaczane data.
4. Obrazy lokalne (`data/raw/images`) - retencja ograniczona i kontrolowana, ze wzgledu na rozmiar i prawa autorskie.

## Provenance

Kazdy rekord powinien zachowac:
- link do zrodla,
- autora,
- timestamp pobrania,
- wersje pipeline'u/modelu.
- hash obrazu (`sha256`) oraz lokalizacje pliku (jesli pobrano)
