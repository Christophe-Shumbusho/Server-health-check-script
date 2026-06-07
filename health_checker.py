import json
import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def load_servers():

    try:
        with open('config.json', 'r') as file:
           data = json.load(file)
           server_list = data.get('servers', [])           
           print(f"Loaded {len(server_list)} servers")
           return server_list

    except FileNotFoundError:
        print("Error: config.json file not found.")
        return []   
    
def check_server(url, max_retries=2):
    for attempt in range(max_retries + 1):
        start_time = time.time()
        
        try:
            response = requests.get(url, timeout=5)
            end_time = time.time()
            elapsed_ms = int((end_time - start_time) * 1000)
            if 200 <= response.status_code < 300:
                is_healthy = True
                try:
                    json_data = response.json()
                    if json_data.get("status") and json_data.get("status") != "ok":
                        is_healthy = False
                except ValueError:
                    pass
            else:
                is_healthy = False
                
            is_slow = elapsed_ms > 500
            if is_healthy:
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms,
                    "is_healthy": True,
                    "is_slow": is_slow
                }
            else:
                if attempt == max_retries:
                    return {
                        "url": url,
                        "status_code": response.status_code,
                        "elapsed_ms": elapsed_ms,
                        "is_healthy": False,
                        "is_slow": is_slow
                    }
                    
        except requests.exceptions.RequestException as error:
            if attempt == max_retries:
                end_time = time.time()
                elapsed_ms = int((end_time - start_time) * 1000)
                
                return {
                    "url": url,
                    "status_code": "DOWN",
                    "elapsed_ms": elapsed_ms,
                    "is_healthy": False,
                    "is_slow": False
                }
                
        time.sleep(1)

def format_result(result):
    clean_url = result["url"].replace("https://", "").replace("http://", "")
    if result["is_healthy"]:
        status_text = "OK"
    else:
        if result["status_code"] == "DOWN":
            status_text = "TIMEOUT"
        else:
            status_text = "DOWN"
    output_line = f"{clean_url:<35} — {status_text} ({result['status_code']})    — {result['elapsed_ms']}ms"
    
    if result.get("is_slow"):
        output_line += "  [slow]"
        
    return output_line

def send_email_alert(failed_services):
    sender_email = os.getenv("ALERT_EMAIL")
    sender_password = os.getenv("ALERT_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    if not all([sender_email, sender_password, receiver_email]):
        print("\n[!] Skipping email alert: Email environment variables not set.")
        return

    print("\nAttempting to send email alert...")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"CRITICAL: {len(failed_services)} Service(s) DOWN"
    
    body = "The Server Health Checker detected the following outages:\n\n"
    for service in failed_services:
        body += f"{service}\n"
    body += "\nPlease investigate immediately."
    
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() 
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print("[✓] Alert email sent successfully!")
        
    except Exception as error:
        print(f"[X] Failed to send email: {error}")

def check_all_servers(servers):  
    print("\nStarting health checks...")
    print("-" * 70)
    failed_services = []
    
    for url in servers:
        result = check_server(url)
        formatted_text = format_result(result)
        print(formatted_text)
        if not result["is_healthy"]:
            failed_services.append(url)
            
    print("-" * 60)
    if failed_services:
        failed_string = ", ".join(failed_services)
        print(f"\nFailed services: {failed_string}\n")
        send_email_alert(failed_services)
        
    else:
        print("\nAll services are healthy!\n")
     
if __name__ == "__main__":
    servers_to_check = load_servers()
    if servers_to_check:
        check_all_servers(servers_to_check)