"""Modelos Pydantic de entrada/saida dos endpoints."""

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class SplitRuleIn(BaseModel):
    product_slug: str = Field(min_length=1)
    company_pct: Decimal = Field(ge=0, le=100)
    pro_labore_pct: Decimal = Field(ge=0, le=100)
    approved_by: str = "Henrique"
    rationale: str | None = None

    @model_validator(mode="after")
    def pcts_must_sum_100(self) -> "SplitRuleIn":
        total = self.company_pct + self.pro_labore_pct
        if total != Decimal("100"):
            raise ValueError(
                f"company_pct + pro_labore_pct deve somar 100 (recebido: {total})"
            )
        return self
