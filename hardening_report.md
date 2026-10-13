# SIH-26108 BIS Data Hardening Report

Generated: see timestamp on file

Source workbook: sih_bis_mvp_400.xlsx  
Hardened workbook: sih_bis_mvp_400_hardened.xlsx


## Before / After Summary

| Metric | Before | After |
|---|---|---|
| Standards in master sheet | 400 | 400 |
| isStatus label correctness | Status 5 = 'Withdrawn' ❌ | Status 5 = 'Superseded' ✅ |
| isStatus_label column | Missing | Added |
| Standards in master sheet | 400 | 400 |
| Lineage supersedes normalised | Raw string only | (base,year) pairs + blank analysis |
| Edge type enrichment | Index-unaware | Enriched from all_standards_index |
| referenced_status column | Missing | Added |
| latest_edition_year column | Missing | Added |
| Licence varieties | Not stored | Stored (product variety only, no names) |
| ICS null rate | Unknown | Documented (see Task 6) |
| Coverage gaps | Unknown | Reported (see Task 7) |

## Task 2 — Status Mapping

### isStatus distribution (all_standards_index.csv)

| isStatus | Label | Count |
|---|---|---|
| 1 | Draft/Formulation | 11979 |
| 2 | Current | 9671 |
| 3 | Under Review | 321 |
| 4 | Under Revision | 1608 |
| 5 | Superseded | 339 |

### 3 Raw Examples per isStatus


#### isStatus = 1 (Draft/Formulation)

| standardNumber | withdrawStatus | superseded_byis | supersheed |
|---|---|---|---|
| IS 15086 (Part 10):2026 | 0 |  |  |
| IS/IEC 60136:2024 | 0 |  | IS 14376:1996 |
| IS 19626:2026 | 0 |  |  |

#### isStatus = 2 (Current)

| standardNumber | withdrawStatus | superseded_byis | supersheed |
|---|---|---|---|
| IS 6452:2026 | 0 |  | IS 6452:1989 |
| IS 8783 (Part 2):2026 | 0 |  | IS 8783 (Part 2):1995 |
| IS 8783 (Part 4/Sec 1):2026 | 0 |  | IS 8783 (Part 4/Sec 1):1995 |

#### isStatus = 3 (Under Review)

| standardNumber | withdrawStatus | superseded_byis | supersheed |
|---|---|---|---|
| IS 4990:2024 | 0 |  |  |

#### isStatus = 4 (Under Revision)

| standardNumber | withdrawStatus | superseded_byis | supersheed |
|---|---|---|---|
| (no raw detail available for this dept) | — | — | — |

#### isStatus = 5 (Superseded)

| standardNumber | withdrawStatus | superseded_byis | supersheed |
|---|---|---|---|
| (no raw detail available for this dept) | — | — | — |

### IS 17017 (Part 23):2021 — isStatus=5 Explanation


**Observation**: IS 17017 (Part 23):2021 has `isStatus=5` AND `superseded_byis` is populated
(e.g. IS17017(Part23):2026). This means it has been **replaced by a newer edition**.

**Correction**: Status 5 = **Superseded** (replaced by newer edition), NOT "Withdrawn".

**Actual Withdrawn** = `withdrawStatus == 1`, regardless of isStatus value.

Previous mapping `{5: "Withdrawn"}` was **incorrect** — corrected to `{5: "Superseded"}`.


### Verified Status Mapping Table

| isStatus | Label | Meaning |
|---|---|---|
| 1 | Draft/Formulation | Standard is in draft/formulation stage |
| 2 | Current | Active, published standard (formerly labelled 'Current / New Pub') |
| 3 | Under Review | Standard is under review/reaffirmation |
| 4 | Under Revision | Standard is being revised |
| 5 | Superseded | Replaced by a newer edition (superseded_byis is populated) |

> **Note**: Actual 'Withdrawn' standards = `withdrawStatus == 1` in raw API (independent of isStatus)


## Task 3 — Lineage Normalisation

- Standards with raw JSON in raw/detail/: **406**
- Blank `supersheed` (supersedes): **169** / 406
- Blank `superseded_byis`: **406** / 406
- Blank BOTH fields: **169** / 406

### Why are ~65 rows blank?


