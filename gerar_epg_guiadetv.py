import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# CANAIS PARA RASPAGEM E API
CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    },
    "canalgov": {
        "url_slug": "canal-gov",
        "nome": "Canal Gov"
    }
}

def formatar_data_xui(dt):
    return dt.strftime("%Y%m%d%H%M%S -0300")

def buscar_ebc_api(slug):
    """Tenta buscar a programação na API oficial da EBC passando intervalo de datas"""
    hoje = datetime.now()
    programas = []
    
    # Busca programação de hoje e dos próximos 2 dias
    for i in range(3):
        data_str = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://epg.ebc.com.br/api/programacao/{slug}/{data_str}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                dados = res.json()
                items = dados if isinstance(dados, list) else dados.get("programas", [])

                for item in items:
                    titulo = item.get("titulo") or item.get("nome")
                    desc = item.get("descricao") or item.get("sinopse") or "Programação Canal Gov."
                    data_inicio_raw = item.get("data_inicio") or item.get("inicio") or item.get("horario")

                    if titulo and data_inicio_raw:
                        try:
                            if "T" in str(data_inicio_raw):
                                dt_inicio = datetime.fromisoformat(str(data_inicio_raw).replace("Z", "+00:00")) - timedelta(hours=3)
                            else:
                                horas, minutos = map(int, str(data_inicio_raw).split(":"))
                                dt_inicio = (hoje + timedelta(days=i)).replace(hour=horas, minute=minutos, second=0, microsecond=0)

                            programas.append({
                                "dt_inicio": dt_inicio,
                                "titulo": titulo.strip(),
                                "desc": desc.strip()
                            })
                        except ValueError:
                            continue
        except Exception:
            continue

    if programas:
        programas.sort(key=lambda x: x["dt_inicio"])
        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)
        print(f"-> Sucesso via API EBC! Extraídos {len(programas)} programas para '{slug}'")
        
    return programas

def raspagem_guiadetv_headless(slug):
    """Raspagem via Playwright para o Guia de TV (usado para Canal Educação e Fallback do Canal Gov)"""
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

        print(f"-> Sucesso via Guia de TV! Extraídos {len(programas)} programas para '{slug}'")
        return programas

    except Exception as e:
        print(f"-> Erro ao raspar Guia de TV ({slug}): {e}")
        return []

def gerar_epg():
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tv = ET.Element("tv", {"generator-info-name": f"EPG Secundario - {agora_str}"})

    for channel_id, info in CANAIS_GUIADETV.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    total = 0

    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"\nBuscando dados para: {info['nome']}...")
        progs = []

        # Tenta a API para o Canal Gov
        if channel_id == "canalgov":
            progs = buscar_ebc_api("canal-gov")

        # Se a API falhar ou se for o Canal Educação, utiliza o Playwright (Guia de TV)
        if not progs:
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

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open("epg_guiadetv.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG Secundário finalizado! Total de programas gravados: {total}")

if __name__ == "__main__":
    gerar_epg()
