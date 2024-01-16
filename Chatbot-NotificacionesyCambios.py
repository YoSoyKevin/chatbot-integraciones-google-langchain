from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload

import io
import os
import tempfile
import pandas as pd
import boto3

from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader

from email.message import EmailMessage
import smtplib

SCOPES = ['https://www.googleapis.com/auth/drive']
OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY')

def handler (event, context):
    print(event)
    validar_notificacion()

    return {
        'statusCode': 200,
    }

#AUTENTICACION GOOGLE DRIVE
def authenticate():
    s3 = boto3.client("s3",aws_access_key_id=os.environ.get('aws_access_key_id'),aws_secret_access_key=os.environ.get('aws_secret_access_key'))
    bucket_name = 'functiongraph'
    file_keys = ['CREDENCIALES/creds_IAM.json']

    with tempfile.TemporaryDirectory() as tmp_directory:
        # Descarga los archivos desde S3 y guárdalos en el directorio temporal
        for file_key in file_keys:
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            content = response['Body'].read()
            file_path = os.path.join(tmp_directory, os.path.basename(file_key))
            with open(file_path, 'wb') as local_file:
                local_file.write(content)

        file_path_faiss=rf'{tmp_directory}/{os.listdir(tmp_directory)[0]}'
        #print(file_path_faiss)
        creds = service_account.Credentials.from_service_account_file(file_path_faiss, scopes=SCOPES)
    return creds

#LISTAR ARCHIVOS DE GOOGLE DRIVE
def list_files():
    creds=authenticate()
    service = build('drive', 'v3', credentials=creds)
    folder_id='1OjqJwgLBcWq9-f9VaI8_bMsLt_bPTxyb'
    query=f"parents='{folder_id}'and trashed=false"

    response=service.files().list(q=query).execute()
    files=response.get('files')
    nextPageToken=response.get('nextPageToken')

    while nextPageToken:
        response=service.files().list(q=query).execute()
        files.extend(response.get('files'))
        nextPageToken=response.get('nextPageToken')

    ids_pdf_drive = [file['id'] for file in files]
    names_pdf_drive = [file['name'] for file in files]

    #df=pd.DataFrame(files)
    #selected_columns = df[['id', 'name']]
    return ids_pdf_drive,names_pdf_drive

#DESCARGAR PDF DE DRIVE Y AGREGAR A DBV
def download_pdf_gdrive_merge_dbv(file_id,file_name):

    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    
    request = service.files().get_media(fileId=file_id)
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)

    done = False

    while done is False:
        status, done = downloader.next_chunk()
    file.seek(0)

    pdf_bytes = file.read()

    with tempfile.TemporaryDirectory() as tmp_directory:
        # Descarga los archivos desde S3 y guárdalos en el directorio temporal
        file_path = os.path.join(tmp_directory, os.path.basename(file_name))
        with open(file_path, 'wb') as local_file:
            local_file.write(pdf_bytes)
        # Imprime la dirección del directorio temporal
        #print(f'Dirección del directorio temporal: {tmp_directory}')
        path_pdf=rf'{tmp_directory}/{os.listdir(tmp_directory)[0]}'
        #print(path_pdf)

        new_dbv=agregar_dbv(path_pdf)
    return new_dbv

#DESCARGAR DBV DE S3
def download_dbv_s3():

    s3 = boto3.client("s3",aws_access_key_id=os.environ.get('aws_access_key_id'),aws_secret_access_key=os.environ.get('aws_secret_access_key'))
    bucket_name = 'functiongraph'
    file_keys = ['FAISS_INDEX/index.faiss', 'FAISS_INDEX/index.pkl']

    with tempfile.TemporaryDirectory() as tmp_directory:
        # Descarga los archivos desde S3 y guárdalos en el directorio temporal
        for file_key in file_keys:
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            content = response['Body'].read()
            file_path = os.path.join(tmp_directory, os.path.basename(file_key))
            with open(file_path, 'wb') as local_file:
                local_file.write(content)

        embeddings = OpenAIEmbeddings()
        knowledge_base = FAISS.load_local(tmp_directory, embeddings)

    return knowledge_base

