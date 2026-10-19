# U1 ataskaita

## Kas padaryta

- **R1:** repo struktūra (`src/`, `docker/`, `k8s/`, `docs/`), README su paleidimu nuo nulio, `docs/requirements.md`
  v1.4: FR-01..05 ir 14 NFR su KPI ir išmatuotomis reikšmėmis, tarp jų reprodukcijos NFR-08 ir padalijimo NFR-01a.
- **R2:** DVC pipeline'as `prepare → train → evaluate` iš 20 CSV (HF `kraina/airbnb`, fiksuota revizija),
  `params.yaml`, commit'intas `dvc.lock`, lokalus DVC remote. 3 run'ai klasterio MLflow (`max_depth` 5 / 10 / 15:
  F1 0,5947 / 0,6181 / 0,6298) su požymių svarba ir klaidų matrica; `reproduce.py` atkūrė pirmą run'ą per 20 s, Δ = 0.
- **R3:** mokymo vaizdas `ghcr.io/lukasja111/mlops-u1/train:sha-71249941` (viešas, digest užfiksuotas): rootfs
  449,63 MB, Trivy CRITICAL 0 / HIGH 44, uid 1000, SBOM; rezultatai `docs/image-sizes.md`, `docs/security-scan.md`.
- **R4:** kind klasteris (`k8s/kind-config.yaml`), namespace `mlops-u1`, PostgreSQL ir MLflow su PVC, pasiekiami per
  `127.0.0.1:5000`; run'ai ir modeliai išliko perkūrus abu Pod'us; DB slaptažodis ne procesų argumentuose.
- **E2:** mokymas kaip Kubernetes Job su viešu GHCR vaizdu, hiperparametrai per ConfigMap; run'o `git_commit`
  sutampa su vaizdo tag'u, metrikos — su `dvc repro`.

## Kas neveikė / ką teko spręsti

1. **Duomenų nutekėjimas.** Peržiūrint rezultatus paaiškėjo, kad tas pats skelbimas yra ir darbo dienų, ir savaitgalio
   faile, o atsitiktinis padalijimas 64,5 % testinių eilučių paliko dvynį mokymo imtyje. Gylio 15 F1 0,7197 buvo
   išpūstas: nematytiems skelbimams tik 0,63. Sprendimas: `data_prep.py` skaido pagal vietą (`city`, `lat`, `lng`) su
   `StratifiedGroupKFold`; bendrų vietų 0 (NFR-01a), gylio 15 F1 0,6298, KPI dabar tenkina tik gylis 15 (anksčiau 10
   ir 15). Seni run'ai liko MLflow su tag'u `split=random`. Likusi rizika: keli to paties šeimininko skelbimai
   skirtingose vietose (šeimininko ID duomenyse nėra).
2. **Žemas F1.** Superhost klasė sudaro 25,6 %, todėl negilus miškas beveik niekada nesako „taip“ (gylis 5 be klasių
   svorių: „taip“ tik 4,3 % atvejų, F1 0,227). `class_weight="balanced"` pakėlė F1 iki 0,595–0,630. F1 riboja ir
   duomenyse nesantys veiksniai (viešnagės, atšaukimai, atsakymų dažnis).
3. **Kurso `train.py` su RandomForest lūžta:** MLflow 3.15 modelį saugo skops formatu, kuris nepasitiki medžių tipais
   (`UntrustedTypesFoundException`). Sprendimas: `skops_trusted_types=["sklearn.tree._tree.Tree"]`.
4. **MLflow serveris netilpo į 2 GiB:** kurso komanda paleidžia 18 Python procesų (išmatuota 2,2 GB). Resursai
   nustatyti pagal matavimą: `requests` 2560Mi, `limits` 3Gi.
5. **HIGH CVE `cryptography` 49.0.0** atkeliavo su pilnu `mlflow` 3.15.2 (`cryptography<50`). Vaizde naudojamas
   `mlflow-skinny`: `cryptography` 50.0.2 (pataisyta), vaizdas 745 → 450 MB, Python radinių nebeliko.
6. **NixOS aplinka:** nixpkgs `dvc` sugadino Python 3.12 venv, pip wheel'ams trūko `libstdc++`, o `gh` nebuvo PATH,
   todėl `scripts/publish.sh` iš pradžių neveikė. Sprendimai: `dvc` venv'e, `LD_LIBRARY_PATH` ir `gh` lokaliame
   `shell.nix` (ne Git; kursas Nix nereikalauja).
7. **Nedaryta:** E1, E3, E4, E5. E3 ir E4 laikas skirtas nutekėjimui ištaisyti; E5 reikia NVIDIA GPU (kompiuteryje
   tik AMD).

## Kiek laiko užtruko

~5 val. per dvi dienas.
