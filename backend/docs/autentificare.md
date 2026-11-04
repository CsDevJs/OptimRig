# Ghid: sistemul de autentificare cu date criptate

Ghidul explică, pas cu pas, cum funcționează autentificarea din PC Configurator și de ce
e construită așa. La fiecare pas ai fișierul în care se află codul, ca să-l poți citi și
reface singur.

## 1. Ce vrem să obținem

- Utilizatorul își creează cont cu **email și parolă** și se loghează cu emailul.
- Aceste date stau **criptate** într-un fișier separat de baza de date,
  `backend/data/users.vault`. Emailul poate fi **decriptat la nevoie** cu
  o cheie; parola e păstrată doar ca **hash Argon2id**, care nu se poate decripta.
- Cine fură doar fișierul, sau doar baza de date, nu află nimic.

## 2. Noțiuni de bază

| Noțiune | Ce înseamnă | Unde o folosim |
|---|---|---|
| **Criptare** | Transformi datele cu o cheie; cu aceeași cheie le poți readuce la forma inițială (reversibil). | Emailul (și tot fișierul vault). |
| **Hash** | Transformare într-un singur sens: din rezultat nu se mai poate afla datele inițiale. | Parola (vezi secțiunea 8). |
| **Argon2id** | Hash creat special pentru parole: lent și cu multă memorie, ca ghicitul să fie scump. Fiecare hash are un *salt* aleator, deci aceeași parolă dă hash-uri diferite. Recomandat de OWASP și RFC 9106. | `app/security.py` |
| **AES-256** | Algoritmul de criptare standard (NIST), cu cheie de 256 de biți (32 de octeți). | `app/vault.py` |
| **GCM** | Modul de lucru al AES-ului care, pe lângă criptare, *autentifică*: dacă cineva modifică un singur octet din fișier, decriptarea eșuează în loc să dea date greșite. | `AESGCM` din biblioteca `cryptography`. |
| **Nonce** | Un număr aleator de 12 octeți, folosit o singură dată la fiecare criptare. Datorită lui, aceleași date dau de fiecare dată alt text criptat. | Se generează din nou la fiecare salvare. |
| **AAD** | Text asociat care nu se criptează, dar e „semnat” împreună cu datele (la noi `pc-configurator-vault/v1`). Un fișier criptat pentru alt scop nu se poate deschide aici. | `_AAD` în `app/vault.py`. |
| **Separarea cheii** | Cheia nu stă niciodată lângă datele pe care le protejează. | `VAULT_KEY` stă în `.env`, fișierul în `data/`. |

## 3. Pasul 1: biblioteca și cheia

1. Instalează biblioteca `cryptography`, întreținută de Python Cryptographic Authority
   (în `requirements.txt`):

   ```bash
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

2. Generează o cheie de 32 de octeți aleatori și pune-o în `backend/.env`:

   ```bash
   python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

   ```
   VAULT_KEY=...cele 44 de caractere...
   ```

   - `secrets`, nu `random`: `random` e previzibil, `secrets` folosește generatorul
     criptografic al sistemului de operare.
   - Fișierul `.env` e în `.gitignore`, deci cheia nu ajunge pe GitHub.
   - **Fă o copie a cheii** într-un loc separat (de exemplu un manager de parole). Dacă
     pierzi cheia, conturile nu mai pot fi citite; dacă o pierzi împreună cu fișierul,
     cine le găsește pe amândouă vede tot.

3. `app/config.py` verifică la pornire că `VAULT_KEY` are exact 32 de octeți
   (`decode_key` din `app/vault.py`). Fără o cheie validă, serverul nu pornește.

## 4. Pasul 2: fișierul criptat (`app/vault.py`)

Formatul fișierului pe disc este JSON:

```json
{"format": "pc-configurator-vault", "version": 1, "nonce": "…base64…", "ciphertext": "…base64…"}
```

Ce e în `ciphertext`, după decriptare:

```json
{"users": {"1": {"email": "ana@exemplu.com", "password_hash": "$argon2id$v=19$…"}}}
```

Pașii clasei `UserVault`:

- **Citire** (`_load`): decodează base64, apoi
  `AESGCM(cheie).decrypt(nonce, ciphertext, AAD)`. Dacă cheia e greșită sau fișierul a
  fost modificat, apare `InvalidTag`, pe care îl transformăm într-o eroare clară
  (`VaultError`).
- **Scriere** (`_save`): un nonce nou cu `os.urandom(12)`, criptare, apoi **scriere
  atomică**:
  1. scrii într-un fișier temporar din același folder;
  2. `flush()` și `os.fsync()`, ca datele să ajungă efectiv pe disc;
  3. `os.replace(temp, fișier)`, care e o redenumire atomică.

  Dacă serverul se oprește la mijloc, rămâne fie fișierul vechi, fie cel nou, niciodată
  unul pe jumătate scris.
