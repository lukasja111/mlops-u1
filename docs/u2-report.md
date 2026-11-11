# U2 ataskaita

## Kas padaryta

- **R1:** Optuna: 20 bandymų (įdėtiniai run'ai `trial-00` ... `trial-19`), 5 grupių kryžminė validacija mokymo imtyje,
  `fold_f1` per žingsnius. Tėvinis `rf-hpo20`: parametrai, `best_cv_f1` per žingsnius, 8 sistemos metrikos, `log_input`
  (train ir test su digest'u), tag'ai `git_commit`, `dvc_raw_md5`, `seed`, modelis su aplinka. v3: `n_estimators` 105,
  `max_depth` 14, `min_samples_leaf` 1; F1 0,6370, accuracy 0,7766.
- **R2:** registras `airbnb-superhost`: v1 (U1 konfigūracija), v2 (HPO, 3 grupės), v3 (HPO, 5 grupės); tag'ai
  `git_commit`, `dvc_raw_md5`, `accuracy`, `f1`, `gate=passed`. API įkelia `models:/airbnb-superhost@champion`,
  `/health` rodo versiją ir run'ą.
- **R3:** Job `train` iš `mlops-u1/train:sha-ca7ea995`, ConfigMap `training-config`, Secret
  `mlflow-trainer-credentials`; `Completed` per 30 s, `git_commit` `ca7ea995`, accuracy 0,7833, F1 0,6393.
- **R4:** FastAPI `src/serve.py`: Deployment (2 replikos, probes, `preStop`), NodePort Service 30800, `/health` ir
  `/predict`.
- **R5:** GitHub Actions `.github/workflows/ci-cd.yml`: `lint`, `test`, `model-gate`, `build` su Trivy, tada abu vaizdai
  į GHCR. Žalias run'as `43011607138` (7 min 39 s), raudonas `43013796244` (`min_f1=0.99`: `model-gate` krito, `build`
  nevykdytas).
- **R6:** `scripts/ci-cd.sh` su kokybės vartu ir `scripts/ci-cd.sh rollback` (žr. „Architektūra“). GitHub job `deploy`
  (self-hosted runner'is) paleidžia tą patį `ci-cd.sh`: žalias run'as `43086372854`, raudonas `43087804813`.
- **R7:** `docs/requirements.md` v2.0: FR-06 iki FR-12, NFR-14 iki NFR-23 išmatuoti.
- **E1:** `src/train_gpu.py` (PyTorch MLP, AMP, `torch.profiler`) su RTX 5070 Ti atskirame kompiuteryje, run'ai
  klasterio MLflow per SSH tunelį. AMP: mažas tinklas 26,7 → 34,6 s, didelis 48,3 → 19,7 s (README 13 žingsnis).

## Architektūra

```
kodo commit    → README 7: docker build api, train (sha-<commit>) → Trivy CRITICAL → kind load → tag'as manifestuose
params commit  → scripts/ci-cd.sh: ruff → pytest → dvc repro → gate.py → register, @champion → MODEL_VERSION → kubectl apply -k → smoke
rollback       → scripts/ci-cd.sh rollback: @champion ↔ @benched → MODEL_VERSION → kubectl apply -k → smoke

kind klasteris, namespace mlops-u1:
  postgres ← mlflow (basic-auth, 127.0.0.1:5000) ← job/train (trainer), deploy/api x2 (serving, NodePort 30800)
```

Modelio vaizde nėra, todėl naujam modeliui build'o nereikia. Vaizdai perkuriami tik pasikeitus kodui. `MODEL_VERSION`
Git'e rodo įdiegtą versiją. Jį pakeitus ConfigMap gauna naują vardą, Pod'ai persikrauna ir įkelia `@champion`.
Smoke testas tikrina, kad abu sutampa.

## Matavimai

| Kas | Reikšmė |
|---|---|
| HPO run'as (20 bandymų po 5 grupes) | 157 s, 20 įdėtinių run'ų |
| Žalias `ci-cd.sh` iki smoke testo | 210 s |
| Raudonas: tik slenkstis `min_f1: 0.99` | 12,2 s, išėjimo kodas 1 |
| Raudonas: `max_depth: 5` be paieškos | 34,3 s, F1 0,5943, išėjimo kodas 1 |
| Rollback v3 → v2, v2 → v3 | 25,8 s, 25,9 s |
| Nukritusios užklausos | rollback'uose 1 iš 1 386 ir 0 iš 1 463; vaizdo keitimas be `preStop` 28 iš 1 827 |
| p50 / p95 / p99 | 14,3 / 20,3 / 22,4 ms (500 užklausų, `docs/load-test.json`) |
| Pralaidumas | 94,1 užklausų/s su 8 gijomis |
| Modelis v3 | 31,13 MB |
| API vaizdas `sha-ca7ea995` | rootfs 439,98 MB; Trivy CRITICAL 0, HIGH 47 (be pataisų) |

## Žalias, raudonas ir rollback

Žalias: `bash scripts/ci-cd.sh`, 210 s, išėjimo kodas 0 (dar su `dev` vaizdu).

```
run_id=a12df7d9… accuracy=0.7766 f1=0.6370
PASS: f1 = 0.6370347102245956 (threshold >= 0.62)
PASS: accuracy = 0.776585460170147 (threshold >= 0.75)
Created version '3' of model 'airbnb-superhost'.
smoke ok: version 3, image dev
```

Raudonas: `min_f1: 0.99` (12,2 s) ir `max_depth: 5` su `n_trials: 0` (34,3 s). Abu kartus išėjimo kodas 1 ir `/health`
liko v3. Run'as `f53bde93` pažymėtas `gate=failed`.

```
FAIL: f1 = 0.6370347102245956 (threshold >= 0.99)
quality gate failed: nothing registered or deployed

run_id=f53bde93… accuracy=0.7095 f1=0.5943
FAIL: f1 = 0.5943026866477656 (threshold >= 0.62)
FAIL: accuracy = 0.7094934261407579 (threshold >= 0.75)
quality gate failed: nothing registered or deployed
```

Rollback: `time bash scripts/ci-cd.sh rollback` du kartus. Po pirmo `@champion` v2 ir `@benched` v3, po antro vėl v3
ir v2. `/predict` atsakymo `model_version` sutampa.

```
version=2
smoke ok: version 2, image sha-ca7ea995
version=3
smoke ok: version 3, image sha-ca7ea995
```

## Kas neveikė / ką teko spręsti

1. **Užklausos krisdavo keičiant Pod'us.** `rollout status` grįžta, kol paskutinis senas Pod'as dar stabdomas ir atmeta
   užklausas (28 iš 1 827). `preStop` 5 s leidžia Service pirma išimti Pod'ą. Po to rollback'uose nukrito 1 ir 0,
   trukmė nepailgėjo.
2. **Pasenęs vaizdo sluoksnis.** Docker kešas laikė seną `apt-get upgrade` sluoksnį. Po `docker build --no-cache`
   HIGH 51 → 47, pataisomų 0.
3. **Atstatymas po raudono.** Blogas modelis perrašo `dvc.lock`, `metrics.json`, `models/run_id.txt` ir `model.pkl`.
   Žalias commit'inamas prieš raudoną, po raudono `git checkout`, `dvc checkout`.

## Nedaryta

- **E2** (Prefect), **E3** (HPA), **E4** (ONNX), **E5** (Argo CD): dėl laiko.

## Kiek laiko užtruko

~9-10 val. per 2d. pagrinde
