"""Normalizace textu (bez diakritiky) a slovník synonym pro vyhledávání."""
import re
import unicodedata


def norm(s) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^0-9a-zA-Z]+", " ", s.lower())
    return s.strip()


def tokens(s) -> list[str]:
    return [t for t in norm(s).split() if t]


# Skupiny rovnocenných výrazů (běžné popisy situací -> pojmy v katalogu).
_SYNONYM_SOURCE = [
    ["bonus", "bonusy", "premie", "tantiema", "pohyblive slozky odmeny", "pohyblivou slozku odmeny",
     "pohyblivá složka odměny", "variabilni odmena", "odmenovani", "odmena"],
    ["auditor", "externi auditor", "statutarni auditor", "zmena auditora", "urceni auditora", "novy auditor"],
    ["ucetni zaverka", "financni vykazy", "rocni zaverka", "zaverka"],
    ["stanovy", "zmena stanov", "zakladni dokument spolecnosti"],
    ["smlouva o vykonu funkce", "manazerska smlouva", "smlouva clena organu", "odmena clena organu"],
    ["outsourcing", "externalizace", "delegovani cinnosti", "svereni cinnosti tretí osobe", "dodavatel sluzby"],
    ["stret zajmu", "konflikt zajmu", "stret zajmu"],
    ["majetkova transakce", "koupe majetku", "prodej majetku", "zcizeni majetku", "nabyti majetku",
     "vyznamna smlouva", "mimo bezny obchodni styk", "zcizeni", "nabyti"],
    ["zmena clena", "volba clena", "odvolani clena", "jmenovani clena", "novy clen", "odchod clena",
     "clen organu", "clen predstavenstva", "clen dozorci rady"],
    ["vnitrni predpis", "smernice", "politika", "interni predpis", "organizacni rad"],
    ["dividenda", "rozdeleni zisku", "vyplata podilu na zisku", "uhrada ztraty"],
    ["aml", "prani spinavych penez", "legalizace vynosu", "financovani terorismu"],
    ["incident", "bezpecnostni incident", "ikt incident"],
    ["rizika", "rizeni rizik", "rizikovy profil"],
    ["valna hromada", "akcionari", "akcionar", "vh"],
]


def _build():
    groups = []
    for g in _SYNONYM_SOURCE:
        groups.append(sorted({norm(x) for x in g if norm(x)}))
    return groups


SYNONYM_GROUPS = _build()


def synonym_terms(query: str) -> list[tuple[str, list[str]]]:
    """Vrátí [(synonymní výraz, [původní tokeny které pokrývá])]."""
    q = norm(query)
    qt = q.split()
    out = []
    for g in SYNONYM_GROUPS:
        for phrase in g:
            p = phrase.split()
            matched = None
            # fráze je obsažena v dotazu (po slovech, s prefixovou shodou jednoslovných výrazů)
            if len(p) == 1:
                for t in qt:
                    if word_match(t, p[0]):
                        matched = [t]
                        break
            else:
                n = len(p)
                for i in range(len(qt) - n + 1):
                    if all(word_match(qt[i + k], p[k]) for k in range(n)):
                        matched = qt[i:i + n]
                        break
            if matched:
                for other in g:
                    if other != phrase:
                        out.append((other, matched))
                break
    return out


def word_match(tok: str, fw: str) -> bool:
    """Shoda slov tolerující české koncovky (bonus ~ bonusu, auditor ~ auditora)."""
    if tok == fw:
        return True
    if len(tok) >= 4 and fw.startswith(tok):
        return True
    if len(fw) >= 4 and tok.startswith(fw):
        return True
    if len(tok) >= 6 and len(fw) >= 6 and tok[:5] == fw[:5]:
        return True
    return False
