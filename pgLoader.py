
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine
import os
import xlwings as xw

#Carga IIF, IRF  y RESB desde excel_file a postgre
class dataManager(object):
    def __init__(self,ip='127.0.0.1',user='postgres',passw='jp123',db='Bolsa'):
        #super(, self).__init__()
        self.connStr = 'postgresql://'+ user +':'+ passw + '@'+ip+':5432/'+db
        self.engine = create_engine(self.connStr)

    def load_sebra(self,excel_file):
        now = dt.datetime.now()
        table_name = ['iif','irf','benchmark']

        #Dataframes
        IIF = pd.read_excel(open(excel_file,"rb"), sheetname="IIF")
        IRF = pd.read_excel(open(excel_file,"rb"), sheetname="IRF")
        Bch = pd.read_excel(open(excel_file,"rb"), sheetname="Benchmark")
        Bch['Fecha'] = IIF['Fecha'][0]

        dfs = [IIF,IRF,Bch]
        for i in range(3):
            dfs[i].columns = dfs[i].columns.str.replace('[ (%)]','')
            dfs[i].to_sql(table_name[i], self.engine, if_exists='append',index=False)

        time = dt.datetime.now() - now
        print('All tables saved succesfully. Execution time: %s' % str(time))

    def load_closing(self,excel_file):
        wb = xw.Book(excel_file)
        sht=wb.sheets('Closing')
        date = sht.range('B4').value

        table_name = ['swap uf','swap clp','libor basis','fwd']
        ranges = ['B18:G35','H18:M35','B39:G52','C80:H92']

        for i in range(len(tablas)):
            tmp = sht.range(ranges[i]).options(pd.DataFrame).value
            tmp['Fecha'] = date
            tmp.to_sql(table_name[i],self.engine,if_exists='append',index=False)

        wb.close()

#Llena la base con los archivos historicos
def populate_db(file_path):
    directory = os.fsencode(file_path)
    dm = dataManager()
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.endswith(".xlsx"):
            excel_file = os.path.join(os.fsdecode(directory), filename)
            dm.load_sebra(excel_file)
        else:
            continue
