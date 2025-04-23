from pymongo import MongoClient
from storage.mongo_keys import *


def send_to_mongo(df):
    """Send the DataFrame to MongoDB."""
    # Send data to MongoDB
    client = MongoClient(connection_string)
    db = client[database_name]
    collection = db[collection_name]

    # Inserir os dados do DataFrame no MongoDB
    collection.insert_many(df.reset_index().to_dict(orient='records'))

    print("Dados enviados para o MongoDB com sucesso!")