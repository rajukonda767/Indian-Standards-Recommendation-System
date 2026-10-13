// ---------------------------------------------------------------------------
// mockData.ts — Plausible BIS standards mock entries
// MOCK PLACEHOLDER DATA — not authoritative. Phase 2 replaces with /api calls.
// ---------------------------------------------------------------------------

export interface StandardRecord {
  isNumber: string
  year: number
  title: string
  status: 'Active' | 'Reaffirmed' | 'Withdrawn'
  scope: string
  sector: string
  icsCode: string
  supersedes: string | null
  supersededBy: string | null
  certifications: string[]
  dept: string
}

// ── Allied Standards (6 BIS-compliant sub-categories) ─────────────────────
export interface AlliedEntry {
  isNumber: string
  year: number
  title: string
  status: 'Active' | 'Reaffirmed' | 'Withdrawn'
}

export interface AlliedGraph {
  normative: AlliedEntry[]       // Normative References
  testMethods: AlliedEntry[]     // Test Methods
  terminology: AlliedEntry[]     // Terminology & Vocabulary
  safety: AlliedEntry[]          // Safety Standards
  installation: AlliedEntry[]    // Installation Standards
  relatedProducts: AlliedEntry[] // Related Product Standards
}

// ── Primary / Certification results ──────────────────────────────────────
export interface PrimaryResult {
  isNumber: string
  year: number
  status: 'Active' | 'Reaffirmed' | 'Withdrawn'
  title: string
  why: string
  confidence: number   // 0–100
  certifications: string[]
}

export interface CertResult {
  title: string
  body: string
  why: string
}

export interface RecommendResponse {
  primary: PrimaryResult[]
  allied: AlliedGraph
  certifications: CertResult[]
}

/** Legacy flat type — still used by ResultCard for primary tab */
export interface RecommendationResult {
  isNumber: string
  year: number
  status: 'Active' | 'Reaffirmed' | 'Withdrawn'
  title: string
  why: string
  confidence: number
  category: 'primary' | 'aligned' | 'certification'
  certifications: string[]
}

export interface AuditDiffRow {
  item: string
  citedStandard: string | null
  status: 'Compliant' | 'Outdated' | 'Missing' | 'Contradiction'
  action: string
}

export interface AuditResult {
  coverage: number
  currency: number
  certification: number
  diffRows: AuditDiffRow[]
}

