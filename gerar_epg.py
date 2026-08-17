import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import json
import urllib.request

# 1. MAPEAMENTO DE CANAIS
# Chave "channel_id": Deve ser EXATAMENTE a mesma chave/id que você cadastrou no painel do XUI ONE.
CANAIS = {
    "tvcamara": {
        "id_claro": "1975",
        "nome": "TV Câmara",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvescola": {
        "id_claro": "1996",
        "nome": "TV Escola",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvjustica": {
        "id_claro": "1995",
        "nome": "TV Justiça",
        "desc_padrao": "Acompanhe a programação ao vivo."
    },
    "tvsenado": {
        "id_claro": "2009",
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

def formatar_data_xui(data_str):
    """
    Converte '2026-08-17T00:30Z' (UTC) para '20260816213000 -0300' (Brasília)
    """
    dt_utc = datetime.strptime(data_str, "%Y-%m-%dT%H:%MZ")
    dt_brasil = dt_utc - timedelta(hours=3)
    return dt_brasil.strftime("%Y%m%d%H%M%S -0300")

def buscar_dados_canal(id_claro, data_inicio, data_fim):
    """
    Busca no intervalo de datas dinâmico (Igual ao INTERVAL do SQL no PHP)
    """
    url = (
        "https://programacao.claro.com.br/gatekeeper/exibicao/select?"
        f"q=id_revel:(1_{id_claro})+AND+id_cidade:1&wt=json&rows=500&start=0"
        "&sort=id_canal+asc,dh_inicio+asc"
        "&fl=dh_fim+dh_inicio+st_titulo+titulo+id_programa+id_canal+id_cidade"
        f"&fq=dh_inicio:[{data_inicio}T00:00:00Z+TO+{data_fim}T23:59:00Z]"
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
    # JANELA DE DATAS: De ontem até daqui a 3 dias (Resoluvel para a margem do XUI ONE)
    hoje = datetime.utcnow()
    data_ontem = (hoje - timedelta(days=1)).strftime("%Y-%m-%d")
    data_futuro = (hoje + timedelta(days=3)).strftime("%Y-%m-%d")

    tv = ET.Element("tv", {"generator-info-name": "EPG"})

    # 1. TAGS <channel>: Usa estritamente a chave do dicionário como ID
    for channel_id, info in CANAIS.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display_name = ET.SubElement(canal_elem, "display-name", lang="pt")
        display_name.text = info["nome"]

    # 2. TAGS <programme>: Garante 100% de match no mesmo ID do <channel>
    for channel_id, info in CANAIS.items():
        print(f"Buscando programação para {info['nome']} ({data_ontem} até {data_futuro})...")
        docs = buscar_dados_canal(info["id_claro"], data_ontem, data_futuro)

        for item in docs:
            programme = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(item["dh_inicio"]),
                "stop": formatar_data_xui(item["dh_fim"]),
                "channel": channel_id  # MATCH EXATO COM O <channel id="...">
            })
            
            title = ET.SubElement(programme, "title", lang="pt")
            title.text = item.get("titulo", "Sem Título")

            desc = ET.SubElement(programme, "desc", lang="pt")
            desc.text = info["desc_padrao"]

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    
    with open("epg.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print("EPG gerado com sucesso!")

if __name__ == "__main__":
    gerar_epg()
