import requests
import re
import time
import sys
import threading
import os

API_KEY = os.environ.get("API_KEY")
print("API_KEY loaded:", (API_KEY[:8] + "..." if API_KEY else "NOT FOUND"))
MODEL = "deepseek/deepseek-chat:free"

def loading_animation():
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while getattr(threading.current_thread(), "do_run", True):
        sys.stdout.write("\r" + "👨‍⚕️ İşlem yapılıyor... " + chars[i % len(chars)])
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1

def is_health_related(text):
    # Sağlıkla ilgili anahtar kelimeler
    health_keywords = [
        'ağrı', 'sancı', 'hasta', 'hastalık', 'rahatsızlık', 'şikayet', 'semptom',
        'ateş', 'öksürük', 'baş', 'mide', 'karın', 'göz', 'kulak', 'burun',
        'boğaz', 'sırt', 'bel', 'bacak', 'kol', 'eklem', 'kas', 'cilt',
        'uykusuzluk', 'yorgunluk', 'halsizlik', 'bulantı', 'kusma', 'ishal',
        'kabızlık', 'baş dönmesi', 'titreme', 'terleme', 'nefes', 'kalp',
        'tansiyon', 'şeker', 'stres', 'alerji', 'astım', 'grip', 'nezle', 'soğuk algınlığı'
    ]
    
    # Sağlık dışı konular
    non_health_topics = [
        'xampp', 'program', 'yazılım', 'kod', 'bilgisayar', 'internet', 'web',
        'site', 'uygulama', 'app', 'software', 'hardware', 'donanım', 'yazılım',
        'windows', 'linux', 'mac', 'android', 'ios', 'telefon', 'tablet', 'laptop'
    ]
    
    text = text.lower()
    
    # Önce sağlık dışı konuları kontrol et
    if any(topic in text for topic in non_health_topics):
        return False
        
    # Sonra sağlık kelimelerini kontrol et
    return any(keyword in text for keyword in health_keywords)

