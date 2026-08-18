import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# 1. CANAIS DO GUIA DE TV (Raspagem)
CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    }
}

# 2. CANAIS DA EBC (API Oficial)
CANAIS_EBC = {
    "canalgov": {
        "slug_ebc": "canal-gov",
        "nome": "Canal Gov"
    }
}

def formatar_data_xui(dt):
    return dt.strftime("%Y%m%d%H%M%S -0300")

def buscar_ebc_api(slug):
    """Busca a programação diretamente da API oficial da EBC (Canal Gov)"""
    url = f"https://epg.ebc.com.br/api/programacao/{slug}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    programas = []

    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            dados = res.json()
            items = dados if isinstance(dados, list) else dados.get("programas", [])

            for item in items:
                # Trata campos da API
                titulo = item.get("titulo") or item.get("nome")
                desc = item.get("descricao") or item.get("sinopse") or "Programação Canal Gov."
                data_inicio_raw = item.get("data_inicio") or item.get("inicio")

                if titulo and data_inicio_raw:
                    # Converte formato ISO/Timestamp para datetime
                    try:
                        dt_inicio = datetime.fromisoformat(data_inicio_raw.replace("Z", "+00:00")) - timedelta(hours=3)
                    except ValueError:
                        continue

                    programas.append({
                        "dt_inicio": dt_inicio,
                        "titulo": titulo.strip(),
                        "desc": desc.strip()
                    })

            # Calcula horário de término encadeado
            programas.sort(key=lambda x: x["dt_inicio"])
            for i in range(len(programas)):
                if i < len(programas) - 1:
                    programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
                else:
                    programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

            print(f"-> Sucesso! Extraídos {len(programas)} programas da API EBC ({slug})")
            return programas

    except Exception as e:
        print(f"-> Erro ao buscar API EBC ({slug}): {e}")

    return []

def raspagem_guiadetv_headless(slug):
    """Raspagem Headless para o Guia de TV"""
    url = f"https://www.guiadetv.com/canal/{slug}"
    programas = []
    hoje_base = datetime.now()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, "html.parser")
        elementos_hora = soup.find_all(text=re.compile(r"^\d{2}:\d{2}$"))

        for elem in elementos_hora:
            horario_str = elem.strip()
            container = elem.parent
            for _ in range(2):
                if container and not container.find("a", href=re.compile(r"/programa/")):
                    container = container.parent

            if not container:
                continue

            link_titulo = container.find("a", href=re.compile(r"/programa/"))
            if not link_titulo:
                continue

            titulo = link_titulo.text.strip()
            if not titulo or "Programação" in titulo:
                continue

            desc_tag = container.find("p")
            desc = desc_tag.text.strip() if desc_tag else "Acompanhe a programação ao vivo."

            horas, minutos = map(int, horario_str.split(":"))
            dt_inicio = hoje_base.replace(hour=horas, minute=minutos, second=0, microsecond=0)

            if not any(p["dt_inicio"] == dt_inicio for p in programas):
                programas.append({
                    "dt_inicio": dt_inicio,
                    "titulo": titulo,
                    "desc": desc
                })

        programas.sort(key=lambda x: x["dt_inicio"])

        for i in range(1, len(programas)):
            if programas[i]["dt_inicio"] < programas[i-1]["dt_inicio"]:
                programas[i]["dt_inicio"] += timedelta(days=1)

        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

        print(f"-> Sucesso! Extraídos {len(programas)} programas de '{slug}'")
        return programas

    except Exception as e:
        print(f"-> Erro ao raspar Guia de TV ({slug}): {e}")
        return []

def gerar_epg():
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tv = ET.Element("tv", {"generator-info-name": f"EPG Secundario - {agora_str}"})

    # 1. Registrar Canais
    todos_canais = {**CANAIS_GUIADETV, **CANAIS_EBC}
    for channel_id, info in todos_canais.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    total = 0

    # 2. Processar Guia de TV (Canal Educação)
    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"Buscando no Guia de TV: {info['nome']}...")
        progs = raspagem_guiadetv_headless(info["url_slug"])
        for p in progs:
            prog = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(p["dt_inicio"]),
                "stop": formatar_data_xui(p["dt_fim"]),
                "channel": channel_id
            })
            ET.SubElement(prog, "title", lang="pt").text = p["titulo"]
            ET.SubElement(prog, "desc", lang="pt").text = p["desc"]
            total += 1

    # 3. Processar API EBC (Canal Gov)
    for channel_id, info in CANAIS_EBC.items():
        print(f"Buscando na API EBC: {info['nome']}...")
        progs = buscar_ebc_api(info["slug_ebc"])
        for p in progs:
            prog = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(p["dt_inicio"]),
                "stop": formatar_data_xui(p["dt_fim"]),
                "channel": channel_id
            })
            ET.SubElement(prog, "title", lang="pt").text = p["titulo"]
            ET.SubElement(prog, "desc", lang="pt").text = p["desc"]
            total += 1

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open("epg_guiadetv.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG Secundário finalizado! Total de programas gravados: {total}")

if __name__ == "__main__":
    gerar_epg()
