#Note: falta mejorar mensajes
#version 2.0
################# Libraries #######################
import QuantLib as ql
from qlChileCal import *
from pgLoader import *
from datetime import datetime
from pandas.tseries.offsets import *
from scipy.interpolate import CubicSpline, interp1d
import pandas as pd
import numpy as np
################# Helper Functions #################
##Builds QuantLib Curve object
def get_curve(date,swap,currency = 'CLP', clp_curve = 'Swap'):
    calendar = create_calendar_chile(2001,50)
    dayCounter_Act360 = ql.Actual360()
    settlement_days_icp = 2
    # OIS quotes up to 20 years
    ICP = ql.OvernightIndex("ICP", settlement_days_icp, ql.CLPCurrency(), calendar, dayCounter_Act360)
    fixingDays = 0
    #Build curve depending on the source currency.
    if currency == 'CLP':
        # Build curve from already boostrapped Zero Rates or Swap Curve.
        if clp_curve == 'Swap':
            TPM = swap[0]
            months = [3,6,9,12,18]
            swap_month = swap[1:6]
            years =[2,3,4,5,6,7,8,9,10,15,20]
            swap_years = swap[6:]
            helpers = [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(TPM/100)),
                                         ql.Period(1,ql.Days), fixingDays,
                                         calendar, ql.Unadjusted, False, ql.Actual360())]

            helpers += [ql.OISRateHelper(settlement_days_icp, ql.Period(months,ql.Months),
                                             ql.QuoteHandle(ql.SimpleQuote(rate/100)),ICP)
                                             for rate, months in zip(swap_month,months)]

            helpers += [ql.OISRateHelper(settlement_days_icp, ql.Period(years,ql.Years),
                                             ql.QuoteHandle(ql.SimpleQuote(rate/100)),ICP)
                                             for rate, years in zip(swap_years,years)]
        if clp_curve == 'Zero':
            TPM = swap[0]
            months = [3,6,9,12,18]
            swap_month = swap[1:6]
            years =[2,3,4,5,6,7,8,9,10,15,20]
            swap_years = swap[6:]
            helpers = [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(TPM/100)),
                                         ql.Period(1,ql.Days), fixingDays,
                                         calendar, ql.Unadjusted, False, ql.Actual360())]

            helpers += [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)),
                                         ql.Period(months,ql.Months), settlement_days_icp,
                                         calendar, ql.Unadjusted, False, ql.Actual360())
                                         for rate, months in zip(swap_month,months)]

            helpers += [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)),
                                         ql.Period(years,ql.Years), settlement_days_icp,
                                         calendar, ql.Unadjusted, False, ql.Actual360())
                                         for rate, years in zip(swap_years,years)]
    else:
        months = [3,6,12,18]
        swap_month = swap[0:3]
        years =[2,3,4,5,6,7,8,9,10,15,20]
        swap_years = swap[4:]
        helpers = []

        helpers += [ql.OISRateHelper(settlement_days_icp, ql.Period(months,ql.Months),
                                         ql.QuoteHandle(ql.SimpleQuote(rate/100)),ICP)
                                         for rate, months in zip(swap_month,months)]

        helpers += [ql.OISRateHelper(settlement_days_icp, ql.Period(years,ql.Years),
                                         ql.QuoteHandle(ql.SimpleQuote(rate/100)),ICP)
                                         for rate, years in zip(swap_years,years)]
    #Define type of curve interpolation 
    icp_curve = ql.PiecewiseCubicZero(date, helpers, ql.Actual360())
    #Enable Extrapolation
    icp_curve.enableExtrapolation()
    return icp_curve
