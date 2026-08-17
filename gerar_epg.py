import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import json
import urllib.request

# 1. MAPEAMENTO DE CANAIS
# Chave: ID no XUI ONE (ex: "tvplanetanet")
# Valor: Tupla com (ID da Claro API, Nome Exibido, Descrição Padrão)
CANAIS = {
    "TV Câmara": {
        "id_claro": "1975",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TV Escola": {
        "id_claro": "1996",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TV Justiça": {
        "id_claro": "1995",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TV Senado": {
        "id_claro": "2009",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TV Verdes Mares - Globo": {
        "id_claro": "1889",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },	
    "TV Cidade - Record": {
        "id_claro": "1908",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TNT Novelas": {
        "id_claro": "1026",
        "nome": "Tv Planetanet",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "TV Jangadeiro - SBT": {
        "id_claro": "1953",
        "nome": "Globo",
        "desc_padrao": "Programação aberta e jornalismo."
    }
}

def formatar_data_xui(data_str):
    """
    Converte '2026-08-17T00:30Z' (UTC) para o formato '20260816213000 -0300' (Horário de Brasília)
    """
    dt_utc = datetime.strptime(data_str, "%Y-%m-%dT%H:%MZ")
    # Subtrai 3 horas para ajustar o fuso do Brasil (-03:00)
    dt_brasil = dt_utc - timedelta(hours=3)
    return dt_brasil.strftime("%Y%m%d%H%M%S -0300")

def buscar_dados_canal(id_claro, data_hoje):
    url = (
        "https://programacao.claro.com.br/gatekeeper/exibicao/select?"
        f"q=id_revel:(96_{id_claro})+AND+id_cidade:96&wt=json&rows=100&start=0"
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
        print(f"Erro ao buscar canal {id_claro}: {e}")
        return []

def gerar_epg():
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    # Cabeçalho idêntico ao exigido pelo XUI ONE
    tv = ET.Element("tv", {"generator-info-name": "EPG"})

    # 1. Criar as tags <channel>
    for channel_id, info in CANAIS.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display_name = ET.SubElement(canal_elem, "display-name", lang="pt")
        display_name.text = info["nome"]

    # 2. Criar as tags <programme>
    for channel_id, info in CANAIS.items():
        print(f"Processando {info['nome']}...")
        docs = buscar_dados_canal(info["id_claro"], hoje)

        for item in docs:
            programme = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(item["dh_inicio"]),
                "stop": formatar_data_xui(item["dh_fim"]),
                "channel": channel_id  # Usa o mesmo ID cadastrado no XUI ONE
            })
            
            # Título
            title = ET.SubElement(programme, "title", lang="pt")
            title.text = item.get("titulo", "Sem Título")

            # Descrição
            desc = ET.SubElement(programme, "desc", lang="pt")
            desc.text = info["desc_padrao"]

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print("EPG atualizado com sucesso no formato XUI ONE!")

if __name__ == "__main__":
    gerar_epg()
