from pymongo import MongoClient
from utils.util import *

url_str = ""
if netcl_conf.mongodb.user:
    url_str = "mongodb://{}:{}@{}:{}/".format(
        netcl_conf.mongodb.user, netcl_conf.mongodb.password, netcl_conf.mongodb.host, netcl_conf.mongodb.port)
else:
    url_str = "mongodb://{}:{}/".format(netcl_conf.mongodb.host, netcl_conf.mongodb.port)

persLayer = MongoClient(url_str)
OSSdb = persLayer[netcl_conf.mongodb.db]


class DB:
    @staticmethod
    def insert_DB(collection, data):
        db = OSSdb[collection]
        return db.insert_one(data)

    @staticmethod
    def exists_DB(collection, data):
        db = OSSdb[collection]
        #return db.find(data).count() >= 1
        return db.count_documents(data) > 0

    @staticmethod
    def find_DB(collection, data):
        db = OSSdb[collection]
        return db.find(data)

    @staticmethod
    def findone_DB(collection, data):
        db = OSSdb[collection]
        return db.find_one(data)

    @staticmethod
    def update_DB(table, data, filter):
        db = OSSdb[table]
        db.update_one(filter, {"$set": data}, upsert=True)

    @staticmethod
    def delete_DB(table, filter):
        db = OSSdb[table]
        return db.delete_many(filter)
