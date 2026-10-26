#!/usr/bin/env python3
"""Validação simples antes do deploy."""
import json
import importlib.util
from unittest import mock
import pathlib
import re
import subprocess
import tempfile
root=pathlib.Path(__file__).resolve().parents[1]
page=(root/"index.html").read_text(encoding="utf-8")
match=re.search(r"<script>(.*?)</script>",page,re.S)
assert match, "Script do painel não encontrado"
with tempfile.TemporaryDirectory() as temp:
    code=pathlib.Path(temp)/"frontend.js"
    code.write_text(match.group(1),encoding="utf-8")
    subprocess.run(["node","--check",str(code)],check=True)
radar=json.loads((root/"data/radar.json").read_text(encoding="utf-8"))
assert isinstance(radar["funds"],list)
for fund in radar["funds"]:
    assert re.fullmatch(r"[A-Z]{4}11",fund["ticker"]),fund["ticker"]
    assert fund.get("price") is None or fund["price"]>0
    assert fund.get("vacancy_pct") is None or 0 <= fund["vacancy_pct"] <= 100
    assert fund.get("next_payment") is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}",fund["next_payment"])
    if fund.get("next_payment"):
        assert fund["next_payment"]>radar["generated_at"][:10], "Pagamento futuro precisa ser após hoje"
        assert fund["next_payment"] != fund.get("last_payment"), "Pagamento duplicado em próximo e histórico"
    if fund.get("upcoming_com_date"):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", fund["upcoming_com_date"])
        assert fund["upcoming_com_date"]>=radar["generated_at"][:10], "Não mostrar data-com vencida como oportunidade"
        if fund.get("upcoming_payment_date"):
            assert fund["upcoming_payment_date"]>=fund["upcoming_com_date"]
        if fund.get("upcoming_ex_date"):
            assert fund["upcoming_ex_date"]>fund["upcoming_com_date"]
        assert (fund.get("upcoming_source") or "").startswith("https://"), "Toda data-com futura exige fonte"
print("Verificações OK:",len(radar["funds"]),"fundos.")

# Regressão: API de indicador com valor aninhado em "ultimo" deve ser lida corretamente.
spec = importlib.util.spec_from_file_location("clara_collector", root / "scripts" / "update.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
with mock.patch.object(collector, "safe", return_value={"ultimo":{"valor":13.75, "data":collector.TODAY.isoformat()}}):
    result = collector.macro_series("selic-meta")
assert result["value"] == 13.75 and result["date"] == collector.TODAY.isoformat()
print("Regressão Selic aninhada: OK")

# Snapshot pós-eleição deve ser datado, rastreável e consistente.
snapshot=json.loads((root / "data" / "analise-pos-eleicao-2026-10-26.json").read_text(encoding="utf-8"))
assert snapshot["source_url"].startswith("https://")
assert snapshot["observed_date"] == snapshot["observed_at"][:10]
seen=set()
for row in snapshot["prices"]:
    assert row["ticker"] not in seen
    assert row["before"]>0 and row["after"]>0
    seen.add(row["ticker"])
assert "BTLG11" in seen and "XPML11" in seen and "KNCR11" in seen
assert 'id="refreshData"' in page and 'id="marketResults"' in page
print("Comparação e recarga: OK")
