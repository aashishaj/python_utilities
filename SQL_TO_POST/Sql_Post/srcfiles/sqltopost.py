from sqlalchemy import create_engine
import pandas as pd
import urllib
import psycopg2
import os
import numpy as np

#sql connection
params = urllib.parse.quote_plus("DRIVER={ODBC Driver 13 for SQL Server};"
                                     "SERVER=blrdevsqldb001.fintellix.com;"
                                     "DATABASE=COE_PLATFORM_42;"
                                     "UID=plt;"
                                     "PWD=Welcome1")
    #Connecting to server using an engine
sql_engine = create_engine("mssql+pyodbc:///?odbc_connect={}".format(params))

#postgres connections
user = 'citususer'
password = 'Welcome1'
host = 'blrtestapp027.fintellix.com'
port = 9700
db = 'demo'
url = 'postgresql://{}:{}@{}:{}/{}'
url = url.format(user, password, host, port, db)
postgres_engine = create_engine(url, client_encoding='utf8')    
postgres_engine.connect()


#postgres cursor
connection_post = psycopg2.connect(database = "demo",user ="citususer",password="Welcome1",host = "blrtestapp027.fintellix.com", port = "9700")
#create the connection
cur_postgres = connection_post.cursor()


def insert(dataframe,tablename):
     path = pathgeneration_csv()
     tablename = 'demo_schema.dim_derived_line_item'
     dataframe.to_csv(path, encoding='utf-8', header = True,doublequote = True, sep=',', index=False)      
     f = open(path, "r")
     #cur_postgres.execute("truncate table demo_schema.dim_derived_line_item" )
     cur_postgres.copy_expert("copy {} from STDIN CSV HEADER QUOTE '\"'".format(tablename), f)  
     cur_postgres.execute('set search_path to demo_schema,public')
     cur_postgres.execute("commit;")
     print("insert complete")
     
def upsertion(dataframe,tn):
     path = pathgeneration_csv()
     tablename = 'demo_schema.' + tn
     dataframe.to_csv(path, encoding='utf-8', header = True,doublequote = True, sep=',', index=False)      
     f = open(path, "r")
     cur_postgres.execute("truncate table demo_schema.dim_derived_line_item" )
     cur_postgres.copy_expert("copy {} from STDIN CSV HEADER QUOTE '\"'".format(tablename), f)  
     cur_postgres.execute('set search_path to demo_schema,public')
     cur_postgres.execute("commit;")
     print("upsert complete")

def create(table_name_s):
    col_query ="select case when data_type = 'int' then 'isnull('+column_name+',-123456789) as ' + column_name else column_name end col_name from INFORMATION_SCHEMA.COLUMNS where lower(table_name)='"+table_name_s+"'"      
    sql_col_df =  pd.read_sql(col_query,sql_engine)
    #print(sql_col_df)
    cs = sql_col_df.values.tolist()
    #print(cs)
    query = "select "
    for i in cs:
        t = str(i)
        t = t[2:-2]
        query += t + ","
    query = query[:-1] + " from " + table_name_s
    return(query)
    