#VISUALIZAR LA DB EN PANDAS
def store_to_df(store):
    v_dict=store.docstore._dict
    data_rows=[]

    if not v_dict:  # Comprobar si el diccionario está vacío
        return pd.DataFrame()

    for k in v_dict.keys():
        doc_name=v_dict[k].metadata['source'].split('/')[-1]
        page_number=v_dict[k].metadata['page']+1
        content=v_dict[k].page_content
        data_rows.append({"chunk_id":k,"document":doc_name,"page":page_number,"content":content})
    vector_df=pd.DataFrame(data_rows)
    
    return vector_df

#BORRAR DOCUMENT EN DBV
def delete_document(store,document):
    vector_df = store_to_df(store)
    chunk_list=vector_df.loc[vector_df['document']==document]['chunk_id'].tolist()
    store.delete(chunk_list)
    return store

#FUNCION PRINCIPOAL DE VALIDACION
def validar_notificacion():

    ids_pdf_drive,names_pdf_drive=list_files() 
    #print(ids_pdf_drive,names_pdf_drive)
    dbv=download_dbv_s3()
    #gdrive_files = ['archivo1.pdf', 'archivo2.pdf', 'archivo3.pdf']  # Lista de nombres de archivos en Google Drive
    vector_dbv=store_to_df(dbv)

    if not ids_pdf_drive and vector_dbv.empty:
        print("No hay datos disponibles para la validación. Terminando el proceso.")
        print("print 162")
        return

    if vector_dbv.empty:
        for name_pdf in names_pdf_drive:
            drive_id = ids_pdf_drive[names_pdf_drive.index(name_pdf)]  # Obtener el ID de Google Drive
            print(f"Debe agregarse: {name_pdf} (ID Google Drive: {drive_id}, ID Faiss: No encontrado)")
            dbv_new=download_pdf_gdrive_merge_dbv(drive_id,name_pdf)
            upload_dbv_s3(dbv_new)
            correo_alerta_agregar(name_pdf)
            print("print 172")

    elif not ids_pdf_drive:
        for document in vector_dbv['document'].unique():
            faiss_id = document_id_mapping.get(document, 'No encontrado')
            print(f"Eliminar de Faiss: {document} (ID Faiss: {faiss_id}, ID Google Drive: No encontrado)")
            dbv=download_dbv_s3()
            dbv_new=delete_document(dbv,document)
            upload_dbv_s3(dbv_new)
            correo_alerta_eliminar(document)
            print("print 182")

    else:        
    # Crear un diccionario que mapea nombres de documentos a ID
        document_id_mapping = dict(zip(vector_dbv['document'], vector_dbv['chunk_id']))

    # Paso 1: Verificar si los archivos PDF existen en la base de datos Faiss
        for name_pdf in names_pdf_drive:
            if name_pdf not in vector_dbv['document'].values:
                drive_id = ids_pdf_drive[names_pdf_drive.index(name_pdf)]  # Obtener el ID de Google Drive
                print(f"Debe agregarse: {name_pdf} (ID Google Drive: {drive_id}, ID Faiss: No encontrado)")
                dbv_new=download_pdf_gdrive_merge_dbv(drive_id,name_pdf)
                upload_dbv_s3(dbv_new)
                correo_alerta_agregar(name_pdf)
                print("print 196")

    # Paso 2: Verificar si hay documentos en Faiss que no existen en Google Drive
        for document in vector_dbv['document'].unique():
            if document not in names_pdf_drive:
                faiss_id = document_id_mapping.get(document, 'No encontrado')
                print(f"Eliminar de Faiss: {document} (ID Faiss: {faiss_id}, ID Google Drive: No encontrado)")
                dbv=download_dbv_s3()
                dbv_new=delete_document(dbv,document)
                upload_dbv_s3(dbv_new)
                correo_alerta_eliminar(document)
                print("print 207")

