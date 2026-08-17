import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import json
import urllib.request

# 1. MAPEAMENTO DE CANAIS (Adicione aqui os IDs e os Nomes dos canais desejados)
CANAIS = {
    "1975": "TV Câmara",
    "1996": "TV Escola",
    "1995": "TV Justiça",
    "2009": "TV Senado",
    "1889": "TV Verdes Mares - Globo",
    "1908": "TV Cidade - Record",
    "1026": "TNT Novelas",
    "1953": "TV Jangadeiro - SBT"
}

def formatar_data_xmltv(data_str):
    dt = datetime.strptime(data_str, "%Y-%m-%dT%H:%MZ")
    return dt.strftime("%Y%m%d%H%M%S +0000")

def buscar_dados_canal(id_canal, data_hoje):
    """Busca a programação de um canal específico para o dia atual"""
    # Monta a query da API para o canal específico (ex: 1_1682)
    url = (
        "https://programacao.claro.com.br/gatekeeper/exibicao/select?"
        f"q=id_revel:(96_{id_canal})+AND+id_cidade:96&wt=json&rows=100&start=0"
        "&sort=id_canal+asc,dh_inicio+asc"
        "&fl=dh_fim+dh_inicio+st_titulo+titulo+id_programa+id_canal+id_cidade"
        f"&fq=dh_inicio:[{data_hoje}T00:00:00Z+TO+{data_hoje}T23:59:00Z]"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            dados = json.loads(response.read().decode('utf-8'))
            return dados.get("response", {}).get("docs", [])
    except Exception as e:
        print(f"Erro ao buscar dados do canal {id_canal}: {e}")
        return []

def gerar_epg():
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    tv = ET.Element("tv", {
        "generator-info-name": "Claro EPG Converter",
        "generator-info-url": "https://programacao.claro.com.br"
    })

    # 2. CRIAR CABEÇALHO DOS CANAIS NO XML
    for id_canal, nome_canal in CANAIS.items():
        canal_elem = ET.SubElement(tv, "channel", id=id_canal)
        ET.SubElement(canal_elem, "display-name").text = nome_canal

    # 3. BUSCAR E ADICIONAR A PROGRAMAÇÃO DE CADA CANAL
    for id_canal in CANAIS.keys():
        print(f"Buscando programação do canal {id_canal} ({CANAIS[id_canal]})...")
        docs = buscar_dados_canal(id_canal, hoje)

        for item in docs:
            programme = ET.SubElement(tv, "programme", {
                "start": formatar_data_xmltv(item["dh_inicio"]),
                "stop": formatar_data_xmltv(item["dh_fim"]),
                "channel": item["id_canal"]
            })
            ET.SubElement(programme, "title", lang="pt").text = item.get("titulo", "")

    # 4. SALVAR O ARQUIVO XML
    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print("EPG com múltiplos canais gerado com sucesso!")

if __name__ == "__main__":
    gerar_epg()
