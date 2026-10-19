# Airbnb hostų klasifikatorius į superhostus: U1 MLOps projekto paleidimo instrukcijos

Binarinis klasifikatorius: ar Airbnb skelbimo šeimininkas yra Superhost (10 Europos miestų, 51 707 įrašai). Aplink
modelį: atkartojamas DVC pipeline'as, eksperimentų sekimas savame MLflow serveryje lokaliame kind klasteryje, mokymo
Docker vaizdas GHCR ir mokymas kaip Kubernetes Job (E2).

```
kompiuteris
  dvc repro: prepare → train → evaluate
                  │ HTTP 127.0.0.1:5000 → kind NodePort 30500
                  ▼
kind klasteris mlops-u1 (namespace mlops-u1)
  Service mlflow:5000 → Pod mlflow ──→ PVC mlflow-artifacts (modeliai, artefaktai)
                           │
                           └──→ Service postgres:5432 → Pod postgres ──→ PVC postgres-data (run'ai, metrikos)
  Job train (vaizdas iš GHCR) ──→ http://mlflow:5000
```

## Trumpai

| Kas | Kur |
|---|---|
| Repo, tag'as | https://github.com/lukasja111/mlops-u1, tag `u1-final` |
| Autorius | Lukas Jasiulionis (lukasja111) |
| MLflow UI ir API | http://127.0.0.1:5000 (kompiuterio 5000 → kind NodePort 30500 → Service `mlflow:5000`) |
| MLflow prisijungimas | nėra (E1 nedarytas), todėl kind klausosi tik `127.0.0.1` |
| Postgres | tik klasterio viduje, `postgres:5432`; naudotojas ir slaptažodis Secret `postgres-credentials` (3 žingsnis) |
| MLflow eksperimentas | `airbnb-superhost` |
| Duomenys | 20 CSV iš Hugging Face `kraina/airbnb` (fiksuota revizija), DVC rodyklė `data/raw.dvc` (2 žingsnis) |
| DVC remote | `localremote`: autoriaus kompiuterio katalogas, kitur nepasiekiamas |
| Paskutinio run'o testo metrikos | `metrics.json` (`dvc metrics show`) |
| Mokymo vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-71249941` (viešas), 9 žingsnis |
| Mokymas klasteryje (E2) | Job `train` ir ConfigMap `training-config` (`k8s/jobs/`), 10 žingsnis |
| Reikalavimai ir KPI | [`docs/requirements.md`](docs/requirements.md) v1.4 |
| Architektūra | [`docs/architecture.md`](docs/architecture.md) |
| Vaizdo dydis, digest, Trivy | [`docs/image-sizes.md`](docs/image-sizes.md), [`docs/security-scan.md`](docs/security-scan.md) |
| Ataskaita | [`docs/u1-report.md`](docs/u1-report.md) |

## Repo struktūra

| Kelias | Turinys |
|---|---|
| `src/` | pipeline'o stage'ai: `data_prep.py`, `train.py`, `eval.py` |
| `dvc.yaml`, `dvc.lock` | pipeline'as ir paskutinio paleidimo hash'ai |
| `params.yaml` | hiperparametrai (`train.n_estimators`, `train.max_depth`, `train.random_seed`) |
| `metrics.json`, `models/run_id.txt` | paskutinio run'o testo metrikos ir MLflow `run_id`; commit'inami |
| `data/raw.dvc` | 20 CSV rodyklė (patys duomenys DVC remote, ne Git) |
| `reproduce.py` | istorinio run'o atkūrimas pagal `run_id` |
| `requirements-train.txt`, `requirements.txt`, `requirements-dev.txt` | mokymo priklausomybės (jas diegia ir Docker vaizdas, su `mlflow-skinny`); plius pilnas `mlflow`; plius DVC. Tiesioginės priklausomybės fiksuotos `==` |
| `shell.nix` | Nix aplinka (nebūtina): Python 3.12, kind, kubectl, Trivy, gh |
| `docker/Dockerfile.train`, `.dockerignore` | mokymo vaizdas |
| `scripts/publish.sh` | vaizdo publikavimas į GHCR |
| `k8s/kind-config.yaml`, `k8s/namespace.yaml` | klasterio konfigūracija ir namespace |
| `k8s/mlflow/` | Postgres ir MLflow: PVC, Deployment, Service |
| `k8s/jobs/` | E2: ConfigMap (MLflow adresas, hiperparametrai) ir mokymo Job |
| `docs/` | reikalavimai, architektūra, vaizdo dydis, Trivy ataskaita ir SBOM (`trivy-train.json`, `sbom-train.json`), U1 ataskaita |

## Reikalavimai

Išbandyta Linux'e (NixOS 26.05):

| Įrankis | Versija |
|---|---|
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 (diegiamas su `requirements-dev.txt`) |
| [Trivy](https://trivy.dev/), [gh](https://cli.github.com/) | 0.72.0, 2.102.0 (tik 9 žingsniui) |
| git, curl | bet kokia |

Klasteriui reikia apie 4 GB laisvos RAM, o kompiuterio 5000 portas turi būti laisvas. Python 3.12 galima gauti trimis
būdais, toliau žingsniai tie patys:

- sistemos `python3.12`;
- distribucijoje tik su naujesniu Python (pvz. Arch, CachyOS): 1 žingsnyje `uv venv --seed --python 3.12 .venv`
  vietoje `python3.12 -m venv .venv` (`uv` diegiamas iš distribucijos paketų, `--seed` į venv įdeda `pip`);
- su Nix: `nix-shell` repo šaknyje duoda Python 3.12, kind, kubectl, Trivy ir gh iš fiksuotos nixpkgs revizijos
  (`shell.nix`). Docker visada iš sistemos.

## Paleidimas nuo nulio

Visos komandos vykdomos repo šaknyje, viename terminale.

### 1. Repo ir Python aplinka

```bash
git clone https://github.com/lukasja111/mlops-u1.git && cd mlops-u1
python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
```

Su Nix tarp šių eilučių paleiskite `nix-shell`. Kiekviename naujame terminale aplinką aktyvuokite iš naujo:
`. .venv/bin/activate` (su Nix pirma `nix-shell`).

### 2. Duomenys

Pipeline'as duomenų pats nesiunčia: `data/raw/` užpildomas vieną kartą.

- **A: autoriaus kompiuteryje** užtenka `dvc pull`. Remote `localremote` yra to kompiuterio katalogas, todėl kitur
  `dvc pull` baigiasi klaida.
- **B: bet kuriame kompiuteryje** tie patys 20 CSV atsisiunčiami iš fiksuotos Hugging Face revizijos:

```bash
mkdir -p data/raw
for c in amsterdam athens barcelona berlin budapest lisbon london paris rome vienna; do
  for d in weekdays weekends; do
    curl -fsSL -o "data/raw/${c}_${d}.csv" \
      "https://huggingface.co/datasets/kraina/airbnb/resolve/b9dd71fc8f175b645ce47f87c702492a6128c4dd/data/${c}_${d}.csv"
  done