def correct_turkish_text(text):
    """Türkçe metindeki sağlık şikayetleri için yazım hatalarını kural tabanlı olarak düzeltir."""
    print("\n🔍 Metin düzeltiliyor...")
    
    # Sağlık terimlerinin kök kelime ve ekler için düzeltme sözlüğü
    roots = {
        # Vücut bölgeleri
        'karn': 'karın',      # karın bölgesi
        'kar': 'karın',        # karın kısaltması
        'bas': 'baş',         # baş bölgesi
        'mide': 'mide',       # mide 
        'sirt': 'sırt',       # sırt
        'bel': 'bel',         # bel
        'goz': 'göz',         # göz
        'kol': 'kol',         # kol
        'bacak': 'bacak',     # bacak
        'bogaz': 'boğaz',     # boğaz
        
        # Belirtiler
        'agr': 'ağr',         # ağrı, ağrıyor vb.
        'sanc': 'sancı',      # sancı, sancılar vb.
        'ates': 'ateş',       # ateş, ateşli vb.
        'oksur': 'öksür',     # öksürük, öksürme vb.
        'öksur': 'öksür',     
        'bulan': 'bulan',     # bulantı vb.
        'ishal': 'ishal',     # ishal
        'kabiz': 'kabız',     # kabızlık vb.
        'donme': 'dönme',     # baş dönmesi
    }
    
    # Özel kelime tamlamaları ve birleşik terimler
    special_phrases = {
        'bas agrisi': 'baş ağrısı',
        'bas agrim': 'baş ağrım',
        'bas donmesi': 'baş dönmesi',
        'bas dönmesi': 'baş dönmesi',
        'bas donmsi': 'baş dönmesi',
        'karin agrisi': 'karın ağrısı',
        'karin agrim': 'karın ağrım',
        'karnm agriyor': 'karnım ağrıyor',
        'midem bulan': 'midem bulan',
        'sirt agrim': 'sırt ağrım',
        'sırt agrım': 'sırt ağrım'
    }
    
    # Tam kelime eşleşmesi için düzeltmeler
    exact_corrections = {
        'cok': 'çok',
        'hic': 'hiç',
        'karnm': 'karnım',
        'basim': 'başım',
        'sirtim': 'sırtım',
        'belm': 'belim',
        'bacagm': 'bacağım',
        'agrı': 'ağrı',
        'agrım': 'ağrım',
        'agrıyor': 'ağrıyor',
        'agrısı': 'ağrısı',
        'sanci': 'sancı',
        'sancilar': 'sancılar',
        'sanclarm': 'sancılarım',
        'sanclarim': 'sancılarım',
        'oksuruk': 'öksürük',
        'öksuruk': 'öksürük',
        'bulanti': 'bulantı',
        'kabizlik': 'kabızlık',
        'karinda': 'karında'
    }
    
    # Doğru kelime, yanlışlıkla değişebilecek kelimeler ve hatalı düzeltmeleri engelleme
    preserve_words = {
        'karı': 'karı',  # eş anlamında karı, karın ile karıştırılmamalı
        'karım': 'karım'  # eş anlamında karım, karnım ile karıştırılmamalı
    }
    
    # Birleşik yazılan kelimeleri ayırma
    # Örn: "karnımağrıyor" -> "karnım ağrıyor"
    for root1, correct1 in roots.items():
        for root2, correct2 in roots.items():
            pattern = f"({root1}[a-zçğıöşü]*)({root2}[a-zçğıöşü]*)"
            text = re.sub(pattern, r'\1 \2', text, flags=re.IGNORECASE)
    
    # Metni kelimelerine ayır
    words = re.findall(r'\b\w+\b|[,.;:!?]', text)
    
    # Her kelimeyi kontrol et ve düzelt
    corrected_words = []
    i = 0
    while i < len(words):
        # Özel kelime tamlamaları için
        if i < len(words) - 1:
            two_word_phrase = (words[i] + " " + words[i+1]).lower()
            if two_word_phrase in special_phrases:
                corrected_words.append(special_phrases[two_word_phrase])
                i += 2
                continue
        
        current_word = words[i].lower()
        
        # Korunması gereken kelimeler
        if current_word in preserve_words:
            corrected_words.append(words[i])
            i += 1
            continue
        
        # Tam kelime düzeltmeleri
        if current_word in exact_corrections:
            # Büyük/küçük harf durumunu koru
            if words[i].isupper():
                corrected_words.append(exact_corrections[current_word].upper())
            elif words[i][0].isupper():
                corrected_words.append(exact_corrections[current_word].capitalize())
            else:
                corrected_words.append(exact_corrections[current_word])
            i += 1
            continue
        
        # Kök tabanlı düzeltme
        word_corrected = False
        for root, correct_root in roots.items():
            if current_word.startswith(root):
                # Kökü düzelt, kalan ekleri koru
                suffix = current_word[len(root):]
                corrected_root = correct_root
                corrected_word = corrected_root + suffix
                
                # Büyük/küçük harf durumunu koru
                if words[i].isupper():
                    corrected_word = corrected_word.upper()
                elif words[i][0].isupper():
                    corrected_word = corrected_word.capitalize()
                
                corrected_words.append(corrected_word)
                word_corrected = True
                break
        
        # Eğer düzeltme yapılmadıysa, kelimeyi olduğu gibi ekle
        if not word_corrected:
            corrected_words.append(words[i])
        
        i += 1
    
    # Noktalama işaretleri için boşluk düzeltmeleri
    corrected_text = ' '.join(corrected_words)
    
    # Noktalama işaretleri öncesi fazla boşlukları kaldır
    corrected_text = re.sub(r'\s+([,.;:!?])', r'\1', corrected_text)
    
    # Birden fazla boşluğu tek boşluğa indirge
    corrected_text = re.sub(r'\s+', ' ', corrected_text).strip()
    
    return corrected_text

