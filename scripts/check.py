#!/usr/bin/env python3
"""Validação simples antes do deploy."""
import json
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
    if fund.get("next_payment"): assert fund["next_payment"]>radar["generated_at"][:10]
print("Verificações OK:",len(radar["funds"]),"fundos.")
