Kodas: `mlops-u1.bundle` pateikimo ZIP'e (U2 į GitHub nekeliamas, ten tik U1 su tag'u `u1-final`)
Tag: `u2-final`
Paleidimas: Žemiau pateiktos instrukcijos.

# Airbnb hostų klasifikatorius į superhostus: U2 MLOps projekto paleidimo instrukcijos
U2 išbandyta NixOS 26.05; U1 žingsniai ir CachyOS (su ir be [nix](https://nixos.org/download/#nix))

- Portai: MLflow http://127.0.0.1:5000 (kind NodePort 30500, tik `127.0.0.1`); API `http://<mazgo IP>:30800` (NodePort, 9 žingsnis); Postgres tik klasterio viduje, `postgres:5432`.
- Prisijungimai: MLflow su basic-auth, naudotojai `admin`, `trainer`, `serving`, `viewer`; slaptažodžiai tik Secret `mlflow-auth` ir `mlflow-<naudotojas>-credentials` (3 žingsnis). Postgres naudotojas ir slaptažodis Secret `postgres-credentials`.
- Rezultatai: MLflow eksperimentas ir registruotas modelis `airbnb-superhost` (`@champion`, `@previous`), `metrics.json`, `docs/load-test.json`, KPI `docs/requirements.md`, ataskaita `docs/u2-report.md`.

## Reikalavimai

- `6 GB` laisvos greitai prieinamos atminties (RAM'o): klasterio Pod'ų `requests` 4,1 GiB, `limits` 6 GiB.
- Atlaisvintas `5000` portas.

| Software | Versija |
|---|---|
| git, curl | bet kokia |
| bash arba zsh | bet kokia |
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 (diegiamas su `requirements.txt`) |
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

> [!NOTE]
> Jei Nix įdiegtas be nixpkgs kanalo (pvz. Arch `nix` paketas), `nix-shell` išveda `error: file 'nixpkgs' was not found in the Nix search path` ir `uses bash from your environment`.
> Tai tik jo paties `bash` paieška: `shell.nix` aplinka vis tiek užkraunama, tik su sistemos `bash`. Klaidos ignoruokite ir tęskite.

### 0.B Reikalavimų instaliacija su Pacman package manageriu
Arch-based sistemoms, ant Debian/Ubuntu sistemų, priklausomai nuo package manageriu gali atrodyti kitaip.

```sh
sudo pacman -S --needed docker docker-buildx kind kubectl uv trivy
```

### 1. Repo, įrankiai ir Python aplinka

Repozitorija klonuojama iš pateikimo ZIP'e esančio `mlops-u1.bundle` (visa git istorija su tag'u `u2-final`), tada ruošiama python aplinka. `requirements-dev.txt` duoda testus, `ruff` ir API paketus, kurių reikia 9 žingsniui.
```bash
git clone mlops-u1.bundle mlops-u1
cd mlops-u1
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

> [!WARNING]
> Jei `python3.12` nėra (Arch), tą patį daro `uv`:
> ```bash
> uv venv --seed --python 3.12 .venv
> source .venv/bin/activate
> pip install -r requirements.txt -r requirements-dev.txt
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

MLflow veikia su basic-auth: Secret `mlflow-auth` turi `admin` slaptažodį ir Flask raktą, todėl kuriamas prieš `kubectl apply -f k8s/mlflow/`. Priešpaskutinė komanda laukia, kol MLflow pasileis, paskutinė atsako `OK`; pirmą kartą klasteris dar siunčiasi Postgres ir MLflow vaizdus, tai gali užtrukti kelias minutes.
Svetainę galima bus matyti ir pasiekti naršyklėje per `http://127.0.0.1:5000` (jei ant localhosto `5000` portas nėra užimtas).

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

Trys naudotojai, kiekvienas su savo Secret: `trainer` rašo run'us ir registruoja modelius (4, 8 ir 9 žingsniai), `serving` API skaito modelį, `viewer` tik skaito (UI).

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

`default_permission = READ`: anoniminis API kvietimas gauna 401, `viewer` rašymas ir `serving` alias'o keitimas 403.

### 4. Pipeline: HPO run'as

Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`: run'o `git_commit` tag'as yra HEAD mokymo metu, ir `reproduce.py` atkuria būtent jį. Prisijungimai galioja tik šiame terminale, juos naudoja ir tolesni žingsniai.

```sh
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
export MLFLOW_TRACKING_USERNAME=trainer
export MLFLOW_TRACKING_PASSWORD=$(kubectl -n mlops-u1 get secret mlflow-trainer-credentials -o jsonpath='{.data.MLFLOW_TRACKING_PASSWORD}' | base64 -d)
dvc repro
git commit -am "HPO run"
```

`params.yaml` skyrius `hpo`: Optuna (TPE su seed) per 20 bandymų renka `n_estimators`, `max_depth` ir `min_samples_leaf`, kiekvieną bandymą vertina 5 grupių kryžmine validacija mokymo imtyje (`StratifiedGroupKFold` pagal vietą). Tėvinis run'as `rf-hpo20`, bandymai yra įdėtiniai run'ai `trial-00` ... `trial-19`; testinė imtis naudojama tik galutiniam modeliui. NixOS mini PC (16 gijų) run'as truko 157 s.
Vienas modelis be paieškos: `n_trials: 0`, tada run'as vadinasi `rf-n<n_estimators>-d<max_depth>`.
Jei turite savo DVC remote (`dvc remote modify --local localremote url /jusu/katalogas`), po run'o dar paleiskite `dvc push`.

### 5. Rezultatų tikrinimas

- MLflow UI (http://127.0.0.1:5000) prašo prisijungimo: naudotojas `viewer`, slaptažodį išveda žemiau esanti komanda.
- Eksperimentas `airbnb-superhost`: `rf-hpo20` su 20 įdėtinių bandymų, metrikos per žingsnius (`fold_f1`, `trial_cv_f1`, `best_cv_f1`), sistemos metrikos `system/*`, duomenų rinkiniai (`log_input`), modelis su aplinka, tag'ai `git_commit`, `dvc_raw_md5`, `seed`. Pagrindinė metrika `f1`, šalia `accuracy` ir `eval/*`. Registruotas modelis (Models) atsiranda po 9 žingsnio.

```sh
kubectl -n mlops-u1 get secret mlflow-viewer-credentials -o jsonpath='{.data.MLFLOW_TRACKING_PASSWORD}' | base64 -d; echo
```

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

### 7. Docker vaizdai: build, Trivy ir kind

Lokalus CI: abu vaizdai (`api` ir `train`) žymimi HEAD commit'u, Trivy vartas neleidžia įkelti vaizdo su CRITICAL radiniu, `kind load` įkelia vaizdą tiesiai į klasterį (į registrą niekas nepublikuojama). Abi `sed` komandos įrašo naują tag'ą į manifestus.

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

Trivy perrašo `docs/trivy-api.json` (HIGH ir CRITICAL ataskaita). Docker kešas gali palikti seną `apt-get upgrade` sluoksnį su jau pataisytais CVE; tada `docker build --no-cache`. Mokymo vaizdo U1 aprašas: `docs/docker-image.md`.

### 8. Mokymas kaip Kubernetes Job

Job'as naudoja 7 žingsnio vaizdą `mlops-u1/train:sha-<SHA>` (jau kind'e, `imagePullPolicy: IfNotPresent`), todėl jo run'o `git_commit` yra vaizdo commit'as. ConfigMap `training-config` duoda Job'ui MLflow adresą `http://mlflow:5000` ir hiperparametrus (`N_TRIALS: "0"`, vienas modelis be paieškos), Secret `mlflow-trainer-credentials` (3 žingsnis) duoda prisijungimą.

```sh
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Gylio 15 Job'as duoda accuracy 0,7833 ir F1 0,6393. Sukurto Job'o keisti negalima, todėl kitam gyliui reikia naujo Job'o. Su `MAX_DEPTH: "10"` run'as duoda 0,7423 ir 0,6191, tas pačias metrikas kaip U1 gylio 10 `dvc repro` run'as; paskutinė komanda grąžina failą į gylį 15:

```sh
sed -i 's/MAX_DEPTH: "15"/MAX_DEPTH: "10"/' k8s/jobs/configmap-training.yaml
kubectl apply -f k8s/jobs/configmap-training.yaml
kubectl -n mlops-u1 delete job train && kubectl apply -f k8s/jobs/job-train.yaml
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
git checkout -- k8s/jobs/configmap-training.yaml
```

### 9. Registras ir API: žalias CD paleidimas

`scripts/cd.sh` vykdo visą grandinę; reikia 4 žingsnio prisijungimų ir 7 žingsnio vaizdų:

```
ruff → pytest → dvc repro → gate.py → promote.py register → @champion → MODEL_VERSION → kubectl apply -k → rollout status → smoke
```

Vartas (`scripts/gate.py`) lygina `metrics.json` su `params.yaml` skyriumi `gate` (`min_f1: 0.62`, `min_accuracy: 0.75`). Praėjęs modelis registruojamas kaip nauja `airbnb-superhost` versija su tag'ais `git_commit`, `dvc_raw_md5`, `accuracy`, `f1`, `gate=passed`; ji gauna `@champion`, buvęs čempionas `@previous`. Tas pats run'as antrą kartą neregistruojamas.

```sh
bash scripts/cd.sh
```

API ima modelį tik iš registro: ConfigMap duoda `MODEL_URI=models:/airbnb-superhost@champion`, `src/serve.py` alias'ą paverčia versija ir įkelia `models:/airbnb-superhost/<versija>` su Secret `mlflow-serving-credentials`. `MODEL_VERSION` pakeitimas pervadina ConfigMap, todėl `kubectl apply -k` perkrauna Pod'us. Patikra iš host'o per mazgo IP:

```sh
NODE=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
curl -s http://$NODE:30800/health; echo
curl -s -X POST -H 'Content-Type: application/json' -d @docs/predict-request.json http://$NODE:30800/predict; echo
python scripts/load_test.py http://$NODE:30800 --out docs/load-test.json
```

Apkrovos testas: 500 nuoseklių užklausų po vieną skelbimą (p50, p95, p99) ir 500 užklausų su 8 gijomis (RPS), rezultatai `docs/load-test.json`.

### 10. Raudoni paleidimai

Vartas blokuoja abu atvejus: `cd.sh` baigiasi `quality gate failed: nothing registered or deployed` ir išėjimo kodu 1, `@champion` ir API lieka kokie buvo. Pakeitus tik slenkstį, `dvc repro` nieko nekartoja ir vartas krenta per kelias sekundes (matuota 12,2 s):

```sh
sed -i 's/min_f1: 0.62/min_f1: 0.99/' params.yaml
bash scripts/cd.sh
git checkout -- params.yaml
```

Blogas modelis (`max_depth: 5` be paieškos) turi F1 0,5943 ir accuracy 0,7095, abu žemiau slenksčių. Run'as lieka MLflow, bet neregistruojamas ir nediegiamas; paskutinės dvi komandos grąžina darbo medį:

```sh
sed -i 's/max_depth: 15/max_depth: 5/; s/n_trials: 20/n_trials: 0/' params.yaml
bash scripts/cd.sh
git checkout -- params.yaml dvc.lock metrics.json models/run_id.txt
dvc checkout --force
```

### 11. Antra versija ir rollback

Rollback'ui reikia dviejų versijų: antras žalias paleidimas su 3 grupių CV (F1 0,6340) registruoja v2, `@previous` tampa v1. `cd.sh rollback` sukeičia `@champion` ir `@previous`, įrašo `MODEL_VERSION` ir įdiegia; vaizdas nesikeičia, niekas nemokoma iš naujo. Antras rollback grąžina v2.

```sh
sed -i 's/cv_folds: 5/cv_folds: 3/' params.yaml
git commit -am "HPO with 3 folds"
bash scripts/cd.sh
time bash scripts/cd.sh rollback
time bash scripts/cd.sh rollback
```

Rollback iki smoke testo truko 25,8 s ir 25,9 s. API Pod'ai turi `preStop` 5 s pauzę, kad senas Pod'as išeitų iš Service prieš sustodamas; užklausų nuostoliai rollback'o metu `docs/u2-report.md`.

### 12. CI workflow

`.github/workflows/ci-cd.yml` aprašo CI GitHub Actions: `lint` (ruff) ir `test` (pytest) lygiagrečiai, tada `model-gate` (duomenys iš fiksuotos HF revizijos, `dvc repro` su sqlite MLflow, `scripts/gate.py`), tada `build` (abu vaizdai `sha-<8>`, Trivy CRITICAL vartas). U2 į GitHub nekeliamas (autoriaus sprendimas), todėl workflow ten nevykdomas; tie patys žingsniai vyksta lokaliai: 7 žingsnis ir `scripts/cd.sh`.

## Išvalymas

```sh
kind delete cluster --name mlops-u1
```

PVC išlieka perkūrus Pod'us, bet dingsta kartu su klasteriu. Po kompiuterio perkrovimo klasterį pakelia `docker start mlops-u1-control-plane`; po minutės Pod'ai vėl Running, run'ai vietoje.

## Dažnos klaidos ir jų sprendimai

| Klaida | Priežastis ir sprendimas |
|---|---|
| `nix-shell`: `file 'nixpkgs' was not found in the Nix search path` | Nix be kanalo: `nix-shell` taip ieško tik savo `bash`, nerandęs naudoja sistemos `bash` (`uses bash from your environment`) ir veikia toliau; `shell.nix` nixpkgs turi savo |
| `permission denied while trying to connect to the Docker daemon socket` | Naudotojas ne `docker` grupėje: `sudo usermod -aG docker $USER`, tada atsijunkite ir vėl prisijunkite |
| `dvc: command not found`, `ModuleNotFoundError` arba `.venv/bin/activate: Permission denied` | Neaktyvuotas venv arba failas paleistas kaip programa: `source .venv/bin/activate` (be `sudo`) |
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `MLFLOW_TRACKING_USERNAME: export the trainer credentials first` arba `failed with error code 401 != 200` (`You are not authenticated`) | Šiame terminale neeksportuoti 4 žingsnio `MLFLOW_TRACKING_USERNAME` ir `MLFLOW_TRACKING_PASSWORD` |
| Pod'as `CreateContainerConfigError` | Trūksta Secret: MLflow `mlflow-auth`, API `mlflow-serving-credentials`, Job'as `mlflow-trainer-credentials` (3 žingsnis); kurio, rodo `kubectl -n mlops-u1 describe pod <pod>` |
| Pod'as `ErrImagePull` arba `ImagePullBackOff` | Vaizdo nėra kind'e arba manifesto tag'as kitas: 7 žingsnis (`kind load` ir abi `sed`) |
| `curl 127.0.0.1:5000` atmeta ryšį arba portas užimtas | Persiuntimas 5000 → 30500 nustatomas tik kuriant klasterį su `k8s/kind-config.yaml`; jei Pod'as dar neparengtas, žr. `kubectl -n mlops-u1 get pods`. Užimtą portą (macOS AirPlay) keiskite `hostPort` tame pačiame faile ir `MLFLOW_TRACKING_URI` |

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE). + co-authored su Claude.
