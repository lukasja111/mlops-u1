# U2 ataskaita

## Kas padaryta

- **R1:** `dvc repro` paleidžia Optuna paiešką: 20 bandymų, kiekvienas vertinamas 5 grupių kryžmine validacija mokymo
  imtyje ir yra įdėtinis run'as (`trial-00` ... `trial-19`) su `fold_f1` per žingsnius. Tėvinis run'as `rf-hpo20`:
  parametrai, `best_cv_f1` per žingsnius, 8 sistemos metrikos, `log_input` (train ir test su digest'u), tag'ai
  `git_commit`, `dvc_raw_md5`, `seed`, modelis su aplinka. v3: `n_estimators` 105, `max_depth` 14,
  `min_samples_leaf` 1; F1 0,6370, accuracy 0,7766, 157 s.
- **R2:** registras `airbnb-superhost`: v1 (U1 konfigūracija), v2 (HPO, 3 grupės), v3 (HPO, 5 grupės), kiekviena su
  tag'ais `git_commit`, `dvc_raw_md5`, `accuracy`, `f1`, `gate=passed`. API įkelia
  `models:/airbnb-superhost@champion`, `/health` rodo versiją ir run'ą.
- **R3:** Job `train` iš `mlops-u1/train:sha-ca7ea995`: hiperparametrai ConfigMap `training-config`, prisijungimas
  Secret `mlflow-trainer-credentials`; `Completed` per 30 s, run'o `git_commit` `ca7ea995` (accuracy 0,7833, F1 0,6393).
- **R4:** FastAPI (`src/serve.py`) Deployment su 2 replikomis, probes ir `preStop`, NodePort Service 30800; `/health`
  ir `/predict` (klasė, tikimybė, versija). Apkrovos testas: p95 20,3 ms, 94,1 užklausų/s.
- **R5:** `.github/workflows/ci-cd.yml`: `lint` ir `test`, `model-gate`, `build` su Trivy. GitHub'e nevykdytas (žr.
  „Nedaryta“); tie patys žingsniai vyksta lokaliai: README 7 žingsnis ir `scripts/cd.sh`.
- **R6:** `scripts/cd.sh`: testai → `dvc repro` → vartas (`metrics.json` ≥ `params.yaml` `gate`) → registracija ir
  `@champion` → `MODEL_VERSION` manifeste → `kubectl apply -k` → smoke testas. Rollback: `scripts/cd.sh rollback`.
- **R7:** `docs/requirements.md` v1.9: FR-06 iki FR-10, inferencijos NFR-14 iki NFR-21 su išmatuotomis reikšmėmis.

## Architektūra

```
kodo commit    → README 7: docker build api, train (sha-<commit>) → Trivy CRITICAL → kind load → tag'as manifestuose
params commit  → scripts/cd.sh: ruff → pytest → dvc repro → gate.py → register, @champion → MODEL_VERSION → kubectl apply -k → smoke
rollback       → scripts/cd.sh rollback: @champion ↔ @previous → MODEL_VERSION → kubectl apply -k → smoke

kind klasteris, namespace mlops-u1:
  postgres ← mlflow (basic-auth, 127.0.0.1:5000) ← job/train (trainer), deploy/api x2 (serving, NodePort 30800)
```

Modelio vaizde nėra: modelio pakeitimui build'o nereikia, vaizdai perkuriami tik keičiantis kodui. `MODEL_VERSION`
Git'e rodo, kuri versija įdiegta; jo pakeitimas pervadina ConfigMap, todėl Pod'ai persikrauna ir įkelia `@champion`,
o smoke testas tikrina, kad abu sutampa.

## Matavimai

| Kas | Reikšmė |
|---|---|
| HPO run'as (20 bandymų po 5 grupes) | 157 s, 20 įdėtinių run'ų |
| Žalias `cd.sh` iki smoke testo | 210 s |
| Raudonas: tik slenkstis `min_f1: 0.99` | 12,2 s, išėjimo kodas 1 |
| Raudonas: `max_depth: 5` be paieškos | 34,3 s, F1 0,5943, išėjimo kodas 1 |
| Rollback v3 → v2, v2 → v3 | 25,8 s, 25,9 s |
| Nukritusios užklausos | rollback'uose 1 iš 1 386 ir 0 iš 1 463; vaizdo keitimas be `preStop` 28 iš 1 827 |
| p50 / p95 / p99 | 14,3 / 20,3 / 22,4 ms (500 užklausų, `docs/load-test.json`) |
| Pralaidumas | 94,1 užklausų/s su 8 gijomis |
| Modelis v3 | 31,13 MB |
| API vaizdas `sha-ca7ea995` | rootfs 439,98 MB; Trivy CRITICAL 0, HIGH 47 (be pataisų) |