done
dvc commit -f data/raw.dvc
git diff --exit-code data/raw.dvc && echo "duomenys sutampa"
```

`dvc commit` suskaičiuoja katalogo md5 ir įdeda failus į DVC cache (jo reikia `reproduce.py`). `duomenys sutampa`
reiškia, kad md5 sutampa su `data/raw.dvc` (`a2b156db54022d6fe3c950258a5d5c9a.dir`): tai tie patys duomenys, su
kuriais mokyti autoriaus run'ai. Jei `git diff` rodo pakeitimą, failai skiriasi. `dvc push` veiks tik su savu remote:
`dvc remote modify --local localremote url /jusu/katalogas` (įrašoma į `.dvc/config.local`, kuris į Git nepatenka).

### 3. Klasteris ir MLflow

```bash
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f k8s/namespace.yaml
PG_PASSWORD=$(python -c 'import secrets; print(secrets.token_hex(16))')
kubectl -n mlops-u1 create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=mlflow \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --from-literal=POSTGRES_DB=mlflow
kubectl apply -f k8s/mlflow/
kubectl -n mlops-u1 rollout status deploy/postgres --timeout=180s
kubectl -n mlops-u1 rollout status deploy/mlflow --timeout=300s
until curl -sf http://127.0.0.1:5000/health; do sleep 2; done; echo
```

Paskutinė komanda laukia, kol MLflow atsako `OK`. Pirmą kartą tai užtrunka kelias minutes, nes klasteris atsisiunčia
Postgres ir MLflow vaizdus. UI: http://127.0.0.1:5000.

- `kind create cluster` sukuria kontekstą `kind-mlops-u1` ir į jį persijungia. Turint kelis klasterius:
  `kubectl config use-context kind-mlops-u1`.
- Secret kuriamas komanda, todėl slaptažodis į Git nepatenka. Peržiūrėti:
  `kubectl -n mlops-u1 get secret postgres-credentials -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d`. MLflow
  slaptažodį gauna aplinkos kintamuoju `PGPASSWORD`, todėl jo nerodo nei `ps`, nei `kubectl describe`.
- Run'ai ir artefaktai išlieka perkūrus Pod'us, nes Postgres duomenys ir artefaktai yra PVC. Patikrinti:
  `kubectl -n mlops-u1 delete pod -l app=mlflow`; kai naujas Pod'as parengtas, UI rodo tuos pačius run'us.
- Jei NodePort neveikia: `kubectl -n mlops-u1 port-forward svc/mlflow 5050:5000` → http://127.0.0.1:5050 (tada ir
  `export MLFLOW_TRACKING_URI=http://127.0.0.1:5050`). Kompiuteris be naršyklės: `ssh -L 5000:localhost:5000 <host>`.