##Builds Bond with specific cashflow structures.
def get_bond(issueDate,maturityDate,tir,notional = 100,bond_type ='Zero',couponRate=None,payments=None,currency = 'CLP',infla = None,cashflows=None):
    #Standard Calendar
    calendar = ql.NullCalendar()
    #Basic Parameters for chilean bonds
    coupon_dayCount = ql.Unadjusted
    payment_convention = ql.Following
    dateGeneration = ql.DateGeneration.Forward
    monthEnd = False
    settlementDays = 0
    #First Calculate if the bond is a term deposit, simplest case:
    if bond_type == 'Zero':
        if currency =='CLP':

            #Future Value
            fv = notional*(1+tir*(maturityDate-issueDate)/360)
            #Deposit Object
            fixedRateBond = ql.ZeroCouponBond(settlementDays,
                                              calendar,
                                              fv,
                                              maturityDate,
                                              coupon_dayCount)
            #Rate Object
            rate = ql.InterestRate(tir,
                                   ql.Actual360(),
                                   ql.Simple,
                                   ql.Annual)
            #NPV
            npv = ql.CashFlows.npv(fixedRateBond.cashflows(),
                                   rate,
                                   True)

            return [fixedRateBond, npv]
        elif currency == 'UF':
            #Get Today's UF
            date = ql.Settings.instance().evaluationDate
            date = ql_to_dt(date)
            tod_uf = infla[infla['Dates']==date]['UF'].iloc[0]

            #Get Maturity proy. UF
            date = ql_to_dt(maturityDate)
            mat_uf = infla[infla['Dates']==date]['UF'].iloc[0]

            #UF Deposit, FV UF and UF NPV
            rate = ql.InterestRate(tir,ql.Actual360(),ql.Simple,ql.Annual)
            fv_uf = notional*(1+tir*(maturityDate-issueDate)/360)*100
            cashflow =  ql.Leg([ql.SimpleCashFlow(fv_uf,maturityDate)])
            npv_uf = ql.CashFlows.npv(cashflow,
                                      rate,
                                      True)
            fixedRateBond_uf = ql.ZeroCouponBond(settlementDays,
                                                 calendar,
                                                 fv_uf,
                                                 maturityDate,
                                                 coupon_dayCount)

            #CLP Deposit, FV CLP and CLP NPV
            npv_clp = npv_uf*tod_uf/10000
            fv_clp = fv_uf*mat_uf/10000
            fixedRateBond_clp = ql.ZeroCouponBond(settlementDays,
                                                  calendar,
                                                  fv_clp,
                                                  maturityDate,
                                                  coupon_dayCount)
            return [fixedRateBond_clp, npv_clp,fixedRateBond_uf,npv_uf]

        elif currency == 'USD':
            return None
    ## Else if not Zero, then its a bond
    #Define CashFlows frecuency
    if payments == 'SEMESTRAL':
        tenor = ql.Period(ql.Semiannual)
    if payments == 'TRIMESTRAL':
        tenor = ql.Period(ql.Quarterly)
    if payments == 'MENSUAL':
        tenor = ql.Period(ql.Semmianual)
    if 'CADA' in payments:
        x = int(payments.raplace('CADA ','').replace(' MESES',''))
        tenor = ql.Period(x,ql.Months)

    if bond_type == 'Bullet' or bond_type=='LH':
        interest_dayCount = ql.Thirty360()
        coupons = [couponRate]
        schedule = ql.Schedule (issueDate,
                                maturityDate,
                                tenor,
                                calendar,
                                coupon_dayCount,
                                payment_convention,
                                dateGeneration,
                                monthEnd)

        if currency == 'CLP':
            fixedRateBond = ql.FixedRateBond(settlementDays,
                                            notional,
                                            schedule,
                                            coupons,
                                            interest_dayCount)

            rate = ql.InterestRate(tir,
                                   ql.Actual365Fixed(),
                                   ql.Compounded,
                                   ql.Annual)

            npv = ql.CashFlows.npv(fixedRateBond.cashflows(),rate,True)
            return [fixedRateBond , npv]

        elif currency == 'UF':
            #Parameters for UF indexed bond
            #Evaluation Date
            date = ql.Settings.instance().evaluationDate
            date = ql_to_dt(date)
            eval_uf = infla[infla['Dates']==date]['UF'].iloc[0]

            fixedRateBond_uf = ql.FixedRateBond(settlementDays,
                                                notional,
                                                schedule,
                                                coupons,
                                                interest_dayCount)

            rate = ql.InterestRate(tir,ql.Actual365Fixed(),ql.Compounded,ql.Annual)
            npv_uf = ql.CashFlows.npv(fixedRateBond_uf.cashflows(),rate,True)

            npv_clp = npv_uf * eval_uf
            clp_notional = eval_uf*notional

            proyected_cashflows = []
            for i in fixedRateBond.cashflows():
                future_date = ql_to_dt(i.date())
                uf = infla[infla['Dates']==future_date]['UF']
                if uf.empty:
                    uf = 0
                    issueDate = i.date()
                else:
                    proyected_uf = infla[infla['Dates']==future_date]['UF'].iloc[0]
                    proyected_clp = i.amount()*proyected_uf
                    proyected_cashflows.append(ql.SimpleCashFlow(proyected_clp,i.date()))


            final_cashflows = ql.Leg(proyected_cashflows)
            fixedRateBond_clp = ql.Bond(settlementDays,
                                        calendar,
                                        clp_notional,
                                        maturityDate,
                                        issueDate,
                                        final_cashflows)

            return [fixedRateBond_clp, npv_clp,fixedRateBond_uf,npv_uf]

        elif currency == 'USD':
            return None
    elif bond_type == 'Amortizable' or bond_type == 'Other':
        return None
