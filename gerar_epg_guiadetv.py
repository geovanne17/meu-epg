import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    }
}

def formatar_data_xui(dt):
    return dt.strftime("%Y%m%d%H%M%S -0300")

def raspagem_guiadetv_headless(slug):
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
        
        # O site organiza cada item da grade com links do tipo /programa/...
        links_programas = soup.find_all("a", href=re.compile(r"/programa/"))

        for link in links_programas:
            titulo = link.text.strip()
            
            # Filtra cabeçalhos ou links irrelevantes
            if not titulo or "Programação" in titulo or len(titulo) < 3:
                continue

            # O bloco do programa é o elemento pai imediato do link
            item_box = link.parent
            for _ in range(2):
                if item_box and not item_box.find(text=re.compile(r"^\d{2}:\d{2}$")):
                    item_box = item_box.parent

            if not item_box:
                continue

            # Busca o horário dentro do container do item
            hora_elem = item_box.find(text=re.compile(r"^\d{2}:\d{2}$"))
            if not hora_elem:
                continue
                
            horario_str = hora_elem.strip()

            # Busca a descrição dentro do container
            desc_tag = item_box.find("p")
            desc = desc_tag.text.strip() if desc_tag else "Acompanhe a programação ao vivo."

            horas, minutos = map(int, horario_str.split(":"))
            dt_inicio = hoje_base.replace(hour=horas, minute=minutos, second=0, microsecond=0)

            # Evita duplicatas do mesmo horário e título
            if not any(p["dt_inicio"] == dt_inicio and p["titulo"] == titulo for p in programas):
                programas.append({
                    "dt_inicio": dt_inicio,
                    "titulo": titulo,
                    "desc": desc
                })

        # Ordena cronologicamente
        programas.sort(key=lambda x: x["dt_inicio"])

        # Trata a virada da meia-noite (23:30 -> 00:00)
        for i in range(1, len(programas)):
            if programas[i]["dt_inicio"] < programas[i-1]["dt_inicio"]:
                programas[i]["dt_inicio"] += timedelta(days=1)

        # Define os horários de término (stop)
        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

        print(f"-> Sucesso! Extraídos {len(programas)} programas individuais para '{slug}'")
        return programas

    except Exception as e:
        print(f"-> Erro ao raspar Guia de TV ({slug}): {e}")
        return []

def gerar_epg():
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tv = ET.Element("tv", {"generator-info-name": f"EPG GuiaDeTV - {agora_str}"})

    for channel_id, info in CANAIS_GUIADETV.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    total = 0
    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"Buscando programação para: {info['nome']}...")
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

    print(f"\nEPG Secundário gerado! Total de programas: {total}")

if __name__ == "__main__":
    gerar_epg()
