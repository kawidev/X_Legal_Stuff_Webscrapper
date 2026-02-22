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
- provenance i metadane walidacyjne (`provenance_index`, QA metrics, gate decision)

Nie zbieramy danych prywatnych ani nieautoryzowanych.

## Retencja (propozycja)

1. Dane surowe (`data/raw`) - krotsza retencja, np. 30-180 dni (do ustalenia).
2. Dane przetworzone (`data/processed`) - retencja projektowa.
   - obejmuje m.in. `knowledge_extract`, `knowledge_extract_canonical`, QA/gate reports oraz `knowledge_library_ready/rejects`
3. Eksporty (`data/exports`) - wersjonowane/oznaczane data.
4. Obrazy lokalne (`data/raw/images`) - retencja ograniczona i kontrolowana, ze wzgledu na rozmiar i prawa autorskie.

## Provenance

Kazdy rekord powinien zachowac:
- link do zrodla,
- autora,
- timestamp pobrania,
- wersje pipeline'u/modelu.
- status walidacji (`qa-knowledge`) i decyzje gate (jezeli rekord trafil do ingestu biblioteki wiedzy)
- hash obrazu (`sha256`) oraz lokalizacje pliku (jesli pobrano)

## Kontrola jakosci danych (operacyjnie)

Przed zasileniem biblioteki wiedzy rekomendowany przeplyw:
1. `qa-knowledge`
2. `gate-knowledge-export` (z polityka `strict|balanced|permissive`)
3. `export-knowledge-library`

Artefakty kontrolne:
- `knowledge_qa_report.json`
- `knowledge_export_gate_report.json`
- `knowledge_library_ready.jsonl`
- `knowledge_library_rejects.jsonl`