### 4. MLflow adresas

```bash
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
```

Nustatykite kiekviename naujame terminale, kartu su `. .venv/bin/activate`. Be jo `train.py` iškart baigiasi klaida
(`MLFLOW_TRACKING_URI wasn't set properly`), todėl run'ai nepatenka į vietinį `mlruns/`, tik į klasterio MLflow.

### 5. Pipeline'as

```bash
dvc repro --force
git commit -am "exp: pirmas run'as savame klasteryje"
```

| Stage'as | Skaito | Rašo |
|---|---|---|
| `prepare` | `data/raw/` (20 CSV) | `data/processed/train.csv` ir `test.csv`: imtys skaidomos pagal skelbimą (`city`, `lat`, `lng`), todėl tas pats skelbimas nepatenka į abi (NFR-01a) |
| `train` | `train.csv`, `test.csv`, visas `params.yaml` | `models/model.pkl`, `models/run_id.txt`; MLflow run'as su parametrais, `accuracy` ir `f1`, modeliu, mokymo duomenų rinkiniu ir tag'ais `git_commit`, `dvc_raw_md5` |
| `evaluate` | modelis, `run_id.txt`, `test.csv` | `metrics.json`; tame pačiame run'e `eval/*` metrikos ir artefaktai `eval/feature_importances.json`, `eval/confusion_matrix.json` |

Visas pipeline'as trunka apie 20 s; išvestyje yra `run_id=…` (jo reikės 8 žingsnyje).

- `--force`: po `dvc pull` visos išvestys sutampa su `dvc.lock` ir be jo DVC viską praleistų, o naujame klasteryje
  MLflow tuščias.
- Commit'as reikalingas, nes `reproduce.py` reikalauja švaraus darbo medžio.

## 6. Kur žiūrėti rezultatus