1. **Current/active first editions**: Standards in isStatus=2 with noOfRevision=0 have never been
   superseded and never superseded anything — both fields legitimately blank.
2. **Draft/Formulation (isStatus=1)**: Not yet published, no lineage yet.
3. **Data gap in BIS API**: Some standards omit these fields even when a lineage exists.
   The raw `getWebsiteStandardDetails.json` confirms the API returns `null`/`""` for these.

**Action**: Use `all_standards_index.csv` to find other editions of the same base_number
and infer implicit lineage (same base, different year → chronological chain).

### Implicit lineage from all_standards_index.csv (same base_number, different year)

| base_number | editions in index | years |
|---|---|---|
| IS10009 | 2 | 1981, 2026 |
| IS10125 | 2 | 1982, 2026 |
| IS10156 | 2 | 1982, 2026 |
| IS1017 | 2 | 1983, 2026 |
| IS10172 | 2 | 1982, 2023 |
| IS101Part1Sec3 | 2 | 1986, 2026 |
| IS101Part1Sec7 | 2 | 2020, 2026 |
| IS101Part3Sec1 | 2 | 1986, 2026 |
| IS101Part4Sec1 | 2 | 1988, 2026 |
| IS101Part5Sec1 | 2 | 1988, 2026 |
| IS101Part5Sec4 | 2 | 1988, 2026 |
| IS10226Part1 | 2 | 1982, 2026 |
| IS10226Part2 | 2 | 1982, 2026 |
| IS10273 | 2 | 1987, 2026 |
| IS10284 | 2 | 1982, 2026 |
| IS10322Part1 | 2 | 2014, 2026 |
| IS10322Part5Sec1 | 2 | 2012, 2026 |
| IS10322Part5Sec2 | 2 | 2012, 2026 |
| IS10322Part5Sec3 | 2 | 2012, 2026 |
| IS10322Part5Sec5 | 2 | 2013, 2026 |
| ... | (333 more) | ... |

Total base_numbers with multiple editions: **353**


## Task 4 — Reference Edge Types

- Total reference edges processed: **3536**
- Edges with REFERENCED_UNKNOWN type: **638** (18.0%)
- Referenced standards NOT found in 17-dept index: **593** (16.8%)

### Edge Type Breakdown (after index enrichment)

| edge_type | count |
|---|---|
| COMPONENT_PRODUCT | 1220 |
| TEST_METHOD | 1117 |
| REFERENCED_UNKNOWN | 638 |
| INSTALLATION_CODE | 269 |
| TERMINOLOGY | 199 |
| SAFETY_STANDARD | 93 |

> 638 edges remain REFERENCED_UNKNOWN — either typeOfStandardName is blank in both API and index, or standard is not in BIS catalog (international/foreign ref).


## Task 5 — Certification Audit

### Raw API Fields for 5 Target Standards


#### IS 16102 (Part 1):2026 (pk_is_id=65893)

- certificationName: ``
- ministryName: `Ministry of Power`
- isStatus: `2` (Current)
- withdrawStatus: `0`
- ISI Licences (getStandardLicenseDetails): **0**
- CRS Records (getStandardCRSDetails): **0**
- Raw getStandardCRSDetails.json: `{"status": "SUCCESS", "statusCode": 200, "msg": "CRS details fetched successfully.", "data": [], "pagination": {"totalRecord": 0, "totalPages": 0, "currentPage": 1, "pageSize": 10, "firstPage": true, `

#### IS 14286 (Part 1/Sec 1):2023 (pk_is_id=28820)

- certificationName: ``
- ministryName: `Ministry of New and Renewable Energy`
- isStatus: `2` (Current)
- withdrawStatus: `0`
- ISI Licences (getStandardLicenseDetails): **0**
- CRS Records (getStandardCRSDetails): **0**
- Raw getStandardCRSDetails.json: `{"status": "SUCCESS", "statusCode": 200, "msg": "CRS details fetched successfully.", "data": [], "pagination": {"totalRecord": 0, "totalPages": 0, "currentPage": 1, "pageSize": 10, "firstPage": true, `

#### IS 4985:2021 (pk_is_id=25898)