#Gets Bond Z-spread.
def get_zspread(npv,fixedRateBond,yieldcurve):
    z_spread = ql.CashFlows.zSpread(fixedRateBond.cashflows(),npv,yieldcurve,ql.Actual360(),ql.Compounded,ql.Semiannual,True)*100
    return round(z_spread,2)
## Builds 2y and 20y uf list to price bonds cashflows.
def uf_fwd(today,prices,dates,values ='UF'):
    #dates = [datetime.strptime(x, '%d/%m/%Y') for x in dates]
    ipc = []
    adj_uf = [prices[0]]
    contractDates = []
    periodDates = [dates[0]]
    finalDates = [dates[0]]
    proyUF = []
    counter = 0
    periodDays = []
    proyUF = [prices[0]]
    pi = [0]

    if len(prices)!=len(dates):
        raise ValueError('Length of UF and Dates must be equal.')

    for i in range(len(prices)-1):
        #Periods and adjusted IPC
        if i == 0:
            start_contractPeriod = dates[i]
            next_contractPeriod = dates[i+1]

            start_Period = datetime(dates[i].year,dates[i].month,9)
            next_Period = datetime(dates[i+1].year,dates[i+1].month,9)
            dt = (next_Period-start_Period).days/(next_contractPeriod - start_contractPeriod).days

            ipc.append((prices[i+1]/prices[i])**(dt)-1)
        else:

            start_Period = datetime(dates[i].year,dates[i].month,9)
            start_contractPeriod = start_Period
            next_contractPeriod = dates[i+1]

            next_Period = datetime(dates[i+1].year,dates[i+1].month,9)
            dt = (next_Period-start_Period).days/(next_contractPeriod - start_contractPeriod).days

            adj_uf.append(adj_uf[-1]*(1+ipc[-1]))
            ipc.append((prices[i+1]/adj_uf[i])**(dt)-1)

        periodDays.append((next_Period-start_Period).days)
        contractDates.append(start_contractPeriod)
        periodDates.append(next_Period)

    totalDays = (periodDates[-1] - periodDates[0]).days

    j= 0
    for i in range(totalDays):
        finalDates.append(finalDates[-1]+Day(1,normalize=True))
        counter +=1
        if counter > periodDays[j]:
            counter = 1
            j +=1

        nextUF =  proyUF[-1]*(1+ipc[j])**(1/periodDays[j])
        proyUF.append(nextUF)
        pi.append((proyUF[-1]/proyUF[0]-1)*360/(i+1))

    datatable = {'Dates': finalDates,'UF': proyUF,'PI': pi}
    datatable = pd.DataFrame.from_dict(datatable)

    if values =='UF':
        px = interpol(datatable.index,proyUF)
    elif values =='PI':
        px = interpol(datatable.index,pi)
    elif values =='Datatable':
        px = datatable
    return px
