Repo URL: <https://github.com/lukasja111/mlops-u1>

Tag: `u2-final`

Paleidimas: Žemiau pateiktos instrukcijos.

# Airbnb hostų klasifikatorius į superhostus: U2 MLOps projekto paleidimo instrukcijos
Išbandyta NixOS 26.05 ir CachyOS su [nix](https://nixos.org/download/#nix).

Portai:
- MLflow: 5000 (localhost, 127.0.0.1)
- Kind node: 30500
- API: 30800 (per mazgo IP, 9 žingsnis)
- Postgres (tik klasterio viduje): 5432

Useriai: `admin`, `trainer`, `serving`, `viewer`. Slaptažodžiai yra secret `mlflow-auth` ir `mlflow-<naudotojas>-credentials` (3 žingsnis). Postgres naudotojas ir slaptažodis Secret `postgres-credentials`.

Rezultatai: MLflow eksperimentas ir registruotas modelis `airbnb-superhost` (`@champion`, `@benched`), `metrics.json`, `docs/load-test.json`, KPI `docs/requirements.md`, ataskaita `docs/u2-report.md`.

## Reikalavimai

- `6 GB` laisvos greitai prieinamos atminties.

| Software | Versija |
|---|---|
| git, curl | bet kokia |
| bash arba zsh | bet kokia |
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 |
| [Trivy](https://trivy.dev/) | 0.72.0 (tik 7 žingsniui) |



## Paleidimas nuo nulio.
> [!WARNING]
> Komandos atliekamos nuo nulio naudojant `bash` arba `zsh` *visais atvejais*.
> Žemiau surašytos komandos tinkamos CachyOS ar daugeliui kitų *Arch-based* distribucijų. Jei naudojate pvz. Ubuntu, Debian, gali skirtis reikalavimų atsisiuntimo procesas.
> Rekomenduojama naudoti [nix](https://nixos.org/download/#nix) lengvesniam ir sklandžiam darbui aplinkoje.

### 0.A Reikalavimų instaliacija su Nix package manageriu
Su Nix viską, išskyrus Docker, duoda `shell.nix`; `nix-shell` kartu atidaro `bash`. Venv (1 žingsnis) kurkite ir naudokite `nix-shell` viduje, kitaip Python wheel'ams trūks `libstdc++`. Tokiu atveju, po žemiau paminėto 1. etapo, atkloninus repozitoriją ir nuėjus į ją runninkit `nix-shell`.
```bash
nix-shell
```

### 0.B Reikalavimų instaliacija su Pacman package manageriu
Arch-based sistemoms, ant Debian/Ubuntu sistemų, priklausomai nuo package managerio gali atrodyti kitaip.

```sh
sudo pacman -S --needed docker docker-buildx kind kubectl uv trivy
```

### 1. Repo, įrankiai ir Python aplinka

```sh
git clone https://github.com/lukasja111/mlops-u1.git
cd mlops-u1
```

Python aplinka
```sh
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

### 3. Klasteris, MLflow ir prisijungimai

Šis etapas gali užtrukti kelias minutes, nes klasteriui reikia atsiust Postgres ir MLflow image.
MLflow secret `mlflow-auth` turi `admin` slaptažodį ir Flask raktą, todėl kuriamas prieš `kubectl apply -f k8s/mlflow/`.

```bash
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f k8s/namespace.yaml
kubectl -n mlops-u1 create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=mlflow \
  --from-literal=POSTGRES_DB=mlflow \
  --from-literal=POSTGRES_PASSWORD=$(python -c 'import secrets; print(secrets.token_hex(16))')
ADMIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
kubectl -n mlops-u1 create secret generic mlflow-auth \
  --from-literal=flask-secret-key=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
  --from-literal=basic_auth.ini="[mlflow]
default_permission = READ
database_uri = postgresql://mlflow@postgres:5432/mlflow
admin_username = admin
admin_password = $ADMIN_PASSWORD
authorization_function = mlflow.server.auth:authenticate_request_basic_auth"
kubectl apply -f k8s/mlflow/
kubectl -n mlops-u1 rollout status deploy/mlflow --timeout=300s
curl -sf http://127.0.0.1:5000/health; echo
```

> [!TIP]
> MLflow pasiekiamas jau po šio etapo `http://127.0.0.1:5000`

Kiti useriai
- `trainer` (run'ų loginimui ir t.t.)
- `serving` (API)
- `viewer` (UI)
```bash
ADMIN_PASSWORD=$(kubectl -n mlops-u1 get secret mlflow-auth -o jsonpath='{.data.basic_auth\.ini}' | base64 -d | sed -n 's/^admin_password = //p')
for user in trainer serving viewer; do
  password=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  curl -sf -u "admin:$ADMIN_PASSWORD" -H 'Content-Type: application/json' \
    -d "{\"username\": \"$user\", \"password\": \"$password\"}" \
    http://127.0.0.1:5000/api/2.0/mlflow/users/create > /dev/null
  kubectl -n mlops-u1 create secret generic mlflow-$user-credentials \
    --from-literal=MLFLOW_TRACKING_USERNAME=$user \
    --from-literal=MLFLOW_TRACKING_PASSWORD=$password
done
```

### 4. Hyperparameter optimization (HPO)

`params.yaml` skyrius `hpo`: Optuna per 20 bandymų renka [`n_estimators`, `max_depth`, `min_samples_leaf`]. Kryžminė validacija. 

```sh
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export MLFLOW_TRACKING_USERNAME=trainer
export MLFLOW_TRACKING_PASSWORD=$(kubectl -n mlops-u1 get secret mlflow-trainer-credentials -o jsonpath='{.data.MLFLOW_TRACKING_PASSWORD}' | base64 -d)
dvc repro && git commit -am "HPO run"
```


### 5. Rezultatų tikrinimas

> [!TIP]
> MLflow UI (http://127.0.0.1:5000) prašo prisijungimo: naudotojas `viewer`, slaptažodį išveda žemiau esanti komanda.
> ```sh
> kubectl -n mlops-u1 get secret mlflow-viewer-credentials -o jsonpath='{.data.MLFLOW_TRACKING_PASSWORD}' | base64 -d; echo
> ```

> [!TIP]
> Per CLI galima matyti metrikas ir palyginti su ankstesnėmis:
> ```sh
> dvc metrics show
>
> dvc metrics diff <commit>
> dvc params diff <commit>
> ```


Žemiau esanti komanda turi išvesti `0`:
```sh
python -c "
import pandas as pd
train, test = pd.read_csv('data/processed/train.csv'), pd.read_csv('data/processed/test.csv')
print(len(set(zip(train.lat, train.lng)) & set(zip(test.lat, test.lng))))"
```

### 6. Istorinio run'o reprodukcija

```sh
time python reproduce.py <run_id>
```
> [!TIP]
> `run_id` galima susirasti per MLflow


### 7. Docker vaizdai: build, Trivy ir kind

Trivy perrašo `docs/trivy-api.json` (HIGH ir CRITICAL ataskaita). Docker kešas gali palikti seną `apt-get upgrade` sluoksnį su jau pataisytais CVE; tada `docker build --no-cache`. Mokymo vaizdo U1 aprašas: `docs/docker-image.md`.

```bash
SHA=$(git rev-parse --short=8 HEAD)
for image in api train; do
  docker build -f docker/Dockerfile.$image --build-arg GIT_COMMIT=$SHA -t mlops-u1/$image:sha-$SHA . &&
  trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/$image:sha-$SHA &&
  kind load docker-image mlops-u1/$image:sha-$SHA --name mlops-u1 || break
done
trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-api.json mlops-u1/api:sha-$SHA
sed -i "s/newTag: .*/newTag: sha-$SHA/; s/IMAGE_TAG=.*/IMAGE_TAG=sha-$SHA/" k8s/serving/kustomization.yaml
sed -i "s|image: mlops-u1/train:.*|image: mlops-u1/train:sha-$SHA|" k8s/jobs/job-train.yaml
git commit -am "Images sha-$SHA"
```

### 8. Mokymas kaip Kubernetes Job

```sh
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

```sh
sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
kubectl apply -f k8s/jobs/configmap-training.yaml
kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
git checkout -- k8s/jobs/configmap-training.yaml
```

### 9. Registras ir API ci-cd

`scripts/ci-cd.sh` paleidžia visą grandinę. Reikia 4 žingsnio prisijungimų ir 7 žingsnio vaizdų.

```
ruff → pytest → dvc repro → gate.py → promote.py register → @champion → MODEL_VERSION → kubectl apply -k → rollout status → smoke
```

```sh
bash scripts/ci-cd.sh
```

Vartas `scripts/gate.py` lygina `metrics.json` su `params.yaml` skyriumi `gate`: `min_f1: 0.62`, `min_accuracy: 0.75`.
Praėjęs modelis registruojamas kaip nauja `airbnb-superhost` versija ir gauna `@champion`. Buvęs čempionas tampa `@benched`. Versijos tag'ai: `git_commit`, `dvc_raw_md5`, `accuracy`, `f1`, `gate=passed`. Tas pats run'as antrą kartą neregistruojamas.

API tikrinamas per mazgo IP:
```sh
NODE=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
curl -s http://$NODE:30800/health; echo
curl -s -X POST -H 'Content-Type: application/json' -d @docs/predict-request.json http://$NODE:30800/predict; echo
python scripts/load_test.py http://$NODE:30800 --out docs/load-test.json
```

Rezultatai: `docs/load-test.json`.
Swaggeri naršyklėje: `http://<mazgo IP>:30800/docs`

### 10. Raudoni paleidimai

Abiem atvejais `ci-cd.sh` baigiasi `quality gate failed: nothing registered or deployed` ir išėjimo kodu 1, o `@champion` ir API nesikeis.

Pvz.
Griežtesnis slenkstis:
```sh
sed -i 's/min_f1: 0.62/min_f1: 0.99/' params.yaml
bash scripts/ci-cd.sh
git checkout -- params.yaml
```

Blogas modelis (`max_depth: 5` be paieškos):
```sh
sed -i 's/max_depth: 15/max_depth: 5/; s/n_trials: 20/n_trials: 0/' params.yaml
bash scripts/ci-cd.sh
git checkout -- params.yaml dvc.lock metrics.json models/run_id.txt
dvc checkout --force
```

### 11. Antra versija, rollback naudojimas

Rollback'ui reikia dviejų versijų, todėl pirma daromas antras žalias paleidimas su 3 grupių CV.

```sh
sed -i 's/cv_folds: 5/cv_folds: 3/' params.yaml
git commit -am "HPO with 3 folds"
bash scripts/ci-cd.sh
time bash scripts/ci-cd.sh rollback
time bash scripts/ci-cd.sh rollback
```

### 12. CI workflow (Paleidimai)
- Žalias paleidimas: <https://github.com/lukasja111/mlops-u1/actions/runs/43011607138>
- Raudonas paleidimas: <https://github.com/lukasja111/mlops-u1/actions/runs/43013796244>

`.github/workflows/ci-cd.yml` pasileidžia GitHub Actions po pusho į main.
Pasileidžia: `lint`, `test`, `model-gate`, `build`, - gale vaizdai keliami į GHCR.

Raudonas paleidimas:
```sh
gh workflow run ci-cd.yml -f min_f1=0.99
```

> [!TIP]
> Rankiniam paleidimui reikia `gh` prisijungimo su rašymo teise į repozitoriją tai parequestinkit arba ne kzn.

### 13. GPU mokymas (E1)

`src/train_gpu.py` moko PyTorch MLP tais pačiais duomenimis ir log'ina į tą patį MLflow. 
`--amp` įjungia mišrų tikslumą.
Išbandyta atskirame kompiuteryje su NVIDIA GPU.

Kompiuteryje su NVIDIA GPU, tame pačiame terminale po 4 žingsnio:
```sh
pip install -r requirements-gpu.txt --extra-index-url https://download.pytorch.org/whl/cu132
python src/train_gpu.py
python src/train_gpu.py --amp
python src/train_gpu.py --hidden 4096 --batch-size 8192 --epochs 200
python src/train_gpu.py --hidden 4096 --batch-size 8192 --epochs 200 --amp
```

> [!TIP]
> Jei GPU yra kitame kompiuteryje: nukopijuokite `data/processed/*.csv` ir nukreipkite `MLFLOW_TRACKING_URI` į klasterio MLflow per SSH tunelį. Taip gauti ir rezultatai žemiau.

Rezultatai:

| Tinklas | Batch size | Epochs | fp32 | AMP | Accuracy / F1 (fp32) | GPU usage (max) |
|---|---|---|---|---|---|---|
| 256 | 256 | 100 | 26,7 s | 34,6 s | 0,7385 / 0,6083 | 34 % |
| 4096 | 8192 | 200 | 48,3 s | 19,7 s | 0,7498 / 0,6170 | 100 % |


## Išvalymas

Klusterio šalinimas
```sh
kind delete cluster --name mlops-u1
```

> [!TIP]
> Po kompiuterio perkrovimo klasterio trinti nereikia, jį pakelia `docker start mlops-u1-control-plane`.


## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE). + co-authored su Claude.
