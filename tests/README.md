# Testing Guide

## Manual Testing

### Kjør basic tests
```bash
# Start appen først
python run.py

# I nytt terminal-vindu
python tests/manual/test_basic.py
```

### Testing checklist per uke

#### Uke 1
- [ ] Server starter uten feil
- [ ] Logging fungerer (sjekk app.log fil)
- [ ] Alle sider redirecter til login

#### Uke 2
- [ ] Config loading fungerer
- [ ] Auth blueprint responderer
- [ ] Environment variables leses riktig

#### Uke 3
- [ ] Database operasjoner fungerer
- [ ] Dashboard viser data
- [ ] Nye posts kan opprettes

#### Uke 4
- [ ] Alle moduler fungerer
- [ ] File upload/download
- [ ] Alle forms fungerer
- [ ] Ingen 404 errors

## Browser testing

1. **Åpne:** http://localhost:5000
2. **Test login flow:** Skal redirecte til Microsoft login
3. **Test alle menyer:** Dashboard, Dokumenter, Kalender, Oppgaver
4. **Test forms:** Opprett posts, upload filer, lag oppgaver

## Debugging tips

- Sjekk `app.log` for feilmeldinger
- Bruk browser developer tools for frontend errors
- Test med `curl` hvis browser oppfører seg rart

## Logging levels

- **INFO:** Normal app oppførsel (startup, config loading)
- **WARNING:** Potensielle problemer (unauthorized access)
- **ERROR:** Feil som må fikses (database errors, missing files)
- **DEBUG:** Detaljert info for debugging (SQL queries, route calls)

## Test kommandoer

```bash
# Test at server svarer
curl -I http://localhost:5000

# Test specific routes
curl -I http://localhost:5000/auth/login
curl -I http://localhost:5000/documents

# Check logs for errors
grep ERROR app.log
grep WARNING app.log
```