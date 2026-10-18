# Airbnb Superhost klasifikatorius — reikalavimai

**Versija:** 1.0
**Data:** 2026-10-19
**Autoriai(-ius):** Lukas Jasiulionis (lukasja111)

## 1. Apimtis

### 1.1 Problema
Prognozuoti, ar Airbnb skelbimo šeimininkas turi Superhost statusą, pagal skelbimo požymius: kainą, kambario
tipą, talpą, įvertinimus, atstumą iki centro ir metro, vietos indeksus, miestą ir dienų tipą (darbo dienos /
savaitgalis). Duomenys — vieši 10 Europos miestų Airbnb skelbimai (HF `kraina/airbnb`, fiksuota revizija
`b9dd71fc`, CC BY 4.0; Gyódi & Nawaro, 2021): 51 707 skelbimai, 25,6 % — Superhost (nuo 14 % Paryžiuje iki
43 % Atėnuose). Klasės nesubalansuotos, todėl pagrindinė metrika — F1 (Superhost klasė). Vertinamas srautas
aplink modelį (DVC, MLflow, Kubernetes), ne aukščiausia modelio kokybė.

### 1.2 Suinteresuotosios šalys
| Šalis | Interesas |
|---|---|
| ML inžinierius (studentas) | Greitai kartoti eksperimentus ir atkurti bet kurį run'ą |
| Vertintojas (dėstytojas) | Paleisti sistemą pagal README be paslėptų žingsnių, matyti ≥3 run'us klasterio MLflow |
| Šeimininkai / platforma | Suprasti, kurie skelbimo požymiai susiję su Superhost statusu |
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
| NFR-01 | Kokybė | Superhost klasės F1 testinėje imtyje | F1 ≥ 0,62 (`metrics.json` raktas `f1`). Nepasiekus — keičiami hiperparametrai |
| NFR-02 | Kokybė | Modelis geresnis už „visada ne Superhost“ | accuracy ≥ 0,75 („visada ne“ — 0,744). Nepasiekus — keičiami hiperparametrai |
| NFR-03 | Našumas | Mokymo trukmė CPU | `train` stage'as ≤ 2 min; matuojama `time dvc repro --force -s train` |
| NFR-04 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres` |
| NFR-05 | Saugumas | MLflow serveris nepasiekiamas iš tinklo | Klausosi tik `127.0.0.1:5000` (kind `listenAddress`); tikrinama `ss -ltn` |
| NFR-06 | Saugumas | Jokių paslapčių Git repozitorijoje | 0 slaptažodžių / token'ų; Postgres prisijungimai tik K8s Secret; tikrinama `git grep -i password` |
| NFR-07 | Privatumas | Jokių asmenį identifikuojančių duomenų | Duomenyse nėra šeimininkų vardų ar ID; žali duomenys ne Git (tik `data/raw.dvc`); tikrinama `git ls-files data/` |

## 4. KPI
- **Modelio:** F1 (Superhost) — pagrindinė; accuracy lyginama su 0,744 („visada ne“); precision ir recall — informacinės.
- **Sistemos:** mokymo trukmė, MLflow pasiekiamumas demonstracijos metu, run'ų išlikimas perkūrus Pod'us.
- **Proceso:** 100 % run'ų turi `git_commit` ir `dvc_raw_md5` tag'us.

## 5. Prielaidos
- HF rinkinys naudojamas fiksuota revizija; žalių duomenų baitus fiksuoja DVC (`data/raw.dvc`).
- Superhost statusas priklauso ir nuo duomenyse nesančių veiksnių (viešnagių skaičius, atšaukimai, atsakymų
  dažnis), todėl F1 lubos ≈ 0,75.
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

## 7. Keitimo istorija
| Versija | Data | Pakeitimai |
|---|---|---|
| 1.0 | 2026-10-19 | Pradinė versija: apimtis, FR-01..05, NFR-01..07 |
