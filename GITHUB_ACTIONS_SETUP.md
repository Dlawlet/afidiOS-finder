# 🚀 GitHub Actions Setup - Guide Rapide

## ✅ Repo nettoyé et prêt !

Le repository ne contient plus que les fichiers essentiels :

```
📦 afidiOS-finder
├── 📄 scheduled_scraper.py     # Scraper principal
├── 📄 semantic_analyzer.py     # Analyse IA Groq
├── 📄 job_exporter.py          # Export JSON/CSV
├── 📄 requirements.txt         # Dependencies
├── 📄 README.md                # Documentation
├── 📄 .gitignore               # Fichiers ignorés
├── 📁 .github/workflows/       # GitHub Actions
│   └── daily-scrape.yml        # Automation config
└── 📁 exports/                 # Résultats
    ├── remote_jobs_latest.json
    ├── remote_jobs_latest.csv
    └── README.md
```

---

## 🔧 Configuration GitHub Actions (5 étapes)

### Étape 1 : Rendre le repo PUBLIC

1. Aller sur https://github.com/Dlawlet/afidiOS-finder
2. **Settings** (en haut à droite)
3. Scroll tout en bas → **Danger Zone**
4. **Change visibility** → **Make public**
5. Taper le nom du repo pour confirmer

✅ **Pourquoi ?** Les GitHub Raw URLs ne fonctionnent qu'avec les repos publics.

---

### Étape 2 : Ajouter la clé Groq

1. Aller sur https://github.com/Dlawlet/afidiOS-finder/settings/secrets/actions
2. Cliquer **"New repository secret"**
3. Remplir :
   - **Name:** `GROQ_API_KEY`
   - **Secret:** Votre clé Groq (obtenir sur https://console.groq.com)
4. Cliquer **"Add secret"**

✅ **Pourquoi ?** Le scraper utilise l'API Groq pour l'analyse IA.

---

### Étape 3 : Activer les permissions Git

1. Aller sur https://github.com/Dlawlet/afidiOS-finder/settings/actions
2. Scroll vers **"Workflow permissions"**
3. Cocher **"Read and write permissions"**
4. Cocher **"Allow GitHub Actions to create and approve pull requests"** (optionnel)
5. Cliquer **"Save"**

✅ **Pourquoi ?** GitHub Actions doit pouvoir commit les exports automatiquement.

---

### Étape 4 : Activer GitHub Actions

1. Aller sur https://github.com/Dlawlet/afidiOS-finder/actions
2. Si message "Workflows disabled" → Cliquer **"I understand my workflows, go ahead and enable them"**

✅ **Pourquoi ?** GitHub désactive parfois Actions sur les nouveaux repos.

---

### Étape 5 : Test manuel

1. Aller sur https://github.com/Dlawlet/afidiOS-finder/actions
2. Cliquer sur **"Daily Job Scraper"** (dans la liste à gauche)
3. Cliquer **"Run workflow"** (bouton bleu à droite)
4. Sélectionner branch **"main"**
5. Cliquer **"Run workflow"**

Attendre 2-3 minutes, puis vérifier :
- ✅ Workflow devient vert (✓)
- ✅ Nouveau commit automatique dans l'historique
- ✅ Fichiers mis à jour dans `exports/`

---

## 🎯 Vérification finale

### Tester l'URL publique

Ouvrir dans le navigateur :
```
https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/remote_jobs_latest.json
```

Vous devriez voir le JSON avec les jobs ! 🎉

### Tester depuis votre site web

```javascript
fetch('https://raw.githubusercontent.com/Dlawlet/afidiOS-finder/main/exports/remote_jobs_latest.json')
  .then(r => r.json())
  .then(data => {
    console.log(`${data.jobs.length} jobs trouvés !`);
  });
```

---

## ⏰ Automatisation

Le scraper tournera automatiquement **tous les jours à 7h du matin** (heure de Paris).

Pour changer l'heure, éditer `.github/workflows/daily-scrape.yml` :

```yaml
schedule:
  - cron: '0 6 * * *'  # 7h Paris (UTC+1 en hiver)
  # Changer à '0 5 * * *' pour 7h Paris en été (UTC+2)
```

---

## 🐛 Dépannage

### Workflow échoue avec "Permission denied"
→ Vérifier **Étape 3** (permissions Git)

### Workflow échoue avec "Invalid API key"
→ Vérifier **Étape 2** (clé Groq correcte)

### URL retourne 404
→ Vérifier **Étape 1** (repo public)

### Workflow ne s'exécute pas
→ Vérifier **Étape 4** (Actions activées)

---

## 📊 Monitoring

Voir tous les runs :
- https://github.com/Dlawlet/afidiOS-finder/actions

Voir les logs d'un run :
- Cliquer sur un workflow → Cliquer sur "scrape" → Voir les logs détaillés

---

## ✅ Checklist finale

- [ ] Repo rendu public
- [ ] Clé Groq ajoutée dans Secrets
- [ ] Permissions Git activées
- [ ] GitHub Actions activé
- [ ] Test manuel réussi
- [ ] URL publique fonctionne
- [ ] Site web peut fetch les données

---

**🎉 Setup terminé ! Le scraper tourne automatiquement dans le cloud !**

**Coût : 0€/mois** (GitHub Actions gratuit jusqu'à 2000 min/mois, vous utilisez ~30 min/mois)
