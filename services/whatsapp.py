import os, requests, json

def send_template_message(phone, template_id):
    url = "https://graph.facebook.com/v21.0/589214864273665/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_id, 
            "language": { 
                "code": "en_US" 
            }
        }
    })

    headers = {
        'Authorization': f'Bearer {os.environ.get("WHATSAPP_ACCESS_TOKEN")}',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)

def send_text_message(message, phone):
    url = "https://graph.facebook.com/v21.0/589214864273665/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": message
        }
    })
    headers = {
        'Authorization': f'Bearer {os.environ.get("WHATSAPP_ACCESS_TOKEN")}',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)


def send_media_message(link, caption, phone):
    url = "https://graph.facebook.com/v21.0/589214864273665/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "text": {
            "link": link,
            "caption": caption if caption is not None else ""
        }
    })
    headers = {
        'Authorization': f'Bearer {os.environ.get("WHATSAPP_ACCESS_TOKEN")}',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)


def upload_media_message(filename, filepath, phone):
    url = "https://graph.facebook.com/v21.0/589214864273665/media"
    file_path = os.path.join(os.getcwd(), "logo.png")
    
    with open(file_path, "rb") as file:
        files = {"file": ("logo.png", file, "image/png")}
        data = {"messaging_product": "whatsapp", "type": "image/png"}
        headers = {"Authorization": f'Bearer {os.environ.get("WHATSAPP_ACCESS_TOKEN")}'}
        
        response = requests.post(url, headers=headers, files=files, data=data)
    
    return response.json()