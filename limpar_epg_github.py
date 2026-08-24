import xml.etree.ElementTree as ET
import requests

URL_XML_ORIGINAL = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/epg.xml"
ARQUIVO_SAIDA = "epg_limpo.xml"

def limpar_elemento(elem):
    """Remove linhas em branco e espaços desnecessários dos nós XML"""
    for child in list(elem):
        limpar_elemento(child)
        if child.tail:
            child.tail = child.tail.strip()
    if elem.text:
        elem.text = elem.text.strip()
    if elem.tail:
        elem.tail = elem.tail.strip()

def limpar_e_gerar_epg():
    print("Baixando XML do GitHub...")
    try:
        response = requests.get(URL_XML_ORIGINAL, timeout=30)
        response.raise_for_status()
        xml_data = response.content
    except Exception as e:
        print(f"Erro ao baixar o XML: {e}")
        return

    print("Processando e limpando quebras de linha e tags em branco...")
    try:
        root_origem = ET.fromstring(xml_data)

        # Elemento raiz limpo
        tv_novo = ET.Element("tv", root_origem.attrib)

        # 1. Copia os canais
        for channel in root_origem.findall("channel"):
            limpar_elemento(channel)
            tv_novo.append(channel)

        # 2. Processa cada programa de forma estrita
        programas_mantidos = 0
        for prog in root_origem.findall("programme"):
            attribs = {
                "start": prog.get("start", ""),
                "stop": prog.get("stop", ""),
                "channel": prog.get("channel", "")
            }

            prog_novo = ET.SubElement(tv_novo, "programme", attribs)

            # Título (obrigatório)
            title = prog.find("title")
            if title is not None and title.text:
                t_elem = ET.SubElement(prog_novo, "title", lang=title.get("lang", "pt"))
                t_elem.text = title.text.strip()

            # Descrição (obrigatória)
            desc = prog.find("desc")
            d_elem = ET.SubElement(prog_novo, "desc", lang="pt")
            if desc is not None and desc.text:
                d_elem.text = desc.text.strip()
            else:
                d_elem.text = "Sem descrição disponível."

            programas_mantidos += 1

        # Limpa todas as quebras vazias no documento gerado
        limpar_elemento(tv_novo)

        # Salva o arquivo XML com declaração limpa e codificação UTF-8
        tree = ET.ElementTree(tv_novo)
        tree.write(ARQUIVO_SAIDA, encoding="utf-8", xml_declaration=True)

        print(f"-> Sucesso! {programas_mantidos} programas limpos e salvos em '{ARQUIVO_SAIDA}'.")

    except Exception as e:
        print(f"Erro ao processar a limpeza do XML: {e}")

if __name__ == "__main__":
    limpar_e_gerar_epg()
