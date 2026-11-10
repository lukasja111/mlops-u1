# Airbnb Superhost klasifikatorius: reikalavimai

**Versija:** 1.9
**Data:** 2026-11-10
**Autoriai(-ius):** Lukas Jasiulionis (lukasja111)

## 1. Apimtis

### 1.1 Problema
Prognozuoti, ar Airbnb skelbimo šeimininkas, pagal `kraina/airbnb` naujausius duomenis, turi Superhost statusą, pagal skelbimo požymius: 
- kaina 
- kambario tipas 
- talpa
- įvertinimai
- atstumai
- vietos indeksai
- miestas
- dienų tipas

Fiksuota revizija `b9dd71fc`, CC BY 4.0, 10 Europos miestų, 51 707 įrašai apie 30 125 vietas, iš jų 25,6% Superhost. 
Klasės nesubalansuotos, todėl pagrindinė metrika yra F1 (**Superhost klasė**).
Skelbimo ID rinkinyje nėra, todėl skelbimas atpažįstamas pagal vietą (`city`, `lat`, `lng`); tas pats skelbimas būna ir darbo dienų, ir savaitgalio faile, todėl imtys skaidomos pagal vietą (NFR-01a).

### 1.2 Suinteresuotosios šalys
| Šalis | Interesas |
|---|---|
| ML inžinierius | Greitai kartoti eksperimentus ir atkurti bet kurį run'ą |
| Vertintojas | Paleisti sistemą pagal README, matyti HPO run'ų medį, registrą su `@champion`, veikiantį API, raudoną CD paleidimą ir rollback |
| Šeimininkai / platforma | Suprasti, kurie požymiai susiję su Superhost statusu (`eval/feature_importances.json`) |
| API klientas | Prognozė per `/predict` su žinoma modelio versija (`model_version` atsakyme) |
| Komandinis projektas | Tas pats MLflow serveris su prisijungimais ir registru |

### 1.3 Panaudos atvejai
| ID | Aktorius | Atvejis |
|---|---|---|
| UC-01 | ML inžinierius | Pakeičia hiperparametrą `params.yaml`, paleidžia `dvc repro`; run'as atsiranda klasterio MLflow |
| UC-02 | ML inžinierius | Palygina run'us MLflow UI ir `dvc metrics diff` |
| UC-03 | Vertintojas | Atkuria pasirinktą run'ą `python reproduce.py <run_id>` |
| UC-04 | ML inžinierius | Paleidžia mokymą kaip Kubernetes Job |
| UC-05 | ML inžinierius | Commit'ina `params.yaml` pakeitimą ir paleidžia `bash scripts/cd.sh`; vartą praėjęs modelis tampa `@champion` ir įdiegiamas |
| UC-06 | ML inžinierius | Blogas modelis arba griežtesnis slenkstis: `cd.sh` sustoja ties vartu, API nesikeičia |
| UC-07 | ML inžinierius | `bash scripts/cd.sh rollback` grąžina ankstesnę versiją |
| UC-08 | API klientas | Siunčia skelbimus į `/predict`, gauna klasę, tikimybę ir modelio versiją |

## 2. Funkciniai reikalavimai
| ID | Reikalavimas | Prioritetas |
|---|---|---|
| FR-01 | Modelis pagal skelbimo požymius grąžina klasę: Superhost / ne Superhost | Must |
| FR-02 | `dvc.yaml` pipeline'as `prepare → train → evaluate` iš DVC versijuotų žalių duomenų sukuria modelį ir `metrics.json` | Must |
| FR-03 | Kiekvienas mokymas registruojamas klasterio MLflow: parametrai, metrikos, modelis, duomenų rinkinys, `git_commit` ir `dvc_raw_md5` tag'ai | Must |
| FR-04 | Mokymas supakuotas į Docker vaizdą, paleidžiamą be vietinės Python aplinkos | Must |
| FR-05 | Mokymas paleidžiamas kaip Kubernetes Job, log'inantis į klasterio MLflow; parametrai per ConfigMap, prisijungimai per Secret | Must |
| FR-06 | Hiperparametrų paieška (Optuna, ≥ 5 bandymai) su įdėtiniais MLflow run'ais ir grupine kryžmine validacija mokymo imtyje | Must |
| FR-07 | Vartą praėjęs modelis registruojamas MLflow Model Registry su `git_commit`, `dvc_raw_md5`, metrikų ir `gate` tag'ais; alias'ai `@champion` ir `@previous` | Must |
| FR-08 | Inferencijos API (`/health`, `/predict`) Kubernetes Deployment ir Service; modelis įkeliamas iš registro pagal `@champion`, ne iš failo | Must |
| FR-09 | CD (`scripts/cd.sh`): testai, `dvc repro`, kokybės vartas iš `params.yaml` `gate`, registracija, `MODEL_VERSION` manifeste, diegimas ir smoke testas; vartas blokuoja blogą modelį | Must |
| FR-10 | Rollback (`scripts/cd.sh rollback`) grąžina `@champion` į `@previous` ir perdiegia API | Must |

