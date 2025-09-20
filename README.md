# GRM Intranett

Et moderne og ryddig intranett for firmaet GRM, bygget med Flask og inspirert av Facebook's design. Systemet gir ansatte tilgang til nøkkelfunksjoner som nyhetsfeed, dokumentbank, kalender, oppgaveadministrasjon og nyhetsbrev.

## ✨ Funksjoner

### 🏠 Dashboard / Nyhetsfeed
- Facebook-inspirert design med midtstilt feed
- Opprett og del innlegg med kollegaer
- Kommentarfunksjon (grunnleggende struktur)
- Sanntidsvisning av nyeste innlegg

### 📁 Dokumentbank
- Organiserte mapper: Salg, Verksted, HR, IT
- Sikker opplasting og nedlasting av filer
- Søkefunksjonalitet
- Filtyping med ikoner

### 📅 Kalender
- Månedlig og ukentlig visning
- Opprett hendelser med detaljer (tid, sted, ansvarlig)
- Visuell kalendervisning
- Widget på dashboard for kommende hendelser

### ✅ Oppgaver / Feilmelding
- Kanban-style oppgavestyring (Å gjøre, Pågår, Ferdig)
- Prioritetsnivåer (Høy, Medium, Lav)
- Avdelingsfiltrering
- Tildeling av oppgaver til ansatte

### 📧 Nyhetsbrev
- Opprett og send nyhetsbrev (kun admin)
- Arkivering av tidligere nyhetsbrev
- Forhåndsvisning før sending

### 👥 Brukeradministrasjon
- Sikker innlogging med Flask-Login
- Roller: Admin / Bruker
- Brukerprofiler

## 🎨 Design

Systemet bruker en moderne og ren design med:
- **Fargepalett**: Hentet fra GRM-logoen (grønn #10B981 og rød #DC2626)
- **Responsivt design**: Fungerer på desktop og mobil
- **Font Awesome ikoner**: For visuell klarhet
- **Topbar navigasjon**: Med logo og menyvalg
- **Widget-basert dashboard**: Modulær oppbygning

## 🚀 Installasjon

### Forutsetninger
- Python 3.8 eller nyere
- Git

### Trinn 1: Klone prosjektet
```bash
git clone <repository-url>
cd intranett_grm
```

### Trinn 2: Opprett virtuelt miljø
```bash
python3 -m venv venv
source venv/bin/activate  # På Windows: venv\Scripts\activate
```

### Trinn 3: Installer avhengigheter
```bash
pip install -r requirements.txt
```

### Trinn 4: Start applikasjonen
```bash
python app.py
```

Applikasjonen vil være tilgjengelig på `http://localhost:5000`

## 🔐 Standard innlogging

**Administrator:**
- E-post: `admin@grm.no`
- Passord: `admin123`

## 📂 Filstruktur

```
intranett_grm/
├── app.py                 # Flask backend
├── requirements.txt       # Python avhengigheter
├── database.db           # SQLite database (opprettes automatisk)
├── logo.png              # GRM logo
├── templates/             # HTML-filer
│   ├── base.html         # Grunnmal
│   ├── login.html        # Innloggingsside
│   ├── dashboard.html    # Dashboard / nyhetsfeed
│   ├── documents.html    # Dokumentbank
│   ├── calendar.html     # Kalender
│   ├── tasks.html        # Oppgaver
│   └── newsletter.html   # Nyhetsbrev
├── static/               # Statiske filer
│   ├── css/
│   │   └── style.css     # Hovedstil
│   └── js/
│       └── main.js       # JavaScript-funksjonalitet
└── uploads/              # Opplastede dokumenter
    ├── salg/
    ├── verksted/
    ├── hr/
    └── it/
```

## 🗄️ Database

Systemet bruker SQLite som database med følgende tabeller:

- **users**: Brukere og roller
- **posts**: Innlegg i nyhetsfeed
- **comments**: Kommentarer til innlegg
- **documents**: Filer i dokumentbanken
- **calendar_events**: Kalenderhendelser
- **tasks**: Oppgaver og feilmeldinger
- **newsletters**: Nyhetsbrev

Databasen opprettes automatisk ved første oppstart.

## 🔧 Konfigurering

### Miljøvariabler
Du kan tilpasse applikasjonen ved å endre verdier i `app.py`:

```python
app.config['SECRET_KEY'] = 'din-secret-key-her'
app.config['UPLOAD_FOLDER'] = 'uploads'
```

### Produksjon
For produksjonsbruk bør du:

1. Endre `SECRET_KEY` til en sikker verdi
2. Bytte til PostgreSQL eller MySQL
3. Konfigurere en webserver (nginx + gunicorn)
4. Implementere e-postintegrasjon for nyhetsbrev
5. Legge til SSL-sertifikat

## 🔮 Fremtidige funksjoner

### Planlagte forbedringer:
- **E-postintegrasjon**: Send nyhetsbrev via SMTP
- **Post via e-post**: Opprett innlegg ved å sende e-post
- **Avansert søk**: Søk på tvers av alle moduler
- **Brukergruppering**: Avdelingsspesifikk tilgang
- **Filversjonering**: Spor endringer i dokumenter
- **Push-varsler**: Sanntidsvarsler for nye innlegg
- **API**: RESTful API for integrering
- **Mobilapp**: Dedikert mobilapplikasjon

### Tekniske forbedringer:
- **Caching**: Redis for bedre ytelse
- **Testing**: Enhetstester og integrasjonstester
- **Logging**: Strukturert logging
- **Overvåking**: Ytelsesovervåking og feilsporing

## 📱 Responsivt design

Systemet er optimalisert for:
- **Desktop**: Full funksjonalitet med sidebars og widgets
- **Tablet**: Tilpasset layout med sammenslåtte kolonner
- **Mobil**: Forenklet navigasjon og stakket innhold

## 🛡️ Sikkerhet

Implementerte sikkerhetstiltak:
- Passordkryptering med werkzeug
- Sesjonshåndtering med Flask-Login
- Filvalidering ved opplasting
- SQL injection-beskyttelse
- XSS-beskyttelse

## 🤝 Bidrag

For å bidra til prosjektet:

1. Fork repositoryet
2. Opprett en feature branch: `git checkout -b min-nye-funksjon`
3. Commit endringene: `git commit -am 'Legg til ny funksjon'`
4. Push til branchen: `git push origin min-nye-funksjon`
5. Opprett en Pull Request

## 📄 Lisens

Dette prosjektet er utviklet for GRM og er underlagt selskapets interne retningslinjer.

## 📞 Support

For teknisk support eller spørsmål, kontakt IT-avdelingen.

---

**Utviklet med ❤️ for GRM**