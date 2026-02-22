# Security Notes

## Sekrety i klucze

1. Klucze API przechowuj tylko w `.env`.
2. Nigdy nie commituj `.env`, tokenow, cookies, sesji.
3. Rotuj klucze po incydencie lub podejrzeniu wycieku.

## Logi

1. Nie zapisuj sekretow w logach.
2. Maskuj tokeny i naglowki autoryzacyjne.
3. Ogranicz logowanie payloadow zewnetrznych API.
4. Nie zapisuj pelnych obrazow w logach/debug dumpach.
5. Traktuj `knowledge_library_rejects.jsonl` i QA/gate reports jako dane operacyjne (mogą zawierac fragmenty tresci / provenance excerpts).

## Dostep

1. Ogranicz dostep do danych surowych.
2. Rozdziel srodowiska (dev / prod) jesli projekt urosnie.
3. Backupuj tylko dane potrzebne i bez sekretow.

## Polityki i konfiguracja gate

1. Profile polityk (`policies/*.json`) nie powinny zawierac sekretow.
2. Zmiany progow/severity policy dokumentuj (kto/co/kiedy/dlaczego), bo wpływaja na jakosc ingestu do biblioteki wiedzy.
3. Przy testach "strict" / "permissive" nie nadpisuj bezrefleksyjnie wynikow produkcyjnych runu (trzymaj osobny `DATA_DIR` albo zapis raportow porownawczych).
