import requests
from flask import Flask, jsonify, request

# 1. Inicializa o servidor Flask
app = Flask(__name__)


# 2. ENDPOINT DE "BUSCA" (Find)
# ------------------------------------
# (Esta função não precisa de alteração)
@app.route('/Capture/Interactive/Find/v1.00/json3.ws', methods=['GET'])
def find_address():
    query_text = request.args.get('Text', '').strip()
    words = query_text.split(' ')
    cep = words[-1] if words else ''
    cep = cep.replace('-', '')
    
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


# 3. ENDPOINT DE "CAPTURA" (Retrieve)
# ------------------------------------

# --- Provedor 1: BrasilAPI (AGORA É O PRIMÁRIO) ---
def try_brasilapi(cep):
    """Tenta buscar e mapear o CEP usando o BrasilAPI."""
    try:
        print(f"Tentando provedor: BrasilAPI (Primário) para o CEP {cep}")
        brasil_api_url = f"https://brasilapi.com.br/api/cep/v1/{cep}"
        brasil_response = requests.get(brasil_api_url, timeout=3)
        brasil_response.raise_for_status() # Verifica erros (ex: 404 se CEP não existe)
        brasil_data = brasil_response.json()
        
        # --- Mapeamento (DE/PARA) BrasilAPI -> Opera ---
        opera_item = {
            "Id": cep, "DomesticId": cep, "Language": "PT", "LanguageAlternatives": "PT",
            "Department": "", "Company": "", "SubBuilding": "", "BuildingNumber": "", 
            "BuildingName": "", "SecondaryStreet": "",
            "Street": brasil_data.get('street', ''),          # DE: street
            "Block": "",
            "Neighbourhood": brasil_data.get('neighborhood', ''), # DE: neighborhood
            "District": brasil_data.get('neighborhood', ''),      # DE: neighborhood
            "City": brasil_data.get('city', ''),              # DE: city
            "Line1": brasil_data.get('street', ''),
            "Line2": "", "Line3": brasil_data.get('neighborhood', ''), "Line4": "", "Line5": "",
            "AdminAreaName": "", "AdminAreaCode": "",
            "Province": brasil_data.get('state', ''),         # DE: state (UF)
            "ProvinceName": "", "ProvinceCode": "",
            "PostalCode": brasil_data.get('cep', '').replace('-', ''), # DE: cep
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
        return None # Retorna None em caso de falha

# --- Provedor 2: ViaCEP (AGORA É O FALLBACK) ---
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

        # --- Mapeamento (DE/PARA) ViaCEP -> Opera ---
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
    if not address_id_cep:
        return jsonify({"Items": []})

    # <--- LÓGICA DE FAILOVER ATUALIZADA --->
    # Lista de funções (provedores) para tentar em ordem
    providers = [
        try_brasilapi,  # Tenta este primeiro
        try_viacep      # Se o BrasilAPI falhar, tenta este
    ]

    opera_item = None
    for provider_func in providers:
        opera_item = provider_func(address_id_cep)
        if opera_item:
            break # Se um provedor for bem-sucedido, para o loop

    # Se, após todas as tentativas, o opera_item ainda for None, retorna lista vazia
    if not opera_item:
        print(f"Todos os provedores falharam para o CEP {address_id_cep}")
        return jsonify({"Items": []})
    
    # Monta a resposta final que o Opera espera
    response_data = {
        "Items": [opera_item]
    }
    return jsonify(response_data)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
