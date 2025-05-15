from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import threading
import time
import requests
import os

# Import our health assistant logic
from de import API_KEY, MODEL, is_health_related, correct_turkish_text

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def analyze_health_query(query, should_correct=True):
    """Process a health query using the deepseek model"""
    print(f"Received query: {query}")
    
    # Only correct the text if requested
    corrected_query = query
    if should_correct:
        print(f"Correcting text: {query}")
        corrected_query = correct_turkish_text(query)
        if corrected_query != query:
            print(f"Corrected query: {corrected_query}")
    else:
        print("Text correction skipped as per user request")
    
    # Check if health related after correction
    if not is_health_related(corrected_query):
        return {"error": "Lütfen sağlığınızla ilgili şikayetlerinizi detaylı ve düzgün kelimelerle belirtiniz. Sistem sadece sağlık şikayetlerini analiz edebilmektedir."}
    
    messages = [
        {"role": "system", "content": """Sen bir sağlık asistanısın. Kullanıcının sağlık şikayetlerini dinleyip, 
        olası nedenleri ve önerileri sunacaksın. Her zaman şu formatta yanıt ver:
        1. Olası Nedenler:
        2. Öneriler:
        3. Ne Zaman Doktora Gitmelisiniz:
        4. Hangi Branşa Gitmelisiniz:"""},
        {"role": "user", "content": corrected_query}
    ]
    
    try:
        print("Sending request to OpenRouter API...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.3
            }
        )
        
        print(f"OpenRouter API response status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                response_json = response.json()
                # API yanıtını kontrol et ve hata ayıklama bilgisini yazdır
                print(f"API response content: {response_json}")
                
                # 'choices' anahtarının var olup olmadığını kontrol et
                if 'choices' not in response_json or not response_json['choices']:
                    print("Error: 'choices' key not found in API response")
                    return {"error": "API yanıtı beklenmeyen formatta. Lütfen daha sonra tekrar deneyin."}
                
                if len(response_json["choices"]) == 0:
                    print("Error: 'choices' array is empty")
                    return {"error": "API yanıtı boş döndü. Lütfen daha sonra tekrar deneyin."}
                
                if "message" not in response_json["choices"][0]:
                    print("Error: 'message' key not found in choices[0]")
                    return {"error": "API yanıtı geçersiz formatta. Lütfen daha sonra tekrar deneyin."}
                
                if "content" not in response_json["choices"][0]["message"]:
                    print("Error: 'content' key not found in choices[0]['message']")
                    return {"error": "API yanıtı geçersiz formatta. Lütfen daha sonra tekrar deneyin."}
                
                ai_response = response_json["choices"][0]["message"]["content"]
                
                # Yıldız (*) işaretlerini temizle
                ai_response = re.sub(r'\*+', '', ai_response)
                
                # Parse the AI response to extract structured information
                causes = ""
                recommendations = ""
                when_to_see_doctor = ""
                which_specialist = ""
                
                # Daha güçlü regex pattern'ler ile ayrıştırma yaparak temiz sonuçlar elde et
                
                # Olası Nedenler kısmını ayıkla
                causes_match = re.search(r'(?:1\.[\s]*)?Olası Nedenler:(.+?)(?:(?:2\.[\s]*)?Öneriler:|$)', ai_response, re.DOTALL)
                
                # Öneriler kısmını ayıkla
                recommendations_match = re.search(r'(?:2\.[\s]*)?Öneriler:(.+?)(?:(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:|$)', ai_response, re.DOTALL)
                
                # Doktor tavsiyesi kısmını ayıkla
                doctor_match = re.search(r'(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:(.+?)(?:(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:|$)', ai_response, re.DOTALL)
                
                # Branş tavsiyesi kısmını ayıkla
                specialist_match = re.search(r'(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:(.+?)$', ai_response, re.DOTALL)
                
                if causes_match:
                    causes = causes_match.group(1).strip()
                if recommendations_match:
                    recommendations = recommendations_match.group(1).strip()
                if doctor_match:
                    when_to_see_doctor = doctor_match.group(1).strip()
                if specialist_match:
                    which_specialist = specialist_match.group(1).strip()
                
                # Yanıt verisini hazırla
                return {
                    "causes": causes,
                    "recommendations": recommendations,
                    "when_to_see_doctor": when_to_see_doctor,
                    "which_specialist": which_specialist,
                    "full_response": ai_response,
                    "corrected_query": corrected_query if corrected_query != query else None
                }
            except Exception as e:
                print(f"Error parsing API response: {str(e)}")
                return {"error": "API yanıtının işlenmesi sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin."}
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response content: {response.text}")
            return {"error": f"API Hatası: {response.status_code}", "details": response.text}
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {"error": f"Bağlantı hatası: {str(e)}"}

@app.route('/api/health', methods=['POST'])
def health_analysis():
    try:
        print("Received request:", request.data)
        data = request.json
        if not data:
            print("No JSON data found in request")
            return jsonify({"error": "Geçersiz istek formatı"}), 200
        
        if 'symptoms' not in data:
            print("No 'symptoms' key in request JSON")
            return jsonify({"error": "Semptom bilgisi gerekli"}), 200
        
        symptoms = data['symptoms']
        should_correct = data.get('should_correct', True)  # Varsayılan olarak düzeltme yap
        
        print(f"Processing symptoms: {symptoms}")
        print(f"Should correct text: {should_correct}")
        
        result = analyze_health_query(symptoms, should_correct)
        
        # Always return 200 status code, even if there's an error
        return jsonify(result), 200
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Sunucu hatası: {str(e)}"}), 200

@app.route('/')
def home():
    return "Neyim Var API is running!"

if __name__ == '__main__':
    # Lokalde çalıştığınızda
    # app.run(host='0.0.0.0', port=5000, debug=True)
    # Render.com'da çalıştığınızda:
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port) 