## Žalias, raudonas ir rollback

Žalias (`bash scripts/cd.sh`, 210 s, išėjimo kodas 0; dar `dev` vaizdu, vėliau tas pats `cd.sh` įdiegė
`sha-ca7ea995` ir praleido registraciją: `run already registered`):

```
run_id=a12df7d9… accuracy=0.7766 f1=0.6370
PASS: f1 = 0.6370347102245956 (threshold >= 0.62)
PASS: accuracy = 0.776585460170147 (threshold >= 0.75)
Created version '3' of model 'airbnb-superhost'.
smoke ok: version 3, image dev
```

Raudonas: `min_f1: 0.99` (12,2 s) ir `max_depth: 5`, `n_trials: 0` (34,3 s); abu kartus išėjimo kodas 1, `/health`
liko v3, run'as `f53bde93` pažymėtas `gate=failed`:

```
FAIL: f1 = 0.6370347102245956 (threshold >= 0.99)
quality gate failed: nothing registered or deployed

run_id=f53bde93… accuracy=0.7095 f1=0.5943
FAIL: f1 = 0.5943026866477656 (threshold >= 0.62)
FAIL: accuracy = 0.7094934261407579 (threshold >= 0.75)
quality gate failed: nothing registered or deployed
```

Rollback (`time bash scripts/cd.sh rollback`, du kartus): po pirmo `@champion` v2 ir `@previous` v3, po antro vėl v3
ir v2; `/predict` atsakymo `model_version` sutampa.

```
version=2
smoke ok: version 2, image sha-ca7ea995
version=3
smoke ok: version 3, image sha-ca7ea995
```

## Kas neveikė / ką teko spręsti

1. **Užklausos krisdavo keičiant Pod'us:** `rollout status` grįžta, kol paskutinis senas Pod'as dar stabdomas, ir į jį
   patekusi užklausa atmetama (28 iš 1 827 keičiant vaizdą). `preStop` 5 s pauzė (Kubernetes `sleep` veiksmas) leidžia
   Service pirma išimti Pod'ą: rollback'uose 1 ir 0, o rollback'as nepailgėjo.
2. **Pasenęs vaizdo sluoksnis:** Docker kešas paliko 11-01 `apt-get upgrade` sluoksnį, todėl 4 HIGH radiniai (apt
   RCE ir du zlib) turėjo pataisas. Su `docker build --no-cache`: HIGH 51 → 47, pataisomų 0.
3. **MLflow su prisijungimais:** `basic-auth` reikia savo DB lentelių (`mlflow.server.auth db upgrade`
   initContainer'yje), ini failo iš Secret ir Flask rakto; naudotojai kuriami per admin API. Su
   `default_permission = READ` eksperimento ar modelio kūrėjas gauna MANAGE, kiti tik skaito.
4. **Sistemos metrikos:** `log_system_metrics=True` be `psutil` meta klaidą net su pilnu `mlflow`, todėl `psutil`
   įrašytas į reikalavimus.
5. **Registracija:** MLflow 3 `runs:/<id>/model` randa LoggedModel tik su įspėjimu, todėl registruojama
   `models:/<model_id>`. `search_model_versions` grąžina versijas be alias'ų, alias'ai skaitomi
   `get_model_version_by_alias`.
6. **Raudono paleidimo atstatymas:** blogas modelis perrašo `dvc.lock`, `metrics.json`, `models/run_id.txt` ir
   `model.pkl`, todėl žalias rezultatas commit'inamas prieš raudoną, o atstatoma `git checkout` ir `dvc checkout`.
7. **`ruff` 0.17** pagal nutylėjimą įjungia I ir BLE taisykles: `select` užfiksuotas `pyproject.toml`, kad lint
   nepriklausytų nuo versijos.

## Nedaryta

- **U2-R5 GitHub dalis:** workflow parašytas, bet GitHub Actions nevykdytas, vaizdai GHCR nepublikuoti. Autoriaus
  sprendimas U2 nekelti į jokį nuotolinį repo: pateikiamas lokalus tag'as `u2-final` (ZIP su `git bundle`). Tie patys
  žingsniai (lint, testai, vartas, build, Trivy) vykdomi lokaliai, žalias ir raudonas paleidimas parodyti su
  `scripts/cd.sh`.
- **E5** (Argo CD) reikalauja Git remote, kurio U2 neturi; **E1** neatliktas, nes kompiuteryje tik AMD GPU; **E3**
  dėl laiko.