## 3. Nefunkciniai reikalavimai
| ID | Kategorija | Reikalavimas | KPI | Išmatuota |
|---|---|---|---|---|
| NFR-01 | Kokybė | Superhost klasės F1 testinėje imtyje | F1 ≥ 0,62 (`metrics.json` raktas `f1`, tas pats slenkstis `params.yaml` `gate.min_f1`) | v3 (HPO, 5 grupės): 0,6370; v2 (HPO, 3 grupės): 0,6340; U1 gylis 5 / 10 / 15: 0,5943 / 0,6191 / 0,6393 |
| NFR-01a | Vertinimo validumas | Tas pats skelbimas nepatenka ir į mokymo, ir į testinę imtį | 0 bendrų vietų (`lat`, `lng`) tarp `train.csv` ir `test.csv`; patikra README 5 žingsnyje | 0 (v1.2 atsitiktinis padalijimas: 6 321) |
| NFR-02 | Kokybė | Modelis geresnis už „visada ne Superhost“ | accuracy ≥ 0,75 („visada ne“ duoda 0,744; `gate.min_accuracy`) | v3 0,7766; v2 0,7716; U1 0,7095 / 0,7423 / 0,7833 |
| NFR-03 | Našumas | Mokymo trukmė CPU | HPO run'as (20 bandymų po 5 grupes) ≤ 5 min, vienas modelis ≤ 2 min (MLflow run'o trukmė) | HPO 157 s (16 gijų); Job'o run'as su vienu modeliu 19,9 s (pats Job'as 30 s); U1 `train` 6,7 iki 9,0 s |
| NFR-04 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres` | išliko 10/10 run'ų ir modelių |
| NFR-05 | Saugumas | MLflow serveris nepasiekiamas iš tinklo | klausosi tik `127.0.0.1:5000` (kind `listenAddress`, `ss -ltn`) | tik `127.0.0.1:5000` |
| NFR-06 | Saugumas | Jokių paslapčių Git repozitorijoje | 0 slaptažodžių ir token'ų (`git grep -i password`); prisijungimai tik K8s Secret | 0 (tik Secret raktų ir kintamųjų pavadinimai) |
| NFR-07 | Privatumas | Jokių asmenį identifikuojančių duomenų | nėra šeimininkų vardų ar ID; žali duomenys ne Git (`git ls-files data/`) | tik `data/.gitignore` ir `data/raw.dvc` |
| NFR-08 | Atkartojamumas | Istorinis run'as atkuriamas `python reproduce.py <run_id>` | ≤ 2 min; \|Δaccuracy\| ir \|Δf1\| ≤ 0,005 | 32 s, abu Δ = 0,0000 (`e8e623d7` atkurtas kaip `9f177ff7`); U1 klasteryje 22 s |
| NFR-09 | Atsekamumas | Kiekvienas run'as turi `git_commit` ir `dvc_raw_md5` tag'us | 100 % pagrindinių run'ų | 12/12; 2 iš jų (`299b7851`, `ce7777dd`) pažymėti `superseded`, nes mokyti iš necommit'into kodo ir jų `git_commit` neteisingas (80 įdėtinių HPO bandymų žymų neturi, jų tėvinis run'as pažymėtas) |
| NFR-10 | Duomenų versija | Mokymo duomenų versija fiksuota DVC | `dvc.lock` `data/raw` md5 = run'o `dvc_raw_md5`, 100 % pagrindinių run'ų | `a2b156db…` sutampa 12/12 |
| NFR-11 | Dydis | Mokymo vaizdas kuo mažesnis | rootfs ≤ 500 MB (`docs/docker-image.md`) | 449,68 MB (`sha-08fbb275`) |
| NFR-12 | Saugumas | 0 CRITICAL pažeidžiamumų prieš įkeliant vaizdą į klasterį | `trivy image --scanners vuln --severity CRITICAL --exit-code 1` grąžina 0 prieš `kind load` (README 7 žingsnis); HIGH aptarti `docs/docker-image.md` | `sha-ca7ea995` api ir train: CRITICAL 0; api HIGH 47 (11 Debian CVE be pataisų, Python 0); U1 `sha-08fbb275` HIGH 44 |
| NFR-13 | Saugumas | Konteineriai vykdomi ne root | UID ≠ 0: mokymo vaizdas (`docker run --rm --entrypoint id <vaizdas> -u`), API ir Job `runAsNonRoot: true`, `runAsUser: 1000`; MLflow ir Postgres naudoja oficialius vaizdus ir pasiekiami tik per `127.0.0.1` (NFR-05) | uid 1000 (`mluser`) |
| NFR-14 | Našumas | Inferencijos vėlinimas | p95 ≤ 100 ms vienam skelbimui (`scripts/load_test.py`, 500 nuoseklių užklausų, `docs/load-test.json`) | p95 20,3 ms (p50 14,3, p99 22,4), v3, 2 replikos |
| NFR-15 | Našumas | Pralaidumas | ≥ 50 užklausų/s su 8 lygiagrečiais klientais | 94,1 užklausų/s |
| NFR-16 | Dydis | Modelio dydis | `model.pkl` ≤ 100 MB (MLflow metrika `model_size_mb`) | 31,13 MB (v3) |
| NFR-17 | Dydis | API vaizdas kuo mažesnis | rootfs ≤ 500 MB (`du -sx --apparent-size`) | 439,98 MB (`sha-ca7ea995`) |
| NFR-18 | Kokybė | Blogas modelis neįdiegiamas | modelis žemiau `gate` slenksčių neregistruojamas, `@champion` ir API nesikeičia, `cd.sh` išėjimo kodas 1 | 2 iš 2 raudonų paleidimų sustabdyti: slenkstis 0,99 per 12,2 s, `max_depth: 5` (F1 0,5943) per 34,3 s |
| NFR-19 | Patikimumas | Rollback į ankstesnę versiją | `scripts/cd.sh rollback` iki smoke testo ≤ 60 s | 25,8 s (v3 → v2) ir 25,9 s (v2 → v3) |
| NFR-20 | Patikimumas | API veikia keičiant versiją | 2 replikos, `readinessProbe`, `preStop` 5 s; rollback'o metu nukritusių užklausų < 0,1 % | 1 iš 1 386 ir 0 iš 1 463 (be `preStop` 28 iš 1 827) |
| NFR-21 | Saugumas | MLflow prieiga tik su prisijungimu | anoniminis API kvietimas 401; `viewer` rašymas ir `serving` alias'o keitimas 403 | 401 / 403 / 403 |

Nutekėjimas tarp imčių įvyko v1.2: atsitiktinis padalijimas paliko 6 321 bendrą vietą, ir gylio 15 F1 0,7197 buvo išpūstas; v1.3 ištaisyta padalijimu pagal vietą (NFR-01a). Lieka to paties šeimininko skelbimai skirtingose vietose, nes šeimininko ID nėra.
U2 hiperparametrai renkami 5 grupių kryžmine validacija mokymo imtyje (grupės pagal vietą, kaip NFR-01a), testinė imtis naudojama tik galutiniam modeliui; v3 F1 0,6370, tik 0,017 virš NFR-01 slenksčio.
U2 vaizdai į registrą nepublikuojami (autoriaus sprendimas U2 nekelti į jokį nuotolinį repo): tag'as `sha-<commit>`, Trivy vartas prieš `kind load` (NFR-12).

## 4. Keitimo istorija
| Versija | Data | Autorius | Pakeitimai |
|---|---|---|---|
| 1.0 | 2026-10-19 | lukasja111 | Pradinis dokumentas: problema, suinteresuotosios šalys, panaudos atvejai, FR, NFR su KPI, rizikos |
| 1.1 | 2026-10-19 | lukasja111 | Reprodukcijos, atsekamumo ir duomenų versijos NFR; visos reikšmės išmatuotos klasterio run'uose |
| 1.2 | 2026-10-19 | lukasja111 | Mokymo vaizdo NFR: dydis, Trivy, ne root |
| 1.3 | 2026-10-19 | lukasja111 | Rastas ir ištaisytas nutekėjimas tarp imčių (tas pats skelbimas abiejose); naujas padalijimo NFR; reikšmės išmatuotos iš naujo |
| 1.4 | 2026-10-19 | lukasja111 | Sutrumpinta; padalijimo NFR pervadintas NFR-01a (saugo NFR-01); NFR-03 matuojamas run'o trukme |
| 1.5 | 2026-10-20 | lukasja111 | Dokumentų redakcijos prieš pridavimą, bugų ieškojimas |
| 1.6 | 2026-10-20 | lukasja111 | Naujas seed 133707331 padalijimui ir modeliui; visos reikšmės išmatuotos iš naujo; vaizdas perpublikuotas kaip `sha-08fbb275` |
| 1.7 | 2026-10-21 | lukasja111 | Sutrumpinta: NFR vienoje lentelėje, KPI ir išmatuotos reikšmės atskiruose stulpeliuose, KPI, prielaidų ir rizikų skyriai įlieti; NFR-01a patikra perkelta į README; `docs/image-sizes.md` ir `docs/security-scan.md` sujungti į `docs/docker-image.md` |
| 1.8 | 2026-10-21 | lukasja111 | Galutinė versija prieš `u1-final`: `dvc.lock` atnaujintas po `src/` komentarų, NFR-09 ir NFR-10 išmatuota iš naujo (21/21); README patikrintas nuo nulio NixOS ir CachyOS (su Nix ir be) |
| 1.9 | 2026-11-10 | lukasja111 | U2: hiperparametrų paieška, registras, API, CD su kokybės vartu ir rollback; inferencijos NFR (vėlinimas, pralaidumas, modelio ir API vaizdo dydis, vartas, rollback, MLflow prieiga) išmatuoti klasteryje; kokybės, trukmės ir atsekamumo reikšmės išmatuotos iš naujo; vaizdai nepublikuojami, tik `kind load` |
