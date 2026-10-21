# Airbnb hostų klasifikatorius į superhostus: U1 MLOps projekto paleidimo instrukcijos
Išbandyta Linux sistemose (CachyOS (su ir be [nix](https://nixos.org/download/#nix)) bei NixOS 26.05)

- Portai: MLflow http://127.0.0.1:5000 (kind NodePort 30500, tik `127.0.0.1`); Postgres tik klasterio viduje, `postgres:5432`.
- Prisijungimai: MLflow be prisijungimo; Postgres naudotojas ir slaptažodis Secret `postgres-credentials` (3 žingsnis).
- Rezultatai: MLflow eksperimentas `airbnb-superhost`, `metrics.json`, KPI `docs/requirements.md` (5 žingsnis).

## Reikalavimai

- `4 GB` laisvos greitai prieinamos atminties (RAM'o).
- Atlaisvintas `5000` portas.

| Software | Versija |
|---|---|
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 (diegiamas su `requirements.txt`) |
| [Trivy](https://trivy.dev/), [gh](https://cli.github.com/) | 0.72.0, 2.102.0 (tik 7 žingsniui) |
| git, curl | bet kokia |


## Paleidimas nuo nulio.
> [!TIP]
> Žemiau surašytos komandos tinkamos CachyOS ar daugeliui kitų *Arch-based* distribucijų. Jei naudojate pvz. Ubuntu, Debian, gali skirtis reikalavimų atsisiuntimo procesas.
> Rekomenduojama naudoti [nix](https://nixos.org/download/#nix) lengvesniam ir sklandžiam darbui aplinkoje.

### 0.A Reikalavimų instaliacija su Nix package manageriu
Su Nix viską, išskyrus Docker, duoda `shell.nix`. Venv (1 žingsnis) kurkite ir naudokite `nix-shell` viduje, kitaip Python wheel'ams trūks `libstdc++`.
```bash
nix-shell
```

### 0.B Reikalavimų instaliacija su Pacman package manageriu
Arch-based sistemoms, ant Debian/Ubuntu sistemų, priklausomai nuo package manageriu gali atrodyti kitaip.

```sh
sudo pacman -S --needed docker docker-buildx kind kubectl uv
```

### 1. Repo, įrankiai ir Python aplinka

Repozitorijis klonavimas ir python aplinkos paruošimas.
```bash
git clone https://github.com/lukasja111/mlops-u1.git
cd mlops-u1
python3.12 -m venv .venv 
source .venv/bin/activate 
pip install -r requirements.txt
```

> [!WARNING]
> Jei `python3.12` nėra (Arch), tą patį daro `uv`:
> ```bash
> uv venv --seed --python 3.12 .venv
> source .venv/bin/activate 
> pip install -r requirements.txt
> ```

### 2. Duomenų atsisiuntimas

```bash
curl -fsSL --create-dirs -o "data/raw/#1_#2.csv" \
  "https://huggingface.co/datasets/kraina/airbnb/resolve/b9dd71fc8f175b645ce47f87c702492a6128c4dd/data/{amsterdam,athens,barcelona,berlin,budapest,lisbon,london,paris,rome,vienna}_{weekdays,weekends}.csv"
dvc commit -f data/raw.dvc
```

> [!TIP]
> Komanda patikrinti, jog duomenys yra byte-identical. Sėkmingu atveju atprintinama į terminalą: "duomenys sutampa".
> ```sh
> git diff --exit-code data/raw.dvc && echo "duomenys sutampa"
> ```

### 3. Klasteris ir MLflow

Priešpaskutinė komanda laukia, kol MLflow pasileis, paskutinė atsako `OK`; pirmą kartą klasteris dar siunčiasi Postgres ir MLflow vaizdus, tai gali užtrukti kelias minutes.
Svetainę galima bus matyti ir pasiekti naršyklėje per `http://127.0.0.1:5000` (jei ant localhosto `5000` portas nėra užimtas).

```bash
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f k8s/namespace.yaml
kubectl -n mlops-u1 create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=mlflow \
  --from-literal=POSTGRES_DB=mlflow \
  --from-literal=POSTGRES_PASSWORD=$(python -c 'import secrets; print(secrets.token_hex(16))')
kubectl apply -f k8s/mlflow/
kubectl -n mlops-u1 rollout status deploy/mlflow --timeout=300s
curl -sf http://127.0.0.1:5000/health; echo
```

### 4. Pipeline: trys run'ai

Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`: run'o `git_commit` tag'as yra HEAD mokymo metu, ir `reproduce.py` atkuria būtent jį.

```sh
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
sed -i 's/max_depth: 15/max_depth: 5/' params.yaml
dvc repro --force
git commit -am "max_depth 5 run"

sed -i 's/max_depth: 5/max_depth: 10/' params.yaml
dvc status
dvc repro
dvc params diff && dvc metrics diff
git commit -am "max_depth 10 run"

sed -i 's/max_depth: 10/max_depth: 15/' params.yaml
dvc repro
git commit -am "max_depth 15 run"
```

`dvc status` rodo pasikeitusį `train` parametrą. `dvc repro` iš naujo paleidžia tik `train` ir `evaluate`, nes `prepare` nuo `params.yaml` nepriklauso; `dvc.lock` pasikeičia `train` parametro reikšmė ir `model.pkl`, `run_id.txt`, `metrics.json` md5.
Jei turite savo DVC remote (`dvc remote modify --local localremote url /jusu/katalogas`), po run'o dar paleiskite `dvc push`.

### 5. Rezultatų tikrinimas

- MLflow UI (http://127.0.0.1:5000), eksperimentas `airbnb-superhost`, run'ai vadinasi `rf-n<n_estimators>-d<max_depth>`. Pagrindinė metrika `f1`, šalia `accuracy`, `eval/*`, artefaktai, modelis ir tag'ai.
- Terminale metrikas rodo `dvc metrics show`; su ankstesniu commit'u palygina `dvc metrics diff <commit>` ir `dvc params diff <commit>`.
- KPI ir išmatuotos reikšmės: `docs/requirements.md`.
- Imtys nesidalija skelbimais (NFR-01a), komanda turi išvesti `0`:

```sh
python -c "
import pandas as pd
train, test = pd.read_csv('data/processed/train.csv'), pd.read_csv('data/processed/test.csv')
print(len(set(zip(train.lat, train.lng)) & set(zip(test.lat, test.lng))))"
```

### 6. Istorinio run'o reprodukcija

Reikia švaraus darbo medžio ir šakos, nes skriptas pabaigoje daro `git checkout --force`; `<run_id>` yra 4 žingsnio išvestyje arba MLflow UI.

```sh
time python reproduce.py <run_id>
```

Pavyzdys su `rf-n100-d15`:

```
accuracy: original=0.7833 reproduced=0.7833 delta=0.0000
f1: original=0.6393 reproduced=0.6393 delta=0.0000
REPRODUCED in 22s -> new run 1f02d0d1274447bd8e22231e5aac62e4
```

### 7. Mokymo Docker vaizdas

Publikuotas vaizdas pasileidžia be build'o ir log'ina run'ą į klasterio MLflow:

```sh
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 ghcr.io/lukasja111/mlops-u1/train:sha-08fbb275
```

Savas vaizdas: build, bandomasis run'as, Trivy, SBOM ir publikavimas į GHCR (reikia Trivy ir `gh auth login --scopes write:packages`):

```sh
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 mlops-u1/train:sha-$SHA

trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json mlops-u1/train:sha-$SHA
trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
trivy image -f spdx-json -o docs/sbom-train.json mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```

### 8. Mokymas kaip Kubernetes Job

Job'as traukia viešą GHCR vaizdą `sha-08fbb275`, todėl jo run'o `git_commit` yra vaizdo commit'as, ne HEAD (savam vaizdui atlikite 7 žingsnį ir pakeiskite `image:` faile `k8s/jobs/job-train.yaml`). ConfigMap `training-config` duoda Job'ui MLflow adresą `http://mlflow:5000` ir hiperparametrus `N_ESTIMATORS`, `MAX_DEPTH`.

```sh
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Sukurto Job'o keisti negalima, todėl kitam gyliui reikia naujo Job'o. Su `MAX_DEPTH: "10"` run'as duoda tas pačias metrikas kaip gylio 10 `dvc repro` run'as:

```sh
sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
kubectl apply -f k8s/jobs/configmap-training.yaml
kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
```

## Išvalymas

```sh
kind delete cluster --name mlops-u1
```

PVC išlieka perkūrus Pod'us, bet dingsta kartu su klasteriu. Po kompiuterio perkrovimo klasterį pakelia `docker start mlops-u1-control-plane`; po minutės Pod'ai vėl Running, run'ai vietoje.

## Dažnos klaidos ir jų sprendimai

| Klaida | Priežastis ir sprendimas |
|---|---|
| `permission denied while trying to connect to the Docker daemon socket` | Naudotojas ne `docker` grupėje: `sudo usermod -aG docker $USER`, tada atsijunkite ir vėl prisijunkite |
| `dvc: command not found`, `ModuleNotFoundError` arba `.venv/bin/activate: Permission denied` | Neaktyvuotas venv arba failas paleistas kaip programa: `source .venv/bin/activate` (be `sudo`) |
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `curl 127.0.0.1:5000` atmeta ryšį arba portas užimtas | Persiuntimas 5000 → 30500 nustatomas tik kuriant klasterį su `k8s/kind-config.yaml`; jei Pod'as dar neparengtas, žr. `kubectl -n mlops-u1 get pods`. Užimtą portą (macOS AirPlay) keiskite `hostPort` tame pačiame faile ir `MLFLOW_TRACKING_URI` |

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE). + co-authored su Claude.
