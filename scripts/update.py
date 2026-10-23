#!/usr/bin/env python3
"""Atualização semanal: dados públicos + proventos/vacância opcionais via brapi Pro."""
import datetime as dt
import json
import email.utils
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "radar.json"
WATCH = {
    "BTLG11": "Logística", "HGLG11": "Logística", "XPLG11": "Logística",
    "KNCR11": "Recebíveis", "RBRR11": "Recebíveis", "MXRF11": "Recebíveis",
    "XPML11": "Shoppings", "VISC11": "Shoppings",
    "KNRI11": "Híbrido", "HGRU11": "Renda urbana",
    "PVBI11": "Lajes corporativas", "VILG11": "Logística",
}
TOKEN = os.getenv("BRAPI_TOKEN", "").strip()
TODAY = dt.datetime.now(dt.timezone.utc).date()
UA = "ClaraFIIs/1.0 (dados publicos para pesquisa pessoal)"
ERRORS = []

def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=22) as res:
        return json.load(res)

def safe(url, headers=None):
    try:
        return get(url, headers)
    except Exception as exc:
        ERRORS.append(url.split("?")[0] + ": " + type(exc).__name__)
        return {}

def date_only(value):
    if not value:
        return None
    found = re.match(r"\d{4}-\d{2}-\d{2}", str(value))
    return found.group(0) if found else None

def valid_num(value, minimum=None, maximum=None):
    try:
        x = float(value)
        if not (-1e15 < x < 1e15): return None
        if minimum is not None and x < minimum: return None
        if maximum is not None and x > maximum: return None
        return x
    except (ValueError, TypeError, OverflowError):
        return None

def get_items(data):
    return data.get("itens", []) if isinstance(data, dict) else []

def news_for(ticker):
    query = urllib.parse.urlencode({"ticker": ticker, "limite": 5})
    raw = safe("https://capitalagora.com.br/api/noticias?" + query)
    seen, items = set(), []
    for n in get_items(raw):
        title, url = (n.get("titulo") or "").strip(), n.get("url") or ""
        if not title or not url.startswith("https://") or url in seen: continue
        seen.add(url)
        published = date_only(n.get("publicado"))
        if published:
            try:
                if (TODAY - dt.date.fromisoformat(published)).days > 100: continue
            except ValueError:
                continue
        items.append({"title": title[:220], "url": url, "source": n.get("veiculo", "Veículo"), "date": published})
        if len(items) == 3: break
    return items

def topics_in_news(news):
    keywords = [
        ("emiss", "emissão de cotas"),
        ("vacância", "vacância"),
        ("inadimpl", "inadimplência"),
        ("aquisi", "aquisições"),
        ("alavanc", "alavancagem"),
        ("distribuição", "distribuição"),
        ("rebaix", "rebaixamento"),
        ("dívida", "dívidas"),
    ]
    text = " ".join(n["title"].casefold() for n in news)
    return [label for key, label in keywords if key in text][:4]

def rss_search(query, label, limit=3):
    # RSS público de manchetes: sempre mostrar fonte, data e link original.
    args = urllib.parse.urlencode({"q": query, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
    url = "https://news.google.com/rss/search?" + args
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ClaraFIIs)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read(250000))
        result = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = item.findtext("link") or ""
            if not title or not link.startswith("https://"): continue
            dateval = None
            try:
                dateval = email.utils.parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
                if not 0 <= (TODAY - dt.date.fromisoformat(dateval)).days <= 21: continue
            except (ValueError, TypeError, OverflowError):
                continue
            source = (item.findtext("source") or label).strip()
            result.append({"title": title[:220], "url": link, "source": source + " • " + label, "date": dateval})
            if len(result) >= limit: break
        return result
    except Exception as exc:
        ERRORS.append("Google News RSS: " + type(exc).__name__)
        return []

def macro_series(slug):
    """Extrai o último indicador confirmado sem aceitar observações futuras."""
    url = "https://capitalagora.com.br/api/indicador/" + slug
    d = safe(url)
    if isinstance(d, dict):
        latest = d.get("ultimo")
        record = latest if isinstance(latest, dict) else d
        value = valid_num(record.get("valor", record.get("value", record.get("ultimo_valor"))))
        date = date_only(record.get("data", record.get("date")))
        if value is not None and date and date <= str(TODAY):
            return {"value": value, "date": date, "source": url}
    # A série 432 do Banco Central é a meta Selic; 433 seria IPCA mensal,
    # portanto não serve para substituir o indicador IPCA acumulado em 12 meses.
    if slug == "selic-meta":
        bcb_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
        response = safe(bcb_url)
        if isinstance(response, list) and response:
            item = response[-1]
            value = valid_num(item.get("valor"), 0, 100)
            try:
                reference = dt.datetime.strptime(item.get("data", ""), "%d/%m/%Y").date()
            except (TypeError, ValueError):
                reference = None
            if value is not None and reference and reference <= TODAY:
                return {"value": value, "date": reference.isoformat(), "source": bcb_url}
    return {"value": None, "date": None, "source": url}

