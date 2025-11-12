import requests
from flask import Flask, jsonify, request
import re  # <--- NOVO IMPORT

# 1. Inicializa o servidor Flask
app = Flask(__name__)


# --- FUNÇÃO HELPER (NOVA) ---
# Esta função checa de forma rápida se um CEP existe na BrasilAPI
# Usada pelo endpoint de "Busca"
def check_cep_exists(cep):
    """
    Faz uma chamada rápida (timeout curto) à BrasilAPI para 
    verificar se um CEP retorna status 200 (OK).
    """
    try:
        url = f"https://brasilapi.com.br/api/cep/v1/{cep}"
        # Timeout curto (2 segundos) pois é para sugestão "ao vivo"
        response = requests.get(url, timeout=2) 
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao checar CEP {cep}: {e}")
        return False # Falha seguro (assume que não existe se der erro)
# --- FIM DA FUNÇÃO HELPER ---


# 2. ENDPOINT DE "BUSCA" (Find)
# ------------------------------------
# (Esta função foi TOTALMENTE ATUALIZADA)
@app.route('/Capture/Interactive/Find/v1.00/json3.ws', methods=['GET'])
def find_address():
    query_text = request.args.get('Text', '').strip()
    
    # --- Lógica de Limpeza e Validação ---
    
    # 1. Pega a última "palavra" digitada.
    words = query_text.split(' ')
    cep_bruto = words[-1] if words else ''
    
    # 2. Limpa a "palavra", mantendo apenas dígitos (remove 'ABC', '-', '.')
    cep_limpo = re.sub(r'\D', '', cep_bruto)
    
    # 3. Verifica se o resultado limpo tem EXATAMENTE 8 dígitos
    if len(cep_limpo) == 8:
        
        # 4. VALIDA A EXISTÊNCIA do CEP (chamada externa)
        if check_cep_exists(cep_limpo):
            # SUCESSO: O CEP tem 8 dígitos E existe.
            suggestion_id = cep_limpo
            suggestion_text = f"Usar endereço com CEP: {suggestion_id}"
            suggestion_type = "Address" # Tipo padrão
            suggestion_desc = f"Clique para buscar o CEP {suggestion_id}"
        
        else:
            # ERRO: O CEP tem 8 dígitos mas NÃO FOI ENCONTRADO.
            suggestion_id = f"not_found_{cep_limpo}"
            suggestion_text = f"CEP {cep_limpo} não encontrado"
            suggestion_type = "Warning" # Um tipo diferente (informativo)
            suggestion_desc = "O CEP digitado não retornou resultados."
            
        # Monta a resposta que o Opera espera
        response_data = {
            "Items": [
                {
                    "Id": suggestion_id,
                    "Type": suggestion_type,
                    "Text": suggestion_text,
                    "Highlight": "",
                    "Description": suggestion_desc
                }
            ]
        }
        return jsonify(response_data)
    
    # Se não tiver 8 dígitos limpos, não é um CEP válido.
    # Retorna lista vazia (sem sugestões)
    return jsonify({"Items": []})


# 3. ENDPOINT DE "CAPTURA" (Retrieve)
# ------------------------------------
# (Esta seção inteira NÃO MUDA. A lógica de failover abaixo está correta)

# --- Provedor 1: BrasilAPI (PRIMÁRIO) ---
def try_brasilapi(cep):
    """Tenta buscar e mapear o CEP usando o BrasilAPI."""
    try:
        print(f"Tentando provedor: BrasilAPI (Primário) para o CEP {cep}")
        brasil_api_url = f"https://brasilapi.com.br/api/cep/v1/{cep}"
        brasil_response = requests.get(brasil_api_url, timeout=3)
        brasil_response.raise_for_status() 
        brasil_data = brasil_response.json()
        
        opera_item = {
            "Id": cep, "DomesticId": cep, "Language": "PT", "LanguageAlternatives": "PT",
            "Department": "", "Company": "", "SubBuilding": "", "BuildingNumber": "", 
            "BuildingName": "", "SecondaryStreet": "",
            "Street": brasil_data.get('street', ''),
            "Block": "",
            "Neighbourhood": brasil_data.get('neighborhood', ''),
            "District": brasil_data.get('neighborhood', ''),
            "City": brasil_data.get('city', ''),
            "Line1": brasil_data.get('street', ''),
            "Line2": "", "Line3": brasil_data.get('neighborhood', ''), "Line4": "", "Line5": "",
            "AdminAreaName": "", "AdminAreaCode": "",
            "Province": brasil_data.get('state', ''),
            "ProvinceName": "", "ProvinceCode": "",
            "PostalCode": brasil_data.get('cep', '').replace('-', ''),
            "CountryName": "BR", "CountryIso2": "BR", "CountryIso3": "BR",
            "CountryIsoNumber": "", "SortingNumber1": "", "SortingNumber2": "",
            "Barcode": "", "POBoxNumber": "", "Label": "",
            "Type": "Residential", "DataLevel": "Premise", 
            "Field1": "", "Field2": "", "Field3": "", "Field4": "", "Field5": "",
            "Field6": "", "Field7": "", "Field8": "", "Field9": "", "Field10": "",
            "Field11": "", "Field12": "", "Field13": "", "Field14": "", "Field15": "",
            "Field16": "", "Field17": "", "Field18": "", "Field19": "", "Field20": ""
        }
        print("Sucesso com BrasilAPI!")
        return opera_item

    except Exception as e:
        print(f"Falha no BrasilAPI: {e}")
        return None

