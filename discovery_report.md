# BIS Standard Details API Discovery Report

## 1. Executive Summary

This report documents the network endpoints discovered for the Bureau of Indian Standards (BIS) Standard Details portal (`https://standards.bis.gov.in/website/standard-details?encryptedId=<token>`).

The web application is an Angular single-page application (SPA). The initial HTML is merely an empty shell. All domain data, standard metadata, cross-references, amendments, gazette notifications, laboratory accreditations, and certification licences are populated via background XHR/Fetch `POST` calls to the BIS backend review service at `https://standardsadmin.bis.gov.in/review-service/`.

Discovery was performed by intercepting network traffic using Playwright Chromium across two reference standards:
1. **`IS 15086 (Part 10):2026`** (`pk_is_id: 67227`) — Recent publication (August 2026), Voluntary Certification, dual-numbered IEC equivalent (`IEC 60099 (Part 10):2024`).
2. **`IS 694:2010`** (`pk_is_id: 13829`) — Mature standard (PVC cables), Mandatory certification, 4 amendments, 1,304 licences, 51 accredited test laboratories.

Raw requests and responses for all discovered endpoints have been saved to:
- `raw/discovery/IS 15086 (Part 10)_2026/*.json`
- `raw/discovery/IS 694_2010/*.json`

---

## 2. Authentication, Session & Token Analysis

### Is any login or cookie required?
**No.** All data endpoints are completely public and accessible without authentication or active session cookies.

### Are there expiring tokens?
**No.**
- While the request JSON bodies include fields like `"token": null`, `"refreshToken": null`, `"clientId": null`, `"clientSecret": null`, and `"sub": null`, these are default API boilerplate and can be passed as `null`.
- Requests require only the encrypted standard identifier (`encId` / `standardId`), which is already present as `standardId` in `standards_list.csv` (originating from the list API crawl) or in the query parameter `?encryptedId=...` of the detail URL.
- The standard token is a Laravel-style base64-encoded encrypted object (`{"iv":"...","value":"...","mac":"...","tag":""}`). These tokens are **persistent and static** for each standard; they do not expire per user session.

### Required HTTP Headers
All endpoints require the following headers:
```http
POST /review-service//<endpointName> HTTP/1.1
Host: standardsadmin.bis.gov.in
Content-Type: application/json
Accept: application/json, text/plain, */*
Origin: https://standards.bis.gov.in
Referer: https://standards.bis.gov.in/
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```
*(Requests missing `Origin` or `Referer` may return 403 Forbidden or empty responses).*

---

## 3. Discovered Endpoints Catalogue

### 3.1 `getWebsiteStandardDetails` (Primary Identity & Lifecycle)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getWebsiteStandardDetails`
- **UI Mapping**: Top header summary card, "Basic Details" tab, and "Classification Details" tab.
- **Request Payload**:
  ```json
  {
    "encId": "<encrypted_standard_id>",
    "fromPage": "guestUserPage",
    "token": null,
    "refreshToken": null,
    "clientId": null,
    "clientSecret": null,
    "sub": null
  }
  ```
  *(Note payload key: `encId`)*
- **Response Structure (`data`)**:
  - **Identity**: `pk_is_id` (int), `rowStandardId` (int), `standardNumber` (str), `standardName` (str), `shortTitle` (str)
  - **Equivalence**: `equivalentIs` (str, e.g. "IEC 60099 (Part 10):2024"), `identical_is` (str), `equivalenceTypeName` (str, e.g. "Identical under dual numbering", "Modified/Technically Equivalent"), `degreeOfEquivalenceId` (int)
  - **Classification**: `departmentName`, `deptAliasName` ("ETD"), `deptPreparedName` ("Electrotechnical Department(ETD)"), `departmentId`, `committeeName`, `committeePreparedName` (e.g. "ETD 09 - Power Cables"), `committeeId`, `icsCode` (e.g. "ICS 29.120.50; 29.240.10"), `typeOfStandardId` ("Product Specification", "Code of Practice"), `groupName`, `subGroupName`, `subSubGroupName`, `ministryName`
  - **Lifecycle**: `isStatus` (int, e.g. 2 = current), `publishedOn` (date), `reAffirmationYear` (date), `reviewOn` (date), `noOfRevision` (str/int), `noOfAmendment` (str/int), `withdrawStatus` (int), `withdrawOn`, `supersheed` (str), `superseded_byis`, `reviewList` (array of review stages)
  - **Certification**: `certificationName` ("Mandatory", "Voluntary")
  - **Documents**: `is_documents` (relative PDF path, e.g. `BisProd/.../694.pdf`), `is_hindi_document`

---

