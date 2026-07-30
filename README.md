# Niedersachsen-Anfragen – Starter

Dieses Repository:

1. durchsucht die Dokumentensuche des Niedersächsischen Landtags,
2. filtert Antworten der Landesregierung,
3. extrahiert Text aus den verlinkten PDFs,
4. schreibt die Ergebnisse nach `data/documents.json`,
5. kann täglich über GitHub Actions aktualisiert werden.

## Lokal ausführen

```bash
python -m pip install -r requirements.txt
python scraper.py --pages 10
```

## GitHub Action

Der Workflow `.github/workflows/update.yml` läuft täglich und kann unter
**Actions → Update documents → Run workflow** manuell gestartet werden.

## Cloudflare Worker

Der Ordner `worker/` enthält eine kleine Such-API. Vor dem Deployment muss in
`worker/wrangler.toml` der GitHub-Benutzername und Repositoryname eingesetzt
werden.

## Hinweis

Bitte vor einem größeren Abruf die aktuellen Nutzungsbedingungen und
`robots.txt` der Zielseite prüfen. Der Crawler wartet zwischen Seiten und
verwendet einen identifizierbaren User-Agent.
