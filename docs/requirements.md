# Airbnb Superhost klasifikatorius — reikalavimai

**Versija:** 1.3
**Data:** 2026-10-19
**Autoriai(-ius):** Lukas Jasiulionis (lukasja111)

## 1. Apimtis

### 1.1 Problema
Prognozuoti, ar Airbnb skelbimo šeimininkas turi Superhost statusą, pagal skelbimo požymius: kainą, kambario
tipą, talpą, įvertinimus, atstumą iki centro ir metro, vietos indeksus, miestą ir dienų tipą (darbo dienos /
savaitgalis). Duomenys — vieši 10 Europos miestų Airbnb skelbimai (HF `kraina/airbnb`, fiksuota revizija
`b9dd71fc`, CC BY 4.0; Gyódi & Nawaro, 2021): 51 707 įrašai apie 30 125 vietas (tas pats skelbimas būna ir darbo
dienų, ir savaitgalio faile), 25,6 % — Superhost (nuo 14 % Paryžiuje iki 43 % Atėnuose). Klasės nesubalansuotos,
todėl pagrindinė metrika — F1 (Superhost klasė). Vertinamas srautas aplink modelį (DVC, MLflow, Kubernetes), ne
aukščiausia modelio kokybė.

### 1.2 Suinteresuotosios šalys
| Šalis | Interesas |
|---|---|
| ML inžinierius (studentas) | Greitai kartoti eksperimentus ir atkurti bet kurį run'ą |
| Vertintojas (dėstytojas) | Paleisti sistemą pagal README be paslėptų žingsnių, matyti ≥3 run'us klasterio MLflow |
| Šeimininkai / platforma | Suprasti, kurie skelbimo požymiai susiję su Superhost statusu (MLflow artefaktas `eval/feature_importances.json`) |
| U2 / komandinis projektas | Tas pats MLflow serveris naudojamas modelių registrui |

### 1.3 Panaudos atvejai
| ID | Aktorius | Atvejis |
|---|---|---|
| UC-01 | ML inžinierius | Pakeičia hiperparametrą `params.yaml`, paleidžia `dvc repro`; run'as atsiranda klasterio MLflow |
| UC-02 | ML inžinierius | Palygina run'us MLflow UI ir `dvc metrics diff` |
| UC-03 | Vertintojas | Atkuria pasirinktą run'ą `python reproduce.py <run_id>` |
| UC-04 | ML inžinierius | Paleidžia mokymą kaip Kubernetes Job |

## 2. Funkciniai reikalavimai
| ID | Reikalavimas | Prioritetas |
|---|---|---|
| FR-01 | Modelis pagal skelbimo požymius grąžina klasę: Superhost / ne Superhost | Must |
| FR-02 | `dvc.yaml` pipeline'as `prepare → train → evaluate` iš DVC versijuotų žalių duomenų (20 CSV) sukuria modelį ir `metrics.json` | Must |
| FR-03 | Kiekvienas mokymas registruojamas klasterio MLflow: parametrai, metrikos, modelis, duomenų rinkinys, `git_commit` ir `dvc_raw_md5` tag'ai | Must |
| FR-04 | Mokymas supakuotas į Docker vaizdą, paleidžiamą be vietinės Python aplinkos | Must |
| FR-05 | Mokymas paleidžiamas kaip Kubernetes Job, log'inantis į klasterio MLflow | Should |

