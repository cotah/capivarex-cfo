"""Smoke test da Fase B: sobe o uvicorn REAL com env fake e exercita rotas
que nao tocam o banco. Roda manualmente: .venv\\Scripts\\python tests/smoke_local_server.py

Nao faz parte da suite pytest (sem prefixo test_ no nome do arquivo).
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time

import httpx

SECRET = "whsec_smoke_local"
BASE = "http://127.0.0.1:8123"


def sign(payload: bytes) -> str:
    ts = int(time.time())
    v1 = hmac.new(SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256)
    return f"t={ts},v1={v1.hexdigest()}"


def main() -> int:
    # Chave fake em FORMATO JWT: o create_client do supabase-py valida o
    # formato na inicializacao (sem rede). Conteudo e 100% falso.
    fake_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoiZmFrZSJ9"
        ".assinatura-falsa"
    )
    env = {
        **os.environ,
        "SUPABASE_URL": "http://supabase.fake.local",
        "SUPABASE_SERVICE_KEY": fake_jwt,
        "STRIPE_WEBHOOK_SECRET": SECRET,
        "CFO_API_KEY": "fake-cfo-key",
    }
    # stdout/stderr para arquivo (PIPE sem leitor pode encher e travar o server)
    log = open("uvicorn_smoke.log", "wb")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8123"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(50):  # espera o boot (max ~5s)
            try:
                httpx.get(f"{BASE}/docs", timeout=0.5)
                break
            except httpx.TransportError:
                time.sleep(0.1)

        results = []

        def timed(name, expect, fn):
            t0 = time.monotonic()
            r = fn()
            results.append((f"{name} [{time.monotonic() - t0:.1f}s]",
                            r.status_code, expect))
            return r

        timed("GET /docs (boot ok)", 200, lambda: httpx.get(f"{BASE}/docs", timeout=30))

        timed(
            "webhook SEM assinatura -> 401", 401,
            lambda: httpx.post(f"{BASE}/webhooks/stripe", content=b"{}", timeout=30),
        )

        payload = json.dumps(
            {"id": "evt_smoke", "type": "product.created", "data": {"object": {}}}
        ).encode()
        timed(
            "webhook assinatura FALSA -> 401", 401,
            lambda: httpx.post(
                f"{BASE}/webhooks/stripe",
                content=payload,
                headers={"Stripe-Signature": "t=1,v1=falsa"},
                timeout=30,
            ),
        )

        timed(
            "webhook ASSINADO (evento ignorado, sem tocar banco) -> 200", 200,
            lambda: httpx.post(
                f"{BASE}/webhooks/stripe",
                content=payload,
                headers={"Stripe-Signature": sign(payload)},
                timeout=30,
            ),
        )

        timed(
            "reports sem API key -> 401", 401,
            lambda: httpx.get(f"{BASE}/reports/summary", timeout=30),
        )

        timed(
            "split-rules sem API key -> 401", 401,
            lambda: httpx.post(f"{BASE}/split-rules", json={}, timeout=30),
        )

        failed = 0
        for name, got, want in results:
            status = "PASS" if got == want else "FAIL"
            if got != want:
                failed += 1
            print(f"[{status}] {name}: esperado {want}, recebido {got}")
        return 1 if failed else 0
    finally:
        server.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