def uf_list(date_dt,infla,yieldcurve_clp,yieldcurve_uf):
    #Quantlib day_count, compounding and frequency convention
    day_count = ql.Actual360()
    compounding = ql.Simple
    freq = ql.Annual
    #Todays UF
    actual_uf = infla[infla['Dates']==date_dt]['UF'].iloc[0]
    #Today date in quantlib format from datetime format
    today_date_ql = ql.Date(date_dt.day,date_dt.month,date_dt.year)
    size = len(infla)
    dates = []
    ufs = []
    i = 0
    for i in range(7300- size):
        #next date to calculate UF
        i+=1
        calc_date = infla['Dates'].iloc[-1] + Day(i,normalize=True)
        aux_date_ql = ql.Date(calc_date.day,calc_date.month,calc_date.year)
        yrs = day_count.yearFraction(today_date_ql,aux_date_ql)

        rate_uf = yieldcurve_uf.zeroRate(yrs, compounding, freq).rate()
        rate_clp = yieldcurve_clp.zeroRate(yrs, compounding, freq).rate()
        next_uf = (1+rate_clp*yrs)*actual_uf/(1+rate_uf*yrs)

        dates.append(calc_date)
        ufs.append(next_uf)

    tmp = pd.DataFrame.from_dict({'Dates': dates,'UF': ufs})
    final = pd.concat([infla,tmp],ignore_index=True)
    return final
## Auxiliary functions
def print_amorttable(fixedRateBond):
    for i in fixedRateBond.cashflows():
        print(i.date(),i.amount())
def print_zero(date,yieldcurve):
    day_count = ql.Actual360()
    spots = []
    dates = []
    tenors = []
    df = []
    for d in yieldcurve.dates():
        yrs = day_count.yearFraction(date, d)
        df.append(yieldcurve.discount(d))
        dates.append(d)
        compounding = ql.Simple
        freq = ql.Annual
        zero_rate = yieldcurve.zeroRate(yrs, compounding, freq)
        tenors.append(yrs)
        eq_rate = zero_rate.equivalentRate(day_count,compounding,freq,date,d).rate()
        zero_rate.equivalentRate(day_count,compounding,freq,date,d).rate()
        spots.append(100*eq_rate)

    datatable = {'Dates':dates,'Years': tenors,'DF':df,'Zero': spots}
    datatable = pd.DataFrame.from_dict(datatable)
    print(datatable)
def ql_to_dt(date):
    d = date.dayOfMonth()
    m = date.month()
    y = date.year()
    date_str = str(d) + '/' + str(m) + '/' + str(y)
    date_dt = datetime.strptime(date_str, '%d/%m/%Y')
    return date_dt
def dt_to_ql(date):
    d = date.day
    m = date.month
    y = date.year
    date_ql = ql.Date(d,m,y)
    return date_ql
def run_example(yieldcurve_clp=None,infla_20y=None):
    ############ Bond Example, BCP0450620 ############
    issueDate = ql.Date(1,6,2015)
    maturityDate = ql.Date(1,6,2020)
    payments = 'SEMESTRAL'
    bond_type ='Bullet'
    currency = 'CLP'
    couponRate = 4.5/100
    tir = 3.22/100

    irf_objects = get_bond(issueDate,maturityDate,tir,bond_type,couponRate,payments,currency,infla_20y)
    print('BTP0450326')
    print_amorttable(irf_objects[0])
    print('NPV: ',irf_objects[1])

    ## Get z-spread
    try:
        z_spread = get_zspread(npv,bond,yieldcurve_clp)
        print('z-spread: ', z_spread)
    except:
        pass    
    ##################################################
## This function depends on how you store your data in de database.    
def define_queries (date,clp_curve = 'Swap'):
    if clp_curve == 'Swap':
        q_swap_clp = 'Select \"Mid\" from swap_clp where \"Date\"= \'' + date + '\';'
    else:
        q_swap_clp = 'Select \"Zero\" from swap_clp where \"Date\"= \'' + date + '\';'
    q_swap_uf = 'Select \"Mid\" from swap_uf where \"Date\"= \'' + date + '\';'
    q_fwd_uf = 'Select \"Bid\" from fwd_uf where \"Date\"= \'' + date + '\';'
    q_fwd_uf_dates = 'Select \"Maturity\" from fwd_uf where \"Date\"= \'' + date + '\';'
    q_irf = 'Select * from irf where \"Fecha\"= \'' + date + '\';'
    q_iif = 'Select * from iif where \"Fecha\"= \'' + date + '\';'
    q_series = 'Select * from \"series\";'
    return [q_swap_clp,q_swap_uf,q_fwd_uf,q_fwd_uf_dates,q_irf,q_iif,q_series]
