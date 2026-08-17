import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import json
import urllib.request

# 1. MAPEAMENTO DE CANAIS (Cidade 96 - Fortaleza)
CANAIS = {
    "tvcamara": {
        "id_claro": "1682",
        "nome": "TV Câmara",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvescola": {
        "id_claro": "1684",
        "nome": "TV Escola",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvjustica": {
        "id_claro": "1683",
        "nome": "TV Justiça",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvsenado": {
        "id_claro": "1681",
        "nome": "TV Senado",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvverdesmares": {
        "id_claro": "1889",
        "nome": "TV Verdes Mares - Globo",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },    
    "tvcidade": {
        "id_claro": "1908",
        "nome": "TV Cidade - Record",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tntnovelas": {
        "id_claro": "1026",
        "nome": "TNT Novelas",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvjangadeiro": {
        "id_claro": "1953",
        "nome": "TV Jangadeiro - SBT",
        "desc_padrao": "Programação aberta e jornalismo."
    }
}

# Código da Cidade (96 = Fortaleza)
ID_CIDADE = "96"

def formatar_data_xui(data_str):
    """Converte formato ISO da Claro para o padrão aceito pelo XUI ONE (-0300)"""
    dt_utc = datetime.strptime(data_str, "%Y-%m-%dT%H:%MZ")
    dt_brasil = dt_utc - timedelta(hours=3)
    return dt_brasil.strftime("%Y%m%d%H%M%S -0300")

def buscar_dados_canal(id_claro, data_inicio_str, data_fim_str):
    url = (
        "https://programacao.claro.com.br/gatekeeper/exibicao/select?"
        f"q=id_revel:({ID_CIDADE}_{id_claro})+AND+id_cidade:{ID_CIDADE}&wt=json&rows=500&start=0"
        "&sort=id_canal+asc,dh_inicio+asc"
        "&fl=dh_fim+dh_inicio+st_titulo+titulo+id_programa+id_canal+id_cidade"
        f"&fq=dh_inicio:[{data_inicio_str}T00:00:00Z+TO+{data_fim_str}T23:59:00Z]"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            dados = json.loads(response.read().decode('utf-8'))
            docs = dados.get("response", {}).get("docs", [])
            print(f"-> Sucesso! Encontrados {len(docs)} programas para o ID Claro {id_claro}")
            return docs
    except Exception as e:
        print(f"-> Erro ao buscar canal {id_claro}: {e}")
        return []

def gerar_epg():
    hoje = datetime.utcnow()
    # Busca de ontem até daqui a 2 dias
    data_inicio = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")
    data_fim = (hoje + timedelta(days=2)).strftime("%Y-%m-%d")

    tv = ET.Element("tv", {"generator-info-name": "EPG"})

    # 1. Tags <channel>
    for channel_id, info in CANAIS.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display_name = ET.SubElement(canal_elem, "display-name", lang="pt")
        display_name.text = info["nome"]

    # 2. Tags <programme>
    total_programas = 0
    for channel_id, info in CANAIS.items():
        print(f"Buscando: {info['nome']} (ID Claro: {info['id_claro']} - Cidade: {ID_CIDADE})...")
        docs = buscar_dados_canal(info["id_claro"], data_inicio, data_fim)

        for item in docs:
            programme = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(item["dh_inicio"]),
                "stop": formatar_data_xui(item["dh_fim"]),
                "channel": channel_id
            })
            
            title = ET.SubElement(programme, "title", lang="pt")
            title.text = item.get("titulo", "Sem Título")

            desc = ET.SubElement(programme, "desc", lang="pt")
            desc.text = info["desc_padrao"]
            total_programas += 1

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG finalizado com sucesso! Total de programas gravados: {total_programas}")

if __name__ == "__main__":
    gerar_epg()
