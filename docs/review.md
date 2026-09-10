# Review templatki FastAPI

Stan wyjściowy: `master` (`db63eb1`) oraz otwarty PR #1. Cel: mała templatka
feature-based z warstwami routes → services → repository, Pythonem 3.14 i niską
złożonością kodu. PR #1 zachowano i rozwinięto; jego kierunek był poprawny, ale
sam nie domykał architektury ani części przypadków brzegowych.

## Co było dobrze zrobione

- **Cienkie route'y i małe serwisy use case'ów.** Przepływ jest jawny, bez kontenera
  DI i rozbudowanej hierarchii klas. Zachowano ten styl.
- **Repozytoria bez commitów.** Własność transakcji jest czytelna: use case HTTP
  kończy transakcję, a worker korzysta z jednego session scope. Testy savepointów
  pozwalają sprawdzać prawdziwy commit/rollback.
- **Zależności ładujące zasoby.** `ValidItem` usuwa powtarzające się fetch/404 i
  korzysta z cache zależności FastAPI w ramach requestu.
- **Async SQLAlchemy, psycopg, migracje i realny PostgreSQL w testach.** To dobra
  baza do projektów korzystających z relacyjnej bazy danych.
- **UUIDv7, timestampy ze strefą, naming conventions i check constraints.** Spójne
  podstawy modelowania bez własnego frameworka persistence.
- **Jawny kontrakt błędów i test rejestru kluczy.** Stabilne klucze i18n mogą zostać,
  jeżeli projekty używają wspólnego klienta/frontendowego tłumaczenia komunikatów.
- **Cykl życia workerów.** Stała pętla async na proces, late ACK i prefetch=1 są
  wartościowe, kiedy projekt rzeczywiście potrzebuje Celery.

## Wykryte problemy i wdrożone poprawki

| Priorytet | Problem | Zmiana |
|---|---|---|
| P1 | Limit body sprawdzał tylko Content-Length; chunked omijał limit, a niepoprawny nagłówek powodował 500. | Liczenie odebranych bajtów oraz odpowiedzi 400/413; testy chunked, błędnego nagłówka i wartości granicznej. |
| P1 | Globalny handler 500 działał poza dodanymi middleware. Błędy traciły CORS, security headers i request ID. | Zewnętrzne wrappery ASGI otaczają cały FastAPI; test rzeczywistego błędu endpointu sprawdza nagłówki. |
| P1 | Synchroniczne publikowanie Celery z `async def` blokowało pętlę API. | Endpoint enqueue jest synchroniczny, więc FastAPI uruchamia go w thread poolu. |
| P1 | Klient Bedrock był tworzony podczas importu modułu agenta, mimo deklarowanej inicjalizacji po fork. | Agent i provider powstają w cache'owanej fabryce przy pierwszym użyciu; import nie wymaga AWS. |
| P2 | Window count zwracał zero na stronie poza zakresem. Sortowanie po samym created_at nie ustalało kolejności remisów. | Osobny COUNT i sortowanie created_at + id. Pusta strona zachowuje total_count/total_pages. |
| P2 | Feature był rozdzielony między features i centralne repositories; repozytoria zawierały również zależności HTTP. | Model, repository, dependencies, schemas, routes i services są w jednym katalogu feature'a. |
| P2 | Serwisy używały FastAPI-owego AsyncDb, a serializer walidował model Pydantic, robił dict i oddawał go do ponownej walidacji. | Konstruktor przyjmuje AsyncSession, serwisy zwracają encje/TypedDict, Pydantic serializuje na granicy HTTP. |
| P2 | Testy budowały schema przez create_all, więc nie sprawdzały migracji. Modele nie deklarowały serwerowych defaultów obecnych w migracji. | Testy używają Alembica; modele/defaulty są zgodne, CI sprawdza drift i pełny upgrade/downgrade. |
| P2 | Alembic czytał URL inaczej niż aplikacja, a kod SET search_path wymagał ręcznego domykania transakcji. | Jeden odczyt settings env/.env, poprawne escapowanie %, transakcję migracji prowadzi Alembic. |
| P2 | Testy i fixture'y mogły korzystać z różnych pętli przy wspólnej puli async. | Jeden session loop dla obu. |
| P2 | Ustawienia nadpisywały jawne wartości, miały przykładowe domeny produkcyjne i arbitralnie większe pule na produkcji. | Proste, jawne defaulty; puste CORS i zero overflow są zachowane; ENVIRONMENT jest walidowane. |
| P2 | Wyłączenie dokumentacji pozostawiało endpoint OpenAPI. | Wspólne SHOW_DOCS steruje docs, redoc i openapi.json. |
| P2 | Każda replika API uruchamiała migracje w entrypoincie, a worker mógł wystartować przed nimi. | Osobna usługa migrate; API i worker czekają na jej zakończenie. |
| P2 | Kod aplikacji nie zamykał puli DB przy shutdown. Child disposował odziedziczone połączenia z close=True. | Cleanup w lifespan i dispose(close=False) przy inicjalizacji childa. |
| P3 | Pusta po trimowaniu nazwa przechodziła walidację. | Normalizacja przed sprawdzeniem długości. |
| P3 | Soft timeout z globalnej konfiguracji przewyższał hard timeout krótszych tasków. | Jawne soft limity poniżej hard limitów. |

