# EduVulcan2.0 — elektroniczny dziennik demonstracyjny

> Aplikacja edukacyjna Flask + MySQL uruchamiana w Docker Compose. **Projekt demonstracyjny**, nie system do obsługi rzeczywistych danych szkoły.

## 1. O projekcie

EduVulcan2.0 to przeglądarkowy dziennik elektroniczny z trzema rolami: administrator, nauczyciel i uczeń. Zawiera zarządzanie uczniami i przedmiotami, oceny, opisy i kategorie ocen, frekwencję oraz wewnętrzną pocztę z załącznikami. Moduł planów lekcji jest przygotowany w repozytorium; jego użycie wymaga wykonania migracji `init_timetables.py` na danym serwerze.

**Repozytorium:** https://github.com/marcinioza/EduVulcan2.0

## 2. Dlaczego właśnie te technologie?

| Element | Uzasadnienie |
|---|---|
| **Python 3.13** | Czytelny kod backendu, szeroki ekosystem bibliotek. |
| **Flask** | Lekki framework HTTP; prostszy punkt startowy niż rozbudowany Django, możliwość samodzielnego wyboru komponentów. |
| **Jinja2 + HTML/CSS** | Renderowanie stron na serwerze bez konieczności tworzenia oddzielnej aplikacji SPA/API. |
| **MySQL 8.4** | Relacyjna struktura danych oraz trwały serwer bazy; powiązania uczniów, ocen, przedmiotów i kont. |
| **Flask-SQLAlchemy** | ORM mapuje klasy Pythona na tabele i obsługuje relacje. |
| **Flask-Login** | Zarządzanie sesją zalogowanego użytkownika. |
| **Flask-WTF/CSRFProtect** | Zabezpieczenie formularzy przed CSRF. |
| **Docker + Compose** | Powtarzalne uruchamianie dwóch niezależnych usług i ich konfiguracji. |
| **Git/GitHub + Actions** | Historia zmian, PR-y, automatyczne uruchamianie testów. |

## 3. Architektura

```text
Przeglądarka użytkownika
          |
          | żądania HTTP(S) przez dostępny adres serwera
          v
Serwer Linux: port 10114
          |
          v
Kontener WEB: Flask (port 5000)
          |
          | sieć wewnętrzna Compose; host `db`, port 3306
          v
Kontener DB: MySQL 8.4
          |
          v
Wolumen Docker `mysql_data` — trwałe dane
```

**Kontener `web`** jest budowany z `Dockerfile` z bazą `python:3.13-slim`; instaluje `requirements.txt`, kopiuje kod i uruchamia `python app.py`.

**Kontener `db`** wykorzystuje oficjalny obraz `mysql:8.4`. Ma healthcheck, który sprawdza, czy serwer bazy odpowiada. Usługa `web` zależy od zdrowej usługi `db`.

**Dlaczego dwa kontenery?** Oddzielamy logikę WWW od przechowywania danych. Dzięki temu można odtwarzać aplikację niezależnie od bazy. MySQL nie ma opublikowanego na zewnątrz portu w `compose.yaml`.

**Dlaczego port `10114:5000`?** 10114 to port hosta Linux, a 5000 port aplikacji wewnątrz kontenera. Port 10116 jest zarezerwowany na inne potrzeby i nie należy go zmieniać.

## 4. Struktura danych

- `users` — login, hash hasła, rola i opcjonalne powiązanie z uczniem.
- `students` — imię, nazwisko, klasa.
- `subjects` — nazwy przedmiotów.
- `grades` — oceny połączone kluczami obcymi z uczniem i przedmiotem.
- `teacher_assignments` — konkretne przydziały nauczyciel–klasa–przedmiot.
- `grade_metadata` — typ/kolor i krótki opis oceny. Wszystkie oceny mają taką samą wagę.
- `attendance` — data, przedmiot, uczeń, status obecności.
- `mail_messages`, `mail_recipients`, `mail_attachments` — wiadomości, osobny stan przeczytania/kosza dla odbiorców i załączniki.
- `class_timetables` — plan PDF klasy (po uruchomieniu migracji).

## 5. Wymagania

- Linux z Docker Engine i wtyczką Docker Compose v2 (`docker compose`).
- Git i dostęp do repozytorium.
- Wolny port TCP **10114** na serwerze.
- Odpowiednie uprawnienia do poleceń `docker`.
- Plik `.env` z własnymi sekretami (nie umieszczaj go na GitHubie).

## 6. Pierwsze uruchomienie na nowej instalacji

Poniższe kroki dotyczą **pustej, nowej bazy**. Nie wykonuj pełnej inicjalizacji bez zastanowienia na serwerze zawierającym dane.

```bash
# 1. Pobierz repozytorium
git clone https://github.com/marcinioza/EduVulcan2.0.git
cd EduVulcan2.0

# 2. Utwórz plik .env; nie umieszczaj w nim publicznych danych testowych
cp .env.example .env
python3 -c 'import secrets; print("SECRET_KEY=" + secrets.token_hex(32))'
# Edytuj .env (np. nano .env):
# MYSQL_PASSWORD=<własne silne hasło>
# MYSQL_ROOT_PASSWORD=<inne silne hasło>
# SECRET_KEY=<wynik polecenia powyżej>
chmod 600 .env

# 3. Zbuduj i uruchom usługi
docker compose up -d --build

# 4. Dla NOWEJ, pustej bazy utwórz tabele wszystkich modeli
docker compose exec web python -c 'from app import app; from models import db; app.app_context().push(); db.create_all(); print("Tabele gotowe")'

# 5. Załóż konto administratora — podasz własne hasło interaktywnie
docker compose exec web python create_admin.py

# 6. Sprawdź działanie
docker compose ps
```

