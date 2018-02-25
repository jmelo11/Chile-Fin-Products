# Version 1.0
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine
import os
import xlwings as xw
#import tia.bbg.datamgr as dm
try:
    import tia.bbg.datamgr as dm
except:
    pass

#Carga IIF, IRF  y RESB en access desde excel_file a postgre
class dataManager(object):
    def __init__(self,ip='127.0.0.1',port='5432',user='postgres',passw='jp123',db='Bolsa'):
        super().__init__()
        self.connStr = 'postgresql://'+ user +':'+ passw + '@'+ip+':'+port+'/'+db
        self.engine = create_engine(self.connStr)
    def upload_sebra(self,excel_file):
        now = dt.datetime.now()
        table_name = ['iif','irf','benchmark']

        #Dataframes
        IIF = pd.read_excel(open(excel_file,"rb"), sheet_name="IIF")
        IRF = pd.read_excel(open(excel_file,"rb"), sheet_name="IRF")
        IIF['Fecha'] = IRF['Fecha'].iloc[0]
        if not 'Hora' in IIF.columns:
            IIF['Hora'] = IRF['Hora'].iloc[0]

        try:
            Bch = pd.read_excel(open(excel_file,"rb"), sheet_name="Benchmark")
            Bch['Fecha'] = IIF['Fecha'][0]

            x = 3
        except:
            x = 2
            Bch = []

        dfs = [IIF,IRF,Bch]
        for i in range(x):
            dfs[i].columns = dfs[i].columns.str.replace('[ (%)]','')
            dfs[i].to_sql(table_name[i],self.engine,if_exists='append',index=False)
        time = dt.datetime.now() - now
        print('All tables saved succesfully. Execution time: %s' % str(time))
        return 0
    def upload_closing(self,excel_file):
        wb = xw.Book(excel_file)
        sht=wb.sheets('Closing')
        date = sht.range('B4').value

        table_name = ['swap_uf','swap_clp','libor_basis','fwd_usd']
        ranges = ['B18:E35','H18:K35','B39:E52','C80:F92']

        for i in range(len(table_name)):
            tmp = sht.range(ranges[i]).options(pd.DataFrame).value
            tmp['Fecha'] = date
            tmp.to_sql(table_name[i],self.engine,if_exists='append',index=True)

        sht=wb.sheets('FWD inf and CLP NDF Curve')
        table_name = 'fwd_uf'
        ranges = 'B9:F33'
        tmp = sht.range(ranges).options(pd.DataFrame).value
        print(tmp)
        tmp['Fecha'] = date
        tmp.to_sql(table_name,self.engine,if_exists='append',index=True)

        wb.close()
    def upload_df(self,df,table_name,operation ='append',first_time = False,dup_cols=None):
        if first_time == True:
            df.to_sql(table_name, self.engine, if_exists=operation,index=False)
        else:
            tmp_df = clean_df_db_dups(df,table_name,self.engine,dup_cols=dup_cols)
            tmp_df.to_sql(table_name, self.engine, if_exists=operation,index=False)
    def get_df(self,query):
        df = pd.read_sql(query,self.engine)
        return df
    def get_raw_data(self,query):
        cnxn = self.engine.connect()
        data = cnxn.execute(query)
        raw = [x[0] for x in data]
        cnxn.close()
        return raw
    def execute_query(self,query):
        cnxn = self.engine.connect()
        data = cnxn.execute(query)
        cnxn.close()
        return 0
    def upload_bbg_data(self):
        now = dt.datetime.now()
        today_date = dt.datetime.date(now.year,now.month,now.day)
        table_name = ['swap_uf','swap_clp','fwd_usd','fwd_uf']
        mgr = dm.BbgDataManager()
        mgr.sid_result_mode = 'frame'

        icp_clp = ['CHSWPC ICCH Curncy','CHSWPF ICCH Curncy','CHSWPI ICCH Curncy','CHSWP1 ICCH Curncy','CHSWP1F ICCH NCY Curncy','CHSWP2 ICCH Curncy','CHSWP3 ICCH Curncy','CHSWP4 ICCH Curncy','CHSWP5 ICCH Curncy','CHSWP6 ICCH Curncy','CHSWP8 ICCH Curncy','CHSWP9 ICCH Curncy','CHSWP10 ICCH Curncy','CHSWP15 ICCH Curncy','CHSWP20 ICCH Curncy']
        icp_uf = ['CHSWCC ICCH Curncy','CHSWCF ICCH Curncy','CHSWPI ICCH Curncy','CHSWC1 ICCH Curncy','CHSWC1F ICCH Curncy','CHSWC2 ICCH Curncy','CHSWC3 ICCH Curncy','CHSWC4 ICCH Curncy','CHSWC5 ICCH Curncy','CHSWC6 ICCH Curncy','CHSWC7 ICCH Curncy','CHSWC8 ICCH Curncy','CHSWC9 ICCH Curncy','CHSWC10 ICCH Curncy','CHSWC15 ICCH Curncy','CHSWC20 ICCH Curncy']
        fwd_usd = ['CHN1W ICCH Curncy','CHN2W ICCH Curncy','CHN1M ICCH Curncy','CHN2M ICCH Curncy','CHN3M ICCH Curncy','CHN4M ICCH Curncy','CHN5M ICCH Curncy','CHN6M ICCH Curncy','CHN9M ICCH Curncy','CHN12M ICCH Curncy','CHN18M ICCH Curncy','CHN2Y ICCH Curncy']
        fwd_uf = ['CFNP1 ICCH Curncy','CFNP2 ICCH Curncy','CFNP3 ICCH Curncy','CFNP4 ICCH Curncy','CFNP5 ICCH Curncy','CFNP6 ICCH Curncy','CFNP7 ICCH Curncy','CFNP8 ICCH Curncy','CFNP9 ICCH Curncy','CFNP10 ICCH Curncy','CFNP11 ICCH Curncy','CFNP12 ICCH Curncy','CFNP13 ICCH Curncy','CFNP14 ICCH Curncy','CFNP15 ICCH Curncy','CFNP16 ICCH Curncy','CFNP17 ICCH Curncy','CFNP18 ICCH Curncy']

        tickers = [icp_clp,icp_uf,fwd_usd,fwd_uf]

        for i in range(len(table_name)):
            sids = mgr[tickers[i]]
            #Get data an df from bbg.
            table = sids['PX_BID','PX_MID','PX_ASK','MATURITY']
            table.columns = ['Bid','Mid','Offer','Maturity']

            if i == 0:
                tpm = mgr[['CHOVCHOV Index']]
                tpm_table = tpm.PX_LAST
                tpm_table.columns = ['Mid']
                tpm_table['Bid'] = tpm_table['Mid'].iloc[0]
                tpm_table['Offer'] = tpm_table['Mid'].iloc[0]
                table = pd.concat([tpm_table,table])
            if i == 3:
                tod_uf = mgr[['CHUF9 Index']]

                uf_first = tod_uf['PREV_CLOSE_VAL','PREV_TRADING_DT_REALTIME']
                uf_first.columns = ['Mid','Maturity']
                uf_first['Maturity'].iloc[0].replace(day=9)
                uf_first['Bid'] = uf_first['Mid'].iloc[0]
                uf_first['Offer'] = uf_first['Mid'].iloc[0]

                uf_second = tod_uf['PX_LAST','LAST_UPDATE_DT']
                uf_second.columns = ['Mid','Maturity']
                uf_second['Maturity'].iloc[0].replace(day=9)
                uf_second['Bid'] = uf_second['Mid'].iloc[0]
                uf_second['Offer'] = uf_second['Mid'].iloc[0]

                table = pd.concat([uf_first,uf_second,table])

            table['Date'] = today_date
            print(table)
            #Clean from duplicated rows in db
            #tmp_df = clean_df_db_dups(table,table_name[i],self.engine)

            ##REVISAR COMO ABRIR PUERTOS
            table.to_sql(table_name[i],self.engine,if_exists='append',index=True)

        #Load Currencies to DB
        currencies = ['CLP Curncy','EUR Curncy','JPY Curncy','BRL Curncy','COP Curncy','PEN Curncy','XBT Curncy']
        sids = mgr[currencies]
        table = sids.PX_LAST
        table['Date'] = today_date
        table.to_sql(currency,self.engine,if_exists='append',index=True)

        #Commodities - pending
        time = dt.datetime.now() - now
        print('All tables saved succesfully. Execution time: %s' % str(time))