### 3.2 `getCrossRefDetails` (Normative & Referenced Standards)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getCrossRefDetails`
- **UI Mapping**: "Standards Referred" tab.
- **Request Payload**:
  ```json
  {
    "encId": "<encrypted_standard_id>",
    "fromPage": "guestUserPage",
    "token": null,
    "refreshToken": null,
    "clientId": null,
    "clientSecret": null,
    "sub": null
  }
  ```
  *(Note payload key: `encId`)*
- **Response Structure (`data.crossRefData`)**: Array of referenced standard objects:
  - `standardId` (int)
  - `standardNumber` (str, e.g. "IS 10418:2024", "IS 10810 (Part 1):1984")
  - `standardName` (str, title)
  - `standardEncId` (str, encrypted token to referenced standard)
  - `equivalent_is`, `identical_is`
  - `reviewOn`, `noOfReview`
  - `isType` (int, 1 = Indian Standard)
  - `typeLabel` ("Indian")
  - `data.totalRecord` (total count of referenced standards)

---

### 3.3 `getAmendmentDetails` (Amendments)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getAmendmentDetails`
- **UI Mapping**: "Amendment" tab.
- **Request Payload**:
  ```json
  {
    "standardId": "<encrypted_standard_id>",
    "token": null,
    "refreshToken": null,
    "clientId": null,
    "clientSecret": null,
    "sub": null
  }
  ```
  *(Note payload key: `standardId`)*
- **Response Structure**:
  - `totalAmendments` (int)
  - `data`: Array of amendment objects:
    - `standardId` (int, numeric row id)
    - `standardNumber` (str)
    - `noOfAmendment` (int, amendment sequence number)
    - `amendmentYear` (str, e.g. "2012", "2020")
    - `amendmentLabel` (str, e.g. "First Amendment", "Fourth Amendment")
    - `is_documents` (str, relative PDF path to amendment document)

---

### 3.4 `getGazettedetails` (Official Gazette Notifications)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getGazettedetails`
- **UI Mapping**: "Gazette Document" tab.
- **Request Payload**:
  ```json
  {
    "standardId": "<encrypted_standard_id>",
    "fromPage": "guestUserPage",
    "token": null,
    "refreshToken": null,
    "clientId": null,
    "clientSecret": null,
    "sub": null
  }
  ```
  *(Note: also accepts nested `{"standardId": {"standardId": "<encrypted_standard_id>"}}`)*
- **Response Structure (`data`)**: Array of gazette records:
  - `IS_NO` (int, pk_is_id)
  - `So_No` (str, Statutory Order number, e.g. "2072 (E)", "PUB/3/4/2019-20 ")
  - `Amd_No` (int, associated amendment number if applicable)
  - `standardNumber` (str, e.g. " Amendment 3 to IS 694:2010")
  - `migratedFiles` (str, relative PDF path to gazette notification)
  - `pki_id` (int)

---

### 3.5 `getStandardLicenseDetails` (Certification Licences / Manufacturers)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getStandardLicenseDetails`
- **UI Mapping**: "Licence" tab.
- **Request Payload**:
  ```json
  {
    "standardId": "<encrypted_standard_id>",
    "status": "Operative",
    "page": 1,
    "limit": 10,
    "searchText": "",
    "token": null,
    "refreshToken": null,
    "clientId": null,
    "clientSecret": null,
    "sub": null
  }
  ```
- **Response Structure**:
  - `pagination.totalRecord` (total operative licence count, e.g. 1,304 for IS 694)
  - `data`: Array of licence records:
    - `licenseNo` (str, e.g. "7200193911")
    - `firmName` (str, manufacturer name)
    - `firmAddress`, `district`, `state`
    - `validityDate` (date)
    - `status` ("Operative")
    - `variety` (detailed product grade/variety description covered by licence)
    - `brandName`, `scale` ("Small", "Medium", "Large")
    - `region`, `branchOffice`
    - `licenseGrantDate`

---

### 3.6 `getStandardCRSDetails` (Compulsory Registration Scheme)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getStandardCRSDetails`
- **UI Mapping**: CRS Certification section.
- **Request Payload**: Same format as `getStandardLicenseDetails` (`standardId`, `status: "Operative"`, `page`, `limit`).
- **Response Structure**:
  - `pagination.totalRecord`
  - `data`: Array of CRS registrations (relevant for electronics/IT standards under CRS order).

---

### 3.7 `getStandardMCSDetails` (Management Systems Certification Scheme)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getStandardMCSDetails`
- **UI Mapping**: Management Systems certification section.
- **Request Payload**: `{"standardId": "<encrypted_standard_id>", "page": 1, "limit": 10, "searchText": ""}`
- **Response Structure**:
  - `pagination.totalRecord`
  - `data`: Array of MCS records.

---

