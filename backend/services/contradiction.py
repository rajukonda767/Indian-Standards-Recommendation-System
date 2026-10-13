"""
contradiction.py
================
Rule-based contradiction detector (material families, voltage levels, etc.).
No ML hallucination — strictly deterministic logic.
"""

import re
from typing import Optional, Tuple


def get_standard_material_family(title: str, standard_number: str) -> Optional[str]:
    """
    Determines material family from official BIS title or standard number.
    Returns: 'XLPE', 'PVC', 'TMT_STEEL', 'STRUCTURAL_STEEL', 'HDPE', 'UPVC', 'OPC', 'PPC', or None
    """
    t = f"{standard_number} {title}".upper()
    
    # Cable families
    if "XLPE" in t or "CROSS-LINKED POLYETHYLENE" in t or "CROSSLINKED" in t or "IS 7098" in t:
        return "XLPE"
    if "PVC" in t or "POLYVINYL CHLORIDE" in t or "IS 694" in t or "IS 1554" in t:
        return "PVC"
        
    # Steel families
    if "DEFORMED" in t or "TMT" in t or "CONCRETE REINFORCEMENT" in t or "IS 1786" in t:
        return "TMT_REBAR"
    if "STRUCTURAL STEEL" in t or "HOT ROLLED" in t or "IS 2062" in t:
        return "STRUCTURAL_STEEL"
        
    # Pipe families
    if "HDPE" in t or "POLYETHYLENE PIPE" in t or "IS 4984" in t:
        return "HDPE"
    if "UPVC" in t or "UNPLASTICIZED" in t or "IS 4985" in t:
        return "UPVC"
        
    # Cement families
    if "PORTLAND POZZOLANA" in t or "PPC" in t or "IS 1489" in t:
        return "PPC_CEMENT"
    if "ORDINARY PORTLAND" in t or "OPC" in t or "IS 269" in t:
        return "OPC_CEMENT"
        
    return None


def normalize_material_input(material_str: Optional[str]) -> Optional[str]:
    """Normalizes extracted material to canonical family name."""
    if not material_str:
        return None
    m = material_str.strip().upper()
    if "XLPE" in m or "CROSS" in m:
        return "XLPE"
    if "PVC" in m or "POLYVINYL" in m:
        return "PVC"
    if "TMT" in m or "REBAR" in m or "REINFORC" in m:
        return "TMT_REBAR"
    if "STRUCTURAL" in m or "HOT ROLLED" in m:
        return "STRUCTURAL_STEEL"
    if "HDPE" in m or "POLYETHYLENE" in m:
        return "HDPE"
    if "UPVC" in m or "UNPLASTICIZED" in m:
        return "UPVC"
    if "OPC" in m:
        return "OPC_CEMENT"
    if "PPC" in m or "POZZOLANA" in m:
        return "PPC_CEMENT"
    return m


def check_voltage_band_contradiction(
    extracted_voltage: Optional[str],
    candidate_title: str,
    candidate_number: str
) -> Optional[str]:
    """
    Checks voltage-level compatibility:
    Low Voltage (LV): <= 1100 V (1.1 kV)
    Medium/High Voltage (MV/HV): 3.3 kV to 33 kV
    Extra High Voltage (EHV): > 33 kV
    """
    if not extracted_voltage:
        return None
    v_norm = extracted_voltage.strip().upper()
    is_lv = bool(re.search(r'1\.1\s*KV|1100\s*V|415\s*V|230\s*V|440\s*V|\bLV\b', v_norm))
    is_hv = bool(re.search(r'(?:3\.3|6\.6|11|22|33)\s*KV|\bHV\b|HIGH\s*VOLTAGE', v_norm))

    t_upper = f"{candidate_number} {candidate_title}".upper()

    if is_lv and ("HIGH VOLTAGE" in t_upper or "SHORT-CIRCUIT RATINGS OF HIGH VOLTAGE" in t_upper):
        return "This standard covers High Voltage (HV) cables, your description specifies Low Voltage (1.1kV / 1100V) — confirm intended voltage grade."
    if is_hv and "UP TO AND INCLUDING 1 100" in t_upper:
        return "This standard is limited to 1.1kV (1100V), your description specifies Medium/High Voltage (>1.1kV) — confirm intended voltage grade."
    return None


def check_contradiction(
    extracted_material: Optional[str],
    candidate_title: str,
    candidate_number: str,
    extracted_voltage: Optional[str] = None
) -> Optional[str]:
    """
    Checks if extracted material or voltage conflicts with candidate's standard.
    If contradiction exists, returns an explicit warning string.
    """
    # 1. Material check
    user_fam = normalize_material_input(extracted_material)
    if user_fam:
        std_fam = get_standard_material_family(candidate_title, candidate_number)
        if std_fam:
            # Cable contradiction: PVC requested vs XLPE standard, or XLPE requested vs PVC standard
            if user_fam == "PVC" and std_fam == "XLPE":
                return "This standard covers XLPE insulation, your description mentions PVC — confirm intended material before citing."
            if user_fam == "XLPE" and std_fam == "PVC":
                return "This standard covers PVC insulation, your description mentions XLPE — confirm intended material before citing."
                
            # Pipe contradiction: HDPE vs UPVC
            if user_fam == "HDPE" and std_fam == "UPVC":
                return "This standard covers uPVC piping, your description mentions HDPE — confirm intended material before citing."
            if user_fam == "UPVC" and std_fam == "HDPE":
                return "This standard covers HDPE piping, your description mentions uPVC — confirm intended material before citing."
                
            # Steel contradiction: TMT rebar vs Structural Steel
            if user_fam == "TMT_REBAR" and std_fam == "STRUCTURAL_STEEL":
                return "This standard covers Structural Steel sections (beams/plates), your description mentions TMT reinforcement rebars — confirm intended product before citing."
            if user_fam == "STRUCTURAL_STEEL" and std_fam == "TMT_REBAR":
                return "This standard covers Concrete Reinforcement Bars (TMT), your description mentions Structural Steel — confirm intended product before citing."

    # 2. Voltage band check
    if extracted_voltage:
        volt_warn = check_voltage_band_contradiction(extracted_voltage, candidate_title, candidate_number)
        if volt_warn:
            return volt_warn

    return None
