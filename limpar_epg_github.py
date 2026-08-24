import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests

URL_XML_ORIGINAL = "https://raw.githubusercontent.com/limaalef/BrazilTVEPG/refs/heads/main/epg.xml"
ARQUIVO_SAIDA = "epg_limpo.xml"

def limpar_e_gerar_epg():
    print("Baixando XML do GitHub...")
    try:
        response = requests.get(URL_XML_ORIGINAL, timeout=30)
        response.raise_for_status()
        xml_data = response.content
    except Exception as e:
        print(f"Erro ao baixar o XML: {e}")
        return

    print("Processando e limpando o XML...")
    try:
        # Lê o XML original
        root_origem = ET.fromstring(xml_data)

        # Cria a nova estrutura raiz do XMLTV
        tv_novo = ET.Element("tv", root_origem.attrib)

        # 1. Copia todos os canais sem alterações
        for channel in root_origem.findall("channel"):
            tv_novo.append(channel)

        # 2. Processa cada programa, mantendo apenas start, stop, channel, title e desc
        programas_mantidos = 0
        for prog in root_origem.findall("programme"):
            attribs = {
                "start": prog.get("start", ""),
                "stop": prog.get("stop", ""),
                "channel": prog.get("channel", "")
            }

            # Cria a tag programme limpa
            prog_novo = ET.SubElement(tv_novo, "programme", attribs)

            # Mantém apenas o título
            title = prog.find("title")
            if title is not None:
                prog_novo.append(title)

            # Mantém apenas a descrição (cria uma vazia se não existir para evitar erros)
            desc = prog.find("desc")
            if desc is not None:
                prog_novo.append(desc)
            else:
                ET.SubElement(prog_novo, "desc", lang="pt").text = ""

            # Garante que a subtítulo vá para a descrição se a descrição estiver vazia
            sub_title = prog.find("sub-title")
            if sub_title is not None and sub_title.text and not (desc is not None and desc.text):
                desc_elem = prog_novo.find("desc")
                if desc_elem is not None:
                    desc_elem.text = sub_title.text

            programas_mantidos += 1

        # Formata o XML para ficar legível
        xml_str = minidom.parseString(ET.tostring(tv_novo, encoding="utf-8")).toprettyxml(indent="  ")

        # Salva o arquivo limpo
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(xml_str)

        print(f"-> Sucesso! {programas_mantidos} programas processados e salvos em '{ARQUIVO_SAIDA}'.")

    except Exception as e:
        print(f"Erro ao processar a limpeza do XML: {e}")

if __name__ == "__main__":
    limpar_e_gerar_epg()
