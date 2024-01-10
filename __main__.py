import ibm_boto3
import sys
from ibm_botocore.client import Config
from PyPDF2 import PdfReader
import io
import pinecone
from sentence_transformers import SentenceTransformer
import openai
import json
import os
# Import the `dotenv` module and load the environment variables
from dotenv import load_dotenv
load_dotenv()
# Initialize Pinecone
pinecone.init(api_key=os.environ.get("pinecone-key"), environment="gcp-starter")
print(os.environ.get("pinecone-key"))
# Define Pinecone index
index_name = "langchain"
dimension = 384

# Create a new index (you only need to create it once)
index = pinecone.Index(index_name)

# Initialize the Sentence Transformer model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Initialize GPT-4
openai.api_key = os.environ.get("api-key")
print(openai.api_key)

def get_item(bucket_name, item_name):
    print(f"Retrieving item from bucket: {bucket_name}, key: {item_name}")
    # Initialize IBM Cloud Object Storage client
    cos = ibm_boto3.client("s3",
            ibm_api_key_id=os.environ.get("ibm_api_key_id"),
            ibm_service_instance_id=os.environ.get("ibm_service_instance_id"),
            ibm_auth_endpoint=os.environ.get("ibm_auth_endpoint"),
            config=Config(signature_version="oauth"),
            endpoint_url=os.environ.get("endpoint_url")
        )

    try:
        # Download the file from IBM Cloud Object Storage
        response = cos.get_object(Bucket=bucket_name, Key=item_name)
        file_data = response["Body"].read()

        if item_name.lower().endswith('.pdf'):
            # Extract text from PDF using PyPDF2
            text = extract_text_using_pypdf2(file_data)
            return text
        elif item_name.lower().endswith('.txt'):
            # Read text from a plain text file
            text = file_data.decode('utf-8')
            return text
        else:
            return None

    except Exception as e:
        raise Exception(f"ERROR: {e}")

def extract_text_using_pypdf2(pdf_data):
    pdf = PdfReader(io.BytesIO(pdf_data))
    text = ''
    for page in pdf.pages:
        text += page.extract_text()
    return text

def upsert_text_to_pinecone(index, doc_id, text):
    sample_vector = model.encode(text).tolist()
    metadata = {"content": text}
    index.upsert(vectors=[(doc_id, sample_vector, metadata)])

def generate_answer_using_gpt3(query, content):
    system_role="Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the text and requires some latest information to be updated, print 'Sorry Not Sufficient context to answer query' \n" 
    context = content
    user_input = context + '\n' + query +'\n'
    gpt4_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role":"system","content":system_role},
            {"role":"user","content":user_input}
        ]
    )
    print(gpt4_response["choices"][0]["message"]["content"])
    return gpt4_response["choices"][0]["message"]["content"]

def main(params):
    bucket_name = "langchaintest"

    try:
        # List objects in the bucket
        cos = ibm_boto3.client("s3",
            ibm_api_key_id=os.environ.get("ibm_api_key_id"),
            ibm_service_instance_id=os.environ.get("ibm_service_instance_id"),
            ibm_auth_endpoint=os.environ.get("ibm_auth_endpoint"),
            config=Config(signature_version="oauth"),
            endpoint_url=os.environ.get("endpoint_url")
        )
        objects = cos.list_objects(Bucket=bucket_name)['Contents']

        for obj in objects:
            item_name = obj['Key']
            text = get_item(bucket_name, item_name)
            if text:
                print(f"File: {item_name}")
                print(f"Text: {text}")
                upsert_text_to_pinecone(index, item_name, text)

        # Perform a similarity search with a query
        query_text = params["query"]#"Global Presence of ibm cloud."
        print("query text is", query_text)
        query_vector = model.encode(query_text).tolist()
        top_k = 5

        results = index.query(query_vector, top_k=top_k, include_metadata=True)
        print("results are", results)
        for result in results["matches"]:
            doc_id = result["id"]
            similarity = result["score"]
            content = result["metadata"]["content"]

            # Use GPT-3 to generate an answer
            answer = generate_answer_using_gpt3(query_text, content)

            print(f"Document ID: {doc_id}")
            print(f"Similarity Score: {similarity:.4f}")
            print(f"Answer: {answer}\n")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': results
        }

    except Exception as error:
        print(error)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': {
                'message': 'There seems to be an error!'
            }
        }


main({
    "query":"filler"
})