## Co uproszczono lub usunięto

- Python **3.14** we wszystkich środowiskach; `uuid.uuid7()` zastępuje `uuid-utils`
  i wrapper. Zaktualizowano zależności binarne niezgodne ze starym lockiem na 3.14.
- **Celery/Redis oraz AI są extras.** Core uruchamia publiczne CRUD bez brokera i AWS.
  Instalacja `ai` dodaje przykład endpointu AI; `workers` wystarcza do zadań bez LLM.
- Jednomodułowy router nie potrzebuje osobnego katalogu. Usunięto pośredni serializer
  oraz nieużywany mechanizm wyliczania FK w factory.
- Zachowano z PR #1 usunięcie `fastapi-guard`, scalenie modułów DB i nazwę `enqueue.py`.
  Małe middleware obsługują potrzebne funkcje; polityki rate limiting/WAF konfiguruje ingress.
- Usunięto hipotetyczne wyjątki dużych uploadów oraz niestandardowe nazwy kluczy AWS.
- Skrócono i ujednolicono instrukcje kodowania. Nie ma obowiązku rozbijania prostych
  operacji na prywatną metodę dla każdego kroku ani trzymania indeksów poza metadata.

## Czytelność i complexipy

PR #1 wprowadził właściwe narzędzie: **complexipy**, limit **10 na funkcję**, wspólny
dla `app`, `tests` i `alembic`, uruchamiany lokalnie oraz w CI. Zachowano tę bramkę
oraz Ruff i Pyright. Najwyższy wynik po zmianach: **7**.

Wynik traktujemy jako ograniczenie zagnieżdżeń i rozgałęzień. Osobne klasy/funkcje
nie poprawiają czytelności automatycznie; nie warto rozdrabniać sekwencyjnego
trzywierszowego use case'a wyłącznie dla struktury. Typowane wyniki i jawne
transakcje pomagają bardziej niż kolejna warstwa abstrakcji.

## Czego świadomie nie dodano

Auth/RBAC, generic CRUD, kontenera DI, rozbudowanego Unit of Work, cache, outboxa,
metryk i gotowych workflowów deploymentu. Ich wymagania zależą od projektu;
nie powinny być obowiązkowe w podstawowej templatce.

Przykład AI zabezpiecza przed ponownym przetworzeniem już zapisanej odpowiedzi,
nie przed równoczesnymi wywołaniami ani awarią między wywołaniem modelu i commitem.
Prawdziwe exactly-once dla zewnętrznego efektu wymaga dodatkowych gwarancji.
Osobny COUNT i lista przy READ COMMITTED mogą zobaczyć równoczesne zmiany; API nie
obiecuje snapshotu. `/up` sprawdza proces, nie gotowość wszystkich zależności.
Te ograniczenia są jawne w README, bez dokładania niepotrzebnej infrastruktury.