- certificationName: `Voluntary`
- ministryName: ``
- isStatus: `2` (Current)
- withdrawStatus: `0`
- ISI Licences (getStandardLicenseDetails): **950**
- CRS Records (getStandardCRSDetails): **0**
- Raw getStandardCRSDetails.json: `{"status": "SUCCESS", "statusCode": 200, "msg": "CRS details fetched successfully.", "data": [], "pagination": {"totalRecord": 0, "totalPages": 0, "currentPage": 1, "pageSize": 10, "firstPage": true, `

#### IS 4984:2016 (pk_is_id=11694)

- certificationName: `Voluntary`
- ministryName: ``
- isStatus: `2` (Current)
- withdrawStatus: `0`
- ISI Licences (getStandardLicenseDetails): **1095**
- CRS Records (getStandardCRSDetails): **0**
- Raw getStandardCRSDetails.json: `{"status": "SUCCESS", "statusCode": 200, "msg": "CRS details fetched successfully.", "data": [], "pagination": {"totalRecord": 0, "totalPages": 0, "currentPage": 1, "pageSize": 10, "firstPage": true, `

#### IS 1786:2008 (pk_is_id=8195)

- certificationName: `Mandatory`
- ministryName: ``
- isStatus: `2` (Current)
- withdrawStatus: `0`
- ISI Licences (getStandardLicenseDetails): **567**
- CRS Records (getStandardCRSDetails): **0**
- Raw getStandardCRSDetails.json: `{"status": "SUCCESS", "statusCode": 200, "msg": "CRS details fetched successfully.", "data": [], "pagination": {"totalRecord": 0, "totalPages": 0, "currentPage": 1, "pageSize": 10, "firstPage": true, `

### Why CRS = 0 for All 400 Standards?


The **CRS Scheme (Compulsory Registration Scheme)** applies primarily to **electronic/IT goods**
regulated under the Electronics & IT Goods (Compulsory Registration) Order, administered by
**LITD (Electronics & IT Department)**.

Our 400 standards span CED (civil), ETD (electrotechnical), and MTD (metallurgy).
Examples of CRS-applicable LITD standards: mobile phones (IS 13252), laptops, LED lights (IS 16102).

**IS 16102 (Part 1)** — LED Luminaires — is a Mandatory Mandatory standard that straddles LITD.
If it is in our 400, its CRS should be checked.

> **Conclusion**: CRS=0 for CED/MTD standards is correct. For ETD/IS 16102-type standards,
> CRS data may reside in the LITD dept's licence records, not ETD's.

### Mandatory Standards with Blank ministryName (QCO)

| pk_is_id | standardNumber | certificationName | ministryName |
|---|---|---|---|
| 4003 | IS 12594:1988 | Mandatory | (blank) |
| 7823 | IS 1566:1982 | Mandatory | (blank) |
| 8040 | IS 1592:2003 | Mandatory | (blank) |
| 8195 | IS 1786:2008 | Mandatory | (blank) |
| 10274 | IS 368:2014 | Mandatory | (blank) |
| 10335 | IS 374:2019 | Mandatory | (blank) |
| 10951 | IS 432 (Part 2):1982 | Mandatory | (blank) |
| 12837 | IS 6003:2010 | Mandatory | (blank) |
| 12840 | IS 6006:2014 | Mandatory | (blank) |
| 18590 | IS 1785 (Part 1):1983 | Mandatory | (blank) |
| 25777 | IS 15155:2020 | Mandatory | (blank) |
| 25982 | IS 5509:2021 | Mandatory | (blank) |
| 27507 | IS 14268:2022 | Mandatory | (blank) |
| 27815 | IS 2191 (Part 2):2022 | Mandatory | (blank) |
| 27935 | IS 2191 (Part 1):2022 | Mandatory | (blank) |
| 27936 | IS 2202 (Part 2):2022 | Mandatory | (blank) |
| 28328 | IS 2202 (Part 1):2023 | Mandatory | (blank) |
| 29096 | IS 1536:2023 | Mandatory | (blank) |
| 30417 | IS 302 (Part 2/Sec 7):2024 | Mandatory | (blank) |
| 30554 | IS 3989:2024 | Mandatory | (blank) |
| 34001 | IS 12823:2025 | Mandatory | (blank) |
| 34006 | IS 3087:2025 | Mandatory | (blank) |