#SUBIR NUEVA DBV A S3
def upload_dbv_s3(new_dbv):

    with tempfile.TemporaryDirectory() as tmp_dir:
        new_dbv.save_local(tmp_dir)
        #print(os.listdir(tmp_dir))

        file_path_faiss=rf'{tmp_dir}/{os.listdir(tmp_dir)[0]}'
        file_path_pkl=rf'{tmp_dir}/{os.listdir(tmp_dir)[1]}'

    # Crear un cliente de S3
        s3 = boto3.client("s3", aws_access_key_id=os.environ.get('aws_access_key_id'),aws_secret_access_key=os.environ.get('aws_secret_access_key'))

    # Nombre de tu bucket de S3
        bucket_name = 'functiongraph'

    # Lista de archivos locales que deseas subir
        archivos_locales = [file_path_faiss,file_path_pkl]

    # Subir cada archivo al bucket de S3
        for archivo_local in archivos_locales:
            nombre_archivo_s3 = 'FAISS_INDEX/' + os.path.basename(archivo_local)  # Utiliza el nombre del archivo local
            s3.upload_file(archivo_local, bucket_name, nombre_archivo_s3)

#AGREGAR PDF A DBV
def agregar_dbv(file_pdf):
    dbv_principal=download_dbv_s3()

    #path=open(file_pdf,'rb')
    loader_pdf = PyPDFLoader(file_pdf)
    docs = loader_pdf.load()

    text_splitter = RecursiveCharacterTextSplitter(separators="\n",chunk_size=1000,chunk_overlap=200,length_function=len)
    chunks = text_splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()
    dbv_nuevo= FAISS.from_documents(chunks, embeddings)
    dbv_principal.merge_from(dbv_nuevo)
    #print(dbv_principal.docstore._dict)
    return dbv_principal

def correo_alerta_agregar(file_name):
    remitente = os.environ.get('gmail_user')
    destinatario = os.environ.get('gmail_user')
    # Mensaje en formato HTML
    mensaje_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Notificación</title>
</head>
<body>
    <p>Estimado/a [Nombre del Destinatario o Título],</p>
    <p>Queremos informarte que el documento <strong>"{file_name}"</strong> ha sido agregado a nuestra base de datos en ChatbotPDF.</p>
    <p>Estamos seguros de que esta adición será de gran utilidad para ti.</p>
    <p>Si tienes alguna pregunta o necesitas asistencia adicional, no dudes en contactarnos.</p>
    <p>Gracias por contar con nosotros.</p>
    <p>Atentamente,</p>
    <p>[Tu Nombre]</p>
</body>
</html>
"""

    

    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "Notificación Importante: Nuevo Documento Agregado"
    email.set_content("Este es un mensaje en formato HTML. Habilita la visualización HTML en tu cliente de correo para ver el contenido.")

    email.add_alternative(mensaje_html, subtype='html')

    smtp = smtplib.SMTP_SSL("smtp.gmail.com")
    smtp.login(remitente, os.environ.get('gmail_pass'))
    smtp.sendmail(remitente, destinatario, email.as_string())

    smtp.quit()

def correo_alerta_eliminar(file_name):
    remitente = os.environ.get('gmail_user')
    destinatario = os.environ.get('gmail_user')
    # Mensaje en formato HTML
    mensaje_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Notificación</title>
</head>
<body>
    <p>Estimado/a [Nombre del Destinatario o Título],</p>
    <p>Te informamos que el documento <strong>"{file_name}"</strong> ha sido eliminado de nuestra base de datos en ChatbotPDF.</p>
    <p>Esta decisión se tomó como parte de nuestra revisión de recursos digitales.</p>
    <p>Si necesitas información adicional o asistencia, no dudes en contactarnos.</p>
    <p>Gracias por tu comprensión.</p>
    <p>Atentamente,</p>
    <p>[Tu Nombre]</p>
</body>
</html>
"""

    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "Notificación: Documento eliminado"
    email.set_content("Este es un mensaje en formato HTML. Habilita la visualización HTML en tu cliente de correo para ver el contenido.")

    email.add_alternative(mensaje_html, subtype='html')

    smtp = smtplib.SMTP_SSL("smtp.gmail.com")
    smtp.login(remitente, os.environ.get('gmail_pass'))
    smtp.sendmail(remitente, destinatario, email.as_string())

    smtp.quit()