- MLflow UI (http://127.0.0.1:5000) → eksperimentas `airbnb-superhost`: run'ai `rf-n<n_estimators>-d<max_depth>`,
  metrikos `f1` (pagrindinė), `accuracy` ir `eval/*`, artefaktai `eval/feature_importances.json` ir
  `eval/confusion_matrix.json`, tag'ai `git_commit` ir `dvc_raw_md5`, modelis. Autoriaus serveryje seni run'ai (prieš
  nutekėjimo taisymą) pažymėti `split=random`.
- Terminale: `dvc metrics show`; palyginimas su ankstesniu eksperimentu: `dvc metrics diff <commit>`,
  `dvc params diff <commit>`.
- KPI ir išmatuotos reikšmės: `docs/requirements.md`.

## 7. Naujas eksperimentas

```bash
# params.yaml: pakeiskite hiperparametrą, pvz. train.max_depth 15 -> 10
dvc status                             # train: changed deps, params.yaml: modified
dvc repro                              # persileidžia tik train ir evaluate (prepare nuo params nepriklauso)
dvc params diff && dvc metrics diff
git commit -am "exp: max_depth 10"
dvc push                               # tik su savu remote (2 žingsnis)
```

- `dvc.lock` pasikeičia: `train` params reikšmė ir `models/model.pkl`, `models/run_id.txt`, `metrics.json` md5;
  `prepare` įrašas lieka toks pat.
- Antras `dvc repro` be pakeitimų nieko neperskaičiuoja (`didn't change, skipping`).
- **Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`:** run'o `git_commit` tag'as yra HEAD mokymo metu, o
  `reproduce.py` atkuria būtent tą commit'ą. Keičiant tik `params.yaml` iš anksto commit'inti nereikia:
  `reproduce.py` hiperparametrus ima iš run'o.

## 8. Istorinio run'o reprodukcija

```bash
git status                             # švarus darbo medis, esate šakoje (main)
time python reproduce.py <run_id>      # ≤ 2 min, |Δaccuracy| ≤ 0,005, |Δf1| ≤ 0,005
```

`<run_id>`: 5 žingsnio išvestyje (`run_id=…`) arba MLflow UI; `models/run_id.txt` rodo tik paskutinį run'ą. Naujame
klasteryje atkurkite savo run'ą: autoriaus run'ų jame nėra.

`reproduce.py`: paima run'ą iš MLflow → `git checkout <git_commit>` → `dvc checkout` žalių duomenų → run'o
hiperparametrai į `params.yaml` → `dvc repro --force` → palygina metrikas, naujam run'ui uždeda tag'ą
`reproduces=<run_id>` → grąžina repo į pradinę šaką. Grąžindamas jis daro `git checkout --force`, todėl necommit'inti
pakeitimai dingtų: dėl to reikia švaraus darbo medžio. Pavyzdys (`rf-n100-d5`):

```
accuracy: original=0.7121 reproduced=0.7121 delta=0.0000
f1: original=0.5947 reproduced=0.5947 delta=0.0000
REPRODUCED in 20s -> new run 4fbc102c1ee841c181489d5ba145deca
```

## 9. Mokymo Docker vaizdas

Publikuotas vaizdas pasileidžia be build'o ir log'ina run'ą į klasterio MLflow:

```bash
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 ghcr.io/lukasja111/mlops-u1/train:sha-71249941
```

Savam vaizdui reikia Trivy ir gh (`gh auth login --scopes write:packages`):

```bash
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 mlops-u1/train:sha-$SHA

trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json mlops-u1/train:sha-$SHA
trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
trivy image -f spdx-json -o docs/sbom-train.json mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```

- Vaizdas kopijuoja `data/processed/`, todėl prieš `docker build` reikia `dvc pull` arba `dvc repro`.
- Tag'as `sha-<8 simboliai>` sutampa su MLflow `git_commit` tag'u ir vaizdo `org.opencontainers.image.revision`
  žyme; `latest` nenaudojamas. Kitas commit'as duoda kitą tag'ą, todėl Trivy komandos kartojamos.
- Trivy komandos perrašo commit'intus `docs/trivy-train.json` ir `docs/sbom-train.json`: naujus commit'inkite arba
  atkurkite `git checkout -- docs/` (prieš `reproduce.py`, nes jis daro `git checkout --force`).
- `--network host` veikia Linux'e; kitur `-e MLFLOW_TRACKING_URI=http://host.docker.internal:5000`.
- `scripts/publish.sh` (reikia `gh` ir `trivy`): CRITICAL vartas, prisijungimas prie GHCR su `gh` token'u, push ir
  digest. Naujas GHCR paketas būna privatus: viešu jį padaro GitHub → Packages → Package settings.
- Publikuoto vaizdo dydis, digest ir Trivy rezultatai: `docs/image-sizes.md`, `docs/security-scan.md`.

## 10. Mokymas kaip Kubernetes Job (E2)

```bash
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Job'as paleidžia viešą GHCR vaizdą `sha-71249941`, todėl nieko kurti ar įkelti į kind nereikia. Jo run'o
`git_commit` tag'as yra vaizdo commit'as.

- Tag'as yra commit'as, iš kurio vaizdas sukurtas, o ne dabartinis HEAD: manifestas negali nurodyti commit'o, kuriame
  pats įrašytas. Naujam vaizdui: sukurti ir publikuoti (9 žingsnis), tada pakeisti `image:` `k8s/jobs/job-train.yaml`.
- MLflow pasiekiamas per `http://mlflow:5000` (ConfigMap); todėl MLflow paleistas su `--allowed-hosts`, kitaip
  atsakytų `403 Invalid Host header`.
- Hiperparametrai `N_ESTIMATORS` ir `MAX_DEPTH` yra ConfigMap `training-config`; Job'as juos perduoda `train.py`
  argumentais (`args` pakeičia vaizdo `CMD`). ConfigMap skaitomas paleidžiant Pod'ą, todėl pakeitimas galioja kitam
  Job'ui:

  ```bash
  sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
  kubectl apply -f k8s/jobs/configmap-training.yaml
  kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
  kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
  ```

- Job'ai nekeičiami: pakartotinai paleisti `kubectl -n mlops-u1 delete job train` ir vėl tas pats `apply`.
- Išbandyta: run'as `bb5f031f` su `git_commit=71249941` davė tas pačias metrikas kaip `dvc repro` (0,7764 / 0,6298),
  o su `MAX_DEPTH: "10"` run'as `64eda7cc` davė tas pačias kaip gylio 10 run'as (0,7440 / 0,6181). Vaizdas
  atsisiųstas per 2,2 s; Job'as su jau atsisiųstu vaizdu baigėsi per 20 s.

## Išvalymas

```bash
kind delete cluster --name mlops-u1
```

Postgres ir MLflow artefaktų PVC išlieka perkūrus Pod'ą, bet dingsta ištrynus klasterį.

## Problemų sprendimas

| Simptomas | Priežastis ir sprendimas |
|---|---|
| `python3.12: command not found` | Distribucijoje tik naujesnis Python (pvz. Arch, CachyOS): `uv venv --seed --python 3.12 .venv` arba `nix-shell` (žr. „Reikalavimai“) |
| `ImportError: libstdc++.so.6: cannot open shared object file` | Python iš Nix, bet venv naudojamas ne `nix-shell` viduje: paleiskite `nix-shell` (`shell.nix` nustato `LD_LIBRARY_PATH`) |
| `permission denied while trying to connect to the Docker daemon socket` | Naudotojas ne `docker` grupėje: `sudo usermod -aG docker $USER`, tada atsijunkite ir vėl prisijunkite |
| `dvc: command not found` arba `ModuleNotFoundError` per `dvc repro` | Neaktyvuotas venv: `. .venv/bin/activate` |
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `403 Invalid Host header` | Host'o nėra MLflow `--allowed-hosts` sąraše (`k8s/mlflow/deployment-mlflow.yaml`) |
| `curl 127.0.0.1:5000` atmeta ryšį | Klasteris sukurtas be `k8s/kind-config.yaml` (portai nustatomi tik kuriant: ištrinkite ir sukurkite iš naujo) arba MLflow Pod'as dar neparengtas (`kubectl -n mlops-u1 get pods`) |
| macOS: 5000 portas užimtas | Jį naudoja AirPlay Receiver: išjunkite jį arba `k8s/kind-config.yaml` pakeiskite `hostPort` (pvz. 5001) ir atitinkamai `MLFLOW_TRACKING_URI` |
| Postgres Pod'as `CrashLoopBackOff` | Secret sukurtas su tuščiu slaptažodžiu (`PG_PASSWORD` nenustatytas): `kubectl -n mlops-u1 delete secret postgres-credentials`, sukurkite jį iš naujo ir ištrinkite abu Pod'us (`-l app=postgres`, `-l app=mlflow`) |
| `dvc repro` nieko nedaro naujame klasteryje | Po `dvc pull` išvestys sutampa su `dvc.lock`: `dvc repro --force` |

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE).
