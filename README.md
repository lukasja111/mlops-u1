# Airbnb hostų klasifikatorius į superhostus: U1 MLOps projekto paleidimo instrukcijos
Išbandyta Linux sistemose (CachyOS (su ir be [nix](https://nixos.org/download/#nix)) bei NixOS 26.05)

- Portai: MLflow http://127.0.0.1:5000 (kind NodePort 30500, tik `127.0.0.1`); Postgres tik klasterio viduje, `postgres:5432`.
- Prisijungimai: MLflow be prisijungimo; Postgres naudotojas ir slaptažodis Secret `postgres-credentials` (3 žingsnis).
- Rezultatai: MLflow eksperimentas `airbnb-superhost`, `metrics.json`, KPI `docs/requirements.md` (5 žingsnis).

## Reikalavimai

- `4 GB` laisvos atminties.
- Atlaisvintas `5000` portas.


| Software | Versija |
|---|---|
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 (diegiamas su `requirements-dev.txt`) |
| [Trivy](https://trivy.dev/), [gh](https://cli.github.com/) | 0.72.0, 2.102.0 (tik 8 žingsniui) |
| git, curl | bet kokia |


## Paleidimas nuo nulio.

> [!WARNING]
> Žemiau surašytos komandos tinkamos CachyOS ar daugeliui kitų *Arch-based* distribucijų. Jei naudojate pvz. Ubuntu, Debian, gali skirtis reikalavimų atsisiuntimo procesas.
> Rekomenduojama naudoti `nix` lengvesniam darbui aplinkoje.

> [!TIP]
>  Su Nix viską, išskyrus Docker, duoda `shell.nix`.
>  ```bash
> nix-shell
> ```

### 1. Repo, įrankiai ir Python aplinka

Arch-based sistemoms
```sh
sudo pacman -S --needed docker docker-buildx kind kubectl uv
```

```bash
git clone https://github.com/lukasja111/mlops-u1.git && cd mlops-u1
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
```

Jei `python3.12` nėra (Arch), tą patį daro `uv`:
```bash
uv venv --seed --python 3.12 .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
```

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

Priešpaskutinė komanda laukia, kol MLflow pasileis, paskutinė atsako `OK`; pirmą kartą klasteris dar siunčiasi Postgres ir MLflow vaizdus, tai gali užtrukti kelias minutes.
Svetainę galima matyti ir pasiekti naršyklėje per `http://127.0.0.1:5000`.


### 4. Pipeline: pirmas runas

```bash
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
dvc repro --force
git commit -am "pirmas runas savame klasteryje"
```

### 5. Rezultatų tikrinimas

- MLflow UI (http://127.0.0.1:5000), eksperimente `airbnb-superhost` run'ai vadinasi `rf-n<n_estimators>-d<max_depth>`.
  Pagrindinė metrika yra `f1`, šalia jos `accuracy` ir `eval/*`, taip pat artefaktai, modelis ir tag'ai. Autoriaus
  serveryje run'ai iš laikotarpio prieš nutekėjimo taisymą turi tag'ą `split=random`.
- Terminale metrikas rodo `dvc metrics show`. Su ankstesniu commit'u palygina `dvc metrics diff <commit>` ir
  `dvc params diff <commit>`.
- KPI ir išmatuotos reikšmės surašytos `docs/requirements.md`.

### 6. Naujas eksperimentas

> [!WARNING]
> Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`: run'o `git_commit` tag'as yra HEAD mokymo metu, ir
> `reproduce.py` atkuria būtent jį. `params.yaml` gali likti necommit'intas, nes hiperparametrus `reproduce.py` ima iš run'o.

```bash
sed -i 's/max_depth: 15/max_depth: 10/' params.yaml
dvc status
dvc repro
dvc params diff && dvc metrics diff
git commit -am "test: max_depth 10"
```

Matomumas:
`dvc status` rodo pasikeitusį `train` parametrą. `dvc repro` iš naujo paleidžia tik `train` ir `evaluate`, nes `prepare`
nuo `params.yaml` nepriklauso. `dvc.lock` pasikeičia `train` parametro reikšmė ir `model.pkl`, `run_id.txt`,
`metrics.json` md5. Pakartotas `dvc repro` be pakeitimų nieko neperskaičiuoja. Jei turite savo DVC remote
(`dvc remote modify --local localremote url /jusu/katalogas`), dar paleiskite `dvc push`.

### 7. Istorinio runo reprodukcija

```bash
time python reproduce.py <run_id>
```

Skriptas iš MLflow paima run'o `git_commit` ir hiperparametrus. Tada daro `git checkout` į tą commit'ą ir
`dvc checkout` žalių duomenų (jų md5 turi sutapti su run'o `dvc_raw_md5` tag'u). Hiperparametrus įrašo į `params.yaml`
ir paleidžia `dvc repro --force`. Pabaigoje palygina `accuracy` ir `f1` (leidžiamas skirtumas 0,005), naujam run'ui
uždeda tag'ą `reproduces=<run_id>` ir grąžina šaką.

Skriptas nepasileidžia su necommit'intais pakeitimais ar be šakos (detached HEAD), nes pabaigoje daro
`git checkout --force` ir tokie pakeitimai dingtų. `<run_id>` yra 4 žingsnio išvestyje arba MLflow UI
(`models/run_id.txt` rodo tik paskutinį). Naujame klasteryje autoriaus run'ų nėra, todėl atkurkite savo. Pavyzdys su
`rf-n100-d5`:

```
accuracy: original=0.7121 reproduced=0.7121 delta=0.0000
f1: original=0.5947 reproduced=0.5947 delta=0.0000
REPRODUCED in 20s -> new run 5c045194b72d415c9b06b03ee03191d7
```

### 8. Mokymo Docker vaizdas

Publikuotas vaizdas pasileidžia be build'o ir log'ina run'ą į klasterio MLflow:

```bash
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 ghcr.io/lukasja111/mlops-u1/train:sha-71249941
```

Toliau einančios komandos sukuria savą vaizdą, jį išbando, nuskenuoja su Trivy, sugeneruoja SBOM ir publikuoja į GHCR.
Joms reikia Trivy ir `gh auth login --scopes write:packages`:

```bash
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 mlops-u1/train:sha-$SHA

trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json mlops-u1/train:sha-$SHA
trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
trivy image -f spdx-json -o docs/sbom-train.json mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```


### 9. Mokymas kaip Kubernetes Job

```bash
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Job'as traukia viešą GHCR vaizdą `sha-71249941`, todėl į kind nieko kelti nereikia. Jo run'o `git_commit` yra vaizdo
commit'as, ne HEAD: savam vaizdui atlikite 8 žingsnį ir pakeiskite `image:` faile `k8s/jobs/job-train.yaml`. ConfigMap
`training-config` duoda Job'ui MLflow adresą `http://mlflow:5000` ir hiperparametrus `N_ESTIMATORS`, `MAX_DEPTH`. Jis
skaitomas tik paleidžiant Pod'ą, o sukurto Job'o keisti negalima, todėl kitam gyliui reikia naujo Job'o:

```bash
sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
kubectl apply -f k8s/jobs/configmap-training.yaml
kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
```

Su `MAX_DEPTH: "10"` Job'o run'as duoda tas pačias metrikas kaip gylio 10 `dvc repro` run'as.

## Išvalymas

```bash
kind delete cluster --name mlops-u1
```

PVC išlieka perkūrus Pod'us, bet dingsta kartu su klasteriu. Po kompiuterio perkrovimo klasterį pakelia
`docker start mlops-u1-control-plane`. Po minutės Pod'ai vėl Running, run'ai vietoje.

## Dažnos klaidos ir jų sprendimai

| Klaida | Priežastis ir sprendimas |
|---|---|
| `python3.12: command not found` | Sistemoje tik naujesnis Python: `uv venv --seed --python 3.12 .venv` arba `nix-shell` (1 žingsnis) |
| `ImportError: libstdc++.so.6: cannot open shared object file` | Python iš Nix, bet venv naudojamas ne `nix-shell` viduje: paleiskite `nix-shell` (`shell.nix` nustato `LD_LIBRARY_PATH`) |
| `permission denied while trying to connect to the Docker daemon socket` | Naudotojas ne `docker` grupėje: `sudo usermod -aG docker $USER`, tada atsijunkite ir vėl prisijunkite |
| `dvc: command not found` arba `ModuleNotFoundError` per `dvc repro` | Neaktyvuotas venv: `source .venv/bin/activate` |
| `bash: .venv/bin/activate: Permission denied` | Failas paleistas kaip programa, o ne įkeltas į shell'ą: `source .venv/bin/activate` (be `sudo`) |
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `403 Invalid Host header` | Host'o nėra MLflow `--allowed-hosts` sąraše (`k8s/mlflow/deployment-mlflow.yaml`) |
| `curl 127.0.0.1:5000` atmeta ryšį | Porto 5000 persiuntimas į 30500 nustatomas tik kuriant klasterį: jei jis sukurtas be `k8s/kind-config.yaml`, ištrinkite ir sukurkite iš naujo. Kitaip MLflow Pod'as dar neparengtas: `kubectl -n mlops-u1 get pods` |
| macOS: 5000 portas užimtas | Jį laiko AirPlay Receiver: išjunkite jį arba `k8s/kind-config.yaml` pakeiskite `hostPort` (pvz. 5001) ir atitinkamai `MLFLOW_TRACKING_URI` |

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE). + co-authored su Claude.
