# Airbnb hostu klasifikatorius i superhostus U1 MLOps Projektui paleidimo instrukcijos

Binarinis klasifikatorius: ar Airbnb skelbimo šeimininkas yra Superhost (10 Europos miestų, 51 707 skelbimai). Aplink
modelį: atkartojamas DVC pipeline'as, eksperimentų sekimas savame MLflow serveryje lokaliame kind klasteryje, mokymo
Docker vaizdas GHCR ir mokymas kaip Kubernetes Job (E2).

- **Repo:** https://github.com/lukasja111/mlops-u1
- **Tag:** `u1-final`
- **Autorius:** Lukas Jasiulionis (lukasja111)
- **Vaizdas:** `ghcr.io/lukasja111/mlops-u1/train:sha-0a26641f` (viešas; digest `docs/image-sizes.md`)
- **Kaip paleisti:** `kind create cluster` → Postgres ir MLflow klasteryje → duomenys (`dvc pull` arba HF) →
  `dvc repro --force`; rezultatai MLflow UI http://127.0.0.1:5000 (žr. [Paleidimas nuo nulio](#paleidimas-nuo-nulio))

## Rezultatai

| Run'as | `max_depth` | accuracy | F1 (Superhost) |
|---|---:|---:|---:|
| `rf-n100-d5` | 5 | 0,7184 | 0,6058 |
| `rf-n100-d10` | 10 | 0,7616 | 0,6465 |
| `rf-n100-d15` | 15 | 0,8279 | 0,7197 |

KPI (`docs/requirements.md`): F1 ≥ 0,62 ir accuracy ≥ 0,75 („visada ne Superhost“ duoda 0,744). Tenkina gyliai 10 ir
15; `params.yaml` dabar 15. Reprodukcija: 15 s, Δ = 0.

## Struktūra

```
src/                   data_prep.py, train.py, eval.py
reproduce.py           istorinio run'o atkūrimas pagal run_id
dvc.yaml, params.yaml  pipeline'as ir hiperparametrai; dvc.lock, metrics.json commit'inami
data/raw.dvc           20 CSV rodyklė (patys duomenys DVC remote, ne Git)
models/run_id.txt      paskutinio mokymo MLflow run_id
docker/Dockerfile.train, .dockerignore, requirements-train.txt   mokymo vaizdas
k8s/kind-config.yaml   klasterio konfigūracija; k8s/namespace.yaml
k8s/mlflow/            Postgres ir MLflow: PVC, Deployment, Service
k8s/jobs/              E2: ConfigMap ir mokymo Job
scripts/publish.sh     vaizdo publikavimas į GHCR
docs/                  requirements.md, architecture.md, image-sizes.md, security-scan.md, u1-report.md,
                       trivy-train.json, sbom-train.json
```

## Reikalavimai

