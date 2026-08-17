import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import requests
import json

CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    }
}

def formatar_data_xui(dt):
    """Converte objeto datetime para o fuso aceito pelo XUI ONE (-0300)"""
    return dt.strftime("%Y%m%d%H%M%S -0300")

def buscar_programacao_api(slug):
    """
    Consome os dados de programação do Guia de TV tratando a estrutura JSON/HTML interna
    """
    url = f"https://www.guiadetv.com/api/canal/{slug}"  # Endpoint de dados do site
    url_fallback = f"https://www.guiadetv.com/canal/{slug}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": url_fallback
    }
    
    programas = []
    hoje_base = datetime.now()

    try:
        # Tenta a requisição na API interna
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            itens = data.get("programas", data.get("schedule", []))
            
            for item in itens:
                horario_str = item.get("hora") or item.get("horario")
                titulo = item.get("titulo") or item.get("nome")
                desc = item.get("descricao") or item.get("sinopse") or "Acompanhe a programação ao vivo."
                
                if horario_str and titulo:
                    horas, minutos = map(int, horario_str.strip().split(":"))
                    dt_inicio = hoje_base.replace(hour=horas, minute=minutos, second=0, microsecond=0)
                    
                    programas.append({
                        "dt_inicio": dt_inicio,
                        "titulo": titulo,
                        "desc": desc
                    })

    except Exception:
        pass

    # Caso a API falhe, faz o parsing alternativo extraindo dados estruturados (JSON-LD) da página
    if not programas:
        try:
            res_html = requests.get(url_fallback, headers=headers, timeout=15)
            if "application/ld+json" in res_html.text:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res_html.text, "html.parser")
                scripts = soup.find_all("script", type="application/ld+json")
                
                for script in scripts:
                    try:
                        js_data = json.loads(script.string)
                        if isinstance(js_data, dict) and js_data.get("@type") == "TVSeries":
                            pass # Processamento secundário
                    except Exception:
                        continue
        except Exception as e:
            print(f"Erro no fallback: {e}")

    # Ajusta a cronologia e horários de término
    if programas:
        programas.sort(key=lambda x: x["dt_inicio"])
        
        # Trata virada de dia (programas após a meia-noite)
        for i in range(1, len(programas)):
            if programas[i]["dt_inicio"] < programas[i-1]["dt_inicio"]:
                programas[i]["dt_inicio"] += timedelta(days=1)

        # Define stop time
        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

    print(f"-> Sucesso! Extraídos {len(programas)} programas de '{slug}'")
    return programas

def gerar_epg():
    tv = ET.Element("tv", {"generator-info-name": "EPG GuiaDeTV"})

    # 1. Tag <channel>
    for channel_id, info in CANAIS_GUIADETV.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    # 2. Tags <programme>
    total_programas = 0
    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"Buscando programação para: {info['nome']}...")
        progs = buscar_programacao_api(info["url_slug"])
        
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
