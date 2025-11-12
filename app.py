import requests
from flask import Flask, jsonify, request
import pyodbc   # <-- Biblioteca para conectar ao SQL Server
import re
import os       # <-- Para ler as Variáveis de Ambiente

# 1. Inicializa o servidor Flask
app = Flask(__name__)

# --- Configuração do Banco de Dados SQL Server ---
db_config = {
    "server": os.environ.get("DB_SERVER", "10.21.233.220"),
    "database": os.environ.get("DB_DATABASE", "tecnologia"),
    "user": os.environ.get("DB_USER", "powerbi"),
    "password": os.environ.get("DB_PASSWORD", "Tecno@2023"),
    "encrypt": True,
    "trustServerCertificate": True,
    "table": "dbo.windsor_cep"
}

def clean_cep(cep):
    """Limpa o CEP para conter apenas dígitos."""
    return re.sub(r'\D', '', cep)

def get_db_conn():
    """Cria e retorna uma nova conexão pyodbc."""
    connection_string = (
       
        f"DRIVER={{ODBC Driver 17 for SQL Server}};" 
        f"SERVER={db_config['server']};"
        f"DATABASE={db_config['database']};"
        f"UID={db_config['user']};"
        f"PWD={db_config['password']};"
        f"Encrypt={'yes' if db_config['encrypt'] else 'no'};"
        f"TrustServerCertificate={'yes' if db_config['trustServerCertificate'] else 'no'};"
    )
    
    try:
        conn = pyodbc.connect(connection_string, autocommit=False)
        return conn
    except Exception as e:
        print(f"ERRO DE CONEXÃO AO BANCO: {e}")
        print("Verifique se o 'ODBC Driver 17 for SQL Server' está instalado nesta máquina.")
        return None

# 2. ENDPOINT DE "BUSCA"
# ------------------------------------
@app.route('/Capture/Interactive/Find/v1.00/json3.ws', methods=['GET'])
def find_address():
    query_text = request.args.get('Text', '').strip()
    
    words = query_text.split(' ')
    cep = words[-1] if words else ''
    cep = clean_cep(cep)
    
    if len(cep) >= 8:
        suggestion_id = cep
        suggestion_text = f"Usar endereço com CEP: {suggestion_id}"
        
        response_data = {
            "Items": [
                {
                    "Id": suggestion_id,
                    "Type": "Address",
                    "Text": suggestion_text,
                    "Highlight": "",
                    "Description": suggestion_text
                }
            ]
        }
        return jsonify(response_data)
    
    return jsonify({"Items": []})