// ── Mock Standards List ───────────────────────────────────────────────────
export const MOCK_STANDARDS: StandardRecord[] = [
  {
    isNumber: 'IS 694', year: 2010, title: 'PVC Insulated Cables for Working Voltages up to and including 1100V',
    status: 'Active', scope: 'Covers PVC insulated, unsheathed and sheathed cables with rigid and flexible conductors.',
    sector: 'Electrotechnical', icsCode: '29.060.20', supersedes: 'IS 694:1990', supersededBy: null,
    certifications: ['ISI Mark (Mandatory)', 'QCO — DPIIT'], dept: 'ETD',
  },
  {
    isNumber: 'IS 269', year: 2015, title: 'Ordinary Portland Cement — Specification',
    status: 'Active', scope: 'Specifies requirements for ordinary portland cement for general construction use.',
    sector: 'Civil Engineering', icsCode: '91.100.10', supersedes: 'IS 269:1989', supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'CED',
  },
  {
    isNumber: 'IS 1786', year: 2008, title: 'High Strength Deformed Steel Bars and Wires for Concrete Reinforcement',
    status: 'Reaffirmed', scope: 'Covers Fe 415, Fe 500, Fe 500D, Fe 550 grades of TMT bars for RCC construction.',
    sector: 'Metallurgical Engineering', icsCode: '77.140.15', supersedes: 'IS 1786:1985', supersededBy: null,
    certifications: ['ISI Mark (Mandatory)', 'QCO — Ministry of Steel'], dept: 'MTD',
  },
  {
    isNumber: 'IS 7098', year: 2011, title: 'Crosslinked Polyethylene (XLPE) Insulated Thermoplastic Sheathed Cables',
    status: 'Active', scope: 'Specifies XLPE insulated cables rated for working voltages up to and including 1100V.',
    sector: 'Electrotechnical', icsCode: '29.060.20', supersedes: null, supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'ETD',
  },
  {
    isNumber: 'IS 1489', year: 2015, title: 'Portland Pozzolana Cement — Specification (Fly Ash Based)',
    status: 'Active', scope: 'Covers fly-ash-based portland pozzolana cement for general construction.',
    sector: 'Civil Engineering', icsCode: '91.100.10', supersedes: 'IS 1489:1991', supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'CED',
  },
  {
    isNumber: 'IS 10810', year: 2019, title: 'Methods of Test for Cables — Part 1 to 67',
    status: 'Active', scope: 'Mandatory laboratory test methods for electrical cables.',
    sector: 'Electrotechnical', icsCode: '29.060.20', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 8130', year: 1984, title: 'Conductors for Insulated Electric Cables and Flexible Cords',
    status: 'Reaffirmed', scope: 'Specifies copper and aluminium conductors used in cable manufacture.',
    sector: 'Electrotechnical', icsCode: '29.060.10', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 4905', year: 1968, title: 'Methods for Random Sampling and Randomisation',
    status: 'Reaffirmed', scope: 'Defines statistical sampling procedures and lot acceptance criteria.',
    sector: 'Management & Quality', icsCode: '03.120.30', supersedes: null, supersededBy: null,
    certifications: [], dept: 'MSD',
  },
  {
    isNumber: 'IS 456', year: 2000, title: 'Plain and Reinforced Concrete — Code of Practice',
    status: 'Reaffirmed', scope: 'General structural design code for concrete structures.',
    sector: 'Civil Engineering', icsCode: '91.080.40', supersedes: 'IS 456:1978', supersededBy: null,
    certifications: [], dept: 'CED',
  },
  {
    isNumber: 'IS 2062', year: 2011, title: 'Hot Rolled Medium and High Tensile Structural Steel',
    status: 'Active', scope: 'Specifies structural steel sections (angles, channels, beams, plates).',
    sector: 'Metallurgical Engineering', icsCode: '77.140.70', supersedes: 'IS 2062:2006', supersededBy: null,
    certifications: ['ISI Mark (Mandatory)', 'QCO — Ministry of Steel'], dept: 'MTD',
  },
  {
    isNumber: 'IS 383', year: 2016, title: 'Coarse and Fine Aggregate for Concrete — Specification',
    status: 'Active', scope: 'Specifies natural, crushed, and recycled aggregate for concrete.',
    sector: 'Civil Engineering', icsCode: '91.100.15', supersedes: 'IS 383:1970', supersededBy: null,
    certifications: [], dept: 'CED',
  },
  {
    isNumber: 'IS 3043', year: 1987, title: 'Code of Practice for Earthing',
    status: 'Reaffirmed', scope: 'Covers design, installation and testing of earth electrodes.',
    sector: 'Electrotechnical', icsCode: '29.020', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 1367', year: 2002, title: 'Technical Supply Conditions for Threaded Steel Fasteners',
    status: 'Reaffirmed', scope: 'Specifies fastener material grades and mechanical properties.',
    sector: 'Mechanical Engineering', icsCode: '21.060.10', supersedes: null, supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'MED',
  },
  {
    isNumber: 'IS 1554', year: 1988, title: 'PVC Insulated (Heavy Duty) Electric Cables — Part 1 (up to 1100 V)',
    status: 'Reaffirmed', scope: 'Heavy-duty PVC insulated armoured cables for industrial power distribution.',
    sector: 'Electrotechnical', icsCode: '29.060.20', supersedes: null, supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'ETD',
  },
  {
    isNumber: 'IS 9537', year: 1983, title: 'Conduits for Electrical Installations',
    status: 'Reaffirmed', scope: 'Covers rigid and flexible conduits for routing electrical wiring.',
    sector: 'Electrotechnical', icsCode: '29.120.10', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 13947', year: 1993, title: 'Low-Voltage Switchgear and Controlgear',
    status: 'Reaffirmed', scope: 'Specifies MCBs, fuses, contactors, and LV panels up to 1000V AC.',
    sector: 'Electrotechnical', icsCode: '29.130.20', supersedes: null, supersededBy: null,
    certifications: ['ISI Mark (Mandatory)'], dept: 'ETD',
  },
  {
    isNumber: 'IS 1646', year: 1982, title: 'Code of Practice for Fire Safety of Buildings — Electrical Installations',
    status: 'Reaffirmed', scope: 'Fire safety requirements for electrical installations in buildings.',
    sector: 'Electrotechnical', icsCode: '13.220.01', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 3961', year: 1967, title: 'Recommended Current Ratings for Cables',
    status: 'Reaffirmed', scope: 'Current-carrying capacity tables for PVC and XLPE insulated cables.',
    sector: 'Electrotechnical', icsCode: '29.060.20', supersedes: null, supersededBy: null,
    certifications: [], dept: 'ETD',
  },
  {
    isNumber: 'IS 432', year: 1982, title: 'Mild Steel Bars for Concrete Reinforcement',
    status: 'Withdrawn', scope: 'Plain round bars (Fe 250) — superseded by IS 1786.',
    sector: 'Metallurgical Engineering', icsCode: '77.140.15', supersedes: null, supersededBy: 'IS 1786:2008',
    certifications: [], dept: 'MTD',
  },
  {
    isNumber: 'IS 3025', year: 1987, title: 'Methods of Sampling and Test for Water Used in Industry',
    status: 'Reaffirmed', scope: 'Water quality testing methods for industrial use.',
    sector: 'Civil Engineering', icsCode: '13.060.01', supersedes: null, supersededBy: null,
    certifications: [], dept: 'CED',
  },
]