- **Lacăt** (`self.lock`): două înregistrări simultane nu pot citi amândouă „emailul e
  liber” și apoi scrie amândouă. Verificarea și scrierea se fac sub același lacăt.
- **Unicitate**: emailul se salvează cu litere mici, deci `Ana@exemplu.com` și
  `ana@exemplu.com` sunt același cont.

## 5. Pasul 3: baza de date

Tabelul `users` nu mai conține date personale, doar `id` și `created_at`.
Build-urile salvate trimit spre `users.id`, așa că un cont tot are nevoie de un rând în
baza de date. Migrarea `alembic/versions/20261103_0005_users_vault.py` șterge coloanele
`email` și `password_hash`.

```bash
.venv\Scripts\python -m alembic upgrade head
```

## 6. Pasul 4: endpoint-urile (`app/api/auth.py`)

- **`POST /auth/register`** primește `{email, password}`:
  1. sub lacătul vault-ului verifică dacă emailul e deja folosit
     (dacă da, 409);
  2. creează rândul din `users` ca să obțină un `id`;
  3. transformă parola în hash Argon2id (`hash_password`) și scrie emailul
     și hash-ul în vault (criptate);
  4. salvează (commit) în baza de date.

  Dacă salvarea din bază eșuează, scoate contul din vault, ca să nu rămână date
  orfane.
- **`POST /auth/login`** primește `{login, password}`, unde `login` e emailul:
  - caută utilizatorul în vault și verifică parola cu `verify_password`. Argon2
    calculează hash-ul parolei introduse, cu salt-ul din hash-ul salvat, și compară
    rezultatele. Parola salvată nu e niciodată decriptată, pentru că nici nu există în
    clar;
  - pentru un cont inexistent verifică totuși un hash fals (`_DUMMY_HASH`) și răspunde
    **exact la fel** ca la o parolă greșită ("Wrong login or password"), în același
    timp. Astfel nimeni nu poate afla ce emailuri au cont.
- La succes primești un **token JWT** (`app/security.py`), semnat cu `JWT_SECRET`, pe
  care frontend-ul îl trimite la fiecare cerere: `Authorization: Bearer <token>`.

## 7. Pasul 5: decriptarea la nevoie

```bash
.venv\Scripts\python -m scripts.vault show   # id, email
```

Fără `VAULT_KEY` corect, comanda nu afișează nimic. Parolele nu pot fi afișate: în
fișier există doar hash-ul lor. Dacă cineva își uită parola, soluția corectă e o
resetare (setează o parolă nouă), nu recuperarea celei vechi.

## 8. De ce parola e hash, nu criptare

Inițial parola era criptată reversibil; acum e hash Argon2id, cum recomandă OWASP și
NIST. Diferența contează când cineva fură date:

- **Cu criptare:** cine obține fișierul **și** cheia află toate parolele în clar. Iar
  oamenii folosesc aceeași parolă pe multe site-uri (email, bancă).
- **Cu hash Argon2id:** nici noi, nici atacatorul nu putem afla parola din hash. Singura
  cale e ghicitul, iar Argon2id face fiecare încercare lentă și costisitoare în memorie,
  deci ghicitul pe scară largă devine impractic. Salt-ul unic face ca două conturi cu
  aceeași parolă să aibă hash-uri diferite, deci nu se pot ataca deodată.

Emailul rămâne criptat reversibil, pentru că uneori chiar trebuie citite
(de exemplu ca să trimiți un email). Parola nu trebuie citită niciodată, doar
verificată.

## 9. Teste (`tests/test_accounts.py`)

Testele verifică:

- că în fișier nu apare nimic în clar (nici emailul, nici hash-ul parolei);
- că hash-ul e Argon2id, are salt nou de fiecare dată și verifică doar parola corectă;
- că o cheie greșită sau un fișier modificat sunt respinse;
- că două salvări identice dau texte criptate diferite (nonce nou);
- că duplicatele sunt refuzate și că login-ul merge cu emailul;
- că erorile de login nu se pot deosebi între ele.

Fiecare test primește propriul vault într-un folder temporar, așa că nu atinge fișierul
real.

```bash
.venv\Scripts\python -m pytest -q tests/test_accounts.py
```

## 10. Exerciții ca să înveți

1. Creează un cont, apoi deschide `data/users.vault` într-un editor: vei vedea doar
   base64. Rulează `scripts.vault show` ca să vezi datele decriptate.
2. Schimbă o literă din `ciphertext` și pornește din nou serverul: login-ul va da eroare
   de decriptare (GCM detectează modificarea).
3. Pune altă `VAULT_KEY` în `.env`: fișierul nu se mai poate deschide. Pune cheia
   înapoi și totul merge din nou.
4. În Python, rulează de două ori `hash_password("Parola1!")` din `app.security`:
   rezultatele diferă (salt nou), dar `verify_password` acceptă parola pentru amândouă.
   Explică de ce.
