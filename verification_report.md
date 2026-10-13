# Verification and Research Report: BIS Standards Detail Pilot

## 1. Overview
This report provides full field-by-field verification of the parsed pilot dataset (`pilot_standards.json`) against the live Bureau of Indian Standards (BIS) portal (`https://standards.bis.gov.in/website/standard-details`), followed by data-backed answers to the key architecture and domain questions.

All 10 pilot standards were fetched using the plain HTTP client (`bis_detail.py`) into `raw/detail/<pk_is_id>/`, parsed into `pilot_standards.json`, and independently verified against the rendered browser DOM using Playwright Chromium (`verify_browser.py`).

---

## 2. Side-by-Side Field Verification Table

| Standard | Field | API Extracted Value | Live Website (DOM) Value | Match? |
|---|---|---|---|:---:|
| **IS 15086 (Part 10):2026** | Standard Number | `IS 15086 (Part 10):2026` | `IS 15086 (Part 10):2026` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 30 - Surge Arresters` | `ETD 30 - Surge Arresters` | **YES** |
| | Equivalent Standard | `IEC 60099 (Part 10):2024` | `IEC 60099 (Part 10):2024` | **YES** |
| | Certification Type | `Voluntary` | Badge: `Voluntary Certification` | **YES** |
| **IS 694:2010** | Standard Number | `IS 694:2010` | `IS 694:2010` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 09 - Power Cables` | `ETD 09 - Power Cables` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `Mandatory` | Badge / Text: `Mandatory` | **YES** |
| **IS 8130:2013** | Standard Number | `IS 8130:2013` | `IS 8130:2013` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 09 - Power Cables` | `ETD 09 - Power Cables` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `null` (General Standard) | None displayed | **YES** |
| **IS 1554 (Part 1):1988** | Standard Number | `IS 1554 (Part 1):1988` | `IS 1554 (Part 1):1988` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 09 - Power Cables` | `ETD 09 - Power Cables` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `Mandatory` | Badge / Text: `Mandatory` | **YES** |
| **IS 4289 (Part 1):2026** | Standard Number | `IS 4289 (Part 1):2026` | `IS 4289 (Part 1):2026` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 44 - Electric Welding Equipment` | `ETD 44 - Electric Welding Equipment` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `null` | None displayed | **YES** |
| **IS 8783 (Part 4/Sec 1):2026** | Standard Number | `IS 8783 (Part 4/Sec 1):2026` | `IS 8783 (Part 4/Sec 1):2026` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 33 - Winding Wires` | `ETD 33 - Winding Wires` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `null` | None displayed | **YES** |
| **IS 10810 (Part 60):1988** | Standard Number | `IS 10810 (Part 60):1988` | `IS 10810 (Part 60):1988` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 09 - Power Cables` | `ETD 09 - Power Cables` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `null` (Test method) | None displayed | **YES** |
| **IS/IEC 60136:2024** | Standard Number | `IS/IEC 60136:2024` | `IS/IEC 60136:2024` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 15 - Rotating Machinery` | `ETD 15 - Rotating Machinery` | **YES** |
| | Equivalent Standard | `IEC 60136:1986` | `IEC 60136:1986` | **YES** |
| | Certification Type | `null` | None displayed | **YES** |
| **IS 2026 (Part 1):2011** | Standard Number | `IS 2026 (Part 1):2011` | `IS 2026 (Part 1):2011` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 16 - Transformers` | `ETD 16 - Transformers` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `null` | None displayed | **YES** |
| **IS 1293:2019** | Standard Number | `IS 1293:2019` | `IS 1293:2019` | **YES** |
| | Department | `Electrotechnical Department(ETD)` | `Electrotechnical Department(ETD)` | **YES** |
| | Technical Committee | `ETD 14 - Electrical Wiring Accessories` | `ETD 14 - Electrical Wiring Accessories` | **YES** |
| | Equivalent Standard | `null` | None displayed | **YES** |
| | Certification Type | `Mandatory` | Badge / Text: `Mandatory` | **YES** |

*Verification Result*: **100% match (50/50 checks confirmed across browser DOM and API JSON).**

---

## 3. Detailed Answers to Specific Research Questions

### a) What does "Superseding IS" mean?
> **Does it point to the standard THIS one replaces, or the newer one replacing it?**

**Evidence from the data:**
In the BIS database schema, there are two distinct fields:
1. `supersheed` (in `getWebsiteStandardDetails`):
   - Example from live standard **`IS 302 (Part 2/Sec 26):2026`** (`isStatus: 2`, Current):
     ```json
     "supersheed": "IS 302 (Part 2/Sec 26):2014"
     ```
   - Here, `IS 302 (Part 2/Sec 26):2026` is the **active, newest standard**. Its `supersheed` field contains the **older, previous 2014 edition that this standard replaces**.
2. `superseded_byis` (in `getWebsiteStandardDetails`):
   - Example from standard **`IS 17017 (Part 23):2021`** (`isStatus: 5`):
     ```json
     "superseded_byis": "IS17017(Part23):2026"
     ```
   - Here, the old 2021 standard points to the **newer 2026 edition replacing it**.

**Conclusion:** 
- In the UI and API, **"Superseding IS" (`supersheed`) points to the PREVIOUS/OLDER standard that THIS standard replaces**. 
- Conversely, **`superseded_byis` points to the NEWER standard that replaced THIS one**.

---

### b) How do we decide "current vs superseded vs withdrawn"?
> **Which field(s) determine it?**

Across the 1,946 ETD standards list, `isStatus` has the following distribution:
- `isStatus == 1`: 1,148 records (Draft / Preliminary formulation / New publication awaiting gazette sync)
- `isStatus == 2`: 653 records (**Current / In-force**)
- `isStatus == 4`: 83 records (**Superseded**)
- `isStatus == 5`: 38 records (**Withdrawn**)
- `isStatus == 3`: 24 records (**Under Review / Reaffirmation**)

**Decision Rule Algorithm:**
```python
def determine_standard_status(data):
    if data.get("withdrawStatus") == 1 or data.get("isStatus") == 5:
        return "Withdrawn"
    elif data.get("superseded_byis") or data.get("isStatus") == 4:
        return "Superseded"
    elif data.get("isStatus") == 2:
        return "Current"
    elif data.get("isStatus") == 3:
        return "Under Review"
    elif data.get("isStatus") == 1:
        return "Current / New Publication" # (or Draft/Formulation depending on publishedOn)
    return "Unknown"