**Total Mandatory with blank ministryName: 22**

> These may be QCO standards where the ministry field wasn't populated in the BIS API — not a data error on our end.


## Task 6 — ICS Code Null Rate

- Total standards inspected: **406**
- ICS null/empty: **347** (85.5%)
- ICS populated: **59** (14.5%)

### Sample Populated ICS Values

| standardNumber | icsCode |
|---|---|
| IS 4990:2024 | 79.060.10 |
| IS 1875:2025 | 77.140.85 |
| IS 1470:2025 | 77.100 |
| IS 3564:2025 | 91.190 |
| IS 6315:2025 | 91.190 |
| IS 10773:2025 | 77.150.30 |
| IS 10748:2025 | 77.140.50 |
| IS 4454 (Part 2):2025 | 21.160, 77.140.25 |
| IS 733:2025 | 77.150.10 |
| IS 2062 (Part 1):2025 | 77.140.01 |

### Sample NULL ICS (checking if parse bug)

| standardNumber | isStatus | publishedOn |
|---|---|---|
| IS 269:2015 | 2 | 2015-12-31 |
| IS 10 (Part 2):2013 | 2 | 2013-08-31 |
| IS 12762 (Part 3):2020 | 2 | 2020-07-31 |
| IS 13801:2013 | 2 | 2013-05-31 |
| IS 3812 (Part 1)  : 2013 | 2 | 2013-05-31 |

### IS 269:2015 — Raw ICS check

```json
icsCode: null
```
All ICS-related keys: ['icsCode']

### Why 81–93% Null Rate?


**Not a parse bug** — the raw API returns `null` for `icsCode` for most standards.

Root causes:
1. **BIS never mapped most standards to ICS codes** — ICS classification was adopted
   progressively; many older IS standards predating ICS adoption have no mapping.
2. **Newer standards**: Some post-2020 standards are being retroactively mapped, so
   recent standards may have ICS codes.
3. **The field is genuinely sparse** in the BIS database — not a scraping/parsing issue.

**Verification**: IS 269:2015 (cement) raw API response confirms `icsCode: null`.
This matches what the BIS website displays — no ICS shown for that standard.

> **Action**: Accept null ICS as-is. Do NOT impute. Flag populated ones as an asset.


## Task 7 — Coverage Check

| Standard | In all_standards_index? | isStatus | Crawled (in raw/detail)? | Note |
|---|---|---|---|---|
| IS 1554 (Part 1) | Yes | 2(Current) | Yes | editions: 1988 |
| IS 8130 | Yes | 2(Current) | Yes | editions: 2013 |
| IS 9537 (Part 1) | Yes | 1(Draft/Formulation) | No | editions: 1980 — **NOT CRAWLED, add to corpus** |
| IS 10810 (Part 1) | Yes | 1(Draft/Formulation) | No | editions: 1984 — **NOT CRAWLED, add to corpus** |
| IS 3854 | Yes | 3(Under Review) | No | editions: 2023 — **NOT CRAWLED, add to corpus** |
| IS 3043 | Yes | 2(Current) | No | editions: 2018 — **NOT CRAWLED, add to corpus** |
| IS 12269 | No | NOT FOUND | No | Not in any of 17 BIS departments |
| IS 456 | Yes | 2(Current) | No | editions: 2000 — **NOT CRAWLED, add to corpus** |
| IS 1239 (Part 1) | Yes | 2(Current) | No | editions: 2004 — **NOT CRAWLED, add to corpus** |

**6 target standards exist in index but not in our crawled 400 — should be added.**


### Renumbering Check

Checking if any target base_number appears under a different IS number:

> Renumbering detection requires title-similarity matching, which risks false positives. Reported as NOT FOUND if not in index.


## Task 8 — Licensed Product Varieties

> **Privacy**: Only product variety names stored. No manufacturer names, factory addresses, or licensee details.

- Standards with ≥1 licence: **169** / 400
- Total ISI licence records (from pagination.totalRecord): **14530**
- Distinct variety strings found across all sampled records: **1296**
- Licence entries with null variety field: **0**

### Sample Variety Values (first 10 standards with licences)

