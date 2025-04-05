from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.generativeai as genai
import gradio as gr 
from api_reader import GEMINI_API_KEY
from datetime import datetime, timedelta
from agents import Agent, Runner
import asyncio

genai.configure(api_key=GEMINI_API_KEY)

# Servis hesabı kimlik bilgileri
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'C:/Users/borak/Desktop/google-calendar-app/calendar-app-454821-13ba84191d91.json'
calendar_id = '2c383d5ffd75a2709410d955383c9c7b4fe3255638ee56a8528b7fe673ed63bb@group.calendar.google.com'

# Etkinlik Agent'ı tanımlama
etkinlik_olusturucu_agent = Agent(
    name="Etkinlik Oluşturucu Agent",
    instructions="""
        Kullanıcıdan etkinlik adı, tarihi ve saatini al.
        Kullanıcının verdiği doğal dilde tarih ve saat ifadelerini kesin bir şekilde **sadece** ISO8601 formatına çevir.
        Ekstra açıklama yapma, sadece tarih ve saati yaz.
        Örnek çıktı: `2025-04-02T17:00:00`
    """,
    model="gpt-4o-mini"
)

etkinlik_silici_agent = Agent(
    name="Etkinlik Silici",
    instructions="""
    Kullanıcıdan silmek istediği etkinliğin adını veya tarihini iste.
    Etkinliği bulup silme işlemini gerçekleştir.
    """,
    model="gpt-4o-mini"
)

etkinlik_guncelle_agent = Agent(
    name="Etkinlik Güncelleyici",
    instructions="""
    Kullanıcıdan güncellemek istediği etkinliğin adını veya tarihini iste.
    Yeni bilgileri alıp etkinliği güncelle.
    """,
    model="gpt-4o-mini"
)

# Google Calendar API'ye bağlan
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

async def format_tarih_zaman(user_input):
    prompt = f"""
    Sen bir tarih ve saat formatlama uzmanısın. Şu an 2025 yılındayız. 
    Kullanıcının verdiği doğal dildeki tarih ve saat ifadelerini kesin bir şekilde **ISO 8601** formatına çevir. 
    Sadece **tarih ve saat döndür**, ekstra açıklama yapma.
    
    Kullanıcı 'bugün', 'yarın', 'haftaya' gibi ifadeler kullanırsa **Europe/Istanbul** saat dilimini referans al.

    Kullanıcı Mesajı: {user_input}
    """
    
    response = await Runner.run(etkinlik_olusturucu_agent, prompt)
    
    # Yanıtı temizle (Ters tırnak ve boşlukları kaldır)
    tarih_zaman = response.final_output.strip("` ").replace("\n", "")

    try:
        return datetime.fromisoformat(tarih_zaman)
    except ValueError as e:
        print(f"Hata: {e} - Yanıt: {tarih_zaman}")
        return None  # Hata durumunda None döndür


# Yeni bir etkinlik ekleme fonksiyonu
async def add_event(event_name, user_input):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    sonuc = await Runner.run(etkinlik_olusturucu_agent, f"{event_name} için {user_input} tarihinde bir etkinlik eklemek istiyorum.")
    event_time = sonuc.final_output

    event_start = datetime.fromisoformat(event_time)
    event_end = event_start + timedelta(hours=1)

    event = {
        'summary': event_name,
        'start': {
            'dateTime': event_start.isoformat(),
            'timeZone': "Europe/Istanbul"
        },
        'end': {
            'dateTime': event_end.isoformat(),
            'timeZone': "Europe/Istanbul"
        }
    }
    try:
        event = await asyncio.to_thread(service.events().insert(calendarId=calendar_id, body=event).execute)
        event_link = event.get('htmlLink')
        return f"✅ Etkinlik başarıyla oluşturuldu!\n🔗 [Etkinliği Google Takvim'de aç]({event_link})"
    except Exception as e:
        return f"❌ Hata oluştu: {str(e)}"

