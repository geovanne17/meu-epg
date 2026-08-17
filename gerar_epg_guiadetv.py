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
        
        # Encontra todos os elementos de texto com formato de hora HH:MM
        elementos_hora = soup.find_all(text=re.compile(r"^\d{2}:\d{2}$"))
        
        for elem in elementos_hora:
            horario_str = elem.strip()
            
            # Sobe no DOM para encontrar o container principal do programa
            container = elem.parent
            for _ in range(3):
                if container and container.parent and container.parent.name != "body":
                    container = container.parent

            if not container:
                continue

            # Busca exata do Título: procura links <a>, <h2>, <h3> ou tags com texto
            titulo = ""
            for tag in container.find_all(["a", "h2", "h3", "h4", "strong"]):
                texto = tag.text.strip()
                # Evita pegar a própria hora ou textos curtos irrelevantes
                if texto and texto != horario_str and len(texto) > 2 and "No Ar" not in texto:
                    titulo = texto
                    break

            if not titulo:
                continue

            # Busca a Descrição (tag <p>)
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

        # Trata virada da meia-noite
        for i in range(1, len(programas)):
            if programas[i]["dt_inicio"] < programas[i-1]["dt_inicio"]:
                programas[i]["dt_inicio"] += timedelta(days=1)

        # Define o horário de término
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
    # Adiciona o timestamp no gerador para forçar alteração do arquivo no Git
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
