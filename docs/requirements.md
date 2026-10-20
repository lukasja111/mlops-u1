# Airbnb Superhost klasifikatorius: reikalavimai

**Versija:** 1.6
**Data:** 2026-10-20
**Autoriai(-ius):** Lukas Jasiulionis (lukasja111)

## 1. Apimtis

### 1.1 Problema
Prognozuoti, ar Airbnb skelbimo šeimininkas turi Superhost statusą, pagal skelbimo požymius (kaina, kambario
tipas, talpa, įvertinimai, atstumai, vietos indeksai, miestas, dienų tipas). Duomenys: HF `kraina/airbnb`
(fiksuota revizija `b9dd71fc`, CC BY 4.0), 10 Europos miestų, 51 707 įrašai apie 30 125 vietas, iš jų 25,6 %
Superhost. Klasės nesubalansuotos, todėl pagrindinė metrika yra F1 (Superhost klasė).

### 1.2 Suinteresuotosios šalys
| Šalis | Interesas |
|---|---|
| ML inžinierius (studentas) | Greitai kartoti eksperimentus ir atkurti bet kurį run'ą |
| Vertintojas (dėstytojas) | Paleisti sistemą pagal README, matyti ≥3 run'us klasterio MLflow |
| Šeimininkai / platforma | Suprasti, kurie požymiai susiję su Superhost statusu (`eval/feature_importances.json`) |
| U2 / komandinis projektas | Tas pats MLflow serveris modelių registrui |

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
| FR-02 | `dvc.yaml` pipeline'as `prepare → train → evaluate` iš DVC versijuotų žalių duomenų sukuria modelį ir `metrics.json` | Must |
| FR-03 | Kiekvienas mokymas registruojamas klasterio MLflow: parametrai, metrikos, modelis, duomenų rinkinys, `git_commit` ir `dvc_raw_md5` tag'ai | Must |
| FR-04 | Mokymas supakuotas į Docker vaizdą, paleidžiamą be vietinės Python aplinkos | Must |
| FR-05 | Mokymas paleidžiamas kaip Kubernetes Job, log'inantis į klasterio MLflow | Should |

