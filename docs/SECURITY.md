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

## Dostep

1. Ogranicz dostep do danych surowych.
2. Rozdziel srodowiska (dev / prod) jesli projekt urosnie.
3. Backupuj tylko dane potrzebne i bez sekretow.
