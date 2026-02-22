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
- obrazy powiazane z postem (lub ich referencje)
- metadane przetwarzania (`scraped_at`, `processed_at`)

Nie zbieramy danych prywatnych ani nieautoryzowanych.

## Retencja (propozycja)

1. Dane surowe (`data/raw`) - krotsza retencja, np. 30-180 dni (do ustalenia).
2. Dane przetworzone (`data/processed`) - retencja projektowa.
3. Eksporty (`data/exports`) - wersjonowane/oznaczane data.

## Provenance

Kazdy rekord powinien zachowac:
- link do zrodla,
- autora,
- timestamp pobrania,
- wersje pipeline'u/modelu.
