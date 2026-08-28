cat << 'EOF' > scraper_playtv.py
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import re

URL_PROGRAMACAO = "https://playtv.com.br/site/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CHANNEL_ID = "playtv.br"
CHANNEL_NAME = "PlayTV"

def buscar_html():
    try:
        res = requests.get(URL_PROGRAMACAO, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print(f"Erro ao acessar o site: {e}")
    return None

def parsear_programacao(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    programas_por_dia = []

    # Localiza o container principal da tabela de programação no site
    # Ajuste de seletores baseado no layout WordPress/Elementor do site
    linhas = soup.find_all('tr') or soup.select('.elementor-widget-container div')
    
    # Processamento fallback buscando por padrão de horário HH:MM e texto do programa
    eventos_brutos = []
    
    # Busca por elementos que contenham horário no formato HH:MM
    for item in soup.find_all(['div', 'td', 'li', 'p']):
        texto = item.get_text(strip=True)
        match = re.search(r'^(\d{2}:\d{2})\s*[-–]?\s*(.+)$', texto)
        if match:
            hora, titulo = match.groups()
            eventos_brutos.append((hora, titulo))

    return eventos_brutos

def gerar_xmltv():
    print(f"Obtendo HTML de {URL_PROGRAMACAO}...")
    html_content = buscar_html()
    
    if not html_content:
        print("Não foi possível carregar a página.")
        return

    tv = ET.Element('tv', generator_info_name="PlayTV EPG Scraper")
    
    # Definindo Canal
    channel_elem = ET.SubElement(tv, 'channel', id=CHANNEL_ID)
    display_name = ET.SubElement(channel_elem, 'display-name')
    display_name.text = CHANNEL_NAME

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extrai tabelas ou blocos contendo a programação da semana
    # O layout exibe blocos por data (ex: 28/08/26)
    hoje = datetime.now()
    total_programas = 0

    # Raspagem direta buscando pares de Hora -> Titulo nas colunas
    # Procura estrutura com horários e títulos
    elementos_horario = soup.find_all(text=re.compile(r'^\d{2}:\d{2}$'))
    
    grade = []
    for elem in elementos_horario:
        parent = elem.parent
        # Busca o título na célula/tag adjacente
        proximo = parent.find_next_sibling() or parent.parent.find_next_sibling()
        if proximo:
            titulo = proximo.get_text(strip=True)
            if titulo and len(titulo) > 1:
                grade.append({
                    "hora": elem.strip(),
                    "titulo": titulo
                })

    # Remove duplicados mantendo a ordem
    grade_filtrada = []
    for item in grade:
        if not grade_filtrada or grade_filtrada[-1] != item:
            grade_filtrada.append(item)

    # Processa os horários para montar os blocos de programa (start/stop)
    for i in range(len(grade_filtrada)):
        prog_atual = grade_filtrada[i]
        hora_str = prog_atual["hora"]
        titulo = prog_atual["titulo"]

        # Define início
        h, m = map(int, hora_str.split(':'))
        dt_inicio = hoje.replace(hour=h, minute=m, second=0, microsecond=0)

        # Define fim (horário do próximo programa ou +1h se for o último)
        if i < len(grade_filtrada) - 1:
            prox_hora_str = grade_filtrada[i+1]["hora"]
            ph, pm = map(int, prox_hora_str.split(':'))
            dt_fim = hoje.replace(hour=ph, minute=pm, second=0, microsecond=0)
            if dt_fim <= dt_inicio:
                dt_fim += timedelta(days=1)
        else:
            dt_fim = dt_inicio + timedelta(hours=1)

        start_xml = dt_inicio.strftime("%Y%m%d%H%M%S -0300")
        stop_xml = dt_fim.strftime("%Y%m%d%H%M%S -0300")

        p_elem = ET.SubElement(tv, 'programme', start=start_xml, stop=stop_xml, channel=CHANNEL_ID)
        t_elem = ET.SubElement(p_elem, 'title', lang="pt")
        t_elem.text = titulo
        total_programas += 1

    xml_bytes = ET.tostring(tv, encoding='utf-8')
    dom = minidom.parseString(xml_bytes)
    
    with open("playtv.xml", "wb") as f:
        f.write(dom.toprettyxml(indent="  ", encoding="utf-8"))

    print(f"\nFinalizado! Gerado 'playtv.xml' com {total_programas} programas.")

if __name__ == "__main__":
    gerar_xmltv()
EOF
