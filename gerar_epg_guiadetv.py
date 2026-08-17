import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup

# CANAIS PARA RASPAGEM NO GUIA DE TV
CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    }
}

def formatar_data_xui(dt):
    """Converte um objeto datetime para o fuso aceito pelo XUI ONE (-0300)"""
    return dt.strftime("%Y%m%d%H%M%S -0300")

def raspagem_guiadetv(slug):
    url = f"https://www.guiadetv.com/canal/{slug}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    programas = []

    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Busca por elementos que contenham blocos de horários e títulos
        itens = soup.find_all(["div", "li"], class_=re.compile(r"(program|item|row)", re.I))
        hoje_base = datetime.now()
        
        for item in itens:
            horario_elem = item.find(text=re.compile(r"^\d{2}:\d{2}$"))
            titulo_elem = item.find(["h2", "h3", "h4", "a", "strong", "span"])
            desc_elem = item.find("p")
            
            if horario_elem and titulo_elem:
                horario_str = horario_elem.strip()
                titulo = titulo_elem.text.strip()
                desc = desc_elem.text.strip() if desc_elem else "Acompanhe a programação ao vivo."
                
                horas, minutos = map(int, horario_str.split(":"))
                dt_inicio = hoje_base.replace(hour=horas, minute=minutos, second=0, microsecond=0)
                
                programas.append({
                    "dt_inicio": dt_inicio,
                    "titulo": titulo,
                    "desc": desc
                })

        # Preenche os horários de término encadeando até o início do próximo programa
        for i in range(len(programas)):
            if i < len(programas) - 1:
                dt_fim = programas[i + 1]["dt_inicio"]
                if dt_fim <= programas[i]["dt_inicio"]:
                    dt_fim += timedelta(days=1)
            else:
                dt_fim = programas[i]["dt_inicio"] + timedelta(minutes=30)
            
            programas[i]["dt_fim"] = dt_fim

        print(f"-> Sucesso! Extraídos {len(programas)} programas de '{slug}'")
        return programas

    except Exception as e:
        print(f"-> Erro na raspagem do Guia de TV ({slug}): {e}")
        return []

def gerar_epg():
    tv = ET.Element("tv", {"generator-info-name": "EPG GuiaDeTV"})

    # 1. Tags <channel>
    for channel_id, info in CANAIS_GUIADETV.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    # 2. Tags <programme>
    total_programas = 0
    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"Buscando programação para: {info['nome']}...")
        progs = raspagem_guiadetv(info["url_slug"])
        
        for p in progs:
            prog = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(p["dt_inicio"]),
                "stop": formatar_data_xui(p["dt_fim"]),
                "channel": channel_id
            })
            ET.SubElement(prog, "title", lang="pt").text = p["titulo"]
            ET.SubElement(prog, "desc", lang="pt").text = p["desc"]
            total_programas += 1

    # Salva em um XML separado
    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open("epg_guiadetv.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG Secundário gerado! Total de programas: {total_programas}")

if __name__ == "__main__":
    gerar_epg()