Docker, [kind](https://kind.sigs.k8s.io/) ≥ 0.31, kubectl, Python 3.12, apie 4 GB laisvos RAM. Vaizdo skenavimui ir
publikavimui: [Trivy](https://trivy.dev/) ir [gh](https://cli.github.com/) (`gh auth login --scopes write:packages`).

```bash
python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
```

`requirements-train.txt`: mokymo priklausomybės (jas diegia ir Docker vaizdas, su `mlflow-skinny`);
`requirements.txt`: plius pilnas `mlflow`; `requirements-dev.txt`: plius DVC. Tiesioginės priklausomybės fiksuotos `==`.

Visos komandos vykdomos repo šaknyje, viename terminale su aktyvuotu `.venv`. Naujame terminale:
`. .venv/bin/activate && export MLFLOW_TRACKING_URI=http://127.0.0.1:5000`.

## Paleidimas nuo nulio

```bash
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

# 4. Duomenys: atlikite bloką „Duomenys be DVC remote“ žemiau (autoriaus kompiuteryje vietoje jo: dvc pull)

# 5. Pipeline'as: run'as klasterio MLflow
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
dvc repro --force
git commit -am "exp: pirmas run'as savame klasteryje"
```

- 2 žingsnis: slaptažodis šešioliktainis, todėl jo nereikia koduoti MLflow DB URI.
- 5 žingsnis: naujame klasteryje MLflow tuščias, o po `dvc pull` (autoriaus kompiuteryje) visos išvestys sutampa su `dvc.lock`, todėl be
  `--force` DVC viską praleistų ir run'o nebūtų. Commit'as reikalingas, nes `dvc.lock` ir `models/run_id.txt` dabar
  rodo į jūsų run'ą, o `reproduce.py` reikalauja švaraus darbo medžio.
- `train.py` be `MLFLOW_TRACKING_URI` neveikia: run'ai log'inami tik į klasterio MLflow, ne į vietinį `mlruns/`.

### Duomenys be DVC remote

`localremote` yra autoriaus kompiuterio katalogas, todėl kitur `dvc pull` baigiasi klaida. 4 žingsnyje
atsisiųskite 20 CSV iš fiksuotos HF revizijos ir patikrinkite, kad jie sutampa su `data/raw.dvc`:

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

`dvc commit` suskaičiuoja katalogo md5 ir įdeda failus į DVC cache (jo reikia `reproduce.py`). Jei `git diff` rodo
pakeitimą, failai skiriasi nuo autoriaus (md5 `a2b156db54022d6fe3c950258a5d5c9a.dir`). Toliau tęskite 5 žingsniu.
`dvc push` (žr. „Naujas eksperimentas“) veiks tik su savu remote: `dvc remote modify --local localremote url /jusu/katalogas`.

## Portai

| Kas | Adresas |
|---|---|
| MLflow UI / API | http://127.0.0.1:5000 → kind NodePort 30500 → Service `mlflow:5000` |
| Postgres | tik klasterio viduje: `postgres:5432` |

- Jei NodePort neveikia: `kubectl -n mlops-u1 port-forward svc/mlflow 5050:5000` → http://127.0.0.1:5050 (tada ir
  `export MLFLOW_TRACKING_URI=http://127.0.0.1:5050`).
- Kompiuteris be naršyklės (SSH): `ssh -L 5000:localhost:5000 <host>` ir naršyklėje http://localhost:5000.

## Prisijungimai

- **Postgres:** naudotojas ir slaptažodis tik Secret `postgres-credentials` (2 žingsnis). Peržiūrėti:
  `kubectl -n mlops-u1 get secret postgres-credentials -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d`.
  Kompromisas: MLflow slaptažodį gauna `--backend-store-uri` argumente, todėl Pod'o viduje jis matomas `ps` išvestyje;
  lokaliam klasteriui tai priimtina.
- **MLflow:** be autentifikacijos (E1 nedaromas), todėl kind klausosi tik `127.0.0.1`.

## Kur žiūrėti rezultatus

- MLflow UI → eksperimentas `airbnb-superhost`: run'ai `rf-n<n_estimators>-d<max_depth>`; metrikos `f1` (Superhost
  klasės, pagrindinė), `accuracy` ir `eval/*` (iš `eval.py`); tag'ai `git_commit`, `dvc_raw_md5`; modelis MLflow 3
  skiltyje „Logged models“ (susietas su run'u).
- `dvc metrics show`: dabartinės metrikos; `dvc metrics diff <commit>`, `dvc params diff <commit>`: palyginimas su
  ankstesniu eksperimentu.
- `docs/image-sizes.md`, `docs/security-scan.md`: vaizdo dydis ir Trivy rezultatai.

## Naujas eksperimentas

```bash
# params.yaml: pakeiskite hiperparametrą, pvz. train.max_depth 15 -> 10
dvc status                             # train: changed deps, params.yaml: modified
dvc repro                              # persileidžia tik train ir evaluate (prepare nuo params nepriklauso)
dvc params diff && dvc metrics diff
git commit -am "exp: max_depth 10"
dvc push                               # tik su savu remote, žr. „Duomenys be DVC remote“
```

- `dvc.lock` pasikeičia: `train` params reikšmė ir `models/model.pkl`, `models/run_id.txt`, `metrics.json` md5;
  `prepare` įrašas lieka toks pat.
- Antras `dvc repro` be pakeitimų nieko neperskaičiuoja (`didn't change, skipping`).
- **Kodo pakeitimus (`src/`) commit'inkite prieš `dvc repro`:** run'o `git_commit` tag'as yra HEAD mokymo metu, o
  `reproduce.py` atkuria būtent tą commit'ą. Keičiant tik `params.yaml` iš anksto commit'inti nereikia: `reproduce.py`
  hiperparametrus ima iš run'o.

## Reprodukcija

```bash
git status                             # švarus darbo medis, esate šakoje (main)
time python reproduce.py <run_id>      # ≤ 2 min, |Δaccuracy| ≤ 0,005, |Δf1| ≤ 0,005
```

`<run_id>`: 5 žingsnio išvestyje (`run_id=…`) arba MLflow UI; `models/run_id.txt` rodo tik paskutinį run'ą.

`reproduce.py`: paima run'ą iš MLflow → `git checkout <git_commit>` → `dvc checkout` žalių duomenų → run'o
hiperparametrai į `params.yaml` → `dvc repro --force` → palygina metrikas, naujam run'ui uždeda tag'ą
`reproduces=<run_id>` → grąžina repo į pradinę šaką. Pavyzdys (`rf-n100-d5`):

```
accuracy: original=0.7184 reproduced=0.7184 delta=0.0000
f1: original=0.6058 reproduced=0.6058 delta=0.0000
REPRODUCED in 15s -> new run 2bece1a9d32348c3b5f568730ece235c
```

Naujame klasteryje atkurkite savo run'ą: autoriaus run'ų jame nėra.

## Docker vaizdas

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
- Publikuota: `ghcr.io/lukasja111/mlops-u1/train:sha-0a26641f`, digest
  `sha256:74fbf9921a9e6c76ab8c86170d1991c24db62ca24e44ced6fef351ed9b81ea8a`; rootfs 449,63 MB; Trivy CRITICAL 0 /
  HIGH 44 (visi Debian, pataisų dar nėra); vykdomas kaip uid 1000. Išsamiau `docs/image-sizes.md`,
  `docs/security-scan.md`.

## E2: mokymas kaip Kubernetes Job

```bash
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

- Job'as paleidžia viešą GHCR vaizdą `sha-0a26641f`, todėl nieko kurti ar įkelti į kind nereikia.
- MLflow pasiekiamas per `http://mlflow:5000` (ConfigMap); todėl MLflow paleistas su `--allowed-hosts`, kitaip
  atsakytų `403 Invalid Host header`.
- Job'ai nekeičiami: pakartotinai paleisti `kubectl -n mlops-u1 delete job train` ir vėl tas pats `apply`.
- Išbandyta: Job'as baigėsi per 29 s (kartu su vaizdo atsisiuntimu); run'as `f57ff3c2` su `git_commit=0a26641f`.

## Problemų sprendimas

| Simptomas | Priežastis ir sprendimas |
|---|---|
| `MLFLOW_TRACKING_URI wasn't set properly` | Kintamasis nenustatytas šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5000` |
| `403 Invalid Host header` | Host'o nėra MLflow `--allowed-hosts` sąraše (`k8s/mlflow/deployment-mlflow.yaml`) |
| `curl 127.0.0.1:5000` atmeta ryšį | Klasteris sukurtas be `k8s/kind-config.yaml` (portai nustatomi tik kuriant: ištrinkite ir sukurkite iš naujo) arba MLflow Pod'as dar neparengtas (`kubectl -n mlops-u1 get pods`) |
| macOS: 5000 portas užimtas | Jį naudoja AirPlay Receiver: išjunkite jį arba `k8s/kind-config.yaml` pakeiskite `hostPort` (pvz. 5001) ir atitinkamai `MLFLOW_TRACKING_URI` |
| Postgres Pod'as `CrashLoopBackOff` | Secret sukurtas su tuščiu slaptažodžiu (`PG_PASSWORD` nenustatytas): `kubectl -n mlops-u1 delete secret postgres-credentials`, sukurkite jį iš naujo ir ištrinkite abu Pod'us (`-l app=postgres`, `-l app=mlflow`) |
| `dvc repro` nieko nedaro naujame klasteryje | Po `dvc pull` išvestys sutampa su `dvc.lock`: `dvc repro --force` |

## Išvalymas

```bash
kind delete cluster --name mlops-u1
```

Postgres ir MLflow artefaktų PVC (kind `local-path`) yra kind mazgo konteineryje: perkūrus Pod'ą duomenys išlieka,
ištrynus klasterį dingsta.

## Pateikimas (ZIP į eMokymus)

```bash
git archive --format=zip -o ../mlops-u1-u1-final.zip u1-final
```

Į ZIP patenka tik Git sekami failai (kodas, `k8s/`, `docs/`), be `mlruns/`, DVC cache ir duomenų.

## Duomenys ir licencija

- **Duomenys:** Gyódi, K., & Nawaro, Ł. (2021). Determinants of Airbnb prices in European cities: A spatial
  econometrics approach. *Tourism Management*, 104319. https://doi.org/10.1016/j.tourman.2021.104319. Rinkinys
  Zenodo 4446043, licencija CC BY 4.0. Gauta per Hugging Face `kraina/airbnb` (Vroclavo mokslo ir technologijų
  universitetas), revizija `b9dd71fc8f175b645ce47f87c702492a6128c4dd`. Pirminis šaltinis: Inside Airbnb.
- **Kodas:** MIT, žr. [LICENSE](LICENSE).
