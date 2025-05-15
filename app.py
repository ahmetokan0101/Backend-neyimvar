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
        olası nedenleri ve önerileri sunacaksın. Aşağıdaki tüm başlıkların her birine mutlaka kapsamlı yanıt ver:
        
        1. Olası Nedenler: Belirtilen şikayetlere neden olabilecek sağlık sorunlarını listele.
        2. Öneriler: Şikayetleri hafifletmek için evde uygulanabilecek yöntemleri açıkla.
        3. Ne Zaman Doktora Gitmelisiniz: Hangi belirtiler görüldüğünde acilen tıbbi yardım alınması gerektiğini belirt.
        4. Hangi Branşa Gitmelisiniz: Bu şikayetler için hangi doktor branşına başvurulması gerektiğini söyle.
        5. Olası Teşhisler: Şikayetlere göre muhtemel tıbbi tanıları listele.
        6. İlgili Tetkikler: Doğru tanı için gerekebilecek laboratuvar testleri ve görüntüleme yöntemlerini belirt.
        7. Ortalama İyileşme Süresi: Belirtilen sorunun tedavi edilmezse ve tedavi edilirse beklenen iyileşme sürelerini açıkla.
        8. Sık Görülen Yan Etkiler: Tedavi sürecinde karşılaşılabilecek yan etki veya komplikasyonları açıkla.
        
        Tüm başlıklar için bilgi vermek zorunludur, hiçbir başlığı boş bırakma."""},
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
                "temperature": 0.1
            }
        )
        
        print(f"OpenRouter API response status: {response.status_code}")
        
        if response.status_code == 200:
            response_json = response.json()
            print(f"API response: {response_json}")
            
            # Yanıtta 'choices' anahtarı var mı kontrol et
            if 'choices' not in response_json or not response_json['choices']:
                print("API response does not contain 'choices' key or it's empty")
                return {"error": "API yanıtında beklenen format bulunamadı. Lütfen daha sonra tekrar deneyin."}
                
            # choices[0]['message']['content'] var mı kontrol et
            if 'message' not in response_json['choices'][0] or 'content' not in response_json['choices'][0]['message']:
                print("API response does not contain expected message content")
                return {"error": "API yanıtı beklenen içeriği sağlamadı. Lütfen daha sonra tekrar deneyin."}
                
            ai_response = response_json['choices'][0]['message']['content']
            
            # Yıldız (*) işaretlerini temizle
            ai_response = re.sub(r'\*+', '', ai_response)
            
            # Parse the AI response to extract structured information
            causes = ""
            recommendations = ""
            when_to_see_doctor = ""
            which_specialist = ""
            possible_diagnoses = ""
            related_tests = ""
            recovery_time = ""
            common_side_effects = ""
            
            # Daha güçlü regex pattern'ler ile ayrıştırma yaparak temiz sonuçlar elde et
            
            # Olası Nedenler kısmını ayıkla
            causes_match = re.search(r'(?:1\.[\s]*)?Olası Nedenler:(.+?)(?:(?:2\.[\s]*)?Öneriler:|$)', ai_response, re.DOTALL)
            
            # Öneriler kısmını ayıkla
            recommendations_match = re.search(r'(?:2\.[\s]*)?Öneriler:(.+?)(?:(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:|$)', ai_response, re.DOTALL)
            
            # Doktor tavsiyesi kısmını ayıkla
            doctor_match = re.search(r'(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:(.+?)(?:(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:|$)', ai_response, re.DOTALL)
            
            # Branş tavsiyesi kısmını ayıkla
            specialist_match = re.search(r'(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:(.+?)(?:(?:5\.[\s]*)?Olası Teşhisler:|$)', ai_response, re.DOTALL)
            
            # Olası Teşhisler kısmını ayıkla
            diagnoses_match = re.search(r'(?:5\.[\s]*)?Olası Teşhisler:(.+?)(?:(?:6\.[\s]*)?İlgili Tetkikler:|$)', ai_response, re.DOTALL)
            
            # İlgili Tetkikler kısmını ayıkla
            tests_match = re.search(r'(?:6\.[\s]*)?İlgili Tetkikler:(.+?)(?:(?:7\.[\s]*)?Ortalama İyileşme Süresi:|$)', ai_response, re.DOTALL)
            
            # Ortalama İyileşme Süresi kısmını ayıkla
            recovery_match = re.search(r'(?:7\.[\s]*)?Ortalama İyileşme Süresi:(.+?)(?:(?:8\.[\s]*)?Sık Görülen Yan Etkiler:|$)', ai_response, re.DOTALL)
            
            # Sık Görülen Yan Etkiler kısmını ayıkla
            side_effects_match = re.search(r'(?:8\.[\s]*)?Sık Görülen Yan Etkiler:(.+?)$', ai_response, re.DOTALL)
            
            # Yanıt verisini hazırla
            try:
                # Eğer API yanıtımız boşsa veya uygun formatta değilse
                if not ai_response or len(ai_response.strip()) < 20:
                    return {"error": "AI yanıtı çok kısa veya boş. Lütfen daha detaylı bir şikayet açıklaması yapınız."}
                
                # Tüm alanları varsayılan boş değerlerle başlat
                result = {
                    "causes": "",
                    "recommendations": "",
                    "when_to_see_doctor": "",
                    "which_specialist": "",
                    "possible_diagnoses": "",
                    "related_tests": "",
                    "recovery_time": "",
                    "common_side_effects": "",
                    "full_response": ai_response,
                    "corrected_query": corrected_query if corrected_query != query else None
                }
                
                # Regex pattern'leri ile ayıkla ve değerleri doldur
                if causes_match:
                    result["causes"] = causes_match.group(1).strip()
                if recommendations_match:
                    result["recommendations"] = recommendations_match.group(1).strip()
                if doctor_match:
                    result["when_to_see_doctor"] = doctor_match.group(1).strip()
                if specialist_match:
                    result["which_specialist"] = specialist_match.group(1).strip()
                if diagnoses_match:
                    result["possible_diagnoses"] = diagnoses_match.group(1).strip()
                if tests_match:
                    result["related_tests"] = tests_match.group(1).strip()
                if recovery_match:
                    result["recovery_time"] = recovery_match.group(1).strip()
                if side_effects_match:
                    result["common_side_effects"] = side_effects_match.group(1).strip()
                
                # Hiçbir alan doldurulmadıysa format sorununu belirt
                if not any([result["causes"], result["recommendations"], result["when_to_see_doctor"], result["which_specialist"]]):
                    return {"error": "AI yanıtı beklenen formatta değil. Lütfen daha sonra tekrar deneyin."}
                
                return result
            except Exception as parsing_error:
                print(f"Error while parsing AI response: {str(parsing_error)}")
                import traceback
                traceback.print_exc()
                return {
                    "error": "AI yanıtı işlenirken bir hata oluştu",
                    "full_response": ai_response
                }
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response content: {response.text}")
            # OpenRouter API başarısız olursa, alternatif API denemeyi ekleyelim
            try:
                print("Trying alternative API...")
                # Örnek olarak OpenAI API'yi deneyelim (gerçek uygulamada MODEL değişkenine göre seçilmeli)
                fallback_response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo", # Fallback model
                        "messages": messages,
                        "temperature": 0.1
                    }
                )
                
                if fallback_response.status_code == 200:
                    print("Alternative API successful")
                    # Burada fallback_response'u işleyip formatlayarak döndürmeliyiz
                    # (Format ayarlaması için ayrı bir fonksiyon yazılabilir)
                    response = fallback_response
                    # Tekrar işleme için response.status_code == 200 bloğuna git
                    ai_response = response.json()["choices"][0]["message"]["content"]
                    # Yıldız işaretlerini temizle ve devam et...
                    ai_response = re.sub(r'\*+', '', ai_response)
                    # ... (bundan sonrası ana işleme bloğu ile devam ediyor)
                    
                    # Değişkenleri tekrar başlat
                    causes = ""
                    recommendations = ""
                    when_to_see_doctor = ""
                    which_specialist = ""
                    possible_diagnoses = ""
                    related_tests = ""
                    recovery_time = ""
                    common_side_effects = ""
                    
                    # Regex pattern'leri tekrar çalıştır
                    causes_match = re.search(r'(?:1\.[\s]*)?Olası Nedenler:(.+?)(?:(?:2\.[\s]*)?Öneriler:|$)', ai_response, re.DOTALL)
                    recommendations_match = re.search(r'(?:2\.[\s]*)?Öneriler:(.+?)(?:(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:|$)', ai_response, re.DOTALL)
                    doctor_match = re.search(r'(?:3\.[\s]*)?Ne Zaman Doktora Gitmelisiniz:(.+?)(?:(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:|$)', ai_response, re.DOTALL)
                    specialist_match = re.search(r'(?:4\.[\s]*)?Hangi Branşa Gitmelisiniz:(.+?)(?:(?:5\.[\s]*)?Olası Teşhisler:|$)', ai_response, re.DOTALL)
                    diagnoses_match = re.search(r'(?:5\.[\s]*)?Olası Teşhisler:(.+?)(?:(?:6\.[\s]*)?İlgili Tetkikler:|$)', ai_response, re.DOTALL)
                    tests_match = re.search(r'(?:6\.[\s]*)?İlgili Tetkikler:(.+?)(?:(?:7\.[\s]*)?Ortalama İyileşme Süresi:|$)', ai_response, re.DOTALL)
                    recovery_match = re.search(r'(?:7\.[\s]*)?Ortalama İyileşme Süresi:(.+?)(?:(?:8\.[\s]*)?Sık Görülen Yan Etkiler:|$)', ai_response, re.DOTALL)
                    side_effects_match = re.search(r'(?:8\.[\s]*)?Sık Görülen Yan Etkiler:(.+?)$', ai_response, re.DOTALL)
                    
                    # Yanıt verisini hazırla - yukarıdaki try-except bloğundaki işlem aynı şekilde...
                    try:
                        # Eğer API yanıtımız boşsa veya uygun formatta değilse
                        if not ai_response or len(ai_response.strip()) < 20:
                            return {"error": "AI yanıtı çok kısa veya boş. Lütfen daha detaylı bir şikayet açıklaması yapınız."}
                        
                        # Tüm alanları varsayılan boş değerlerle başlat
                        result = {
                            "causes": "",
                            "recommendations": "",
                            "when_to_see_doctor": "",
                            "which_specialist": "",
                            "possible_diagnoses": "",
                            "related_tests": "",
                            "recovery_time": "",
                            "common_side_effects": "",
                            "full_response": ai_response,
                            "corrected_query": corrected_query if corrected_query != query else None
                        }
                        
                        # Regex pattern'leri ile ayıkla ve değerleri doldur
                        if causes_match:
                            result["causes"] = causes_match.group(1).strip()
                        if recommendations_match:
                            result["recommendations"] = recommendations_match.group(1).strip()
                        if doctor_match:
                            result["when_to_see_doctor"] = doctor_match.group(1).strip()
                        if specialist_match:
                            result["which_specialist"] = specialist_match.group(1).strip()
                        if diagnoses_match:
                            result["possible_diagnoses"] = diagnoses_match.group(1).strip()
                        if tests_match:
                            result["related_tests"] = tests_match.group(1).strip()
                        if recovery_match:
                            result["recovery_time"] = recovery_match.group(1).strip()
                        if side_effects_match:
                            result["common_side_effects"] = side_effects_match.group(1).strip()
                        
                        # Hiçbir alan doldurulmadıysa format sorununu belirt
                        if not any([result["causes"], result["recommendations"], result["when_to_see_doctor"], result["which_specialist"]]):
                            return {"error": "AI yanıtı beklenen formatta değil. Lütfen daha sonra tekrar deneyin."}
                        
                        return result
                    except Exception as parsing_error:
                        print(f"Error while parsing alternative API response: {str(parsing_error)}")
                        import traceback
                        traceback.print_exc()
                        return {
                            "error": "Alternatif API yanıtı işlenirken bir hata oluştu",
                            "full_response": ai_response
                        }
                else:
                    print(f"Alternative API also failed: {fallback_response.status_code}")
            except Exception as fallback_error:
                print(f"Error with alternative API: {str(fallback_error)}")
                
            return {"error": f"API Hatası: {response.status_code}", "details": response.text}
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        print(f"Exception type: {type(e)}")
        # Daha ayrıntılı hata bilgilerini göster
        import traceback
        traceback.print_exc()
        return {"error": f"Bağlantı hatası: {str(e)}. Lütfen daha sonra tekrar deneyin."}

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
