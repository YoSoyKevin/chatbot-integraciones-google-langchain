from googleapiclient.discovery import build
from google.oauth2 import service_account
import uuid
import datetime
import boto3
import os
import json

from email.message import EmailMessage
import smtplib

def handler(event, context):
    
   
    DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')
   
    
    #SERVICE_ACCOUNT_FILE = 'creds_IAM.json'
    ACCESS_KEY_S3=os.environ.get('ACCESS_KEY_S3')
    SECRET_KEY_S3=os.environ.get('SECRET_KEY_S3')
    client_s3=boto3.client('s3',aws_access_key_id=ACCESS_KEY_S3,aws_secret_access_key=SECRET_KEY_S3)
    
    creds_download = client_s3.get_object(Bucket='functiongraph',Key='CREDENCIALES/creds_IAM.json',)
    creds_download = creds_download['Body'].read().decode('utf-8')
    creds_IAM_JSON = json.loads(creds_download)
    
    print(creds_IAM_JSON)
    
    
    webhook(creds_IAM_JSON,DRIVE_FOLDER_ID)
    
    return {
        'statusCode': 200,
    }

def authenticate(SERVICE_ACCOUNT_FILE):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return creds


def webhook(creds_IAM_JSON,DRIVE_FOLDER_ID):
    creds = authenticate(creds_IAM_JSON)
    service = build('drive', 'v3', credentials=creds)
    channel_id = str(uuid.uuid4())

    # Obtener la fecha actual
    fecha_actual = datetime.datetime.now()

   # Sumar 1 días a la fecha actual
    nueva_fecha = fecha_actual + datetime.timedelta(days=1)

   # Convertir la nueva fecha en un valor de tiempo UNIX milisegundos
    tiempo_unix_milisegundos = int(nueva_fecha.timestamp() * 1000)
    print("CHANNEL:",channel_id)
    print("EXPIRATION",tiempo_unix_milisegundos)

    notification_body = {
    'id': channel_id,
    'type': 'web_hook',
    'address': 'https://bdf89e1024e24a98b227d92691f1e2db.apig.la-south-2.huaweicloudapis.com/ChatBot-NotificacionesyCambios',
    'expiration':tiempo_unix_milisegundos,}

    print(notification_body)
    
    channel = service.files().watch(fileId=DRIVE_FOLDER_ID,body=notification_body).execute()
    
    correo_alerta(DRIVE_FOLDER_ID,notification_body)

def correo_alerta(DRIVE_FOLDER_ID,notification_body):
    remitente =  os.environ.get('gmail_user')
    destinatario =  os.environ.get('gmail_user')
    # Mensaje en formato HTML
    mensaje_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Notificación</title>
</head>
<body>
    <p>Estimado/a @@@@,</p>
    <p>Queremos informarte que la subscripcion al canal de notificaciones de google drive acaba de realizarse.</p>
    <p>CARPETA_DRIVE_ID:{DRIVE_FOLDER_ID}.</p>
    <p>NOTIFICACION_BODY.</p>
    <p>{notification_body}</p>
    <p>Estamos seguros de que esta adición será de gran utilidad para ti.</p>
    <p>Si tienes alguna pregunta o necesitas asistencia adicional, no dudes en contactarnos.</p>
    <p>Gracias por contar con nosotros.</p>
    <p>Atentamente,</p>
    <p>@@@@</p>
</body>
</html>
"""

    

    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "Notificación WEBHOOK: CANAL DE NOTIFICACIONES CREADO"
    email.set_content("Este es un mensaje en formato HTML. Habilita la visualización HTML en tu cliente de correo para ver el contenido.")

    email.add_alternative(mensaje_html, subtype='html')

    smtp = smtplib.SMTP_SSL("smtp.gmail.com")
    smtp.login(remitente,  os.environ.get('gmail_pass'))
    smtp.sendmail(remitente, destinatario, email.as_string())

    smtp.quit()