# --- Provedor 2: ViaCEP (FALLBACK) ---
def try_viacep(cep):
    """Tenta buscar e mapear o CEP usando o ViaCEP."""
    try:
        print(f"Tentando provedor: ViaCEP (Fallback) para o CEP {cep}")
        viacep_url = f"https://viacep.com.br/ws/{cep}/json/"
        viacep_response = requests.get(viacep_url, timeout=3)
        viacep_response.raise_for_status()
        viacep_data = viacep_response.json()
        
        if viacep_data.get('erro'):
             print("ViaCEP retornou 'erro', CEP não encontrado.")
             return None 

        opera_item = {
            "Id": cep, "DomesticId": cep, "Language": "PT", "LanguageAlternatives": "PT",
            "Department": "", "Company": "", "SubBuilding": "", "BuildingNumber": "", 
            "BuildingName": "", "SecondaryStreet": "",
            "Street": viacep_data.get('logradouro', ''),
            "Block": "",
            "Neighbourhood": viacep_data.get('bairro', ''),
            "District": viacep_data.get('bairro', ''),
            "City": viacep_data.get('localidade', ''),
            "Line1": viacep_data.get('logradouro', ''),
            "Line2": "", "Line3": viacep_data.get('bairro', ''), "Line4": "", "Line5": "",
            "AdminAreaName": "", "AdminAreaCode": "",
            "Province": viacep_data.get('uf', ''),
            "ProvinceName": "", "ProvinceCode": "",
            "PostalCode": viacep_data.get('cep', '').replace('-', ''),
            "CountryName": "BR", "CountryIso2": "BR", "CountryIso3": "BR",
            "CountryIsoNumber": "", "SortingNumber1": "", "SortingNumber2": "",
            "Barcode": "", "POBoxNumber": "", "Label": "",
            "Type": "Residential", "DataLevel": "Premise", 
            "Field1": "", "Field2": "", "Field3": "", "Field4": "", "Field5": "",
            "Field6": "", "Field7": "", "Field8": "", "Field9": "", "Field10": "",
            "Field11": "", "Field12": "", "Field13": "", "Field14": "", "Field15": "",
            "Field16": "", "Field17": "", "Field18": "", "Field19": "", "Field20": ""
        }
        print("Sucesso com ViaCEP!")
        return opera_item

    except Exception as e:
        print(f"Falha no ViaCEP: {e}")
        return None


@app.route('/Capture/Interactive/Retrieve/v1.00/json3.ws', methods=['GET'])
def retrieve_address():
    address_id_cep = request.args.get('Id', '')
    
    # Se o usuário clicar em "CEP não encontrado", o ID começará com "not_found_"
    # e a busca de CEP falhará aqui, o que é o comportamento correto.
    if not address_id_cep or address_id_cep.startswith("not_found_"):
        print(f"Busca 'Retrieve' ignorada para ID inválido: {address_id_cep}")
        return jsonify({"Items": []})

    # Lógica de Failover (INALTERADA)
    providers = [
        try_brasilapi,  # Tenta este primeiro
        try_viacep      # Se o BrasilAPI falhar, tenta este
    ]

    opera_item = None
    for provider_func in providers:
        opera_item = provider_func(address_id_cep)
        if opera_item:
            break 

    if not opera_item:
        print(f"Todos os provedores falharam para o CEP {address_id_cep}")
        return jsonify({"Items": []})
    
    response_data = {
        "Items": [opera_item]
    }
    return jsonify(response_data)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
