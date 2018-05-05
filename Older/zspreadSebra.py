#version 1.0
################# Libraries #######################
import QuantLib as ql
from pgLoader import *
from datetime import datetime
import pandas as pd
from bondTools import *
#######################################################
#Aux function for printing progress in console.
def progressBar(value, endvalue, bar_length=20):    
        percent = float(value) / endvalue
        arrow = '-' * int(round(percent * bar_length)-1) + '>'
        spaces = ' ' * (bar_length - len(arrow))
        sys.stdout.write("\rPercent: [{0}] {1}%".format(arrow + spaces, int(round(percent * 100))))        
        sys.stdout.flush()
################# Main Process #######################        
def main(clp_curve,date=None):
    ################# Date Parameters #################    
    #Define the date which will be processed.
    if date == None:
    ## Get Today's date
        now = [datetime.now().day,datetime.now().month,datetime.now().year]
    ## Date variable used for queries in postGRE
        date_str = str(now[0]) + '/' + str(now[1]) + '/' + str(now[2])
    ## Date variable used in Quantlib
        date_ql = ql.Date(now[0],now[1],now[2])
    ## Date variable used in pandas and others
        date_dt = datetime.strptime(date_str, '%d/%m/%Y')
    else:
        date_str = str(date[0:2]) + '/' + str(date[2:4]) + '/' + str(date[4:8])
        date_dt =  datetime.strptime(date_str, '%d/%m/%Y')
        date_ql = ql.Date(date_dt.day,date_dt.month,date_dt.year)

    print('Loading ' + date_str)
    print('Setting global parameters...')
    
    ql.Settings.instance().evaluationDate = date_ql
    #######################################################
    
    ################# Collect Data ########################
    print('Collecting data from DB...')
    ## Create dataManager
    helper = dataManager()
    ## Get CLP Swap Data
    queries = define_queries(date_str,clp_curve=clp_curve)
    swap_clp = helper.get_raw_data(queries[0])

    ## Get UF Swap Data
    swap_uf = helper.get_raw_data(queries[1])
    ## Get UF FWD Data
    fwd_uf = helper.get_raw_data(queries[2])

    uf_dates = helper.get_raw_data(queries[3])
    #Bonds Data
    bonds = helper.get_df(queries[4])
    #Term Deposit Data
    daps = helper.get_df(queries[5])
    #Series Data
    series = helper.get_df(queries[6])
    #######################################################

    ################# Rate curve building #################
    print('Building Curve Objects...')
    #Swap Bootstrapping
    yieldcurve_clp = get_curve(date_ql,swap_clp,clp_curve=clp_curve)
    yieldcurve_uf = get_curve(date_ql,swap_uf,currency='UF')
    infla_2y = uf_fwd(date_dt,fwd_uf,uf_dates,values='Datatable')
    infla_20y = uf_list(date_dt,infla_2y,yieldcurve_clp,yieldcurve_uf)
    #######################################################
    
    ########## Calculating Z-Spread Depostis #################
    print('\nCalculating Z-Spreads Daps... ' )
    z_spreads_dap = []
    folio_dap = []
    for i in range(len(daps)):
        progressBar(i+1,len(daps))
        #Issuer
        issuer = daps['Emisor'].iloc[i]
        #Dates
        n_day = daps['Días'].iloc[i]
        issueDate = date_ql
        maturityDate = date_ql + n_day
        mat_date = str(maturityDate.dayOfMonth()) + '/' + str(maturityDate.month()) + '/' + str(maturityDate.year())
        #Amount & Others
        folio_dap.append(daps['Folio'].iloc[i])

        if daps['Moneda'].iloc[i] == 'CH$':
            rate = daps['Tasa'].iloc[i]*12/100
            irf_obj = get_bond(issueDate,maturityDate,rate,currency='CLP',infla = infla_20y)
            bond = irf_obj[0]
            npv = irf_obj[1]
            z_spread = get_zspread(npv,bond,yieldcurve_clp)
            z_spreads_dap.append(z_spread)
        elif daps['Moneda'].iloc[i] == 'UF':
            rate = daps['Tasa'].iloc[i]/100
            irf_obj = get_bond(issueDate,maturityDate,rate,currency='UF',infla = infla_20y)
            bond = irf_obj[0]
            npv = irf_obj[1]
            z_spread = get_zspread(npv,bond,yieldcurve_clp)
            #print('Currency: UF','Emisor:',issuer,'Days:',n_day,'Rate:',rate,'Z-Spread:',z_spread)
            z_spreads_dap.append(z_spread)
        else:
            rate = daps['Tasa'].iloc[i]/100
            z_spreads_dap.append('NA')

    iif = {'Zspread':z_spreads_dap,'Date': date_dt,'Folio':folio_dap}
    iif = pd.DataFrame.from_dict(iif)
    #######################################################
    print('Calculating Z-Spreads Bonds...')
    z_spreads = []
    folio_irf = []

    for i in range(len(bonds)):
        progressBar(i+1,len(bonds))
        currency = bonds['Reaj.'].iloc[i]
        tir = bonds['TIR'].iloc[i]/100
        instrument = bonds['Instrumento'].iloc[i]
        folio_irf.append(bonds['Folio'].iloc[i])
        try:
            issuer = series[series['Serie']==instrument]['Emisor'].iloc[0]
            issueDate = dt_to_ql(series[series['Serie']==instrument]['Fec.Emisión'].iloc[0])
            maturityDate = dt_to_ql(series[series['Serie']==instrument]['Fec.Vcto.'].iloc[0])
            couponRate = series[series['Serie']==instrument]['T.Emisión'].iloc[0]/100
            payments = series[series['Serie']==instrument]['Pago'].iloc[0]
            amorts = series[series['Serie']==instrument]['Amort.'].iloc[0]
            rating = series[series['Serie']==instrument]['Riesgo'].iloc[0]
            if amorts == 1:
                bond_type = 'Bullet'
            else:
                bond_type = 'Amortizable'
            if currency == '$':
                irf_obj = get_bond(issueDate,
                                   maturityDate,
                                   tir,
                                   bond_type,
                                   couponRate,
                                   payments,
                                   currency = 'CLP',
                                   infla = infla_20y)

                bond = irf_obj[0]
                npv = irf_obj[1]

            elif currency == 'UF':
                irf_obj = get_bond(issueDate,
                                   maturityDate,
                                   tir,
                                   bond_type,
                                   couponRate,
                                   payments,
                                   currency = 'UF',
                                   infla = infla_20y)

                bond = irf_obj[0]
                npv = irf_obj[1]

            z_spread = get_zspread(npv,bond,yieldcurve_clp)
            z_spreads.append(z_spread)
        except:
            z_spreads.append('NA')
    irf = {'Zspread':z_spreads,'Date':date_dt,'Folio':folio_irf}
    irf = pd.DataFrame.from_dict(irf)
    #######################################################
    print('Uploading ICP Daps...')
    helper.upload_df(iif,'icp_daps',first_time=True)
    print('Table Saved.')
    print('Uploading ICP Bonds...')
    helper.upload_df(irf,'icp_bonds',first_time=True)
    print('Table Saved.')
    #######################################################

#Test case.
if __name__ == '__main__':
    try:
        main(clp_curve='Zero',date='18/01/2018')
    except (KeyboardInterrupt, SystemExit):
        raise
