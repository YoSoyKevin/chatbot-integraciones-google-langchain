import json
import os
import requests
import base64
#from obs import *
import pathlib
import tempfile
import boto3
import pandas as pd
#from langchain.embeddings import HuggingFaceEmbeddings
from langchain.embeddings import OpenAIEmbeddings 
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate


def handler(event, context):
    
    knowledge_base=load_embeddings()
    
    request_body = base64.b64decode(event['body']).decode('utf-8')
    request_body = json.loads(request_body)
    request_msg= json.dumps(request_body['message'])
    chat_id=json.dumps(request_body['message']['chat']['id'])
    text_command = json.dumps(request_body['message']['text']).strip('"')
    
    BOT_TOKEN = os.environ.get('TOKEN_TELEGRAM')

    BOT_CHAT_ID = chat_id
    
    text_command = text_command[0:]
 
    print("==============")
    
    if text_command == '/start':
        messages = "Comando START"
    elif text_command == '/help':
        messages = listar_pdfs(knowledge_base)
    else:
        respuesta_bot=similarity_search(text_command,knowledge_base)
        messages=respuesta_bot
        #messages=text_command
        
    send_text = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={BOT_CHAT_ID}&text={messages}'
    
    response = requests.get(send_text)
    
    return {
        'statusCode': 200,
    }

def load_embeddings():
    
    s3 = boto3.client("s3",aws_access_key_id= os.environ.get('aws_access_key_id'),aws_secret_access_key= os.environ.get('aws_secret_access_key'))
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
    
def similarity_search(pregunta_usuario,knowledge_base):
    user_question=pregunta_usuario.lower()
    if user_question:

        docs = knowledge_base.similarity_search(user_question, 5)
        #print(docs)
        llm = ChatOpenAI(model_name='gpt-3.5-turbo')
        
        prompt_template = """Utilice las siguientes piezas de contexto para responder la pregunta al final,se creativo y desplayate. Si la respuesta no esta en el contexto, simplemente di que no la sabes, no intentes inventar una respuesta..

        {context}

        Pregunta: {question}
        Respuesta en Español:"""

        PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
        
        chain = load_qa_chain(llm, chain_type="stuff", prompt=PROMPT)

        #respuesta = chain.run(input_documents=docs, question=user_question)
        respuesta=chain({"input_documents": docs, "question": user_question})
        print(respuesta) 
        return respuesta['output_text']

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

def listar_pdfs(dbv):
    vectordbv = store_to_df(dbv)

    if vectordbv.empty:
    # Si el DataFrame está vacío, muestra un mensaje
        mensaje = "No se han registrado PDFs."
    else:
    # Si hay elementos en la lista, une los elementos con saltos de línea
        columna_unica = vectordbv['document'].drop_duplicates().tolist()
        mensaje = "Los pdfs registrados son:\n\n" + "\n".join(["- " + nombre for nombre in columna_unica])  
    return mensaje     