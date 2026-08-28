cat << 'EOF' > scraper_playtv.py
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CHANNEL_ID = "playtv.br"
CHANNEL_NAME = "PlayTV"

def obter_html_dinamico():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Acessando a PlayTV via browser headless...")
        page.goto("https://playtv.com.br/site/#programacao", wait_until="networkidle", timeout=60000)
        
        # Rola a página para garantir o carregamento dos componentes
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)
        
        content = page.content()
        browser.close()
        return content

def gerar_xmltv():
    try:
        html_content = obter_html_dinamico()
    except Exception as e:
        print(f"Erro ao capturar página via Playwright: {e}")
        return

    soup = BeautifulSoup(html_content, 'html.parser')
    
    tv = ET.Element('tv', generator_info_name="PlayTV Playwright EPG Scraper")
    
    channel_elem = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel_elem, 'display-name')
    display_name.text = CHANNEL_NAME

    hoje = datetime.now()
    
    # Extrai horários (HH:MM) e textos adjacentes da tabela renderizada
    elementos_horario = soup.find_all(text=re.compile(r'^\d{2}:\d{2}$'))
    
    grade = []
    for elem in elementos_horario:
        parent = elem.parent
        proximo = parent.find_next_sibling() or parent.parent.find_next_sibling()
        if proximo:
            titulo = proximo.get_text(strip=True)
            if titulo and len(titulo) > 1:
                grade.append({
                    "hora": elem.strip(),
                    "titulo": titulo
                })

    # Filtra duplicatas sequenciais
    grade_filtrada = []
    for item in grade:
        if not grade_filtrada or grade_filtrada[-1] != item:
            grade_filtrada.append(item)

    if not grade_filtrada:
        print("Aviso: Nenhum programa encontrado na tabela. Verifique os seletores do site.")
        return

    total_programas = 0
    for i in range(len(grade_filtrada)):
        prog_atual = grade_filtrada[i]
        hora_str = prog_atual["hora"]
        titulo = prog_atual["titulo"]

        h, m = map(int, hora_str.split(':'))
        dt_inicio = hoje.replace(hour=h, minute=m, second=0, microsecond=0)

        if i < len(grade_filtrada) - 1:
            prox_hora_str = grade_filtrada[i+1]["hora"]
            ph, pm = map(int, prox_hora_str.split(':'))
            dt_fim = hoje.replace(hour=ph, minute=pm, second=0, microsecond=0)
            if dt_fim <= dt_inicio:
                dt_fim += timedelta(days=1)
        else:
            dt_fim = dt_inicio + timedelta(hours=1)

        p_elem = ET.SubElement(
            tv, 'programme', 
            start=dt_inicio.strftime("%Y%m%d%H%M%S -0300"), 
            stop=dt_fim.strftime("%Y%m%d%H%M%S -0300"), 
            channel=CHANNEL_ID
        )
        t_elem = ET.SubElement(p_elem, 'title', lang="pt")
        t_elem.text = titulo
        total_programas += 1

    xml_bytes = ET.tostring(tv, encoding='utf-8')
    dom = minidom.parseString(xml_bytes)
    
    with open("playtv.xml", "wb") as f:
        f.write(dom.toprettyxml(indent="  ", encoding="utf-8"))

    print(f"\nSucesso! Arquivo 'playtv.xml' gerado com {total_programas} programas.")

if __name__ == "__main__":
    gerar_xmltv()
EOF
