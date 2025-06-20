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
        4. Hangi Branşa Gitmelisiniz:
        5. Acil Servise Gitmem Gerekir mi?:
        6. Evde Nelere Dikkat Etmeliyim?:
        7. Ne Kadar Sürede Geçmeli?:
        8. Bu Belirtiler Stres Kaynaklı Olabilir mi?:
        9. Bu Belirtiler Hangi Hastalıklarla Karıştırılabilir?:
        10. Bu Belirtiler Ciddi mi?:
        11. Bu Durumda İlaç Kullanmalı mıyım?:
        12. Bu Durum Bulaşıcı mı?:"""},
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
            },
            timeout=60  # 60 saniye bekle
        )
        
        print(f"OpenRouter API response status: {response.status_code}")
        
        if response.status_code == 200:
            ai_response = response.json()["choices"][0]["message"]["content"]
            
            # Yıldız (*) işaretlerini temizle
            ai_response = re.sub(r'\*+', '', ai_response)
            
            # Parse the AI response to extract structured information
            causes = ""
            recommendations = ""
            when_to_see_doctor = ""
            which_specialist = ""
            emergency_visit = ""
            home_care = ""
            duration = ""
            stress_related = ""
            similar_conditions = ""
            severity = ""
            medication = ""
            contagious = ""
            
            # Daha güçlü regex pattern'ler ile ayrıştırma yaparak temiz sonuçlar elde et
            
            # Olası Nedenler kısmını ayıkla
            causes_match = re.search(r'(?:1\.[\s]*)?Olası Nedenler:(.+?)(?:(?:2\.[\s]*)?Öneriler:|$)', ai_response, re.DOTALL)
            
            # Öneriler kısmını ayıkla
            recommendations_match = re.search(r'(?:2\.[\s]*)?Öneriler:(.+?)(?:(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:|$)', ai_response, re.DOTALL)
            
            # Doktor tavsiyesi kısmını ayıkla
            doctor_match = re.search(r'(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:(.+?)(?:(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:|$)', ai_response, re.DOTALL)
            
            # Branş tavsiyesi kısmını ayıkla
            specialist_match = re.search(r'(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:(.+?)(?:(?:5\.[\s]*)?Acil Servise Gitmem Gerekir mi\?:|$)', ai_response, re.DOTALL)
            
            # Acil servis kısmını ayıkla
            emergency_match = re.search(r'(?:5\.[\s]*)?Acil Servise Gitmem Gerekir mi\?:(.+?)(?:(?:6\.[\s]*)?Evde Nelere Dikkat Etmeliyim\?:|$)', ai_response, re.DOTALL)
            
            # Evde dikkat edilecekler kısmını ayıkla
            home_care_match = re.search(r'(?:6\.[\s]*)?Evde Nelere Dikkat Etmeliyim\?:(.+?)(?:(?:7\.[\s]*)?Ne Kadar Sürede Geçmeli\?:|$)', ai_response, re.DOTALL)
            
            # Süre kısmını ayıkla
            duration_match = re.search(r'(?:7\.[\s]*)?Ne Kadar Sürede Geçmeli\?:(.+?)(?:(?:8\.[\s]*)?Bu Belirtiler Stres Kaynaklı Olabilir mi\?:|$)', ai_response, re.DOTALL)
            
            # Stres kaynaklı kısmını ayıkla
            stress_match = re.search(r'(?:8\.[\s]*)?Bu Belirtiler Stres Kaynaklı Olabilir mi\?:(.+?)(?:(?:9\.[\s]*)?Bu Belirtiler Hangi Hastalıklarla Karıştırılabilir\?:|$)', ai_response, re.DOTALL)
            
            # Benzer hastalıklar kısmını ayıkla
            similar_match = re.search(r'(?:9\.[\s]*)?Bu Belirtiler Hangi Hastalıklarla Karıştırılabilir\?:(.+?)(?:(?:10\.[\s]*)?Bu Belirtiler Ciddi mi\?:|$)', ai_response, re.DOTALL)
            
            # Ciddiyet kısmını ayıkla
            severity_match = re.search(r'(?:10\.[\s]*)?Bu Belirtiler Ciddi mi\?:(.+?)(?:(?:11\.[\s]*)?Bu Durumda İlaç Kullanmalı mıyım\?:|$)', ai_response, re.DOTALL)
            
            # İlaç kullanımı kısmını ayıkla
            medication_match = re.search(r'(?:11\.[\s]*)?Bu Durumda İlaç Kullanmalı mıyım\?:(.+?)(?:(?:12\.[\s]*)?Bu Durum Bulaşıcı mı\?:|$)', ai_response, re.DOTALL)
            
            # Bulaşıcılık kısmını ayıkla
            contagious_match = re.search(r'(?:12\.[\s]*)?Bu Durum Bulaşıcı mı\?:(.+?)$', ai_response, re.DOTALL)
            
            if causes_match:
                causes = causes_match.group(1).strip()
            if recommendations_match:
                recommendations = recommendations_match.group(1).strip()
            if doctor_match:
                when_to_see_doctor = doctor_match.group(1).strip()
            if specialist_match:
                which_specialist = specialist_match.group(1).strip()
            if emergency_match:
                emergency_visit = emergency_match.group(1).strip()
            if home_care_match:
                home_care = home_care_match.group(1).strip()
            if duration_match:
                duration = duration_match.group(1).strip()
            if stress_match:
                stress_related = stress_match.group(1).strip()
            if similar_match:
                similar_conditions = similar_match.group(1).strip()
            if severity_match:
                severity = severity_match.group(1).strip()
            if medication_match:
                medication = medication_match.group(1).strip()
            if contagious_match:
                contagious = contagious_match.group(1).strip()
            
            # Yanıt verisini hazırla
            return {
                "causes": causes,
                "recommendations": recommendations,
                "when_to_see_doctor": when_to_see_doctor,
                "which_specialist": which_specialist,
                "emergency_visit": emergency_visit,
                "home_care": home_care,
                "duration": duration,
                "stress_related": stress_related,
                "similar_conditions": similar_conditions,
                "severity": severity,
                "medication": medication,
                "contagious": contagious,
                "full_response": ai_response,
                "corrected_query": corrected_query if corrected_query != query else None
            }
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response content: {response.text}")
            return {"error": f"API Hatası: {response.status_code}", "details": response.text}
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
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