#Auxiliary functions
def clean_df_db_dups(df, tablename, engine, dup_cols=[],filter_continuous_col=None, filter_categorical_col=None):
    """
    Remove rows from a dataframe that already exist in a database
    Required:
        df : dataframe to remove duplicate rows from
        engine: SQLAlchemy engine object
        tablename: tablename to check duplicates in
        dup_cols: list or tuple of column names to check for duplicate row values
    Optional:
        filter_continuous_col: the name of the continuous data column for BETWEEEN min/max filter
                               can be either a datetime, int, or float data type
                               useful for restricting the database table size to check
        filter_categorical_col : the name of the categorical data column for Where = value check
                                 Creates an "IN ()" check on the unique values in this column
    Returns
        Unique list of values from dataframe compared to database table
    """
    args = 'SELECT %s FROM %s' %(', '.join(['"{0}"'.format(col) for col in dup_cols]), tablename)
    args_contin_filter, args_cat_filter = None, None
    if filter_continuous_col is not None:
        if df[filter_continuous_col].dtype == 'datetime64[ns]':
            args_contin_filter = """ "%s" BETWEEN Convert(datetime, '%s')
                                          AND Convert(datetime, '%s')""" %(filter_continuous_col,
                              df[filter_continuous_col].min(), df[filter_continuous_col].max())


    if filter_categorical_col is not None:
        args_cat_filter = ' "%s" in(%s)' %(filter_categorical_col,
                          ', '.join(["'{0}'".format(value) for value in df[filter_categorical_col].unique()]))

    if args_contin_filter and args_cat_filter:
        args += ' Where ' + args_contin_filter + ' AND' + args_cat_filter
    elif args_contin_filter:
        args += ' Where ' + args_contin_filter
    elif args_cat_filter:
        args += ' Where ' + args_cat_filter

    df.drop_duplicates(dup_cols, keep='last', inplace=True)
    df = pd.merge(df, pd.read_sql(args, engine), how='left', on=dup_cols, indicator=True)
    df = df[df['_merge'] == 'left_only']
    df.drop(['_merge'], axis=1, inplace=True)
    return df
def create_tables():
    helper = dataManager()
    tablas = ['swap_clp','swap_uf','fwd_usd','fwd_uf','currencies']

    for i in range(len(tablas)):
        tmp = pd.DataFrame([[dt.datetime(2008,1,1,0,0,0),dt.datetime(2008,1,1,0,0,0),'ABC',1.1,1.1,1.1]],columns=['Maturity','Date','Ticker','Bid','Mid','Offer'])
        currencies = pd.DataFrame([[dt.datetime(2008,1,1,0,0,0),1.1,'ABC']],columns=['Date','px_last','Ticker'])
        if i<4:
            helper.upload_df(tmp,tablas[i],first_time=True)
        else:
            helper.upload_df(currencies,tablas[i],first_time=True)

    return 0