// ── Allied Graph by query domain ──────────────────────────────────────────
const CABLE_ALLIED: AlliedGraph = {
  normative: [
    { isNumber: 'IS 8130', year: 1984, title: 'Conductors for Insulated Electric Cables and Flexible Cords', status: 'Reaffirmed' },
    { isNumber: 'IS 5831', year: 1984, title: 'PVC Insulation and Sheath of Electric Cables', status: 'Reaffirmed' },
  ],
  testMethods: [
    { isNumber: 'IS 10810', year: 2019, title: 'Methods of Test for Cables — Part 1 to 67 (Tensile, Elongation, Flammability)', status: 'Active' },
    { isNumber: 'IS 4905', year: 1968, title: 'Methods for Random Sampling and Randomisation (Lot Acceptance)', status: 'Reaffirmed' },
  ],
  terminology: [],
  safety: [
    { isNumber: 'IS 1646', year: 1982, title: 'Code of Practice for Fire Safety — Electrical Installations in Buildings', status: 'Reaffirmed' },
    { isNumber: 'IS 3043', year: 1987, title: 'Code of Practice for Earthing', status: 'Reaffirmed' },
  ],
  installation: [
    { isNumber: 'IS 9537', year: 1983, title: 'Conduits for Electrical Installations — Rigid and Flexible', status: 'Reaffirmed' },
    { isNumber: 'IS 3961', year: 1967, title: 'Recommended Current Ratings for Cables', status: 'Reaffirmed' },
  ],
  relatedProducts: [
    { isNumber: 'IS 1554', year: 1988, title: 'PVC Insulated Heavy Duty Cables — Part 1 (up to 1100 V)', status: 'Reaffirmed' },
    { isNumber: 'IS 7098', year: 2011, title: 'XLPE Insulated Thermoplastic Sheathed Cables for Voltages up to 1100V', status: 'Active' },
    { isNumber: 'IS 13947', year: 1993, title: 'Low-Voltage Switchgear and Controlgear (MCBs, Contactors)', status: 'Reaffirmed' },
  ],
}

const CEMENT_ALLIED: AlliedGraph = {
  normative: [
    { isNumber: 'IS 650', year: 1991, title: 'Specification for Standard Sand for Testing of Cement', status: 'Reaffirmed' },
  ],
  testMethods: [
    { isNumber: 'IS 4031', year: 1988, title: 'Methods of Physical Tests for Hydraulic Cement', status: 'Reaffirmed' },
    { isNumber: 'IS 4905', year: 1968, title: 'Methods for Random Sampling and Randomisation', status: 'Reaffirmed' },
  ],
  terminology: [
    { isNumber: 'IS 4845', year: 1968, title: 'Definitions and Terminology Relating to Hydraulic Cement', status: 'Reaffirmed' },
  ],
  safety: [],
  installation: [
    { isNumber: 'IS 456', year: 2000, title: 'Plain and Reinforced Concrete — Code of Practice', status: 'Reaffirmed' },
  ],
  relatedProducts: [
    { isNumber: 'IS 1489', year: 2015, title: 'Portland Pozzolana Cement — Specification (Fly Ash Based)', status: 'Active' },
    { isNumber: 'IS 383', year: 2016, title: 'Coarse and Fine Aggregate for Concrete — Specification', status: 'Active' },
  ],
}