def Validation(sql_dataframe,post_dataframe,table_name_s):
    col_query ="select COLUMN_NAME from INFORMATION_SCHEMA.COLUMNS where TABLE_NAME='"+table_name_s  +"'"      
    sql_col_df =  pd.read_sql(col_query,sql_engine)

    Primary_key_query = "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS TC INNER JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS KU ON TC.CONSTRAINT_TYPE = 'PRIMARY KEY' AND TC.CONSTRAINT_NAME = KU.CONSTRAINT_NAME AND KU.table_name='"+table_name_s + "'ORDER BY KU.TABLE_NAME, KU.ORDINAL_POSITION;"    
    primarykeydataframe = pd.read_sql(Primary_key_query,sql_engine)
    #print(primarykeydataframe)
    
    deletecols =['src_hashed','src_combined','tgt_hashed','tgt_combined']
    primarykeylist=[]
    for index,row in primarykeydataframe.iterrows():
        for ele in row:
            t = str(ele).lower()
            primarykeylist.append(t)

    nonprimarykeylist=[]
    nonprimarykeydataframe = pd.concat([sql_col_df,primarykeydataframe]).drop_duplicates(keep=False)
    for index,row in nonprimarykeydataframe.iterrows():
        for ele in row:
            t = str(ele).lower()
            nonprimarykeylist.append(t)
    #print(nonprimarykeylist)
    
    sql_dataframe['src_combined'] = sql_dataframe.apply(lambda x:','.join(map(str,x)),axis=1)
    sql_dataframe['src_hashed'] = sql_dataframe['src_combined'].apply(lambda x : hash(tuple(x))) 
    #print("\n\n",sql_dataframe)

    post_dataframe['tgt_combined']  = post_dataframe.apply(lambda x:','.join(map(str,x)),axis =1)
    post_dataframe['tgt_hashed'] = post_dataframe['tgt_combined'].apply(lambda x :hash(tuple(x)))
   # print("\n\n\n",post_dataframe)       
   
   
    merged_dataframe = pd.merge(sql_dataframe,post_dataframe,how = 'outer',on=primarykeylist)
    merged_dataframe['update'] = np.where(merged_dataframe['src_hashed']==merged_dataframe['tgt_hashed'],'y','n')
    if merged_dataframe['update'].all() == 'n':
        print("Upsert is not required")
    else:
        print("upsert is required")
        merged_dataframe = pd.merge(sql_dataframe,post_dataframe,how = 'left',on=primarykeylist)
        merged_dataframe.columns = merged_dataframe.columns.str.replace('_y', '')
        merged_dataframe['update'] =np.where(merged_dataframe['src_hashed']==merged_dataframe['tgt_hashed'],'n','y')
        update =merged_dataframe['update'] == 'y'
        f1 = merged_dataframe[update]     
        f1 = f1.drop(nonprimarykeylist,axis =1)
        f1 = f1.drop(deletecols,axis=1)
        f1.columns = f1.columns.str.replace('_x','')
        # print(f1)
        update =merged_dataframe['update'] == 'n'
        f2 = merged_dataframe[update]    
        f2 = f2.drop(nonprimarykeylist,axis =1)
        f2 = f2.drop(deletecols,axis=1)
        f2.columns = f2.columns.str.replace('_x','')
        #print(f2)
    
        merged_dataframe = pd.merge(sql_dataframe,post_dataframe,how = 'right', on=primarykeylist)
        merged_dataframe.columns = merged_dataframe.columns.str.replace('_x', '')
        merged_dataframe['update'] =np.where(np.isnan(merged_dataframe['src_hashed']),'y','n')     
        update = merged_dataframe['update'] =='y'
        f3 = merged_dataframe[update]
        f3 = f3.drop(nonprimarykeylist,axis=1)
        f3 = f3.drop(deletecols,axis =1)
        f3.columns = f3.columns.str.replace('_y','')
        #print(f3)
 
    
        cos = ['src_combined', 'src_hashed']
        sql_dataframe = sql_dataframe.drop(cos,axis=1)
        frames = [f1,f2,f3]
        finaldf = pd.concat(frames,ignore_index=True,sort = True)
        finaldf = finaldf.drop('update',axis=1)
    
        finaldf = finaldf[sql_dataframe.columns]

        upsertion(finaldf,table_name_s)



     
def compare():
    
    
    table_name_s = 'DIM_DERIVED_LINE_ITEM'
    table_name_t =table_name_s.lower()
    sql_query = create(table_name_t) 
    sql_dataframe = pd.read_sql(sql_query,sql_engine)    
    schema_name = "demo_schema."
    post_query = "select * from " +schema_name+table_name_t
    post_dataframe = pd.read_sql(post_query,postgres_engine)    
    sql_dataframe.columns =map(str.lower, sql_dataframe.columns)
    #print(nonprimarykeylist)
    
    if  sql_dataframe.empty:
        print("source table empty no data tranference \n")
    elif post_dataframe.empty:
        print("tgt tb is empty data completely transfer \n")
        print("target table is empty perform insertion from source table  \n ")
        insert(sql_dataframe,table_name_s)
        
    else:
        print("checking for upsert required")
        Validation(sql_dataframe,post_dataframe,table_name_s)
    
        
compare()



def pathgeneration_csv():
    tablename = 'dim_derived_line_item'
    tablename = tablename + ".csv"
    currentDirectory = os.path.dirname(os.path.realpath(__file__))
    supportedDatabasePath = os.path.join(currentDirectory, "..")
    supportedDatabasePath = os.path.join(supportedDatabasePath, "csv_files")
    supportedDatabasePath = os.path.join(supportedDatabasePath,tablename)
    #print(type(supportedDatabasePath))
    return supportedDatabasePath



sql_engine.dispose()
postgres_engine.dispose()
cur_postgres.close()