## Dodatkowy przegląd: Alembic, Ruff i Celery

Po scaleniu PR #1 sprawdzono konfigurację tych trzech narzędzi na jego aktualnym
stanie (`6db783a`). Wnioski i poprawki:

| Obszar | Ocena i zmiana |
|---|---|
| Alembic: nazwy | Format był spójny: `YYYY_MM_DD_HHMM-<revision>_<slug>.py`. Dodano UTC, żeby nazwa nie zależała od strefy autora, oraz `alembic[tz]` dla przenośnego dostępu do stref. Kolejność migracji nadal określa `down_revision`. |
| Alembic: schema | Modele już używały `public`, ale tabela wersji zależała od domyślnego schematu połączenia. Jawne `version_table_schema="public"` działa teraz online i offline. |
| Alembic: autogenerate | Samo `include_schemas=True` mogło proponować usunięcie cudzych tabel. Filtr ogranicza introspekcję do `public` i tabel z rejestru modeli, uwzględniając alias domyślnego schematu także przy zmienionym `search_path`. |
| Alembic: narzędzia i constraints | Ruff uruchamia się przez aktywnego Pythona zamiast ścieżki `.venv/bin/ruff`. Pusta migracja przechodzi lint. Nazwy indeksów, unique i FK uwzględniają wszystkie kolumny; dwa indeksy z tą samą pierwszą kolumną nie kolidują. Obecne nazwy jednokolumnowe się nie zmieniają. |
| Ruff | Dotychczasowy zestaw dobrze pokrywał podstawy, async i uproszczenia. Dodano `S`, `DTZ`, `T10`, `PT`, `PIE`, `RET`: wzorce bezpieczeństwa, czas, debugger, pytest i redundantny kod. Usunięto globalne wyłączenie `B008`; znane markery FastAPI mają wąski wyjątek. `S101` jest wyłączone tylko w testach, a `N818` tylko w module wyjątków. |
| Celery: routing | Domyślna kolejka Celery nazywała się `celery`, podczas gdy worker konsumuje `default,heavy`. Zadania bez jawnej kolejki trafiają teraz do `default`; obie kolejki są zadeklarowane, a literówki odrzucane przed publikacją. |
| Celery: trwałość | Sam wolumen Redisa i persistent delivery nie wystarczały do trwałego zapisu ostatnich wiadomości. Compose włącza AOF, `appendfsync always` i `noeviction`. Beat ma osobny wolumen na harmonogram i synchronizację po każdym wysłaniu. |
| Celery: awarie i zamykanie | Zachowano late ACK, reject-on-worker-lost i prefetch=1. Dodano anulowanie niezakończonych zadań przy utracie połączenia oraz jawny, skończony budżet retry producenta. Worker ponawia połączenia bez limitu. Compose uruchamia Celery bez wrappera reload, przekazuje SIGTERM i daje 11 minut na zakończenie pracy. |
| Celery: timeouty | Visibility timeout jest konfigurowalny i walidowany względem globalnego hard limitu. Limity, concurrency i liczba zadań na proces mają walidację dodatnich wartości. Zwykłe błędy/time-outy są ACK-owane; retry błędów przejściowych pozostaje decyzją konkretnego zadania. |

