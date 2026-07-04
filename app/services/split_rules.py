"""Logica de negocio das regras de split (ja validadas pelo schema)."""

from app.schemas import SplitRuleIn


def upsert(db, rule: SplitRuleIn) -> dict:
    data = rule.model_dump(mode="json")
    data["active"] = True
    return db.upsert_split_rule(data)