## 3. Nefunkciniai reikalavimai
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-01 | Kokybė | Superhost klasės F1 testinėje imtyje | F1 ≥ 0,62 (`metrics.json` raktas `f1`). Nepasiekus — keičiami hiperparametrai. Išmatuota (padalijimas pagal skelbimą): 0,5947 / 0,6181 / 0,6298 (`max_depth` 5 / 10 / 15); tenkina tik 15, `params.yaml` dabar 15 |
| NFR-02 | Kokybė | Modelis geresnis už „visada ne Superhost“ | accuracy ≥ 0,75 („visada ne“ — 0,744). Nepasiekus — keičiami hiperparametrai. Išmatuota: 0,7121 / 0,7440 / 0,7764 (`max_depth` 5 / 10 / 15); tenkina tik 15 |
| NFR-03 | Našumas | Mokymo trukmė CPU | `train` stage'as ≤ 2 min; matuojama `time dvc repro --force -s train`. Išmatuota: `reproduce.py` su visu `dvc repro --force` (3 stage'ai) 20 s; MLflow run'o trukmė 6,5–9,1 s (`max_depth` 5–15) |
| NFR-04 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres`. Išmatuota: abu Pod'ai perkurti (pirma Postgres, po to MLflow), RESTARTS 0; išliko 10/10 run'ų ir 10/10 modelių, `rf-n100-d15` modelis įkeltas iš serverio (F1 0,6298) |
| NFR-05 | Saugumas | MLflow serveris nepasiekiamas iš tinklo | Klausosi tik `127.0.0.1:5000` (kind `listenAddress`); tikrinama `ss -ltn`. Išmatuota: `ss -ltn` rodo tik `127.0.0.1:5000` |
| NFR-06 | Saugumas | Jokių paslapčių Git repozitorijoje | 0 slaptažodžių / token'ų; Postgres prisijungimai tik K8s Secret; tikrinama `git grep -i password`. Išmatuota: 0; randamos tik nuorodos į Secret raktus. MLflow slaptažodį gauna iš Secret per `PGPASSWORD`, procesų argumentuose jo nėra |
| NFR-07 | Privatumas | Jokių asmenį identifikuojančių duomenų | Duomenyse nėra šeimininkų vardų ar ID; žali duomenys ne Git (tik `data/raw.dvc`); tikrinama `git ls-files data/`. Išmatuota: tik `data/.gitignore` ir `data/raw.dvc` |

### 3.1 Eksperimentų sekimo ir atkartojamumo NFR (v1.1)
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-08 | Atkartojamumas | Bet kuris istorinis run'as atkuriamas `python reproduce.py <run_id>` | ≤ 2 min (duomenys jau DVC cache), \|Δaccuracy\| ≤ 0,005 ir \|Δf1\| ≤ 0,005; matuojama `time python reproduce.py <run_id>`. Išmatuota: 20 s, Δaccuracy = 0,0000, Δf1 = 0,0000 (run'as `6ef2b108` atkurtas kaip `4fbc102c` su tag'u `reproduces`) |
| NFR-09 | Atsekamumas | Kiekvienas run'as turi `git_commit` ir `dvc_raw_md5` tag'us | 100 % run'ų; tikrinama MLflow paieška. Išmatuota: 13/13 run'ų (6 senojo padalijimo, 3 eksperimentai, reprodukcija, vaizdo run'as ir 2 Job'o run'ai) |
| NFR-10 | Duomenų versija | Mokymo duomenų versija fiksuota DVC | `dvc.lock` `data/raw` md5 = run'o `dvc_raw_md5` tag'as, 100 % run'ų. Išmatuota: `a2b156db…` sutampa 13/13 |

### 3.2 Konteinerizacijos NFR (v1.2)
NFR-12 (kurso pavyzdžio ONNX vaizdo parengtis) šiam projektui netaikomas; numeracija išlaikyta pagal kursą.

| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-11 | Dydis | Mokymo vaizdas kuo mažesnis | rootfs ≤ 500 MB (`du --apparent-size`, MB = 1 000 000 B); `docs/image-sizes.md`. Išmatuota: 449,63 MB rootfs, Docker .Size 464,85 MB (`sha-71249941`) |
| NFR-13 | Saugumas | 0 CRITICAL pažeidžiamumų prieš publikavimą | `trivy image --scanners vuln --severity CRITICAL --exit-code 1` grąžina 0; HIGH radiniai analizuojami `docs/security-scan.md`. Išmatuota: CRITICAL 0, HIGH 44 (8 Debian CVE, pataisų dar nėra), vartas exit 0 |
| NFR-14 | Saugumas | Konteineris vykdomas ne root | UID ≠ 0; tikrinama `docker run --rm --entrypoint id <vaizdas> -u`. Išmatuota: uid 1000 (`mluser`) |

### 3.3 Duomenų padalijimo NFR (v1.3)
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-15 | Vertinimo validumas | Tas pats skelbimas nepatenka ir į mokymo, ir į testinę imtį | 0 bendrų vietų (`lat`, `lng`) tarp `data/processed/train.csv` ir `test.csv`; tikrinama komanda žemiau. Išmatuota: 0 (atsitiktinis padalijimas v1.2: 6 321 bendra vieta, dvynį mokymo imtyje turėjo 64,5 % testinių eilučių) |

```bash
python -c "import pandas as pd; a, b = (pd.read_csv(f'data/processed/{s}.csv') for s in ('train', 'test')); print(len(set(zip(a.lat, a.lng)) & set(zip(b.lat, b.lng))))"
```

## 4. KPI
- **Modelio:** F1 (Superhost) — pagrindinė; accuracy lyginama su 0,744 („visada ne“); precision ir recall — informacinės.
- **Sistemos:** mokymo trukmė, MLflow pasiekiamumas demonstracijos metu, run'ų išlikimas perkūrus Pod'us.
- **Proceso:** 100 % run'ų turi `git_commit` ir `dvc_raw_md5` tag'us.

## 5. Prielaidos
- HF rinkinys naudojamas fiksuota revizija; žalių duomenų baitus fiksuoja DVC (`data/raw.dvc`).
- Skelbimo ID rinkinyje nėra, todėl skelbimas atpažįstamas pagal vietą (`city`, `lat`, `lng`). Tas pats skelbimas
  būna ir darbo dienų, ir savaitgalio faile, todėl imtys skaidomos pagal vietą (NFR-15).
- Superhost statusas priklauso ir nuo duomenyse nesančių veiksnių (viešnagių skaičius, atšaukimai, atsakymų
  dažnis), todėl F1 ribotas: nematytiems skelbimams ≈ 0,63 (`max_depth` 15).
- Klasteris — vieno mazgo kind kūrėjo kompiuteryje; GPU nenaudojamas.
- MLflow klientas ir serveris — ta pati versija (3.15.2); autentifikacijos nėra, todėl serveris pasiekiamas
  tik per localhost.

## 6. Rizikos
| Rizika | Tikimybė | Poveikis | Mažinimas |
|---|---|---|---|
| HF rinkinys pasikeičia | Maža | Didelis | Fiksuota revizija + DVC md5 + DVC remote |
| `kind delete cluster` ištrina MLflow duomenis | Vidutinė | Didelis | Dokumentuota README; run'ai atkuriami `reproduce.py` |
| Accuracy klaidina dėl klasių disbalanso | Didelė | Vidutinis | Pagrindinė metrika — F1; `class_weight="balanced"` |
| Žymė priklauso nuo nestebimų veiksnių | Didelė | Vidutinis | Realistiški KPI; apribojimas dokumentuotas |
| Priklausomybių versijų dreifas | Vidutinė | Vidutinis | Tiesioginės priklausomybės `==`, Python 3.12 |
| Slaptažodis patenka į Git | Maža | Didelis | Secret kuriamas `kubectl create secret`; tikrinama `git grep` |
| Duomenų nutekėjimas: tas pats skelbimas abiejose imtyse | Įvyko (v1.2) | Didelis | Ištaisyta v1.3: padalijimas pagal vietą, NFR-15. Prieš: 64,5 % testinių eilučių turėjo dvynį, gylio 15 F1 0,7197 (nematytiems skelbimams 0,63); po: 0 bendrų vietų, F1 0,6298 |
| Likęs nutekėjimas per šeimininką (keli jo skelbimai skirtingose vietose) | Vidutinė | Mažas | Šeimininko ID duomenyse nėra; apribojimas dokumentuotas |
| Gylio 15 F1 tik 0,01 virš NFR-01 slenksčio | Vidutinė | Vidutinis | Hiperparametrai nerenkami pagal testinę imtį; U2 — kryžminė validacija su grupėmis mokymo imtyje |

## 7. Keitimo istorija
| Versija | Data | Pakeitimai |
|---|---|---|
| 1.0 | 2026-10-19 | Pradinė versija: apimtis, FR-01..05, NFR-01..07 |
| 1.1 | 2026-10-19 | NFR-08..10 (atkartojamumas, atsekamumas, duomenų versija); NFR-01..07 išmatuotos reikšmės iš 3 klasterio run'ų |
| 1.2 | 2026-10-19 | NFR-11, NFR-13, NFR-14 (konteinerizacija) su išmatuotomis reikšmėmis |
| 1.3 | 2026-10-19 | Nutekėjimas ištaisytas: padalijimas pagal skelbimo vietą, NFR-15; NFR-01..04, NFR-06, NFR-08..11 išmatuotos iš naujo (KPI tenkina tik `max_depth` 15); §1.1 įrašų ir vietų skaičius; §1.2 požymių svarba (`eval/feature_importances.json`); §5 be F1 lubų teiginio; §6 nutekėjimo rizikos |
