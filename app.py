from googleapiclient.discovery import build
from google.oauth2 import service_account
import google.generativeai as genai
import gradio as gr 
from api_reader import GEMINI_API_KEY
from datetime import datetime, timedelta

genai.configure(api_key = GEMINI_API_KEY)
# Servis hesabı kimlik bilgileri
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'C:/Users/borak/Desktop/google-calendar-app/calendar-app-454821-13ba84191d91.json'
calendar_id = '2c383d5ffd75a2709410d955383c9c7b4fe3255638ee56a8528b7fe673ed63bb@group.calendar.google.com' ### calendarId: takvim entegrasyonu altındaki takvim kimliği

# Google Calendar API'ye bağlan
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

def format_tarih_zaman(user_input) : 

    prompt = f"""Sen bir tarih ve formatlama uzmanısın. Şuan 2025 yılındayız. Kullanıcının verdiği doğal dildeki tarih ve saat ifadelerini kesin bir şekilde ISO 8601 formatına çevir. Sadece tarih ve saat döndür , ekstra açıklama yapma. Kullanıcı bugün , yarın veya haftaya olacak şekilde etkinlik günü belirtirse timeZone olarak Europe/Istanbul'a göre etkinliği takvime ekle.

    Kullanıcı mesajı : {user_input}
    """

    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)

    return response.text.strip()

# Yeni bir etkinlik ekleme fonksiyonu
def add_event(event_name, user_input):
    event_time = format_tarih_zaman(user_input)

    # ISO 8601 formatında alınan tarihi datetime objesine çevir
    event_start = datetime.fromisoformat(event_time)

    ## bitis zamanını 1 saat ekleyerek oluştur
    event_end = event_start + timedelta(hours=1)

    event = {
        'summary': event_name,
        'start': {
            'dateTime': event_start.isoformat(),
            'timeZone': "Europe/Istanbul" ## Zaman dilimini ayarla
        },
        'end': {
            'dateTime': event_end.isoformat() ,
            'timeZone': "Europe/Istanbul"
        },
        # 'attendees': [{'email': email} for email in participants] ## katılımcı olacaksa etkinliğe katılımcı eklemek için
    }
    try:
        event = service.events().insert(calendarId = calendar_id, body=event).execute() 
        event_link = event.get('htmlLink')
        
        return f"✅ Etkinlik başarıyla oluşturuldu!\n🔗 [Etkinliği Google Takvim'de aç]({event_link})"
        # print(f"✅ Etkinlik oluşturuldu: {event.get('htmlLink')}")
    except Exception as e:
        return {"success": False, "message": f"❌ Hata oluştu: {str(e)}", "event_link": None}
        # print(f"❌ Hata oluştu: {str(e)}")

custom_css = """

h1 {
   text-align : center !important ; 
   font-weight : bold !important;
}

"""

with gr.Blocks(css = custom_css) as demo : 
    gr.HTML("<h1> 📅 Google Takvim Etkinlik Oluşturucu </h1>")
    with gr.Row() : 
        with gr.Column():
            etkinlik_ad = gr.Textbox(label = "Takvime Eklemek İstediğiniz Etkinlik" , placeholder= "Etkinlik Adı.")
            etkinlik_bilgi = gr.Textbox(label = "Etkinlik Tarihi ve Saati", placeholder= "Etkinlik Tarihi ve Saati.") 
            submit_btn = gr.Button("📌 Etkinliği Oluştur")
            clear_btn = gr.Button("Temizle")
        with gr.Column() : 
            output_text = gr.Textbox(label="output")
    submit_btn.click(
        add_event , ## function 
        [etkinlik_ad , etkinlik_bilgi], ## input
        [output_text]
    )

    clear_btn.click(
        lambda : (None , None , None) , 
        [] , 
        [etkinlik_ad , etkinlik_bilgi , output_text]
    )

if __name__ == "__main__" : 
    demo.launch(show_error = True)
