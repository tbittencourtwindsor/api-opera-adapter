import requests
from flask import Flask, jsonify, request

# 1. Inicializa o servidor Flask
app = Flask(__name__)


# 2. ENDPOINT DE "BUSCA" (Find)
# ------------------------------------
# O Opera chama este endpoint primeiro para pegar sugestões
@app.route('/Capture/Interactive/Find/v1.00/json3.ws', methods=['GET'])
def find_address():
    # Pega o texto que o usuário digitou (ex: "Rua X... 90210000")
    query_text = request.args.get('Text', '')
    
    # Pega a última "palavra" do texto, assumindo que é o CEP
    words = query_text.split(' ')
    cep = words[-1] if words else ''
    cep = cep.replace('-', '') # Limpa o CEP
    
    # Só vamos retornar uma sugestão se o CEP parecer válido
    if len(cep) >= 8:
        # IMPORTANTE: Vamos usar o próprio CEP como "Id"
        # Isso simplifica o próximo passo (Retrieve)
        suggestion_id = cep
        
        # O "Text" é o que o usuário vai ver na lista de sugestões
        suggestion_text = f"Usar endereço com CEP: {suggestion_id}"
        
        # Monta a resposta que o Opera espera
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
    
    # Se não encontrar ou o CEP for curto, retorna lista vazia
    return jsonify({"Items": []})


# 3. ENDPOINT DE "CAPTURA" (Retrieve)
# ------------------------------------
# O Opera chama este endpoint após o usuário clicar na sugestão
@app.route('/Capture/Interactive/Retrieve/v1.00/json3.ws', methods=['GET'])
def retrieve_address():
    # Pega o "Id" que enviamos no passo anterior (que é o CEP)
    address_id_cep = request.args.get('Id', '')

    if not address_id_cep:
        return jsonify({"Items": []})

    # --- Chamada à API externa (ViaCEP) ---
    try:
        viacep_url = f"https://viacep.com.br/ws/{address_id_cep}/json/"
        viacep_response = requests.get(viacep_url)
        viacep_data = viacep_response.json()
        
        if viacep_data.get('erro'):
             return jsonify({"Items": []}) # CEP não encontrado no ViaCEP

    except Exception as e:
        print(f"Erro ao chamar ViaCEP: {e}")
        return jsonify({"Items": []})
    
    # --- Mapeamento (DE/PARA) ViaCEP -> Opera ---
    # Esta é a parte mais CRÍTICA.
    # Estamos traduzindo a resposta do ViaCEP para o formato do Opera.
    
    opera_item = {
        "Id": address_id_cep,
        "DomesticId": address_id_cep,
        "Language": "PT",
        "LanguageAlternatives": "PT",
        "Department": "",
        "Company": "",
        "SubBuilding": "",
        "BuildingNumber": "", # ViaCEP não informa o número
        "BuildingName": "",
        "SecondaryStreet": "",
        "Street": viacep_data.get('logradouro', ''),    # DE: logradouro
        "Block": "",
        "Neighbourhood": viacep_data.get('bairro', ''), # DE: bairro
        "District": viacep_data.get('bairro', ''),      # DE: bairro (pode repetir)
        "City": viacep_data.get('localidade', ''),      # DE: localidade
        "Line1": viacep_data.get('logradouro', ''),     # DE: logradouro
        "Line2": viacep_data.get('complemento', ''),   # DE: complemento
        "Line3": "",
        "Line4": viacep_data.get('bairro', ''),         # DE: bairro
        "Line5": "",
        "AdminAreaName": "",
        "AdminAreaCode": "",
        "Province": viacep_data.get('uf', ''),         # DE: uf (Estado)
        "ProvinceName": "",
        "ProvinceCode": "",
        "PostalCode": viacep_data.get('cep', '').replace('-', ''), # DE: cep
        "CountryName": "BR",
        "CountryIso2": "BR",
        "CountryIso3": "BR",
        "CountryIsoNumber": "",
        "SortingNumber1": "",
        "SortingNumber2": "",
        "Barcode": "",
        "POBoxNumber": "",
        "Label": "",
        "Type": "Residential", # Pode ser fixo
        "DataLevel": "Premise", # Pode ser fixo
        "Field1": "", "Field2": "", "Field3": "", "Field4": "", "Field5": "",
        "Field6": "", "Field7": "", "Field8": "", "Field9": "", "Field10": "",
        "Field11": "", "Field12": "", "Field13": "", "Field14": "", "Field15": "",
        "Field16": "", "Field17": "", "Field18": "", "Field19": "", "Field20": ""
    }

    # Monta a resposta final que o Opera espera
    response_data = {
        "Items": [opera_item]
    }

    return jsonify(response_data)


# 4. (Opcional) Linha para Teste Local
# ------------------------------------
# Isso permite rodar o servidor na sua própria máquina para testar
if __name__ == '__main__':
    # Roda o servidor na porta 5000 (ex: http://127.0.0.1:5000)
    app.run(debug=True, port=5000)