### 3.8 `getStandardLaboratoryDetails` (Testing Laboratories)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getStandardLaboratoryDetails`
- **UI Mapping**: "Laboratory" tab.
- **Request Payload**: `{"standardId": "<encrypted_standard_id>", "page": 1, "limit": 10, "searchText": ""}`
- **Response Structure**:
  - `pagination.totalRecord` (e.g. 51 accredited labs for IS 694)
  - `data`: Array of laboratory records:
    - `labName`, `oslCode`, `labType` ("osl" / BIS lab)
    - `contactPerson`, `contactNumber`, `labEmail`
    - `labAddress`, `labCity`, `labDistrict`, `labState`, `labZipcode`
    - `latitude`, `longitude`, `state` ("Recognized")

---

### 3.9 `getProductManualDetails` (Product Manual & SIT Documents)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getProductManualDetails`
- **UI Mapping**: "Product Manual & SIT" tab.
- **Request Payload**: `{"standardId": "<encrypted_standard_id>", ...}`
- **Response Structure (`data.product_manuals_details`)**:
  - `is_number` (str)
  - `file_path` (relative PDF path to Product Manual, e.g. `BisProd/.../product_manual_...pdf`)
  - `file_name` (str)
  - `total_count` (int)

---

### 3.10 `getCorrigendumDetails` (Corrigenda)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getCorrigendumDetails`
- **UI Mapping**: "Corrigendum" tab.
- **Request Payload**: `{"standardId": "<encrypted_standard_id>", ...}`
- **Response Structure**: Corrigenda array and `total_count`.

---

### 3.11 `getSummaryDetails` (Standard Summary PDF Document)
- **URL**: `POST https://standardsadmin.bis.gov.in/review-service//getSummaryDetails`
- **UI Mapping**: "Summary" tab.
- **Request Payload**: `{"standardId": "<encrypted_standard_id>", ...}`
- **Response Structure (`data`)**:
  - `pk_is_id` (str)
  - `file_path` (relative PDF path to Summary document)
  - `file_name` (str)

---

### 3.12 Other Discovered Endpoints (Ignored for Pilot Data Extraction)
1. **`getStandardsWithDeptAndCommittee`** (`proposal-service`): Returns redundant department and committee encrypted keys. All relevant committee names and IDs are already present in `getWebsiteStandardDetails`.
2. **`getStandardFormatDocumentDetails`**: Empty for standards (`total_count: 0`).
3. **`viewAll`** (`standardsmodule.bis.gov.in/cms-service/api/...`): Site CMS footer addresses and top-level navigation menu. Contains no standard metadata.
4. **`logUniqueVisitor`** (`auth//logUniqueVisitor`): Client-side analytics/hit counter. **Must never be called** per project instructions.

---

## 4. Key Payload Parameter Conventions

| Endpoint | Standard Identifier Key | Value Type | Additional Parameters |
|---|---|---|---|
| `getWebsiteStandardDetails` | `encId` | Encrypted token string | `fromPage: "guestUserPage"` |
| `getCrossRefDetails` | `encId` | Encrypted token string | `fromPage: "guestUserPage"` |
| `getAmendmentDetails` | `standardId` | Encrypted token string | none |
| `getGazettedetails` | `standardId` | Encrypted token string | `fromPage: "guestUserPage"` |
| `getStandardLicenseDetails` | `standardId` | Encrypted token string | `status: "Operative", page: 1, limit: 1` |
| `getStandardCRSDetails` | `standardId` | Encrypted token string | `status: "Operative", page: 1, limit: 1` |
| `getStandardMCSDetails` | `standardId` | Encrypted token string | `page: 1, limit: 1` |
| `getStandardLaboratoryDetails` | `standardId` | Encrypted token string | `page: 1, limit: 1` |
| `getProductManualDetails` | `standardId` | Encrypted token string | none |
| `getCorrigendumDetails` | `standardId` | Encrypted token string | none |
| `getSummaryDetails` | `standardId` | Encrypted token string | none |

*Crucial observation*: Even when the key is named `standardId` (as opposed to `encId`), the value is **always the encrypted token string** (the same token from `standards_list.csv["standardId"]`), never the numeric `pk_is_id` or `projectId`.

---

## 5. Verification of Plain HTTP Invocation

All core endpoints were directly tested using Python's `requests` library without a browser:
- `getWebsiteStandardDetails` -> **HTTP 200 SUCCESS**
- `getCrossRefDetails` -> **HTTP 200 SUCCESS**
- `getAmendmentDetails` -> **HTTP 200 SUCCESS**
- `getGazettedetails` -> **HTTP 200 SUCCESS**
- `getStandardLicenseDetails` -> **HTTP 200 SUCCESS**
- `getProductManualDetails` -> **HTTP 200 SUCCESS**

This confirms that:
1. No browser session or cookie handshake is needed.
2. The HTTP client (`bis_detail.py`) can be built purely with `requests`.
3. Calls execute within 200–500ms per endpoint, easily complying with polite throttling (1 req/sec).