def health_chat_assistant():
    print("🏥 Neyim Var? - Sağlık Asistanı")
    print("Çıkmak için 'exit' yazın")
    print("\n💡 Yazım hatalarını otomatik düzeltme özelliği aktif!")
    print("Örnek: 'Karnım agrıyor cok' → 'Karnım ağrıyor çok'")
    
    messages_history = [
        {"role": "system", "content": """Sen bir sağlık asistanısın. Kullanıcının sağlık şikayetlerini dinleyip, 
        olası nedenleri ve önerileri sunacaksın. Her zaman şu formatta yanıt ver:
        1. Olası Nedenler:
        2. Öneriler:
        3. Ne Zaman Doktora Gitmelisiniz:
        
        ÖNEMLİ: Bu bilgiler sadece bilgilendirme amaçlıdır ve kesinlikle tıbbi tavsiye değildir. 
        Ciddi durumlarda mutlaka bir doktora başvurun."""}
    ]
    
    while True:
        user_input = input("\n👤 Şikayetinizi yazın: ")
        
        if user_input.lower() in ["exit", "çık", "quit"]:
            print("Geçmiş olsun! Sağlıklı günler dilerim! 👋")
            break
        
        if not user_input.strip():
            print("\n⚠️ Lütfen şikayetinizi yazın.")
            continue
        
        # Yükleniyor animasyonunu başlat
        loading_thread = threading.Thread(target=loading_animation)
        loading_thread.start()
        
        # Türkçe düzeltme işlemi
        corrected_input = correct_turkish_text(user_input)
        
        # Yükleniyor animasyonunu durdur
        loading_thread.do_run = False
        loading_thread.join()
        sys.stdout.write("\r" + " " * 50 + "\r")  # Yükleniyor yazısını temizle
        
        # Eğer düzeltme yapıldıysa kullanıcıya bildir
        if corrected_input.lower() != user_input.lower():
            print(f"\n✅ Düzeltilmiş şikayetiniz: \"{corrected_input}\"")
        else:
            print(f"\n✓ Şikayetiniz: \"{corrected_input}\"")
            
        # Sağlıkla ilgili olup olmadığını DÜZELTILMIŞ metin üzerinde kontrol et
        if not is_health_related(corrected_input):
            print("\n⚠️ Bu uygulama sadece sağlık şikayetleri için tasarlanmıştır.")
            print("Lütfen sağlıkla ilgili bir şikayet veya soru yazın.")
            continue
            
        messages_history.append({"role": "user", "content": corrected_input})
        
        try:
            # Yükleniyor animasyonunu başlat
            loading_thread = threading.Thread(target=loading_animation)
            loading_thread.start()
            
            print("\n🔍 Şikayetiniz analiz ediliyor...")
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": messages_history,
                    "temperature": 0.3
                }
            )
            
            # Yükleniyor animasyonunu durdur
            loading_thread.do_run = False
            loading_thread.join()
            sys.stdout.write("\r" + " " * 50 + "\r")  # Yükleniyor yazısını temizle
            
            if response.status_code == 200:
                ai_response = response.json()["choices"][0]["message"]["content"]
                print(f"\n👨‍⚕️ Analiz Sonucu:\n{ai_response}")
                messages_history.append({"role": "assistant", "content": ai_response})
            else:
                print(f"\n🚨 API Hatası {response.status_code}: {response.text}")
                
        except Exception as e:
            # Hata durumunda yükleniyor animasyonunu durdur
            if 'loading_thread' in locals():
                loading_thread.do_run = False
                loading_thread.join()
            sys.stdout.write("\r" + " " * 50 + "\r")  # Yükleniyor yazısını temizle
            print(f"\n⚠️ Bağlantı hatası: {str(e)}")
            print("Lütfen internet bağlantınızı kontrol edin ve tekrar deneyin.")

if __name__ == "__main__":
    health_chat_assistant()
