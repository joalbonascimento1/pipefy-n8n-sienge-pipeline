import pandas as pd
import requests
import ssl
from requests.adapters import HTTPAdapter
import os
import time
from bs4 import BeautifulSoup

# --- CLASSE ADAPTADORA PARA FORÇAR PROTOCOLO TLSv1.2 ---
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

# --- CONFIGURAÇÕES ---
EXCEL_PATH_ORIGINAL = r"{{seu caminho}}"
EXCEL_PATH_NOVO = r"{{seu caminho}}"
SHEET_NAME = "incc"

# Mapeamentos de meses
MESES_MAPA_ABREV_PARA_NOME = {
    'jan': 'janeiro', 'fev': 'fevereiro', 'mar': 'marco', 'abr': 'abril',
    'mai': 'maio', 'jun': 'junho', 'jul': 'julho', 'ago': 'agosto',
    'set': 'setembro', 'out': 'outubro', 'nov': 'novembro', 'dez': 'dezembro'
}
MESES_MAPA_NUM_PARA_NOME = {
    1: 'janeiro', 2: 'fevereiro', 3: 'marco', 4: 'abril', 5: 'maio', 6: 'junho',
    7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
}

def buscar_e_preencher_incc():
    if not os.path.exists(EXCEL_PATH_ORIGINAL):
        print(f"ERRO: O arquivo original não foi encontrado: {EXCEL_PATH_ORIGINAL}")
        return
    
    session = requests.Session()
    session.mount('https://', TLSAdapter())

    try:
        df = pd.read_excel(EXCEL_PATH_ORIGINAL, sheet_name=SHEET_NAME)
        print("Planilha lida com sucesso!")
    except Exception as e:
        print(f"Ocorreu um erro ao ler a planilha: {e}")
        return

    valores_atualizados = 0

    for index, row in df.iterrows():
        if pd.notna(row['valor']) and str(row['valor']).strip() != '':
            continue

        data_original = row['data']
        
        try:
            # Lógica para tratar formatos de data diferentes (texto ou data completa)
            if isinstance(data_original, pd.Timestamp) or hasattr(data_original, 'strftime'):
                ano_completo = str(data_original.year)
                mes_num = data_original.month
                mes_completo = MESES_MAPA_NUM_PARA_NOME.get(mes_num)
                mes_pt_abrev = list(MESES_MAPA_ABREV_PARA_NOME.keys())[mes_num-1]
                data_para_comparar = f"{mes_pt_abrev}/{data_original.strftime('%y')}"
            else:
                data_str = str(data_original).strip()
                data_para_comparar = data_str
                mes_abrev, ano_abrev = data_str.split('/')
                ano_completo = f"20{ano_abrev}"
                mes_completo = MESES_MAPA_ABREV_PARA_NOME.get(mes_abrev.lower())

            if not mes_completo:
                print(f"Mês inválido para a data: '{data_original}'. Pulando.")
                continue

            url = f"https://portal.fgv.br/noticias/incc-m-{mes_completo}-{ano_completo}"
            print(f"\nBuscando dados para '{data_para_comparar}' em: {url}")
            
            response = session.get(url, timeout=15)

            if response.status_code != 200:
                print(f"--> Notícia para '{data_para_comparar}' ainda não disponível.")
                time.sleep(1)
                continue
            
            soup = BeautifulSoup(response.content, 'html.parser')
            valor_encontrado = None
            
            tabelas = soup.find_all('table')
            for tabela in tabelas:
                for tr in tabela.find_all('tr'):
                    celulas = tr.find_all('td')
                    if len(celulas) >= 2:
                        # --- LINHAS DE DIAGNÓSTICO ---
                        texto_celula_site = celulas[0].get_text(strip=True)
                        print(f"   > Verificando célula do site: '{texto_celula_site}' contra '{data_para_comparar}'")

                        # Comparação mais robusta (ignora maiúsculas/minúsculas)
                        if texto_celula_site.lower() == data_para_comparar.lower():
                            valor_incc = celulas[1].get_text(strip=True)
                            valor_encontrado = valor_incc
                            break
                if valor_encontrado:
                    break

            if valor_encontrado:
                print(f"--> SUCESSO! Valor encontrado para '{data_para_comparar}': {valor_encontrado}")
                df.loc[index, 'valor'] = valor_encontrado
                valores_atualizados += 1
            else:
                print(f"--> AVISO: A página para '{data_para_comparar}' foi lida, mas a data correspondente não foi achada na tabela.")

        except requests.exceptions.RequestException as e:
            print(f"--> ERRO de conexão para '{data_para_comparar}': {e}")
        except Exception as e:
            print(f"--> ERRO inesperado ao processar '{data_original}': {e}")
        
        time.sleep(1)

    print("\n--- FIM DA BUSCA ---")
    print(f"Total de novos valores encontrados e atualizados: {valores_atualizados}")

    if valores_atualizados > 0:
        try:
            print(f"Salvando {valores_atualizados} atualizações em um NOVO ARQUIVO: {EXCEL_PATH_NOVO}")
            # Salva o DataFrame atualizado em um novo arquivo Excel
            df.to_excel(EXCEL_PATH_NOVO, sheet_name=SHEET_NAME, index=False)
            print("Arquivo atualizado salvo com sucesso!")
        except Exception as e:
            print(f"\nERRO CRÍTICO AO SALVAR O ARQUIVO: {e}")
            print("Verifique se você tem permissão para salvar na pasta e se o arquivo não está aberto.")
    else:
        print("Nenhum novo valor foi adicionado. O arquivo não foi modificado.")

if __name__ == "__main__":
    buscar_e_preencher_incc()