# 3. ENDPOINT DE "CAPTURA"
# ------------------------------------
@app.route('/Capture/Interactive/Retrieve/v1.00/json3.ws', methods=['GET'])
def retrieve_address():
    address_id_cep = request.args.get('Id', '')
    if not address_id_cep:
        return jsonify({"Items": []})

    conn = get_db_conn()
    if not conn:
        # Se a conexão falhou, retorna erro
        return jsonify({"error": "Falha na conexão com o banco de dados"}), 500

    cursor = conn.cursor()
    viacep_data = {} # Dicionário para os dados do CEP

    try:
        # --- 1. TENTA BUSCAR NO CACHE (SQL Server) ---
        sql_select = f"SELECT logradouro, bairro, localidade, uf, cep FROM {db_config['table']} WHERE cep = ?"
        cursor.execute(sql_select, (address_id_cep,))
        
        cep_data_cache = cursor.fetchone() # pyodbc.Row object
        
        if cep_data_cache:
            # --- ENCONTROU NO CACHE! ---
            print(f"CEP {address_id_cep} encontrado no CACHE SQL Server.")
            # Converte o pyodbc.Row para um dicionário padrão
            viacep_data = {
                'logradouro': cep_data_cache.logradouro,
                'bairro': cep_data_cache.bairro,
                'localidade': cep_data_cache.localidade,
                'uf': cep_data_cache.uf,
                'cep': cep_data_cache.cep
            }

        else:
            # --- 2. NÃO ENCONTROU? BUSCA NO VIACEP ---
            print(f"CEP {address_id_cep} não está no cache. Buscando no ViaCEP...")
            try:
                viacep_url = f"https://viacep.com.br/ws/{address_id_cep}/json/"
                viacep_response = requests.get(viacep_url, timeout=5) # Timeout de 5s
                viacep_data = viacep_response.json()
                
                if viacep_data.get('erro'):
                     return jsonify({"Items": []}) # CEP não existe no ViaCEP

            except Exception as e:
                print(f"Erro ao chamar ViaCEP: {e}")
                return jsonify({"Items": []})

            # --- 3. SALVA A RESPOSTA DO VIACEP NO CACHE SQL Server ---
            try:
                cep_limpo = clean_cep(viacep_data.get('cep', ''))
                
                # Se o CEP for válido, salva no banco
                if cep_limpo:
                    sql_insert = f"""
                    INSERT INTO {db_config['table']} (cep, logradouro, bairro, localidade, uf)
                    VALUES (?, ?, ?, ?, ?)
                    """
                    cursor.execute(sql_insert, (
                        cep_limpo,
                        viacep_data.get('logradouro', ''),
                        viacep_data.get('bairro', ''),
                        viacep_data.get('localidade', ''),
                        viacep_data.get('uf', '')
                    ))
                    conn.commit() # Salva a transação
                    print(f"CEP {cep_limpo} salvo no cache SQL Server.")
                
            except pyodbc.IntegrityError:
                # Caso o CEP já tenha sido inserido por outra requisição
                print(f"CEP {cep_limpo} já estava no cache (IntegrityError).")
                conn.rollback() # Desfaz o INSERT
            except Exception as e:
                print(f"Erro ao salvar no cache SQL Server: {e}")
                conn.rollback() # Desfaz o INSERT
        
        # --- 4. MAPEAMENTO (DE/PARA) -> Opera ---
        # (Usa 'viacep_data' que veio ou do cache ou do ViaCEP)
        
        opera_item = {
            "Id": address_id_cep,
            "DomesticId": address_id_cep,
            "Language": "PT",
            "LanguageAlternatives": "PT",
            "Department": "",
            "Company": "",
            "SubBuilding": "",
            "BuildingNumber": "", 
            "BuildingName": "",
            "SecondaryStreet": "",
            "Street": viacep_data.get('logradouro', ''),    
            "Block": "",
            "Neighbourhood": viacep_data.get('bairro', ''), 
            "District": viacep_data.get('bairro', ''),      
            "City": viacep_data.get('localidade', ''),      
            "Line1": viacep_data.get('logradouro', ''),     
            "Line2": "", 
            "Line3": viacep_data.get('bairro', ''),         
            "Line4": "",
            "Line5": "",
            "AdminAreaName": "",
            "AdminAreaCode": "",
            "Province": viacep_data.get('uf', ''),         
            "ProvinceName": "",
            "ProvinceCode": "",
            "PostalCode": clean_cep(viacep_data.get('cep', '')),
            "CountryName": "BR",
            "CountryIso2": "BR",
            "CountryIso3": "BR",
            "CountryIsoNumber": "",
            "SortingNumber1": "",
            "SortingNumber2": "",
            "Barcode": "",
            "POBoxNumber": "",
            "Label": "",
            "Type": "Residential", 
            "DataLevel": "Premise", 
            "Field1": "", "Field2": "", "Field3": "", "Field4": "", "Field5": "",
            "Field6": "", "Field7": "", "Field8": "", "Field9": "", "Field10": "",
            "Field11": "", "Field12": "", "Field13": "", "Field14": "", "Field15": "",
            "Field16": "", "Field17": "", "Field18": "", "Field19": "", "Field20": ""
        }

        response_data = {
            "Items": [opera_item]
        }
        return jsonify(response_data)

    except Exception as e:
        print(f"Erro geral no retrieve_address: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        # Garante que a conexão e o cursor sejam fechados
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    print("Iniciando servidor Flask...")
    print(f"Tentando conectar ao banco: {db_config['server']} / {db_config['database']}")
    print("ATENÇÃO: Certifique-se de ter executado o script SQL para criar a tabela 'dbo.windsor_cep'.")
    print("ATENÇÃO: Certifique-se de ter instalado 'pip install pyodbc' e o 'ODBC Driver' correto.")
    app.run(debug=True, port=5000)
