# Taxonomy (Draft v0)

## Topic Labels

1. `ICT / Core Concepts`
2. `ICT / Model 2022`
3. `ICT / Full Mentoring 2026`
4. `Liquidity / SSL-BSL`
5. `Market Structure`
6. `PD Arrays / FVG / OB`
7. `Session Models / Killzones`
8. `Risk Management`
9. `Trade Examples / Recaps`
10. `Promo / Funnel / Group Selling`

## Additional Dimensions

1. `intent`: `education`, `promotion`, `analysis`, `results`, `mixed`
2. `quality_score`: skala robocza do recznej oceny
3. `review_status`: `pending`, `approved`, `rejected`, `needs_split`
4. `selection_rule`: zapis reguly selektywnego pobrania (np. `tags:[ICT,MENTORSHIP]`, `query:\"LECTURE #1\"`)

## Przyklady fraz selektywnych (operacyjne)

1. `ICT 2026 Mentorship`
2. `LECTURE #x`
3. `Full Mentorship 2026`

## Mapowanie operacyjne (v1)

1. `ICT 2026 Mentorship` -> `label: ICT Full Mentoring 2026`, `series: ICT 2026 Mentorship`
2. `LECTURE #12` -> `label: ICT Full Mentoring 2026`, `series: ICT 2026 Mentorship`, `module: Lecture #12`

## Relacja do biblioteki wiedzy (TRADING_WORD)

Taxonomia w tym repo nie jest jeszcze kanonem wiedzy.
Aktualnie sluzy do:
1. wstepnego tagowania / klasyfikacji roboczej,
2. podpowiedzi `curation_hints.suggested_focus`,
3. organizacji materialu do dalszej kuracji w `knowledge_library_ready.jsonl`.

Decyzje kanoniczne (definicje, relacje, warianty) powinny byc podejmowane na etapie kuracji biblioteki wiedzy, a nie przez sam extractor.
