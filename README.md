# Airbnb hostų klasifikatorius į superhostus: U1 MLOps projekto paleidimo instrukcijos

Binarinis klasifikatorius: ar Airbnb skelbimo šeimininkas yra Superhost (10 Europos miestų, 51 707 įrašai). Aplink
modelį: atkartojamas DVC pipeline'as, eksperimentų sekimas savame MLflow serveryje lokaliame kind klasteryje, mokymo
Docker vaizdas GHCR ir mokymas kaip Kubernetes Job (E2).

Repo https://github.com/lukasja111/mlops-u1, tag'as `u1-final`. Autorius: Lukas Jasiulionis (lukasja111). Paleidimas
nuo nulio: žingsniai 1 iki 4 duoda pirmą run'ą klasterio MLflow serveryje, toliau eksperimentai, reprodukcija, vaizdas
ir Job'as.

## Portai, prisijungimai, rezultatai

| Kas | Kur |
|---|---|
| MLflow UI ir API | http://127.0.0.1:5000: kompiuterio 5000 → kind NodePort 30500 → Service `mlflow:5000`. Prisijungimo nėra (E1 nedarytas), todėl kind klausosi tik `127.0.0.1` |
| Postgres | tik klasterio viduje, `postgres:5432`; naudotojas ir slaptažodis Secret `postgres-credentials` (3 žingsnis) |
| Rezultatai | MLflow eksperimentas `airbnb-superhost`; paskutinio run'o testo metrikos `metrics.json`; KPI ir išmatuotos reikšmės [`docs/requirements.md`](docs/requirements.md) v1.5 (5 žingsnis) |
| Duomenys | 20 CSV iš Hugging Face `kraina/airbnb` (fiksuota revizija), rodyklė `data/raw.dvc`; DVC remote `localremote` yra autoriaus kompiuterio katalogas (2 žingsnis) |
| Mokymo vaizdas | `ghcr.io/lukasja111/mlops-u1/train:sha-71249941` (viešas); dydis, digest ir Trivy: [`docs/image-sizes.md`](docs/image-sizes.md), [`docs/security-scan.md`](docs/security-scan.md) (8 žingsnis) |
| Mokymas klasteryje (E2) | Job `train` ir ConfigMap `training-config` (`k8s/jobs/`, 9 žingsnis) |
| Architektūra, ataskaita | [`docs/architecture.md`](docs/architecture.md), [`docs/u1-report.md`](docs/u1-report.md) |

## Reikalavimai

Išbandyta Linux'e: NixOS 26.05 su `nix-shell`, CachyOS su `nix-shell` ir CachyOS be Nix (įrankiai iš pacman, Python 3.12
per `uv`). Lentelėje `shell.nix` versijos (fiksuota nixpkgs revizija); pacman paketai naujesni ir veikė taip pat.