Filtrowanie tabel to celowy kompromis bezpieczeństwa: **usunięcie modelu wymaga
ręcznie napisanej, sprawdzonej migracji `drop_table`**. Alembic nadal może proponować
destrukcyjne zmiany kolumn w zarządzanych tabelach, więc wynik autogenerate wymaga
review. Nie zmieniano istniejącej migracji ani schematu danych aplikacji.
[Dokumentacja filtrowania Alembica](https://alembic.sqlalchemy.org/en/latest/autogenerate.html#omitting-table-names-from-the-autogenerate-process).

Ruff nie zastępuje kontroli typów ani złożoności. Pozostają Pyright i complexipy
z limitem 10; dodawanie `ALL` lub drugiej bramki złożoności nie jest potrzebne.
Reguły dobrano z [katalogu Ruff](https://docs.astral.sh/ruff/rules/), a wyjątki dla
markerów FastAPI korzystają z [konfiguracji B008](https://docs.astral.sh/ruff/settings/#lint_flake8-bugbear_extend-immutable-calls).

**Granice niezawodności:** pojedynczy Redis nie daje HA ani ochrony przed utratą
dysku/węzła. Fsync każdego zapisu kosztuje throughput. Przy wdrażaniu tej zmiany
na istniejącym wolumenie RDB trzeba zrobić backup i włączyć AOF online, poczekać
na zakończenie przepisywania, dopiero potem restartować z nową konfiguracją;
samo przełączenie konfiguracji przy restarcie może utracić stare dane.
[Redis: persistence i przejście na AOF](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

Zadania muszą tolerować ponowne wykonanie, a `max_retries` samo nie włącza retry.
Nie ma exactly-once, atomowego commitu DB + publikacji ani gwarancji nadrobienia
przegapionych uruchomień beat. Visibility timeout musi obejmować także hard limity
nadpisane w dekoratorach oraz czas ETA/countdown; walidator zna tylko limit globalny.
Po utracie całego workera redelivery może czekać do końca visibility timeout.
[Celery: Redis i visibility timeout](https://docs.celeryq.dev/en/v5.6.0/getting-started/backends-and-brokers/redis.html),
[Celery: przerwanie zadania przy utracie połączenia](https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-cancel-long-running-tasks-on-connection-loss).

Weryfikacja dodatkowego przeglądu:

- **59 testów** w wariancie AI, w tym generowanie rzeczywistej migracji z UTC i lintem,
  SQL offline, izolacja obcych tabel przy innym `search_path`, indeksy złożone,
  walidacja timeoutu oraz publikacja/routing przez transport pamięciowy Kombu.
- Ruff, Pyright i complexipy przechodzą; najwyższa złożoność nadal **7**.
- Zbudowano obraz workers bez narzędzi dev; użytkownik non-root może zapisać harmonogram beat.
- W osobnym testowym Redisie wiadomość Celery przetrwała **SIGKILL i restart brokera**.
- W osobnym kontenerze workera zabito pierwszy proces prefork podczas zadania;
  to samo zadanie zostało dostarczone ponownie i zakończyło się w drugiej próbie.
  To test awarii procesów, bez symulowania awarii dysku lub całego hosta.

## Weryfikacja pierwotnego przeglądu (PR #1)

- Python 3.14.7 i PostgreSQL 18: pełny wariant AI **51 testów**, bez wywołań modelu.
- Osobne czyste instalacje core i workers oraz testy importu runtime bez dev dependencies.
- Ruff format/check, Pyright, complexipy oraz zgodność locka.
- Alembic upgrade/check/downgrade/upgrade i brak różnic metadata względem migracji.
- Budowanie obrazów Docker i walidacja konfiguracji Compose.
- CI wykonuje kontrole w macierzy core/workers/ai na Pythonie 3.14.

Nie testowano rzeczywistego wywołania Bedrock ani wysyłania telemetry do Sentry;
nie są potrzebne do sprawdzenia podstawowej templatki.

## Źródła decyzji dotyczących bibliotek

- [Python 3.14: uuid.uuid7](https://docs.python.org/3.14/library/uuid.html#uuid.uuid7).
- [Complexipy: próg i konfiguracja](https://github.com/rohaquinlop/complexipy/blob/main/README.md).
- [Starlette: CORS Global Enforcement](https://starlette.dev/middleware/#corsmiddleware-global-enforcement).
- [SQLAlchemy: async i wiele pętli zdarzeń](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops).