```

---

### c) What are ALL possible values of certification type across the pilot, and where do CRS/MCS/licence fit?
- **Observed values of `certificationName`**:
  1. `"Mandatory"`: Mandated under a statutory Quality Control Order (QCO) issued by DPIIT, Ministry of Power, etc. (e.g. `IS 694:2010`, `IS 1554 (Part 1):1988`, `IS 1293:2019`).
  2. `"Voluntary"`: Manufacturer certification is voluntary (e.g. `IS 15086 (Part 10):2026`, `IS 398 (Part 1):1996`, `IS 13779:2020`).
  3. `""` / `null`: Test methods, general guides, definitions, or dual-number standards with no product certification scheme assigned (e.g. `IS 10810`, `IS 8130`, `IS/IEC 60136`).

- **Where CRS, MCS, and Licence fit:**
  - **Licence (`getStandardLicenseDetails`)**: Represents the **ISI Mark Product Certification Scheme (Scheme-I)**. Holds manufacturers, factory addresses, varieties, and operative status. `IS 694:2010` has 1,304 licences; `IS 1293:2019` has 585 licences; `IS 1554 (Part 1):1988` has 331 licences.
  - **CRS (`getStandardCRSDetails`)**: Represents the **Compulsory Registration Scheme (Scheme-II)**, primarily for IT, electronics, and solar inverters under MeitY/MNRE mandates.
  - **MCS (`getStandardMCSDetails`)**: Represents **Management Systems Certification (Scheme-IV)** (audits for ISO 9001/14001, etc.).

---

### d) Are referenced standards given as parseable numbers + years? Do they include relationship type?
- **Parseable format**: **Yes.**
  - `getCrossRefDetails` provides `data.crossRefData`, containing clean `standardNumber` strings like `"IS 10418:2024"` and `"IS 10810 (Part 1):1984"`.
  - The standard number, part, and publication year are trivially extractable via regex (`:(\d{4})$`).
- **Relationship Type**: **No.**
  - The API returns a flat list of referenced standards without semantic relationship flags (e.g. it does not state whether a reference is *normative*, *informative*, or a *test-method* citation).
  - Relationship type must be inferred from the referenced standard's title or `typeOfStandardId`.

---

### e) Does any endpoint return scope text or abstract?
- **No.**
- None of the 11 discovered JSON endpoints return the full scope or abstract.
- Metadata is limited to:
  - Title (`standardName`)
  - Subgroup / Sector hierarchy
  - Licence product varieties and grades
- Full scope text is embedded exclusively inside the copyrighted standard PDFs (`is_documents`), which are intentionally not downloaded per project rules.

---

### f) Is the committee available in the detail response? Is there an ICS code?
- **Technical Committee: Yes.**
  - `committeePreparedName`: e.g. `"ETD 09 - Power Cables"`, `"ETD 30 - Surge Arresters"`
  - `committeeName`: e.g. `"Power Cables"`
  - `committeeId`: e.g. `243`
- **ICS Code: Yes.**
  - Returned in `getWebsiteStandardDetails` as `icsCode` (e.g. `"ICS 29.120.50; 29.240.10"` for `IS 15086 (Part 10):2026`).
  - *(Note: older legacy standards may have `icsCode: null` if not yet classified under the International Classification for Standards).*

---

### g) Do any endpoints require cookies/tokens that expire, or are they stateless?
- **Completely stateless.**
- Zero cookies, zero browser sessions, and zero expiring tokens.
- All requests use the static encrypted token (`standardId`) directly from `standards_list.csv`, which remains valid across repeated plain HTTP calls.

---

### h) Timing Breakdown and Crawl Estimation for 1,946 Standards
- **Single standard timing**:
  - 11 endpoints * (1.0 sec polite sleep + ~0.25 sec wire latency) ≈ **13.75 seconds per standard**.
- **Full crawl estimate (1,946 ETD standards)**:
  $$\text{Total Requests} = 1,946 \times 11 = 21,406 \text{ requests}$$
  $$\text{Total Crawl Time} \approx 21,406 \times 1.25\text{ seconds} \approx 26,757\text{ seconds} \approx \mathbf{7.4\text{ hours}} \ (\approx 445\text{ minutes})$$
- Because `bis_detail.py` is fully resumable, the crawl can be safely run in batches or interrupted and resumed at any time without data loss.