## 3. Nefunkciniai reikalavimai
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-01 | Kokybė | Superhost klasės F1 testinėje imtyje | F1 ≥ 0,62 (`metrics.json` raktas `f1`). Išmatuota (`max_depth` 5 / 10 / 15): 0,5943 / 0,6191 / 0,6393; tenkina tik 15 (dabar `params.yaml`) |
| NFR-01a | Vertinimo validumas | Tas pats skelbimas nepatenka ir į mokymo, ir į testinę imtį | 0 bendrų vietų (`lat`, `lng`) tarp `train.csv` ir `test.csv`; tikrinama komanda po lentele. Išmatuota: 0 (v1.2 atsitiktinis padalijimas: 6 321 bendra vieta) |
| NFR-02 | Kokybė | Modelis geresnis už „visada ne Superhost“ | accuracy ≥ 0,75 („visada ne“ duoda 0,744). Išmatuota: 0,7095 / 0,7423 / 0,7833; tenkina tik 15 |
| NFR-03 | Našumas | Mokymo trukmė CPU | `train` stage'as ≤ 2 min; matuojama MLflow run'o trukme. Išmatuota: nuo 6,7 iki 9,0 s; visas `dvc repro --force` per `reproduce.py` 22 s |
| NFR-04 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres`. Išmatuota: išliko 10/10 run'ų ir modelių, modelis įkeltas iš serverio |
| NFR-05 | Saugumas | MLflow serveris nepasiekiamas iš tinklo | Klausosi tik `127.0.0.1:5000` (kind `listenAddress`); tikrinama `ss -ltn`. Išmatuota: tik `127.0.0.1:5000` |
| NFR-06 | Saugumas | Jokių paslapčių Git repozitorijoje | 0 slaptažodžių ir token'ų, prisijungimai tik K8s Secret; tikrinama `git grep -i password`. Išmatuota: 0 (tik Secret raktų pavadinimai) |
| NFR-07 | Privatumas | Jokių asmenį identifikuojančių duomenų | Duomenyse nėra šeimininkų vardų ar ID, žali duomenys ne Git; tikrinama `git ls-files data/`. Išmatuota: tik `data/.gitignore` ir `data/raw.dvc` |

NFR-01a patikra (turi išvesti 0):

```bash
python -c "
import pandas as pd
train, test = pd.read_csv('data/processed/train.csv'), pd.read_csv('data/processed/test.csv')
print(len(set(zip(train.lat, train.lng)) & set(zip(test.lat, test.lng))))"
```

### 3.1 Eksperimentų sekimo ir atkartojamumo NFR (v1.1)
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-08 | Atkartojamumas | Bet kuris istorinis run'as atkuriamas `python reproduce.py <run_id>` | ≤ 2 min (duomenys jau DVC cache), \|Δaccuracy\| ir \|Δf1\| ≤ 0,005; matuojama su `time`. Išmatuota: 22 s, abu Δ = 0,0000 (`cb0eac03` atkurtas kaip `1f02d0d1`) |
| NFR-09 | Atsekamumas | Kiekvienas run'as turi `git_commit` ir `dvc_raw_md5` tag'us | 100 % run'ų; tikrinama MLflow paieška. Išmatuota: 18/18 |
| NFR-10 | Duomenų versija | Mokymo duomenų versija fiksuota DVC | `dvc.lock` `data/raw` md5 = run'o `dvc_raw_md5`, 100 % run'ų. Išmatuota: `a2b156db…` sutampa 18/18 |

### 3.2 Konteinerizacijos NFR (v1.2)
| ID | Kategorija | Reikalavimas | Metrika/KPI |
|---|---|---|---|
| NFR-11 | Dydis | Mokymo vaizdas kuo mažesnis | rootfs ≤ 500 MB (`du --apparent-size`, MB = 1 000 000 B; `docs/image-sizes.md`). Išmatuota: 449,63 MB (`sha-71249941`) |
| NFR-12 | Saugumas | 0 CRITICAL pažeidžiamumų prieš publikavimą | `trivy image --scanners vuln --severity CRITICAL --exit-code 1` grąžina 0; HIGH aptarti `docs/security-scan.md`. Išmatuota: CRITICAL 0, HIGH 44 (8 Debian CVE be pataisų) |
| NFR-13 | Saugumas | Konteineris vykdomas ne root | UID ≠ 0; tikrinama `docker run --rm --entrypoint id <vaizdas> -u`. Išmatuota: uid 1000 (`mluser`) |

## 4. KPI
- **Modelio:** F1 (Superhost) pagrindinė; accuracy lyginama su 0,744; precision ir recall informacinės.
- **Sistemos:** mokymo trukmė, MLflow pasiekiamumas, run'ų išlikimas perkūrus Pod'us.
- **Proceso:** 100 % run'ų su `git_commit` ir `dvc_raw_md5`.

## 5. Prielaidos
- Skelbimo ID rinkinyje nėra, todėl skelbimas atpažįstamas pagal vietą (`city`, `lat`, `lng`). Jis būna ir darbo
  dienų, ir savaitgalio faile, todėl imtys skaidomos pagal vietą (NFR-01a).
- F1 ribotas: Superhost statusas priklauso ir nuo duomenyse nesančių veiksnių (viešnagės, atšaukimai, atsakymų
  dažnis).
- Vieno mazgo kind klasteris kūrėjo kompiuteryje, be GPU.
- MLflow klientas ir serveris 3.15.2; autentifikacijos nėra, todėl serveris pasiekiamas tik per localhost.
- NFR-13 taikomas mokymo vaizdui (vieninteliam savam). MLflow ir Postgres Pod'ai naudoja oficialius vaizdus su jų
  numatytais naudotojais ir pasiekiami tik per `127.0.0.1` (NFR-05).

## 6. Rizikos
| Rizika | Tikimybė | Poveikis | Mažinimas |
|---|---|---|---|
| HF rinkinys pasikeičia | Maža | Didelis | Fiksuota revizija + DVC md5 + DVC remote |
| `kind delete cluster` ištrina MLflow duomenis | Vidutinė | Didelis | Dokumentuota README; run'ai atkuriami `reproduce.py` |
| Priklausomybių versijų dreifas | Vidutinė | Vidutinis | Tiesioginės priklausomybės `==`, Python 3.12 |
| Duomenų nutekėjimas: tas pats skelbimas abiejose imtyse | Įvyko (v1.2) | Didelis | Ištaisyta v1.3 (NFR-01a): gylio 15 F1 0,7197 → 0,6298. Lieka: to paties šeimininko skelbimai skirtingose vietose (šeimininko ID nėra) |
| Gylio 15 F1 tik 0,02 virš NFR-01 slenksčio | Vidutinė | Vidutinis | Hiperparametrai nerenkami pagal testinę imtį; U2: kryžminė validacija su grupėmis mokymo imtyje |

## 7. Keitimo istorija
| Versija | Data | Autorius | Pakeitimai |
|---|---|---|---|
| 1.0 | 2026-10-19 | lukasja111 | Pradinis dokumentas: problema, suinteresuotosios šalys, panaudos atvejai, FR, NFR su KPI, rizikos |
| 1.1 | 2026-10-19 | lukasja111 | Reprodukcijos, atsekamumo ir duomenų versijos NFR; visos reikšmės išmatuotos klasterio run'uose |
| 1.2 | 2026-10-19 | lukasja111 | Mokymo vaizdo NFR: dydis, Trivy, ne root |
| 1.3 | 2026-10-19 | lukasja111 | Rastas ir ištaisytas nutekėjimas tarp imčių (tas pats skelbimas abiejose); naujas padalijimo NFR; reikšmės išmatuotos iš naujo |
| 1.4 | 2026-10-19 | lukasja111 | Sutrumpinta; padalijimo NFR pervadintas NFR-01a (saugo NFR-01); NFR-03 matuojamas run'o trukme |
| 1.5 | 2026-10-20 | lukasja111 | Dokumentų redakcijos prieš pridavimą, bugų ieškojimas |
| 1.6 | 2026-10-20 | lukasja111 | Naujas seed 133707331 padalijimui ir modeliui; visos reikšmės išmatuotos iš naujo |
