# Airbnb hostų klasifikatorius į superhostus: U1 MLOps projekto paleidimo instrukcijos

Binarinis klasifikatorius: ar Airbnb skelbimo šeimininkas yra Superhost (10 Europos miestų, 51 707 įrašai). Aplink
modelį: atkartojamas DVC pipeline'as, eksperimentų sekimas savame MLflow serveryje lokaliame kind klasteryje, mokymo
Docker vaizdas GHCR ir mokymas kaip Kubernetes Job (E2).

- **Repo:** https://github.com/lukasja111/mlops-u1
- **Tag:** `u1-final`
- **Autorius:** Lukas Jasiulionis (lukasja111)
- **Vaizdas:** `ghcr.io/lukasja111/mlops-u1/train:sha-71249941` (viešas; digest `docs/image-sizes.md`)
- **Kaip paleisti:** „Paleidimas nuo nulio“ žemiau; rezultatai MLflow UI http://127.0.0.1:5000
- **Dokumentai:** `docs/requirements.md` (reikalavimai, KPI ir išmatuotos reikšmės), `docs/u1-report.md` (ataskaita),
  `docs/architecture.md`, `docs/runbook.md` (naujas eksperimentas, reprodukcija, Docker vaizdas, Job'as, problemų
  sprendimas)

## Reikalavimai

Docker, [kind](https://kind.sigs.k8s.io/) ≥ 0.31, kubectl, Python 3.12, apie 4 GB laisvos RAM. Išbandyta su: Docker
29.8.1, kind 0.31.0, kubectl 1.36.3, Python 3.12.14, DVC 3.67.1 (Linux).

## Paleidimas nuo nulio

```bash
# 0. Repo ir Python aplinka; visos komandos vykdomos repo šaknyje, viename terminale
git clone https://github.com/lukasja111/mlops-u1.git && cd mlops-u1
python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

# 1. Klasteris (kind sukuria kontekstą kind-mlops-u1 ir į jį persijungia)
kind create cluster --config k8s/kind-config.yaml

# 2. Namespace ir Postgres prisijungimai: Secret kuriamas komanda, į Git nepatenka
kubectl apply -f k8s/namespace.yaml
PG_PASSWORD=$(python -c 'import secrets; print(secrets.token_hex(16))')
kubectl -n mlops-u1 create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=mlflow \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --from-literal=POSTGRES_DB=mlflow

# 3. Postgres ir MLflow serveris
kubectl apply -f k8s/mlflow/
kubectl -n mlops-u1 rollout status deploy/postgres --timeout=180s
kubectl -n mlops-u1 rollout status deploy/mlflow --timeout=300s
until curl -sf http://127.0.0.1:5000/health; do sleep 2; done; echo

# 4. Duomenys: 20 CSV iš fiksuotos HF revizijos ir patikra, kad jie sutampa su data/raw.dvc
mkdir -p data/raw
for c in amsterdam athens barcelona berlin budapest lisbon london paris rome vienna; do
  for d in weekdays weekends; do
    curl -fsSL -o "data/raw/${c}_${d}.csv" \
      "https://huggingface.co/datasets/kraina/airbnb/resolve/b9dd71fc8f175b645ce47f87c702492a6128c4dd/data/${c}_${d}.csv"
  done
done
dvc commit -f data/raw.dvc
git diff --exit-code data/raw.dvc && echo "duomenys sutampa"

# 5. Pipeline'as: run'as klasterio MLflow
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
dvc repro --force
git commit -am "exp: pirmas run'as savame klasteryje"
```

- 4 žingsnis: autoriaus kompiuteryje vietoje jo užtenka `dvc pull`; kitur `dvc pull` neveikia (žr. `docs/runbook.md`).
- 5 žingsnis: `--force`, nes po `dvc pull` visos išvestys sutampa su `dvc.lock` ir be jo DVC viską praleistų, o naujame
  klasteryje MLflow tuščias. Commit'as reikalingas, nes `reproduce.py` reikalauja švaraus darbo medžio.
- Naujame terminale: `. .venv/bin/activate && export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` (be jo `train.py`
  neveikia: run'ai log'inami tik į klasterio MLflow).

## Portai

| Kas | Adresas |
|---|---|
| MLflow UI / API | http://127.0.0.1:5000 → kind NodePort 30500 → Service `mlflow:5000` |
| Postgres | tik klasterio viduje: `postgres:5432` |

Jei NodePort neveikia: `kubectl -n mlops-u1 port-forward svc/mlflow 5050:5000` → http://127.0.0.1:5050 (tada ir
`export MLFLOW_TRACKING_URI=http://127.0.0.1:5050`). Kompiuteris be naršyklės: `ssh -L 5000:localhost:5000 <host>`.

## Prisijungimai

- **Postgres:** naudotojas ir slaptažodis tik Secret `postgres-credentials` (2 žingsnis). Peržiūrėti:
  `kubectl -n mlops-u1 get secret postgres-credentials -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d`. MLflow
  slaptažodį gauna aplinkos kintamuoju `PGPASSWORD`, todėl jo nerodo nei `ps`, nei `kubectl describe`.
- **MLflow:** be autentifikacijos (E1 nedaromas), todėl kind klausosi tik `127.0.0.1`.

## Kur žiūrėti rezultatus

- MLflow UI → eksperimentas `airbnb-superhost`: run'ai `rf-n<n_estimators>-d<max_depth>`, metrikos `f1` (pagrindinė),
  `accuracy` ir `eval/*`, artefaktai `eval/feature_importances.json` ir `eval/confusion_matrix.json`, tag'ai
  `git_commit` ir `dvc_raw_md5`. Seni run'ai (prieš nutekėjimo taisymą) pažymėti `split=random`.
- `dvc metrics show`; palyginimas su ankstesniu eksperimentu: `dvc metrics diff <commit>`, `dvc params diff <commit>`.
- KPI ir išmatuotos reikšmės `docs/requirements.md`; vaizdo dydis ir Trivy `docs/image-sizes.md`,
  `docs/security-scan.md`.

## Reprodukcija

```bash
time python reproduce.py <run_id>      # švarus darbo medis; ≤ 2 min, |Δaccuracy| ir |Δf1| ≤ 0,005
```

`<run_id>` yra 5 žingsnio išvestyje arba MLflow UI. Kaip veikia: `docs/runbook.md`.

## E2: mokymas kaip Kubernetes Job

```bash
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Hiperparametrai yra ConfigMap `training-config`; jų keitimas ir pakartotinis paleidimas `docs/runbook.md`.

## Išvalymas

```bash
kind delete cluster --name mlops-u1
```

Postgres ir MLflow artefaktų PVC išlieka perkūrus Pod'ą, bet dingsta ištrynus klasterį.

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE).
