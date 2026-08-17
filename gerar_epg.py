import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import requests

def formatar_data_xmltv(data_str):
    dt = datetime.strptime(data_str, "%Y-%m-%dT%H:%MZ")
    return dt.strftime("%Y%m%d%H%M%S +0000")

def gerar_epg():
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    
    # URL buscando a programação do dia atual
    url = (
        "https://programacao.claro.com.br/gatekeeper/exibicao/select?"
        "q=id_revel:(1_1682)+AND+id_cidade:1&wt=json&rows=100&start=0"
        "&sort=id_canal+asc,dh_inicio+asc"
        "&fl=dh_fim+dh_inicio+st_titulo+titulo+id_programa+id_canal+id_cidade"
        f"&fq=dh_inicio:[{hoje}T00:00:00Z+TO+{hoje}T23:59:00Z]"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print("Buscando dados da API...")
    response = requests.get(url, headers=headers)
    dados = response.json()
    docs = dados.get("response", {}).get("docs", [])

    if not docs:
        print("Nenhum programa encontrado.")
        return

    tv = ET.Element("tv", {
        "generator-info-name": "Claro EPG Converter",
        "generator-info-url": "https://programacao.claro.com.br"
    })

    id_canal = docs[0]["id_canal"]
    canal_elem = ET.SubElement(tv, "channel", id=id_canal)
    ET.SubElement(canal_elem, "display-name").text = f"Canal {id_canal}"

    for item in docs:
        programme = ET.SubElement(tv, "programme", {
            "start": formatar_data_xmltv(item["dh_inicio"]),
            "stop": formatar_data_xmltv(item["dh_fim"]),
            "channel": item["id_canal"]
        })
        ET.SubElement(programme, "title", lang="pt").text = item.get("titulo", "")

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print("EPG gerado com sucesso!")

if __name__ == "__main__":
    gerar_epg()