def brapi(endpoint, symbols):
    allowed = symbols if TOKEN else [x for x in symbols if x in {"MXRF11", "HGLG11"}]
    if not allowed:
        return {}
    qs = urllib.parse.urlencode({"symbols": ",".join(allowed)})
    auth = {"Authorization": "Bearer " + TOKEN} if TOKEN else None
    return safe("https://brapi.dev/api/v2/fii/" + endpoint + "?" + qs, auth)

def curated_events():
    """Anúncios revisados manualmente, válidos apenas por um período curto."""
    path = ROOT / "data" / "proventos-verificados.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    events = []
    for e in raw.get("events", []):
        ticker = e.get("ticker")
        payment = date_only(e.get("payment_date"))
        cutoff = date_only(e.get("ex_right_date"))
        rate = valid_num(e.get("per_share"), 0.00001, 1000)
        source = e.get("source") or ""
        if ticker not in WATCH or not payment or not cutoff or rate is None:
            continue
        if not source.startswith("https://") or cutoff > payment:
            continue
        try:
            age = (TODAY - dt.date.fromisoformat(payment)).days
            if age > 65 or age < -120:
                continue
        except ValueError:
            continue
        events.append({"symbol": ticker, "label": "RENDIMENTO", "rate": rate, "paymentDate": payment,
                       "lastDatePrior": cutoff, "sourceUrl": source,
                       "sourceKind": "Anúncio revisado manualmente",
                       "verifiedOn": date_only(e.get("verified_on") or raw.get("updated_at"))})
    return events

def reviewed_vacancies():
    path = ROOT / "data" / "vacancias-revisadas.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    records = {}
    for entry in raw.get("items", []):
        ticker = entry.get("ticker")
        rate = valid_num(entry.get("vacancy_pct"), 0, 100)
        reference = date_only(entry.get("reference"))
        source = entry.get("source") or ""
        if ticker not in WATCH or rate is None or not reference or not source.startswith("https://"):
            continue
        try:
            age = (TODAY - dt.date.fromisoformat(reference)).days
        except ValueError:
            continue
        if age < 0 or age > 150:
            continue
        records[ticker] = dict(entry, vacancy_pct=rate, reference=reference)
    return records

def fundamental_context(f):
    observations, cautions = [], []
    pvp = f.get("pvp")
    if pvp is not None:
        if pvp <= .95:
            observations.append("Cota abaixo do valor patrimonial, mas desconto não garante oportunidade")
        elif pvp >= 1.07:
            cautions.append("Negocia acima do valor patrimonial contábil")
    if f.get("last_dividend") is not None:
        observations.append("Valor por cota divulgado: R$ " +
                            format(f["last_dividend"], ".2f").replace(".", ","))
    else:
        cautions.append("Rendimento recente por cota ainda não verificado")
    if f["sector"] != "Recebíveis":
        vacancy = f.get("vacancy_pct")
        if vacancy is None:
            cautions.append("Vacância não encontrada em fonte estruturada")
        else:
            observations.append("Vacância " + (f.get("vacancy_kind") or "física").lower() + " informada: " + format(vacancy, ".1f") + "%")
            if (f.get("vacancy_kind") or "Física") != "Física":
                cautions.append("Indicador de vacância diferente do padrão físico; não comparar diretamente")
            if vacancy > 12:
                cautions.append("Vacância física acima de 12%")
    else:
        cautions.append("Conferir inadimplência, garantias e concentração dos CRIs")
    if f.get("source_reference"):
        try:
            age = (TODAY - dt.date.fromisoformat(f["source_reference"])).days
            if age > 90:
                cautions.append("Informe de patrimônio/rendimentos com mais de 90 dias")
        except ValueError:
            cautions.append("Verificar data do informe")
    for tag, issue in [("emissão de cotas", "Notícia sobre emissão: avaliar diluição e uso do capital"),
                       ("inadimplência", "Manchete sobre inadimplência: apurar fatos nos relatórios"),
                       ("alavancagem", "Manchete sobre alavancagem: checar dívidas")]:
        if tag in f.get("news_topics", []):
            cautions.append(issue)
    if f.get("report_risk_note"):
        cautions.insert(0, f["report_risk_note"])
    cautions.append("Antes de comprar: ler relatório gerencial, contratos e alavancagem")
    return observations[:3], cautions[:5]