| Įrankis | Versija |
|---|---|
| Docker | 29.8.1 |
| [kind](https://kind.sigs.k8s.io/) | 0.31.0 (reikia ≥ 0.31) |
| kubectl | 1.36.3 |
| Python | 3.12.14 |
| DVC | 3.67.1 (diegiamas su `requirements-dev.txt`) |
| [Trivy](https://trivy.dev/), [gh](https://cli.github.com/) | 0.72.0, 2.102.0 (tik 8 žingsniui) |
| git, curl | bet kokia |

Klasteriui reikia apie 4 GB laisvos RAM ir laisvo 5000 porto.

## Paleidimas nuo nulio

Komandos vykdomos `bash` shell'e, repo šaknyje, viename terminale.

### 1. Repo, įrankiai ir Python aplinka

```bash
git clone https://github.com/lukasja111/mlops-u1.git && cd mlops-u1
python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
```

Tam reikia Docker, kind, kubectl ir Python 3.12 (lentelė aukščiau). Su Nix viską, išskyrus Docker, duoda `shell.nix`:
prieš venv komandą paleiskite

```bash
nix-shell
```

Arch ir CachyOS be Nix: įrankiai iš pacman, o Python 3.12 venv'ui parenka `uv` (vietoje `python3.12 -m venv .venv`):

```bash
sudo pacman -S --needed docker docker-buildx kind kubectl uv
uv venv --seed --python 3.12 .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
```

Kiekviename naujame terminale: `nix-shell` (jei Nix) ir `source .venv/bin/activate`.

### 2. Duomenys

Žalius duomenis į `data/raw/` reikia įdėti vieną kartą. Autoriaus kompiuteryje užtenka `dvc pull` (remote `localremote`
yra vietinis katalogas). Kitur tie patys 20 CSV atsisiunčiami iš fiksuotos Hugging Face revizijos:

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

`dvc commit` įdeda failus į DVC cache (iš jo juos ima `reproduce.py`) ir perskaičiuoja katalogo md5. „duomenys sutampa“
reiškia, kad md5 toks pat kaip `data/raw.dvc` (`a2b156db54022d6fe3c950258a5d5c9a.dir`), t. y. autoriaus run'ų duomenys.
`dvc push` veikia tik su savu remote: `dvc remote modify --local localremote url /jusu/katalogas`.

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

Paskutinė komanda laukia, kol MLflow atsakys `OK`; pirmą kartą klasteris dar siunčiasi Postgres ir MLflow vaizdus, tai
užtrunka kelias minutes. UI: http://127.0.0.1:5000.

- Slaptažodis sugeneruojamas komandoje ir į Git nepatenka. Peržiūrėti:
  `kubectl -n mlops-u1 get secret postgres-credentials -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d`. MLflow jį
  gauna aplinkos kintamuoju `PGPASSWORD`, todėl `ps` ir `kubectl describe` jo nerodo.
- Postgres duomenys ir artefaktai yra PVC, todėl run'ai išlieka perkūrus Pod'us: po
  `kubectl -n mlops-u1 delete pod -l app=mlflow` naujas Pod'as rodo tuos pačius run'us.
- Be NodePort: `kubectl -n mlops-u1 port-forward svc/mlflow 5050:5000`, tada
  `MLFLOW_TRACKING_URI=http://127.0.0.1:5050`. Kompiuteris be naršyklės: `ssh -L 5000:localhost:5000 <host>`.

### 4. Pipeline'as

```bash
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
dvc repro --force
git commit -am "exp: pirmas run'as savame klasteryje"
```

`MLFLOW_TRACKING_URI` nustatomas kiekviename naujame terminale: be jo `train.py` iškart baigiasi klaida, todėl run'ai
niekada nepatenka į vietinį `mlruns/`. `--force` reikalingas, nes po `dvc pull` visos išvestys sutampa su `dvc.lock` ir
DVC viską praleistų. Commit'o reikia `reproduce.py` (švarus darbo medis). Visas pipeline'as trunka apie 20 s, išvestyje
yra `run_id=…` (7 žingsnis).

- `prepare`: 20 CSV → `data/processed/train.csv` ir `test.csv`. Imtys skaidomos pagal skelbimą (`city`, `lat`, `lng`),
  kad tas pats skelbimas nepatektų į abi (NFR-01a).
- `train`: pagal `params.yaml` → `models/model.pkl`, `models/run_id.txt`; MLflow run'as su parametrais, `accuracy` ir
  `f1`, modeliu, mokymo duomenų rinkiniu ir tag'ais `git_commit`, `dvc_raw_md5`.
- `evaluate`: `metrics.json`; tame pačiame run'e `eval/*` metrikos ir artefaktai `eval/feature_importances.json`,
  `eval/confusion_matrix.json`.

### 5. Kur žiūrėti rezultatus

- MLflow UI (http://127.0.0.1:5000), eksperimentas `airbnb-superhost`: run'ai `rf-n<n_estimators>-d<max_depth>`,
  metrikos `f1` (pagrindinė), `accuracy` ir `eval/*`, artefaktai, modelis, tag'ai. Autoriaus serveryje seni run'ai
  (prieš nutekėjimo taisymą) pažymėti `split=random`.
- Terminale: `dvc metrics show`; palyginimui su ankstesniu commit'u `dvc metrics diff <commit>` ir
  `dvc params diff <commit>`.
- KPI ir išmatuotos reikšmės: `docs/requirements.md`.

### 6. Naujas eksperimentas

```bash
sed -i 's/max_depth: 15/max_depth: 10/' params.yaml
dvc status
dvc repro
dvc params diff && dvc metrics diff
git commit -am "exp: max_depth 10"
```

`dvc status` rodo pasikeitusį `train` parametrą; `dvc repro` persileidžia tik `train` ir `evaluate`, nes `prepare` nuo
`params.yaml` nepriklauso. `dvc.lock` pasikeičia `train` parametro reikšmė ir `model.pkl`, `run_id.txt`, `metrics.json`
md5. Pakartotas `dvc repro` be pakeitimų nieko neperskaičiuoja. Su savu remote dar `dvc push` (2 žingsnis).

Kodo pakeitimai (`src/`) commit'inami prieš `dvc repro`: run'o `git_commit` tag'as yra HEAD mokymo metu, ir
`reproduce.py` atkuria būtent jį. `params.yaml` gali likti necommit'intas, nes hiperparametrus `reproduce.py` ima iš
run'o.

### 7. Istorinio run'o reprodukcija

```bash
time python reproduce.py <run_id>
```

Skriptas nepasileidžia su necommit'intais pakeitimais ar be šakos (detached HEAD), nes pabaigoje daro
`git checkout --force` ir tokie pakeitimai dingtų. `<run_id>` yra 4 žingsnio išvestyje arba MLflow UI
(`models/run_id.txt` rodo tik paskutinį). Naujame klasteryje autoriaus run'ų nėra, todėl atkurkite savo.

Skriptas iš MLflow paima run'o `git_commit` ir hiperparametrus, daro `git checkout` į tą commit'ą ir `dvc checkout`
žalių duomenų (jų md5 turi sutapti su run'o `dvc_raw_md5` tag'u), įrašo hiperparametrus į `params.yaml`, paleidžia
`dvc repro --force`, palygina `accuracy` ir `f1` (leidžiamas skirtumas 0,005), naujam run'ui uždeda tag'ą
`reproduces=<run_id>` ir grąžina šaką. Pavyzdys (`rf-n100-d5`):

```
accuracy: original=0.7121 reproduced=0.7121 delta=0.0000
f1: original=0.5947 reproduced=0.5947 delta=0.0000
REPRODUCED in 20s -> new run 4fbc102c1ee841c181489d5ba145deca
```

### 8. Mokymo Docker vaizdas

Publikuotas vaizdas pasileidžia be build'o ir log'ina run'ą į klasterio MLflow:

```bash
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 ghcr.io/lukasja111/mlops-u1/train:sha-71249941
```

Savas vaizdas: build'as, bandomasis run'as, Trivy ataskaita, CRITICAL vartas, SBOM ir publikavimas (reikia Trivy ir
`gh auth login --scopes write:packages`):

```bash
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
docker run --rm --network host -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 mlops-u1/train:sha-$SHA

trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output docs/trivy-train.json mlops-u1/train:sha-$SHA
trivy image --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
trivy image -f spdx-json -o docs/sbom-train.json mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```

- Į vaizdą kopijuojamas `data/processed/`, todėl prieš build'ą reikia `dvc pull` arba `dvc repro`.
- Tag'as `sha-<8 simboliai>` yra commit'as: tas pats kaip MLflow `git_commit` ir vaizdo
  `org.opencontainers.image.revision` žymė; `latest` nenaudojamas. Naujas commit'as reiškia naują tag'ą ir naują Trivy
  skenavimą.
- Trivy perrašo commit'intus `docs/trivy-train.json` ir `docs/sbom-train.json`: naujus commit'inkite arba grąžinkite
  `git checkout -- docs/`.
- `scripts/publish.sh` dar kartą praleidžia CRITICAL vartą, prisijungia prie GHCR su `gh` token'u, daro push ir
  išspausdina digest. Naujas GHCR paketas būna privatus; viešas daromas GitHub → Packages → Package settings. Ne Linux'e
  vietoje `--network host` naudokite `-e MLFLOW_TRACKING_URI=http://host.docker.internal:5000`.

### 9. Mokymas kaip Kubernetes Job (E2)

```bash
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Job'as traukia viešą GHCR vaizdą `sha-71249941`, todėl į kind nieko kelti nereikia. Jo run'o `git_commit` yra vaizdo
commit'as, ne HEAD: naujam vaizdui atlikite 8 žingsnį ir pakeiskite `image:` faile `k8s/jobs/job-train.yaml`. MLflow
adresas `http://mlflow:5000` ateina iš ConfigMap; dėl jo serveris paleistas su `--allowed-hosts`, kitaip atsakytų
`403 Invalid Host header`.

Hiperparametrai `N_ESTIMATORS` ir `MAX_DEPTH` taip pat yra ConfigMap `training-config`: Job'as juos perduoda `train.py`
argumentais (`args` pakeičia vaizdo `CMD`). ConfigMap skaitomas paleidžiant Pod'ą, o Job'as po sukūrimo nekeičiamas,
todėl kitas gylis reiškia naują Job'ą:

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
`docker start mlops-u1-control-plane`; po minutės Pod'ai vėl Running, run'ai vietoje.

## Problemų sprendimas

| Simptomas | Priežastis ir sprendimas |
|---|---|
| `python3.12: command not found` | Sistemoje tik naujesnis Python: `uv venv --seed --python 3.12 .venv` arba `nix-shell` (1 žingsnis) |
| `ImportError: libstdc++.so.6: cannot open shared object file` | Python iš Nix, bet venv naudojamas ne `nix-shell` viduje: paleiskite `nix-shell` (`shell.nix` nustato `LD_LIBRARY_PATH`) |
| `permission denied while trying to connect to the Docker daemon socket` | Naudotojas ne `docker` grupėje: `sudo usermod -aG docker $USER`, tada atsijunkite ir vėl prisijunkite |
| `dvc: command not found` arba `ModuleNotFoundError` per `dvc repro` | Neaktyvuotas venv: `source .venv/bin/activate` |
| `bash: .venv/bin/activate: Permission denied` | Failas paleistas kaip programa, o ne įkeltas į shell'ą: `source .venv/bin/activate` (be `sudo`) |
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `403 Invalid Host header` | Host'o nėra MLflow `--allowed-hosts` sąraše (`k8s/mlflow/deployment-mlflow.yaml`) |
| `curl 127.0.0.1:5000` atmeta ryšį | Portas 5000 → 30500 nustatomas tik kuriant klasterį: jei jis sukurtas be `k8s/kind-config.yaml`, ištrinkite ir sukurkite iš naujo. Kitaip MLflow Pod'as dar neparengtas: `kubectl -n mlops-u1 get pods` |
| macOS: 5000 portas užimtas | Jį laiko AirPlay Receiver: išjunkite jį arba `k8s/kind-config.yaml` pakeiskite `hostPort` (pvz. 5001) ir atitinkamai `MLFLOW_TRACKING_URI` |
| Postgres Pod'as `CrashLoopBackOff` | Secret sukurtas su tuščiu slaptažodžiu (`PG_PASSWORD` nenustatytas): `kubectl -n mlops-u1 delete secret postgres-credentials`, sukurkite jį iš naujo ir ištrinkite abu Pod'us (`-l app=postgres`, `-l app=mlflow`) |

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE).
