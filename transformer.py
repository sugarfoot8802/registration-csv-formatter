from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

OUTPUT_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "mobile",
    "team_name",
    "postal_code",
    "country",
    "coach_first_name",
    "coach_last_name",
    "coach_email",
    "coach_mobile",
    "payment_amount",
    "payment_memo",
    "credit_amount",
    "credit_memo",
    "external_id",
    "club_name",
    "rate_id",
]

PLACEHOLDER_FIRST = "TEAM"
PLACEHOLDER_LAST = "MANAGER"
PLACEHOLDER_EMAIL = "Test@testerooo123.com"
PLACEHOLDER_MOBILE = "8888888888"
PLACEHOLDER_ZIP = "90210"

CANADIAN_AREA_CODES = {
    "204","226","249","250","289","306","343","365","387","403","416","418","431",
    "437","438","450","506","514","519","548","579","581","587","600","604","613",
    "639","647","672","705","709","742","778","780","782","807","819","825","867",
    "873","902","905"
}

_DIGIT_TO_LETTER = {str(i): string.ascii_uppercase[i] for i in range(10)}


def _clean_str(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def _digits_only(x) -> str:
    return re.sub(r"\D", "", _clean_str(x))


def _lower(x) -> str:
    s = _clean_str(x)
    return s.lower() if s else ""


def _is_valid_10_digit_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\d{10}", phone))


def _infer_country_from_phone(phone: str) -> str:
    # Locked: placeholder phone => US
    if phone == PLACEHOLDER_MOBILE:
        return "US"
    if len(phone) >= 10:
        area = phone[-10:-7]
        return "CA" if area in CANADIAN_AREA_CODES else "US"
    return "US"


def _format_us_zip(zip_val: str, phone: str) -> str:
    # Locked: placeholder phone => 90210
    if phone == PLACEHOLDER_MOBILE:
        return PLACEHOLDER_ZIP
    digits = re.sub(r"\D", "", _clean_str(zip_val))
    if digits:
        return digits[:5].zfill(5)
    if len(phone) >= 10:
        return phone[-10:-5]
    return PLACEHOLDER_ZIP


def _format_ca_postal(zip_val: str, phone: str) -> str:
    # If placeholder phone, use 90210 (user rule)
    if phone == PLACEHOLDER_MOBILE:
        return PLACEHOLDER_ZIP
    p = re.sub(r"\s", "", _clean_str(zip_val).upper())
    if len(p) >= 6:
        return f"{p[:3]} {p[3:6]}"
    # Infer a valid-looking CA postal from area code (placeholder-ish but formatted)
    if len(phone) >= 10:
        area = phone[-10:-7]
        l1 = _DIGIT_TO_LETTER.get(area[0], "A")
        d1 = area[1] if len(area) > 1 else "1"
        l2 = _DIGIT_TO_LETTER.get(area[2], "A") if len(area) > 2 else "A"
        return f"{l1}{d1}{l2} 1A1"
    return PLACEHOLDER_ZIP


@dataclass
class ColumnMap:
    team_name: Optional[str] = None
    zip: Optional[str] = None
    club_name: Optional[str] = None

    # Manager/rep contact (preferred for A-D)
    mgr_first: Optional[str] = None
    mgr_last: Optional[str] = None
    mgr_email: Optional[str] = None
    mgr_phone: Optional[str] = None

    # Coach contact (fallback for A-D, and also for H-K)
    coach_first: Optional[str] = None
    coach_last: Optional[str] = None
    coach_email: Optional[str] = None
    coach_phone: Optional[str] = None


def _find_col(cols: List[str], include_all: List[str], include_any: List[str] | None = None, exclude_any: List[str] | None = None) -> Optional[str]:
    include_any = include_any or []
    exclude_any = exclude_any or []

    for c in cols:
        cl = c.lower()
        if any(x in cl for x in exclude_any):
            continue
        if all(x in cl for x in include_all) and (not include_any or any(x in cl for x in include_any)):
            return c
    return None


def detect_mapping(df: pd.DataFrame) -> ColumnMap:
    cols = [c for c in df.columns]

    # team name
    team = _find_col(cols, include_all=["team", "name"]) or _find_col(cols, include_all=["current", "team", "name"])

    # zip / postal
    zip_col = None
    for candidate in ["zip", "postal code", "postal", "postcode"]:
        for c in cols:
            if c.lower() == candidate:
                zip_col = c
                break
        if zip_col:
            break

    # club name (optional)
    club = _find_col(cols, include_all=["club", "name"])

    # manager/rep — try "Other (Manager/Team Rep) ..." style first
    mgr_first = _find_col(cols, include_all=["manager", "first"]) or _find_col(cols, include_all=["team rep", "first"]) or _find_col(cols, include_all=["rep", "first"])
    mgr_last  = _find_col(cols, include_all=["manager", "last"])  or _find_col(cols, include_all=["team rep", "last"])  or _find_col(cols, include_all=["rep", "last"])
    mgr_email = _find_col(cols, include_all=["manager", "email"]) or _find_col(cols, include_all=["team rep", "email"]) or _find_col(cols, include_all=["rep", "email"])
    mgr_phone = _find_col(cols, include_all=["manager"], include_any=["phone", "mobile"]) or _find_col(cols, include_all=["team rep"], include_any=["phone", "mobile"]) or _find_col(cols, include_all=["rep"], include_any=["phone", "mobile"])

    # coach
    coach_first = _find_col(cols, include_all=["coach", "first"])
    coach_last  = _find_col(cols, include_all=["coach", "last"])
    coach_email = _find_col(cols, include_all=["coach", "email"])
    coach_phone = _find_col(cols, include_all=["coach"], include_any=["phone", "mobile"])

    # Known alternate schema (older exports): "Manager Name 1" etc
    # If we didn't detect mgr_first/last/email/phone, try these
    if not any([mgr_first, mgr_last, mgr_email, mgr_phone]):
        # Manager Name 1 is a full name. We'll split it later if present.
        mgr_name1 = "Manager Name 1" if "Manager Name 1" in cols else None
        if mgr_name1:
            mgr_first = mgr_name1  # treat as full name field
        mgr_email = mgr_email or ("Manager Email 1" if "Manager Email 1" in cols else None)
        mgr_phone = mgr_phone or ("Manager Phone 1" if "Manager Phone 1" in cols else None)

    # Another alternate: "Enrolled By ..." (as a fallback only if no manager found)
    # We'll pull these during transformation if needed; not stored here.

    return ColumnMap(
        team_name=team,
        zip=zip_col,
        club_name=club,
        mgr_first=mgr_first,
        mgr_last=mgr_last,
        mgr_email=mgr_email,
        mgr_phone=mgr_phone,
        coach_first=coach_first,
        coach_last=coach_last,
        coach_email=coach_email,
        coach_phone=coach_phone,
    )


def _get_series(df: pd.DataFrame, col: Optional[str], kind: str = "text") -> pd.Series:
    if col and col in df.columns:
        if kind == "phone":
            return df[col].apply(_digits_only)
        if kind == "lower":
            return df[col].apply(_lower)
        return df[col].apply(_clean_str)
    return pd.Series([""] * len(df))


def _split_full_name_to_first_last(full_name: str) -> Tuple[str, str]:
    name = _clean_str(full_name)
    if not name:
        return "", ""
    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def transform_dataframe(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], Dict[str, int], Dict[str, str]]:
    df = df_raw.copy()
    mapping = detect_mapping(df)

    # Build output frame
    out = pd.DataFrame(index=df.index, columns=OUTPUT_COLUMNS)
    out[:] = ""

    # team_name (required)
    out["team_name"] = _get_series(df, mapping.team_name, "text")

    # external_id ALWAYS blank
    out["external_id"] = ""

    # club_name optional (kept if you want; safe to leave blank if not present)
    out["club_name"] = _get_series(df, mapping.club_name, "text")

    # manager fields (may be full name in mgr_first if older schema)
    mgr_first = _get_series(df, mapping.mgr_first, "text")
    mgr_last  = _get_series(df, mapping.mgr_last, "text")
    mgr_email = _get_series(df, mapping.mgr_email, "lower")
    mgr_phone = _get_series(df, mapping.mgr_phone, "phone")

    # If mgr_first is actually a "full name" (older schema: Manager Name 1), split it if last is empty
    if mapping.mgr_first == "Manager Name 1":
        split = mgr_first.apply(_split_full_name_to_first_last)
        mgr_first = split.apply(lambda t: t[0])
        mgr_last  = split.apply(lambda t: t[1])
        # Fall back to "Enrolled By ..." if manager fields empty
        enr_name  = _get_series(df, "Enrolled By Name" if "Enrolled By Name" in df.columns else None, "text")
        enr_email = _get_series(df, "Enrolled By Email" if "Enrolled By Email" in df.columns else None, "lower")
        enr_phone = _get_series(df, "Enrolled By Phone" if "Enrolled By Phone" in df.columns else None, "phone")

        # Only use enrolled-by if manager is fully empty across contact signals
        mgr_signal = (mgr_first != "") | (mgr_last != "") | (mgr_email != "") | (mgr_phone != "")
        # Enrolled-by name is full name; split
        e_split = enr_name.apply(_split_full_name_to_first_last)
        enr_first = e_split.apply(lambda t: t[0])
        enr_last  = e_split.apply(lambda t: t[1])

        mgr_first = mgr_first.where(mgr_signal, enr_first)
        mgr_last  = mgr_last.where(mgr_signal, enr_last)
        mgr_email = mgr_email.where(mgr_signal, enr_email)
        mgr_phone = mgr_phone.where(mgr_signal, enr_phone)

    # coach fields
    coach_first = _get_series(df, mapping.coach_first, "text")
    coach_last  = _get_series(df, mapping.coach_last, "text")
    coach_email = _get_series(df, mapping.coach_email, "lower")
    coach_phone = _get_series(df, mapping.coach_phone, "phone")

    # Primary contact A–D: Manager → Coach → Placeholder
    placeholder_primary_rows = 0
    invalid_mobile_fixed_rows = 0

    a_first, a_last, a_email, a_mobile = [], [], [], []
    for i in range(len(df)):
        mgr_has = any([mgr_first.iat[i], mgr_last.iat[i], mgr_email.iat[i], mgr_phone.iat[i]])
        coach_has = any([coach_first.iat[i], coach_last.iat[i], coach_email.iat[i], coach_phone.iat[i]])

        if mgr_has:
            pf, pl, pe, pm = mgr_first.iat[i], mgr_last.iat[i], mgr_email.iat[i], mgr_phone.iat[i]
        elif coach_has:
            pf, pl, pe, pm = coach_first.iat[i], coach_last.iat[i], coach_email.iat[i], coach_phone.iat[i]
        else:
            pf, pl, pe, pm = PLACEHOLDER_FIRST, PLACEHOLDER_LAST, PLACEHOLDER_EMAIL, PLACEHOLDER_MOBILE
            placeholder_primary_rows += 1

        # Required defaults within chosen source
        pf = pf or PLACEHOLDER_FIRST
        pl = pl or PLACEHOLDER_LAST
        pe = pe or PLACEHOLDER_EMAIL
        pm = pm or PLACEHOLDER_MOBILE

        # Validate primary mobile after cleaning: must be 10 digits; else placeholder
        if not _is_valid_10_digit_phone(pm):
            pm = PLACEHOLDER_MOBILE
            pe = pe or PLACEHOLDER_EMAIL
            invalid_mobile_fixed_rows += 1

        a_first.append(pf)
        a_last.append(pl)
        a_email.append(pe)
        a_mobile.append(pm)

    out["first_name"] = a_first
    out["last_name"] = a_last
    out["email"] = [e.lower() if e else PLACEHOLDER_EMAIL.lower() for e in a_email]
    out["mobile"] = a_mobile

    # Country: inferred from primary mobile (locked placeholder behavior)
    out["country"] = out["mobile"].apply(_infer_country_from_phone)

    # Postal: never blank; enforce formatting; placeholder phone => 90210
    zip_series = _get_series(df, mapping.zip, "text")
    postals = []
    for i in range(len(df)):
        phone = out["mobile"].iat[i]
        country = out["country"].iat[i]
        z = zip_series.iat[i] if len(zip_series) else ""
        if country == "CA":
            postals.append(_format_ca_postal(z, phone))
        else:
            postals.append(_format_us_zip(z, phone))
    out["postal_code"] = [p if p else PLACEHOLDER_ZIP for p in postals]

    # Coach fields H–K as parsed
    out["coach_first_name"] = coach_first
    out["coach_last_name"] = coach_last
    out["coach_email"] = coach_email
    out["coach_mobile"] = coach_phone

    # Coach mobile default if coach_first_name present
    mask_mobile_default = (out["coach_first_name"] != "") & (out["coach_mobile"] == "")
    out.loc[mask_mobile_default, "coach_mobile"] = PLACEHOLDER_MOBILE

    # If coach_first_name exists but last/email missing => blank coach group (prevents downstream "required" errors)
    incomplete_coach_mask = (out["coach_first_name"] != "") & ((out["coach_last_name"] == "") | (out["coach_email"] == ""))
    out.loc[incomplete_coach_mask, ["coach_first_name","coach_last_name","coach_email","coach_mobile"]] = ""

    # Rule: coach_email must differ from primary email; if same => blank coach group
    same_email_mask = (out["coach_email"] != "") & (out["coach_email"] == out["email"])
    out.loc[same_email_mask, ["coach_first_name","coach_last_name","coach_email","coach_mobile"]] = ""

    # Rule: A–D cannot match H–K; if they do => blank coach group
    full_dup_mask = (
        (out["coach_email"] != "") &
        (out["first_name"] == out["coach_first_name"]) &
        (out["last_name"] == out["coach_last_name"]) &
        (out["email"] == out["coach_email"]) &
        (out["mobile"] == out["coach_mobile"])
    )
    out.loc[full_dup_mask, ["coach_first_name","coach_last_name","coach_email","coach_mobile"]] = ""

    # Blank financial/rate fields (always)
    for c in ["payment_amount","payment_memo","credit_amount","credit_memo","rate_id"]:
        out[c] = ""

    # Errors/warnings list (non-fatal; you asked to list, not create a separate file)
    errors: List[str] = []
    for idx in range(len(out)):
        rownum = idx + 2  # header=1
        if _clean_str(out["team_name"].iat[idx]) == "":
            errors.append(f"Row {rownum}: team_name is required but blank")

    summary = {
        "rows": len(out),
        "placeholder_primary_rows": placeholder_primary_rows,
        "coach_blanked_rows": int((out["coach_first_name"] == "").sum() - (coach_first == "").sum()),
        "invalid_mobile_fixed_rows": invalid_mobile_fixed_rows,
    }

    mapping_dict = {
        "team_name": mapping.team_name or "",
        "zip/postal": mapping.zip or "",
        "club_name": mapping.club_name or "",
        "mgr_first": mapping.mgr_first or "",
        "mgr_last": mapping.mgr_last or "",
        "mgr_email": mapping.mgr_email or "",
        "mgr_phone": mapping.mgr_phone or "",
        "coach_first": mapping.coach_first or "",
        "coach_last": mapping.coach_last or "",
        "coach_email": mapping.coach_email or "",
        "coach_phone": mapping.coach_phone or "",
    }

    # Ensure final column order
    out = out[OUTPUT_COLUMNS]

    return out, errors, summary, mapping_dict
