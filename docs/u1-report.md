# U1 ataskaita

## Kas padaryta

- **R1:** repo struktūra (`src/`, `docker/`, `k8s/`, `docs/`), README su paleidimu nuo nulio, `docs/requirements.md`
  v1.2: FR-01..05 ir NFR-01..14 su KPI ir išmatuotomis reikšmėmis, tarp jų reprodukcijos NFR-08.
- **R2:** DVC pipeline'as `prepare → train → evaluate` iš 20 CSV (HF `kraina/airbnb`, fiksuota revizija),
  `params.yaml`, commit'intas `dvc.lock`, lokalus DVC remote. 3 run'ai klasterio MLflow (`max_depth` 5 / 10 / 15:
  F1 0,6058 / 0,6465 / 0,7197); `reproduce.py` atkūrė pirmą run'ą per 15 s, Δ = 0.
- **R3:** mokymo vaizdas `ghcr.io/lukasja111/mlops-u1/train:sha-0a26641f` (viešas, digest užfiksuotas): rootfs
  449,63 MB, Trivy CRITICAL 0 / HIGH 44, uid 1000, SBOM; rezultatai `docs/image-sizes.md`, `docs/security-scan.md`.
- **R4:** kind klasteris (`k8s/kind-config.yaml`), namespace `mlops-u1`, PostgreSQL ir MLflow su PVC, pasiekiami per
  `127.0.0.1:5000`; run'ai ir modeliai išliko perkūrus abu Pod'us.
- **E2:** mokymas kaip Kubernetes Job su viešu GHCR vaizdu (29 s); run'o `git_commit` sutampa su vaizdo tag'u.

## Kas neveikė / ką teko spręsti

1. **Žemas F1.** Superhost klasė sudaro 25,6 %, todėl negilus miškas beveik niekada nesako „taip“ (F1 0,236).
   `class_weight="balanced"` pakėlė F1 iki 0,606–0,720. Lubos apie 0,75: Superhost statusas priklauso ir nuo
   duomenyse nesančių veiksnių (viešnagės, atšaukimai, atsakymų dažnis).
2. **Kurso `train.py` su RandomForest lūžta:** MLflow 3.15 modelį saugo skops formatu, kuris nepasitiki medžių tipais
   (`UntrustedTypesFoundException`). Sprendimas: `skops_trusted_types=["sklearn.tree._tree.Tree"]`.
3. **MLflow serveris netilpo į 2 GiB:** kurso komanda paleidžia 18 Python procesų (išmatuota 2,2 GB). Resursai
   nustatyti pagal matavimą: `requests` 2560Mi, `limits` 3Gi.
4. **HIGH CVE `cryptography` 49.0.0** atkeliavo su pilnu `mlflow` 3.15.2 (`cryptography<50`). Vaizde naudojamas
   `mlflow-skinny`: `cryptography` 50.0.2 (pataisyta), vaizdas 745 → 450 MB, Python radinių nebeliko.
5. **NixOS aplinka:** nixpkgs `dvc` sugadino Python 3.12 venv, pip wheel'ams trūko `libstdc++`, o `gh` nebuvo PATH,
   todėl `scripts/publish.sh` iš pradžių neveikė. Sprendimai: `dvc` venv'e, `LD_LIBRARY_PATH` ir `gh` lokaliame
   `shell.nix` (ne Git; kursas Nix nereikalauja).
6. **Nedaryta:** E1, E3, E4 , E5 .

## Kiek laiko užtruko

~5 val. per dvi dienas.