def fundamentals():
    base = safe("https://capitalagora.com.br/api/fiis?limite=200")
    results = {}
    for row in get_items(base):
        ticker = row.get("ticker")
        if ticker not in WATCH or ticker in results: continue
        results[ticker] = row
    # O endpoint por ticker cobre ativos fora da primeira pagina.
    for ticker in WATCH:
        if ticker not in results:
            raw = safe("https://capitalagora.com.br/api/ativo/" + ticker)
            if raw.get("ticker") == ticker:
                results[ticker] = raw
    return results, base.get("pregao") if isinstance(base, dict) else None

def score_fund(f):
    # Pontos proporcionais somente para campos validados; não equivalem a conselho de compra.
    pts, possible, reasons = 0, 0, []
    pvp = f.get("pvp")
    if pvp is not None:
        possible += 35
        pts += 35 if .80 <= pvp <= 1.00 else 24 if 1.00 < pvp <= 1.06 else 18 if .70 <= pvp < .80 else 7
        reasons.append("P/VP " + format(pvp, ".2f"))
    dy = f.get("yield_month_pct")
    if dy is not None:
        possible += 25
        pts += 25 if .65 <= dy <= 1.10 else 19 if .45 <= dy <= 1.35 else 7
        reasons.append("Rendimento mensal do informe: " + format(dy, ".2f") + "%")
    investors = f.get("investors")
    if investors is not None:
        possible += 10
        pts += 10 if investors >= 100000 else 6 if investors >= 30000 else 2
    equity = f.get("equity")
    if equity is not None:
        possible += 10
        pts += 10 if equity >= 1e9 else 6 if equity >= 3e8 else 2
    vacancy = f.get("vacancy_pct")
    if vacancy is not None and f["sector"] != "Recebíveis" and (f.get("vacancy_kind") or "Física") == "Física":
        possible += 20
        pts += 20 if vacancy <= 5 else 15 if vacancy <= 10 else 7 if vacancy <= 20 else 0
        reasons.append("Vacância " + format(vacancy, ".1f") + "%")
    full_weight = 80 if f["sector"] == "Recebíveis" else 100
    score = round(100 * pts / full_weight) if possible else None
    if f.get("source_reference"):
        try:
            age = (TODAY - dt.date.fromisoformat(f["source_reference"])).days
            if age > 180 and score is not None: score = max(0, score - 20)
            elif age > 90 and score is not None: score = max(0, score - 10)
            if age > 100: reasons.append("Informe antigo: " + str(age) + " dias")
        except ValueError: pass
    missing = []
    if f.get("price") is None: missing.append("cotação")
    if f.get("yield_month_pct") is None: missing.append("rendimento")
    if f["sector"] != "Recebíveis" and (f.get("vacancy_pct") is None or f.get("vacancy_kind") != "Física"): missing.append("vacância física")
    f["score"], f["missing"], f["notes"] = score, missing, reasons
    f["classification"] = "Revisar fontes" if missing else "Monitorar"
    return f