const STEEL_ALLIED: AlliedGraph = {
  normative: [
    { isNumber: 'IS 2062', year: 2011, title: 'Hot Rolled Medium and High Tensile Structural Steel', status: 'Active' },
  ],
  testMethods: [
    { isNumber: 'IS 1608', year: 2005, title: 'Mechanical Testing of Metals — Tensile Testing', status: 'Reaffirmed' },
    { isNumber: 'IS 1599', year: 1985, title: 'Method for Bend Test (Steel)', status: 'Reaffirmed' },
  ],
  terminology: [],
  safety: [],
  installation: [
    { isNumber: 'IS 456', year: 2000, title: 'Plain and Reinforced Concrete — Code of Practice', status: 'Reaffirmed' },
  ],
  relatedProducts: [
    { isNumber: 'IS 432', year: 1982, title: 'Mild Steel Bars for Concrete Reinforcement (Withdrawn)', status: 'Withdrawn' },
    { isNumber: 'IS 1367', year: 2002, title: 'Technical Supply Conditions for Threaded Steel Fasteners', status: 'Reaffirmed' },
  ],
}

const GENERIC_ALLIED: AlliedGraph = {
  normative: [], testMethods: [], terminology: [], safety: [], installation: [], relatedProducts: [],
}

// ── Mock Recommendation Response ──────────────────────────────────────────
export function getMockRecommendResponse(query: string): RecommendResponse {
  const q = query.toLowerCase()

  if (q.includes('cable') || q.includes('wire') || q.includes('pvc') || q.includes('तार') || q.includes('కేబుల్')) {
    return {
      primary: [
        { isNumber: 'IS 694', year: 2010, status: 'Active', title: 'PVC Insulated Cables for Working Voltages up to and including 1100V', why: 'Direct match — covers PVC insulated copper/aluminium conductors for low-voltage building and industrial wiring with mandatory ISI Mark under DPIIT QCO.', confidence: 94, certifications: ['ISI Mark (Mandatory)', 'QCO — DPIIT'] },
        { isNumber: 'IS 1554', year: 1988, status: 'Reaffirmed', title: 'PVC Insulated Heavy Duty Electric Cables (up to 1100V)', why: 'Alternative candidate for armoured industrial power cable applications where IS 694 flexible wiring is insufficient.', confidence: 71, certifications: ['ISI Mark (Mandatory)'] },
        { isNumber: 'IS 7098', year: 2011, status: 'Active', title: 'XLPE Insulated Thermoplastic Sheathed Cables (up to 1100V)', why: 'Higher-grade XLPE alternative to PVC — preferred for outdoor, underground, or high-temperature environments.', confidence: 68, certifications: ['ISI Mark (Mandatory)'] },
      ],
      allied: CABLE_ALLIED,
      certifications: [
        { title: 'ISI Mark Certification — Scheme I', body: 'Bureau of Indian Standards', why: 'IS 694 cables must carry ISI Mark under mandatory DPIIT QCO. Licenced manufacturers list available at BIS portal.' },
        { title: 'QCO Compliance — Electrical Cables', body: 'DPIIT / Ministry of Commerce', why: 'Quality Control Order mandates IS 694 compliance for import and domestic sale of PVC insulated cables.' },
      ],
    }
  }

  if (q.includes('cement') || q.includes('opc') || q.includes('सीमेंट') || q.includes('సిమెంట్')) {
    return {
      primary: [
        { isNumber: 'IS 269', year: 2015, status: 'Active', title: 'Ordinary Portland Cement — Specification', why: 'Direct match — IS 269:2015 covers 33/43/53 grade OPC for general construction use with mandatory ISI Mark.', confidence: 97, certifications: ['ISI Mark (Mandatory)'] },
        { isNumber: 'IS 1489', year: 2015, status: 'Active', title: 'Portland Pozzolana Cement (Fly Ash Based)', why: 'Commonly substituted for OPC in mass concrete; fly ash reduces heat of hydration and improves durability.', confidence: 74, certifications: ['ISI Mark (Mandatory)'] },
      ],
      allied: CEMENT_ALLIED,
      certifications: [
        { title: 'ISI Mark Certification — Scheme I', body: 'Bureau of Indian Standards', why: 'Cement must carry ISI Mark under mandatory QCO. All 33/43/53 grade OPC bags must be ISI marked.' },
      ],
    }
  }

  if (q.includes('steel') || q.includes('rebar') || q.includes('tmt') || q.includes('fe 500') || q.includes('इस्पात') || q.includes('స్టీల్')) {
    return {
      primary: [
        { isNumber: 'IS 1786', year: 2008, status: 'Reaffirmed', title: 'High Strength Deformed Steel Bars and Wires for Concrete Reinforcement', why: 'Direct match — covers Fe 415D, Fe 500D, Fe 550D TMT bars for RCC construction with mandatory ISI Mark under Ministry of Steel QCO.', confidence: 96, certifications: ['ISI Mark (Mandatory)', 'QCO — Ministry of Steel'] },
        { isNumber: 'IS 2062', year: 2011, status: 'Active', title: 'Hot Rolled Medium and High Tensile Structural Steel', why: 'For structural sections (beams, columns, plates) where bars alone are insufficient for the design requirement.', confidence: 70, certifications: ['ISI Mark (Mandatory)'] },
      ],
      allied: STEEL_ALLIED,
      certifications: [
        { title: 'ISI Mark Certification — Scheme I', body: 'Bureau of Indian Standards', why: 'TMT bars mandated under Ministry of Steel QCO — ISI Mark required for domestic sale and government procurement.' },
      ],
    }
  }

  return {
    primary: [
      { isNumber: 'IS 694', year: 2010, status: 'Active', title: 'PVC Insulated Cables up to 1100V', why: 'Closest semantic match — please refine your query with the specific product type, material, or application for a higher-confidence result.', confidence: 48, certifications: ['ISI Mark (Mandatory)'] },
    ],
    allied: GENERIC_ALLIED,
    certifications: [],
  }
}

