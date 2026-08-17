import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup

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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    programas = []

    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        hoje_base = datetime.now()
        
        # Procura por linhas do guia ou blocos que contêm texto com padrão de hora HH:MM
        elementos_hora = soup.find_all(text=re.compile(r"^\d{2}:\d{2}$"))
        
        for elem in elementos_hora:
            horario_str = elem.strip()
            
            # Navega até o container pai que guarda hora, título e descrição
            parent = elem.parent
            for _ in range(3):
                if parent and parent.name != "body":
                    parent = parent.parent
            
            if not parent:
                continue

            # Busca o título
            titulo_tag = parent.find(["h2", "h3", "h4", "a", "strong"])
            if not titulo_tag:
                continue
                
            titulo = titulo_tag.text.strip()
            if titulo == horario_str:
                continue

            # Busca a descrição
            desc_tag = parent.find("p")
            desc = desc_tag.text.strip() if desc_tag else "Acompanhe a programação ao vivo."

            horas, minutos = map(int, horario_str.split(":"))
            dt_inicio = hoje_base.replace(hour=horas, minute=minutos, second=0, microsecond=0)

            # Evita duplicatas do mesmo horário
            if not any(p["dt_inicio"] == dt_inicio for p in programas):
                programas.append({
                    "dt_inicio": dt_inicio,
                    "titulo": titulo,
                    "desc": desc
                })

        # Ordena a lista por horário
        programas.sort(key=lambda x: x["dt_inicio"])

        # Ajusta horários do dia seguinte se a hora virar a madrugada (ex: 23:30 -> 00:00)
        for i in range(1, len(programas)):
            if programas[i]["dt_inicio"] < programas[i-1]["dt_inicio"]:
                programas[i]["dt_inicio"] += timedelta(days=1)

        # Define a hora de término (stop)
        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

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

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open("epg_guiadetv.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG Secundário gerado! Total de programas: {total_programas}")

if __name__ == "__main__":
    gerar_epg()