def main():
    previous = {}
    try: previous = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError): pass
    rows, quote_date = fundamentals()
    manual_vacancies = reviewed_vacancies()
    brdiv = brapi("dividends", list(WATCH))
    brvac = brapi("properties", list(WATCH))
    div_index, vac_index = {}, {}
    for d in brdiv.get("dividends", []) + curated_events():
        if d.get("symbol") not in WATCH or d.get("label") != "RENDIMENTO": continue
        if d.get("remarks") and "backfilled" in str(d.get("remarks")).lower(): continue
        amount = valid_num(d.get("rate"), 0, 1000)
        if amount is None: continue
        div_index.setdefault(d["symbol"], []).append(d)
    for v in brvac.get("fiis", []):
        if v.get("symbol") in WATCH:
            vac_index[v["symbol"]] = v
    funds = []
    prev_by_ticker = {x["ticker"]: x for x in previous.get("funds", []) if x.get("ticker") in WATCH}
    for ticker, sector in WATCH.items():
        r = rows.get(ticker, {})
        older = prev_by_ticker.get(ticker, {})
        price = valid_num(r.get("fechamento", r.get("preco")), 0.01)
        pvp = valid_num(r.get("pvp"), .05, 10)
        yield_month = valid_num(r.get("rendimento_mes_pct"), 0, 8)
        fund = {
            "ticker": ticker, "name": r.get("fundo", older.get("name", ticker)),
            "sector": sector, "price": price, "pvp": pvp,
            "yield_month_pct": yield_month,
            "source_reference": date_only(r.get("informe", r.get("informe_referencia"))),
            "quote_date": date_only(r.get("data")) or date_only(quote_date),
            "equity": valid_num(r.get("patrimonio"), 0),
            "investors": valid_num(r.get("cotistas"), 0),
            "source_url": r.get("url") or "https://capitalagora.com.br/fiis/" + ticker,
            "vacancy_pct": None, "vacancy_reference": None, "vacancy_source": None,
            "vacancy_kind": None, "report_risk_note": None, "report_url": None,
            "last_dividend": None, "dividend_reference": None,
            "last_payment": None, "last_com_date": None, "next_payment": None, "next_ex_date": None,
            "next_dividend": None, "dividend_source_type": None,
            "upcoming_com_date": None, "upcoming_ex_date": None,
            "upcoming_payment_date": None, "upcoming_per_share": None,
            "upcoming_source": None, "upcoming_source_type": None,
            "latest_com_date": None, "com_date_history": [],
            "payment_source": None, "news": news_for(ticker)
        }
        fund["news_topics"] = topics_in_news(fund["news"])
        v = vac_index.get(ticker, {})
        vacrate = valid_num((v.get("summary") or {}).get("vacancyRate"), 0, 1)
        if vacrate is not None:
            fund["vacancy_pct"] = round(100 * vacrate, 2)
            fund["vacancy_reference"] = date_only(v.get("referenceDate"))
            fund["vacancy_source"] = "https://brapi.dev/docs/fiis/imoveis"
            fund["vacancy_kind"] = "Física"
        reviewed = manual_vacancies.get(ticker)
        if reviewed and (not fund["vacancy_reference"] or reviewed["reference"] > fund["vacancy_reference"]):
            fund["vacancy_pct"] = reviewed["vacancy_pct"]
            fund["vacancy_kind"] = reviewed.get("vacancy_kind") or "Física"
            fund["vacancy_reference"] = reviewed["reference"]
            fund["vacancy_source"] = reviewed["source"]
        if reviewed:
            fund["report_url"] = reviewed["source"]
            fund["report_risk_note"] = reviewed.get("note")
        valid_events = []
        for d in div_index.get(ticker, []):
            com = date_only(d.get("lastDatePrior"))
            payment = date_only(d.get("paymentDate"))
            ex = date_only(d.get("exDate"))
            amount = valid_num(d.get("rate"), 0.00001, 1000)
            if not com or amount is None:
                continue
            try:
                com_date = dt.date.fromisoformat(com)
                if payment and dt.date.fromisoformat(payment) < com_date:
                    continue
                if ex and dt.date.fromisoformat(ex) <= com_date:
                    ex = None  # Alguns provedores preenchem exDate com a própria data-com
            except ValueError:
                continue
            valid_events.append((d, com, ex, payment, amount))
        # Mais recente data-com primeiro, independente do dia de pagamento.
        valid_events.sort(key=lambda item: (item[1], item[3] or ""), reverse=True)
        fund["com_date_history"] = sorted({x[1] for x in valid_events if x[1] <= str(TODAY)}, reverse=True)[:6]
        fund["latest_com_date"] = fund["com_date_history"][0] if fund["com_date_history"] else None
        # "Próxima compra até" usa somente anúncios confirmados que ainda não perderam a data-com.
        upcoming = [x for x in valid_events if x[1] >= str(TODAY)]
        if upcoming:
            d, com, ex, payment, amount = min(upcoming, key=lambda item: item[1])
            fund["upcoming_com_date"] = com
            fund["upcoming_ex_date"] = ex
            fund["upcoming_payment_date"] = payment
            fund["upcoming_per_share"] = round(amount, 5)
            fund["upcoming_source"] = d.get("sourceUrl") or "https://brapi.dev/docs/fiis/dividendos"
            fund["upcoming_source_type"] = d.get("sourceKind") or "Base de proventos brapi"
        dated = sorted(div_index.get(ticker, []), key=lambda x: date_only(x.get("paymentDate")) or "", reverse=True)
        for d in dated:
            pay = date_only(d.get("paymentDate"))
            if not pay: continue
            amount = round(float(d["rate"]), 5)
            source = d.get("sourceUrl") or "https://brapi.dev/docs/fiis/dividendos"
            source_type = d.get("sourceKind") or "Base de proventos brapi"
            if pay > str(TODAY) and not fund["next_payment"]:
                fund["next_payment"] = pay
                fund["next_ex_date"] = date_only(d.get("lastDatePrior"))
                fund["next_dividend"] = amount
                fund["payment_source"] = source
            if pay <= str(TODAY) and fund["last_dividend"] is None:
                fund["last_dividend"], fund["last_payment"], fund["dividend_reference"] = amount, pay, pay
                fund["last_com_date"] = date_only(d.get("lastDatePrior"))
                fund["payment_source"] = source
                fund["dividend_source_type"] = source_type
        # A data-com é tratada separadamente da data de pagamento. Mesmo se o valor
        # entrar na conta num dia futuro, comprar após a data-com não dá direito.
        # Não prever próximos dias-com a partir do último mês.
        fund = score_fund(fund)
        fund["observations"], fund["cautions"] = fundamental_context(fund)
        fund["evidence_count"] = sum(1 for key in ("price", "pvp", "yield_month_pct", "equity", "investors", "last_dividend") if fund.get(key) is not None)
        fund["data_quality"] = "Em revisão" if fund.get("missing") or fund["evidence_count"] < 5 else "Parcial"
        funds.append(fund)
    funds.sort(key=lambda f: (len(f["missing"]) == 0, f["last_dividend"] is not None, f["score"] if f["score"] is not None else -1), reverse=True)
    headlines = []
    rawnews = safe("https://capitalagora.com.br/api/noticias?tema=mercados&limite=12")
    for n in get_items(rawnews):
        if n.get("titulo") and (n.get("url") or "").startswith("https://"):
            headlines.append({"title": n["titulo"][:220], "url": n["url"], "source": n.get("veiculo", "Fonte"), "date": date_only(n.get("publicado"))})
        if len(headlines) == 6: break
    econnews = []
    for n in get_items(safe("https://capitalagora.com.br/api/noticias?tema=economia&limite=8")):
        if n.get("titulo") and (n.get("url") or "").startswith("https://"):
            econnews.append({"title": n["titulo"][:220], "url": n["url"], "source": n.get("veiculo", "Fonte") + " • Brasil", "date": date_only(n.get("publicado"))})
        if len(econnews) == 3: break
    headlines = (econnews
                 + rss_search("Federal Reserve juros Estados Unidos economia", "Exterior", 2)
                 + headlines)[:8]
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "quote_date": date_only(quote_date),
        "weekly_status": "Atualizado" if any(x["price"] for x in funds) else "Dados indisponíveis",
        "funds": funds,
        "headlines": headlines,
        "macro": {"selic": macro_series("selic-meta"), "inflation": macro_series("ipca-12m")},
        "data_providers": [
            {"name": "Capital Agora (B3 / CVM)", "url": "https://capitalagora.com.br/api"},
            {"name": "CVM - informes de FIIs", "url": "https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal"},
            {"name": "brapi (opcional, Pro)", "url": "https://brapi.dev/docs/fiis"},
            {"name": "Relatórios gerenciais revisados (fontes nos cards)", "url": "https://fnet.bmfbovespa.com.br/fnet/publico/"}
        ],
        "warnings": [
            "Ranking automatizado, não é análise individual nem recomendação de compra.",
            "Taxa mensal do informe não é dividendo anunciado nem garantia de pagamento.",
            "Anúncios revisados manualmente expiram após 65 dias; confira a atualização e o documento da fonte.",
            "Vacância e próximas datas de pagamento só aparecem quando confirmadas por fonte estruturada.",
            "Uma compra realizada após a data-com anunciada não recebe aquele provento."
        ],
        "provider_status": {"capital_agora": bool(rows), "brapi_full": bool(TOKEN), "errors": ERRORS[:15]}
    }
    if not rows:
        # Falha da fonte NÃO deve manter cotação anterior como se fosse atual.
        out["funds"] = [dict(x, price=None, quote_date=None, score=None, classification="Dados indisponíveis") for x in funds]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Fundos:", len(out["funds"]), "Cotação:", out["quote_date"], "Erros:", len(ERRORS))
    if not rows:
        sys.exit("Nenhuma cotação obtida. Snapshot gerado com aviso e sem recomendação.")

if __name__ == "__main__":
    main()