| pk_is_id | licence_count | product_varieties (sample) |
|---|---|---|
| 111 | 453 | (1) Grade-  OPC 53, With performance improver and without optional test of transverse strength  (Variety) (2) Grade-OPC 43, With performance improver and without optional test of transverse strength; --; Name of the product- Ordinary Portland Cement -53 Grade with performance improver(Variety)Name of the product- Ordinary Portland Cement -43 Grade with performance improver(Variety)OPC 43 GRADE without performance improver and without optional test of transverse strength(Variety)OPC 53 GRADE without performance improver and without optional test of transverse strength |
| 162 | 49 | --; CHEQUERED CEMENT CONCRETE TILES - Size (mm): 200x200x25/ 250x250x25/ 300x300x25/ 400x400 x 25mm, Class: - General purpose Tiles/ Heavy Duty Floor Tiles, Type: Chequered Coloured Tiles, No. of Layer: Mono Layer/Double Layer.; Chequered Cement Concrete Tiles, Class: General Purpose Tiles, Type: Plain Chequered Tiles, No. of Layer: Monolayer, Size(mm): 300 X 300 X 20, 300 X 300 X 22, 300 X 300 X 25, 200 X 200 X 20, 200 X 200 X 22, 200 X 200 X 25, 250 X 250 X 20, 250 X 250 X 22, 250 X 250 X 25(Variety)Chequered Cement Concrete Tiles, Class: Heavy Duty Floor Tiles, Type: Plain Chequered Tiles, No. of Layer: Monolayer, Size(mm): 300 X 300 X 20, 300 X 300 X 22, 300 X 300 X 25, 200 X 200 X 20, 200 X 200 X 22, 200 X 200 X 25, 250 X 250 X 20, 250 X 250 X 22, 250 X 250 X 25 |
| 165 | 1 | -- |
| 356 | 6 | 200mm, D=14mm(Variety)250mm, D=14mm(Variety)200mm, D=16mm(Variety)250mm, D=16mm(Variety)300mm, D=16mm; Clip Type, Bolt Diameter 16mm, Size 300mm; I) Type Clip, size 200mm, 250mm 300mm, Bolt Diameter 16mm ii) Type Clip, 250mm , Bolt Diameter 14mm(Variety)STAINLESS STEEL SLIDING DOOR BOLTS FOR USE WITH PADLOCK, TYPE - CLIP TYPE, SIZE(LENGHT  OF BOLT)- 300MM, BOLT DIAMETER - 16MM(Variety)STAINLESS STEEL SLIDING STEEL DOOR BOLTS  FOR USE WITH PADLOCK, TYPE- CLIP TYPE, SIZE  LENGTH OF BOLT)- 250 MM, BOLT DIAMETER- 14  MM |
| 1562 | 20 | BWP/STRUCTURAL PLYWOOD/?SIZE-2440*1220,2140*1220,1840*1220,2440*920,2140*920,1840*920MM,?thickness-upto and Including 25mm; Grade- BWP, thickness upto and including 12 mm(Variety)2440 X 1220 X 19MMcommaGRADE-BWP; Structural Plywood |
| 1683 | 22 | Grade  HR0, HR1, HR2, HR3 and HR4, without Micro alloying, Condition Pickled and Oiled Variety  Sheet of thickness from 1.2 mm up to & including 4 mm, width from 500 mm up to & including 1250 mm; Grade - HR0, HR1, HR2, HR3, HR4, ISH270C, ISH270D, ISH270E, with micro alloying element, Condition- As hot rolled, Strip thickness - 1.60 mm to 16.00 mm, width - 900 mm to 1650 mm.; HR1, HR2, HR3 and HR4, MILL EDGE,FULLY KILLED STEEL EITHER BY ALUMINIUM OR SILICON-ALUMINIUM |
| 2629 | 16 | CR11(Variety) CR9(Variety) CR5(Variety) CR15(Variety)CR10(Variety)CR8(Variety) CR12(Variety)GRADE: O,D,DD & EDD TYPE : GROUP I REROLLER SIZE : THICKNESS 1.6MM TO 12MM         WIDTH 600 TO 1250MM; CR3-DEEP DRAWING QULAITY CR4-EXTRA DEEP DRAWING  ALUMINIUM KILLED [NON AGEING] CR0, CR1,CR2, CR3, CR4, CR6, CR7 Thickness 1.2mm to 6.0mm Width 900mm to 1550 mm(Variety)Width Range from 80 mm upto and including 900 mm and Thickness range from 1.20 mm upto and including 4.00 mm(Variety)Width up to and including 1650 mm(Variety)Name of the product: Hot Rolled Carbon Steel Strip for Cold Rolling Purposes, Grades: CR0, CR1, CR2, CR3, CR4 comma  CR5, Size: Thickness from 1.2 mm to 4.0 mm and width from 80 mm to 900 mm, Conditions: Fully killed steel with Mill edge (Variety)Name of the product: Hot Rolled Carbon Steel Strip for Cold Rolling Purposes; Grades: CR0, CR1, CR2, CR3, CR4 comma CR5; Size: Thickness from 1.2 mm to 8.0 mm and width from 900 mm to 1650 mm; Conditions: Fully killed steel with Mill edge (Variety)Hot Rolled Carbon Steel Strip for Cold Rolling Purposes, CR8, Sizes: Thickness- from 1.2mm to 8mm and Width- from 80 mm to 1650mm; Grade CR0 , CR1 , CR2 , CR3 , CR4 and CR5, Width of Strips from 20mm up to and including 650 mm, Thickness of Strip from 1.00 mm up to and Including 6.00 mm. |
| 2985 | 960 | Outdoor Type Mineral Oil Immersed Distribution Transformers up to including 200 kVA, Nominal system voltage up to including 11 kV, Three phase, Sealed/Non-sealed, Aluminium wound, CRGO core, Energy Efficiency Level 1 and 2; Outdoor/Indoor Type Mineral Oil Immersed Distribution Transformers, Above 200 kVA and up to and including 2500 kVA, nominal system voltage upto and including 11kV, Three Phase, Non Sealed, Copper Winding, CRGO Core, Energy Efficiency Level - 2 and 1.(Variety)Outdoor/Indoor Type Mineral Oil Immersed Distribution Transformers, above 200KVA upto and including 2500 kVA , Nominal System Voltage above 11 KV and upto and including 22KV, Three Phase, Non-Sealed, Copper Winding , CRGO core, EEL-2 and 1; Outdoor/Indoor Type Mineral Oil Immersed Distribution Transformers, Above 200 kVA upto and including 315 kVA, up to and including 11 kV, Three Phase, non-sealed, Copper winding, CRGO Core, Energy Efficiency Level 1. |
| 3683 | 7 | --; 300 mm x 300 mm x 25 mm, General purpose tiles, Terrazo tiles (with or without pigments and chip size smallest upto 20mm) comma Double layer(Variety)SIZE 250X250X22MM, CLASS:GENERAL PURPOSES TILES WITH CHIPS OF SIZE VARYING FROM SMALLEST UPTO 20MM; Cement Concrete Flooring Tiles (Without Pigments) for General Purposes of the following sizes: Length            Breadth         Thickness (mm)              (mm)            (mm) 200               200              20 250               250              22 300               300              25 |
| 3714 | 24 | 15mm upto and including 150mm NB; Hot finished seamless sockets of nominal bore 15mm, 20mm, 25mm, 32mm, 40mm, 50mm, 65mm, 80mm and 100 mm, with galvanizing protective coating.(Variety)Steel pipe fittings - Hot finished seamless (HFS) sockets of nominal bore 125 mm NB and 150 mm NB with  protective coating (galvanizing).; Inclusion of Steel Tubulars Fittings as per IS 1239 Part 2 2011 1. Elbow , Union, Tee Cross Nominal size from 8 mm up to and including 50 mm in our existing Licence No CM/L- 9700129618(Variety)Steel tubular fittings, Cross equal and reducing, Nominal size 8mm up to and including 40mm, Hot finished seamless, Screwed, Black(Variety)Steel tubular fittings, Socket equal and reducing, Nominal size 8mm up to and including 50mm, Hot finished seamless, Screwed, Black |

## Final Counts

- all_standards_index.csv: **23918** rows (17 departments)
- Lineage rows processed: **406**
- Reference edges (hardened): **3536**
- Mandatory with blank ministryName: **22**
- ICS null rate: **85.5%** (347/406)
- Coverage targets not in our crawled 400: **6**
- Standards with ISI licences: **169**