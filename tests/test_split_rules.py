"""POST /split-rules: autenticacao e validacao das regras de split."""

VALID_RULE = {
    "product_slug": "produto-teste",
    "company_pct": "70",
    "pro_labore_pct": "30",
    "rationale": "Margem sugerida pelo Research Agent",
}


def test_rejects_request_without_api_key(client):
    response = client.post("/split-rules", json=VALID_RULE)

    assert response.status_code == 401


def test_rejects_request_with_wrong_api_key(client):
    response = client.post(
        "/split-rules", json=VALID_RULE, headers={"X-API-Key": "chave-errada"}
    )

    assert response.status_code == 401


def test_creates_rule_with_defaults(client, fake_db, auth_headers):
    response = client.post("/split-rules", json=VALID_RULE, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["product_slug"] == "produto-teste"
    assert body["approved_by"] == "Henrique"
    assert body["active"] is True
    assert len(fake_db.split_rules) == 1


def test_rejects_split_that_does_not_sum_100(client, fake_db, auth_headers):
    bad_rule = {**VALID_RULE, "company_pct": "70", "pro_labore_pct": "40"}

    response = client.post("/split-rules", json=bad_rule, headers=auth_headers)

    assert response.status_code == 422
    assert "100" in response.text  # mensagem de erro clara menciona a soma
    assert fake_db.split_rules == []  # nada foi gravado


def test_upsert_same_slug_updates_instead_of_duplicating(
    client, fake_db, auth_headers
):
    client.post("/split-rules", json=VALID_RULE, headers=auth_headers)
    updated = {**VALID_RULE, "company_pct": "80", "pro_labore_pct": "20"}

    response = client.post("/split-rules", json=updated, headers=auth_headers)

    assert response.status_code == 200
    assert len(fake_db.split_rules) == 1
    assert fake_db.split_rules[0]["company_pct"] == "80"