def temizle_ve_normalize(etkinlik_adi):
    """
    Etkinlik adını temizler: Boşlukları, büyük/küçük harf farklarını ve gereksiz karakterleri ortadan kaldırır.
    """
    # Boşlukları temizle
    etkinlik_adi = etkinlik_adi.strip()
    # Küçük harfe çevir
    etkinlik_adi = etkinlik_adi.lower()
    # Özel karakterleri temizleyebilirsiniz, örneğin noktalama işaretlerini
    # Burada sadece örnek olarak temizleme işlemi yapıyorum (özel gereksinime göre uyarlayabilirsiniz)
    etkinlik_adi = etkinlik_adi.replace("ı", "i").replace("ğ", "g").replace("ü" , "u").replace("ç" , "c").replace("ş" , "s").replace("ö" , "o") # Türkçe karakterler için çevrim tablosu
    return etkinlik_adi

async def delete_event(event_name):
    # Etkinlik adını normalize et
    etkinlik_adi = temizle_ve_normalize(event_name)

    # Google Calendar'dan etkinlikleri çek
    events_result = await asyncio.to_thread(service.events().list(calendarId=calendar_id).execute)
    events = events_result.get('items', [])

    if not events:
        return "❌ Google Calendar'dan etkinlik alınamadı."

    print("Google Calendar'dan alınan etkinlikler:")
    for event in events:
        event_name_raw = event.get('summary', '')
        event_name_normalized = temizle_ve_normalize(event_name_raw)
        print(f"Etkinlik ID: {event['id']}, Etkinlik Adı: {event_name_raw}, Başlangıç: {event.get('start', {}).get('dateTime', 'Tarih bilgisi yok')}")
        print(f"Karşılaştırma: {etkinlik_adi} == {event_name_normalized}")

        if etkinlik_adi == event_name_normalized:
            event_id = event['id']
            await asyncio.to_thread(service.events().delete(calendarId=calendar_id, eventId=event_id).execute)
            return f"✅ '{event_name_raw}' etkinliği başarıyla silindi."

    return f"❌ '{event_name}' adlı etkinlik bulunamadı."

# Gradio Arayüzü
custom_css = """
h1 {
   text-align: center !important;
   font-weight: bold !important;
}
"""

with gr.Blocks(css=custom_css) as demo:
    gr.HTML("<h1> 📅 Google Takvim Etkinlik Oluşturucu </h1>")
    with gr.Row():
        with gr.Column():
            etkinlik_ad = gr.Textbox(label="Takvime Eklemek İstediğiniz Etkinlik", placeholder="Etkinlik Adı.")
            etkinlik_bilgi = gr.Textbox(label="Etkinlik Tarihi ve Saati", placeholder="Etkinlik Tarihi ve Saati.")
            submit_btn = gr.Button("📌 Etkinliği Oluştur")
        with gr.Column():
            output_text = gr.Textbox(label="Etkinlik Ekleme Sonucu" , lines = 10)

    # Silme Arayüzü
    with gr.Row():
        with gr.Column():
            silinecek_etkinlik_ad = gr.Textbox(label="Silinecek Etkinlik Adı", placeholder="Etkinlik Adı.")
            delete_btn = gr.Button("🗑️ Etkinliği Sil")
            clear_btn = gr.Button("Temizle")
        with gr.Column():
            deletion_output = gr.Textbox(label = "Etkinlik Silme Sonucu", lines = 10)
    # # Güncelleme Arayüzü
    # with gr.Row():
    #     etkinlik_guncelle_ad = gr.Textbox(label="Güncellenecek Etkinlik Adı", placeholder="Mevcut Etkinlik Adı.")
    #     yeni_etkinlik_ad = gr.Textbox(label="Yeni Etkinlik Adı", placeholder="Yeni Etkinlik Adı.")
    #     yeni_etkinlik_bilgi = gr.Textbox(label="Yeni Etkinlik Tarihi ve Saati", placeholder="Yeni Tarih ve Saat.")
    #     update_btn = gr.Button("✏️ Etkinliği Güncelle")

    submit_btn.click(
        add_event,
        [etkinlik_ad, etkinlik_bilgi],
        [output_text]
    )

    delete_btn.click(
        delete_event , 
        [silinecek_etkinlik_ad] , 
        [deletion_output]
    )

    clear_btn.click(
        lambda: (None, None, None , None , None),
        [],
        [etkinlik_ad, etkinlik_bilgi, silinecek_etkinlik_ad , output_text , deletion_output]
    )

if __name__ == "__main__":
    demo.launch(show_error=True)
