import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CANAIS_GUIADETV = {
    "canaleducacao": {
        "url_slug": "canal-educacao",
        "nome": "Canal Educação"
    },
    "canalgov": {
        "url_slug": "canal-gov",
        "nome": "Canal Gov"
    }
}

def formatar_data_xui(dt):
    return dt.strftime("%Y%m%d%H%M%S -0300")

def raspagem_guiadetv_headless(slug):
    url = f"https://www.guiadetv.com/canal/{slug}"
    programas = []
    hoje = datetime.now()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html_content = page.content()
            browser.close()

        soup = BeautifulSoup(html_content, "html.parser")
        
        # O Guia de TV agrupa os programas dentro de seções de dias
        # Buscamos os containers que separam cada dia de programação
        blocos_dias = soup.find_all(["div", "section"], class_=re.compile(r"dia|programacao", re.I))
        
        # Se não achar blocos específicos, varre o documento garantindo o controle de data
        data_atual_bloco = hoje.date()

        # Encontra todos os elementos relevantes em ordem de aparecimento
        elementos = soup.find_all(text=True)

        for elem in elementos:
            texto = elem.strip()

            # 1. Detecta mudança de dia nos cabeçalhos da página (ex: "Programação de Amanhã, 25 agosto")
            if "Programação de Amanhã" in texto or "Amanhã" in texto and "na tv" in texto:
                data_atual_bloco = hoje.date() + timedelta(days=1)
            elif "Programação de Hoje" in texto:
                data_atual_bloco = hoje.date()

            # 2. Processa o horário
            if re.match(r"^\d{2}:\d{2}$", texto):
                horario_str = texto
                container = elem.parent

                # Subir até encontrar a linha com o link do programa
                for _ in range(3):
                    if container and not container.find("a", href=re.compile(r"/programa/")):
                        container = container.parent

                if not container:
                    continue

                link_titulo = container.find("a", href=re.compile(r"/programa/"))
                if not link_titulo:
                    continue

                titulo = link_titulo.text.strip()
                if not titulo or "Programação" in titulo:
                    continue

                desc_tag = container.find("p")
                desc = desc_tag.text.strip() if desc_tag else "Acompanhe a programação ao vivo."

                horas, minutos = map(int, horario_str.split(":"))
                
                # Monta a data/hora exata do programa combinando o dia correto e a hora
                dt_inicio = datetime.combine(data_atual_bloco, datetime.min.time()).replace(hour=horas, minute=minutos)

                if not any(p["dt_inicio"] == dt_inicio for p in programas):
                    programas.append({
                        "dt_inicio": dt_inicio,
                        "titulo": titulo,
                        "desc": desc
                    })

        # Ordena a lista em ordem cronológica
        programas.sort(key=lambda x: x["dt_inicio"])

        # Calcula a hora correta de término para cada programa
        for i in range(len(programas)):
            if i < len(programas) - 1:
                programas[i]["dt_fim"] = programas[i + 1]["dt_inicio"]
            else:
                programas[i]["dt_fim"] = programas[i]["dt_inicio"] + timedelta(minutes=30)

        print(f"-> Sucesso! Mapeados {len(programas)} programas (incluindo próximos dias) para '{slug}'")
        return programas

    except Exception as e:
        print(f"-> Erro ao raspar Guia de TV ({slug}): {e}")
        return []

def gerar_epg():
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tv = ET.Element("tv", {"generator-info-name": f"EPG GuiaDeTV - {agora_str}"})

    for channel_id, info in CANAIS_GUIADETV.items():
        canal_elem = ET.SubElement(tv, "channel", id=channel_id)
        display = ET.SubElement(canal_elem, "display-name", lang="pt")
        display.text = info["nome"]

    total = 0
    for channel_id, info in CANAIS_GUIADETV.items():
        print(f"Buscando programação para: {info['nome']}...")
        progs = raspagem_guiadetv_headless(info["url_slug"])
        
        for p in progs:
            prog = ET.SubElement(tv, "programme", {
                "start": formatar_data_xui(p["dt_inicio"]),
                "stop": formatar_data_xui(p["dt_fim"]),
                "channel": channel_id
            })
            ET.SubElement(prog, "title", lang="pt").text = p["titulo"]
            ET.SubElement(prog, "desc", lang="pt").text = p["desc"]
            total += 1

    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open("epg_guiadetv.xml", "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nEPG Secundário gerado! Total de programas: {total}")

if __name__ == "__main__":
    gerar_epg()