export const MOCK_AUDIT_RESULT: AuditResult = {
  coverage: 75, currency: 33, certification: 25,
  diffRows: [
    { item: 'Ordinary Portland Cement 43 Grade', citedStandard: 'IS 269:2015', status: 'Compliant', action: 'No action required. Standard is current and active.' },
    { item: '2.5 sq mm multi-strand copper wire, FR grade', citedStandard: 'IS 694:1990', status: 'Outdated', action: 'Update citation to IS 694:2010 — current active revision.' },
    { item: 'Fe 500D TMT bars 16mm for RCC roof slab', citedStandard: null, status: 'Missing', action: 'Mandate compliance with IS 1786:2008 for Fe 500D high-strength deformed bars.' },
    { item: 'PVC insulated power cable 35 sq mm 1.1 kV', citedStandard: 'IS 7098 (Part 1)', status: 'Contradiction', action: 'IS 7098 mandates XLPE insulation. For PVC use IS 694:2010. Correct insulation type or citation.' },
  ],
}

export function getMockBotSuggestions(context: string, query?: string): string[] {
  const q = (query ?? '').toLowerCase()

  // Query-specific suggestions for recommend context
  if (context === 'recommend' && q) {
    if (q.includes('cable') || q.includes('wire') || q.includes('pvc')) return [
      'What are the mandatory lab tests required under IS 694:2010?',
      'What is the difference between IS 694 and IS 7098 XLPE cables?',
      'Which QCO order mandates ISI Mark on PVC insulated cables?',
    ]
    if (q.includes('cement') || q.includes('opc')) return [
      'What are the 3 grades covered under IS 269:2015 OPC?',
      'When should I use IS 1489 PPC instead of IS 269 OPC?',
      'What physical tests are mandatory before lot acceptance of cement?',
    ]
    if (q.includes('steel') || q.includes('tmt') || q.includes('rebar') || q.includes('fe 500')) return [
      'What is the difference between Fe 500 and Fe 500D grades in IS 1786?',
      'Which Ministry QCO covers TMT bars for government procurement?',
      'What are the mandatory bend and tensile tests for IS 1786 bars?',
    ]
    return [
      'What standards are most relevant to my query?',
      'Are there any mandatory QCO certifications for this product?',
      'How do I interpret the confidence score for this recommendation?',
    ]
  }

  if (context === 'standards') return [
    'What is the scope of this standard?',
    'Does this standard have mandatory QCO certification?',
    'What standards does this one supersede?',
  ]
  if (context === 'audit') return [
    'How is the Coverage score calculated?',
    'Which items in this tender need immediate correction?',
    'What is the penalty for non-compliance under BIS Act 2016?',
  ]
  return [
    'How does the AI recommendation engine work?',
    'Which sectors have mandatory QCO standards?',
    'How do I interpret confidence scores?',
  ]
}