Aplikacja jest publikowana pod `http://ADRES_SERWERA:10114/`. Jeśli serwer jest udostępniany przez skonfigurowany adres HTTPS/reverse proxy, korzystaj z jego adresu. `SECRET_KEY` musi mieć co najmniej 32 znaki; w `.env.example` nie ma go domyślnie.

**Uwaga:** `db.create_all()` tworzy brakujące tabele, ale nie zastępuje systemu migracji schematu przy późniejszych zmianach kolumn. Nie uruchamiaj projektu z przykładowymi hasłami jako systemu produkcyjnego.

## 7. Aktualizacja istniejącego szkolnego serwera Linux

Zakładamy, że projekt już istnieje w `~/EduVulcan2.0`, a baza ma dane. **Nie używaj `docker compose down -v`**.

```bash
cd ~/EduVulcan2.0

git status
# Przed aktualizacją wykonaj backup bazy:
docker compose exec -T db sh -c 'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' > ~/eduvulcan-backup.sql
chmod 600 ~/eduvulcan-backup.sql
ls -lh ~/eduvulcan-backup.sql
grep -c '^CREATE TABLE' ~/eduvulcan-backup.sql

# Pobierz sprawdzony kod (najpierw upewnij się, że jest kompletny)
git pull origin main

# Zbuduj obraz web bez naruszania wolumenu bazy
docker compose build web

# Migracje dodatkowych tabel, bez usuwania dotychczasowych danych:
docker compose run --rm --no-deps web python init_roles.py
docker compose run --rm --no-deps web python init_grade_metadata.py
docker compose run --rm --no-deps web python init_attendance.py
docker compose run --rm --no-deps web python init_messages.py
docker compose run --rm --no-deps web python init_timetables.py

# Uruchom aplikację z nowym obrazem
docker compose up -d web
docker compose ps
```

Skrypty `init_*.py` wykorzystują `create(checkfirst=True)`: mają za zadanie utworzyć brakujące tabele. Jeśli któryś krok zgłosi błąd, przerwij wdrożenie i przejrzyj logi, zamiast wykonywać dalsze polecenia.

## 8. Testy

GitHub Actions uruchamia weryfikację składni `python -m compileall -q .` i testy `python -m pytest -q`. Testy działają na tymczasowej bazie SQLite, nie na szkolnym MySQL.

Lokalnie w odizolowanym środowisku (najlepiej świeży Python 3.13):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
python -m compileall -q .
python -m pytest -q
```

Jeśli w GitHub Actions zadanie ma stan `Queued`, oznacza to oczekiwanie na uruchomienie testów, nie wynik pozytywny. Testów nie uznawaj za zaliczone przed statusem `Success`.

## 9. Diagnostyka i obsługa

```bash
docker compose ps                 # Stan web i db
docker compose logs --tail=100 web # Logi aplikacji
docker compose logs --tail=100 db  # Logi bazy
docker compose restart web        # Restart samej aplikacji
```

- **Błąd 500** — sprawdź `docker compose logs --tail=100 web`, w szczególności tabele i konfigurację.
- **Błąd 403** — konto nie ma uprawnień do strony lub działania.
- **Błąd 404** — nieprawidłowy adres lub brak dostępnego zasobu.
- **Błąd połączenia z MySQL** — sprawdź `docker compose ps`, healthcheck i `.env`.
- **Brak planu PDF** — sprawdź `static/files/pusty-plan-lekcji.pdf` oraz tabelę `class_timetables`.

## 10. Bezpieczeństwo

- Hasła są haszowane (`werkzeug.security`), a formularze chronione przez CSRF.
- Uprawnienia ról są weryfikowane po stronie serwera.
- Pliki `.env`, kopie zapasowe i prawdziwe hasła **nie powinny trafiać do repozytorium**.
- Konta demonstracyjne to dane testowe, nie konta do prawdziwej szkoły.
- Wysyłanie załączników jest ograniczone rozmiarem i formatem, ale projekt demonstracyjny nie przeszedł profesjonalnego audytu bezpieczeństwa.
- Własne hasła demo znajdują się w osobnym dokumencie `KONTA_DEMO_PRYWATNE.md`, przeznaczonym tylko do prywatnego przechowywania.

## 11. Loginy demonstracyjne (bez haseł)

| Rola | Login |
|---|---|
| Nauczyciel matematyki i informatyki | `demo_nauczyciel_matematyka` |
| Nauczyciel polskiego i historii | `demo_nauczyciel_polski` |
| Nauczyciel angielskiego | `demo_nauczyciel_angielski` |
| Uczeń Anna Nowicka | `demo_uczen_anna` |
| Uczeń Zofia Lewandowska | `demo_uczen_zofia` |
| Uczeń Julia Szymańska | `demo_uczen_julia` |
| Administrator | `admin` (hasło ustawiane osobno) |

## 12. Ograniczenia i rozwój

Projekt ma charakter dydaktyczny. Plany lekcji wymagają migracji na docelowym serwerze, a mechanizmy produkcyjne (centralne logowanie, audyt bezpieczeństwa, wydajność, zarządzanie sekretami i automatyczne wdrożenia) wymagałyby dalszych prac.
