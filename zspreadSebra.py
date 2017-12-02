################# Libraries #################

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
def get_curve(date,swap,currency = 'CLP'):

	## Swap Instrument Parameters
    calendar = create_calendar_chile(2001,50)
    bussiness_convention = ql.Unadjusted
    day_count = ql.Actual360()
    month_end = False
    fixedLegAdjustment = ql.Unadjusted

    ## OVernight index definition
    settlementDays = 0
    ICP = ql.IborIndex('ICP',ql.Period(1,ql.Days),0,ql.CLPCurrency(),calendar,ql.Unadjusted,month_end,day_count)

    ## If currency=CLP then add TPM as 1 day deposit rate
    if currency == 'CLP':
        depo_helper = [ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(swap[0]/100)),ql.Period(1,ql.Days),settlementDays,calendar,bussiness_convention,month_end,day_count)]
    else:
        depo_helper = []

    ## Swap tenors in months and years
    terms = [3,6,9,12,18,2,3,4,5,6,7,8,9,10,12,15,20]
    settlementDays = 2

    ## Define Rate helpers
    swap_helpers = []
    for i in range(len(terms)):


        if i < 5:
            ## Zero coupon swaps (tenors < 18 months)
            fixedLegFrequency = ql.Once
            tenor = ql.Period(terms[i],ql.Months)
            rate = swap[i]
            depo_helper.append(ql.DepositRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100)),tenor,settlementDays,calendar,bussiness_convention,False,ql.Actual360()))
        else:
            ## Semmianual payments for swaps longer than 18 months
            fixedLegFrequency = ql.Semiannual
            tenor = ql.Period(terms[i],ql.Years)
            rate = swap[i]
            swap_helpers.append(ql.SwapRateHelper(ql.QuoteHandle(ql.SimpleQuote(rate/100.0)),tenor, calendar,fixedLegFrequency, fixedLegAdjustment,day_count,ICP))

    #Yield Curve
    rate_helpers = depo_helper + swap_helpers
    yieldcurve = ql.PiecewiseFlatForward(date,rate_helpers,day_count)
    return yieldcurve
##Builds Bond with specific cashflow structure
def get_bond(issueDate,maturityDate,tir,bond_type = 'Zero',couponRate=None,payments=None,currency = 'CLP',infla = None,cashflows=None):
    #Standard Calendar
    calendar = ql.NullCalendar()

    if bond_type == 'Zero':
        if currency =='CLP':
            faceValue = 100
            redemption = 100*(1+tir*(maturityDate-issueDate)/360)
            settlementDays = 0
            fixedRateBond = ql.ZeroCouponBond(settlementDays,calendar,faceValue,maturityDate,ql.Unadjusted,redemption,issueDate)
            rate = ql.InterestRate(tir,ql.Actual360(),ql.Simple,ql.Annual)
            npv = ql.CashFlows.npv(fixedRateBond.cashflows(),rate,True)
            return fixedRateBond, npv

        elif currency == 'UF':
            date = ql.Settings.instance().evaluationDate
            date = ql_to_dt(date)
            tod_uf = infla[infla['Dates']==date]['UF'].iloc[0]
            date = ql_to_dt(maturityDate)
            mat_uf = infla[infla['Dates']==date]['UF'].iloc[0]

            faceValue = tod_uf
            redemption = (1+tir*(maturityDate-issueDate)/360)*mat_uf
            settlementDays = 0
            fixedRateBond = ql.ZeroCouponBond(settlementDays,calendar,faceValue,maturityDate,ql.Unadjusted,redemption,issueDate)
            rate = ql.InterestRate(tir,ql.Actual360(),ql.Simple,ql.Annual)
            npv = ql.CashFlows.npv(fixedRateBond.cashflows(),rate,True)
            print(faceValue,redemption)
            return fixedRateBond, npv


    #Basic Parameters for chilean bonds
    coupon_dayCount = ql.Unadjusted
    payment_convention = ql.Following
    dateGeneration = ql.DateGeneration.Forward
    monthEnd = False
    settlementDays = 1

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
        faceValue = 100
        schedule = ql.Schedule (issueDate, maturityDate, tenor, calendar, coupon_dayCount,payment_convention, dateGeneration, monthEnd)

        if currency == 'CLP':

            fixedRateBond = ql.FixedRateBond(settlementDays, faceValue, schedule, coupons, interest_dayCount)
            rate = ql.InterestRate(tir,ql.Actual365Fixed(),ql.Compounded,ql.Semiannual)
            npv = ql.CashFlows.npv(fixedRateBond.cashflows(),rate,True)
            return fixedRateBond , npv

        elif currency == 'UF':
            date = ql.Settings.instance().evaluationDate
            date = ql_to_dt(date)

            adj_cashflows = []
            fixedRateBond = ql.FixedRateBond(settlementDays, faceValue, schedule, coupons, interest_dayCount)
            rate = ql.InterestRate(tir,ql.Actual365Fixed(),ql.Compounded,ql.Semiannual)
            npv_uf = ql.CashFlows.npv(fixedRateBond.cashflows(),rate,True)

            npv_clp = npv_uf * infla[infla['Dates']==date]['UF'].iloc[0]/10000
            faceValue = infla[infla['Dates']==date]['UF'].iloc[0]/10000

            for i in fixedRateBond.cashflows():
                date = ql_to_dt(i.date())
                uf = infla[infla['Dates']==date]['UF']
                if uf.empty:
                    uf = 0
                    issueDate = i.date()
                else:
                    uf = infla[infla['Dates']==date]['UF'].iloc[0]
                    amount = i.amount()*uf/10000
                    adj_cashflows.append(ql.SimpleCashFlow(amount,i.date()))


            cashflows = ql.Leg(adj_cashflows)
            fixedRateBond = ql.Bond(settlementDays,calendar,faceValue,maturityDate,issueDate,cashflows)
            return fixedRateBond, npv_clp

        elif currency == 'USD':
            fixedRateBond = ql.FixedRateBond(settlementDays, faceValue, schedule, coupons, interest_dayCount)
            return fixedRateBond
    elif bond_type == 'Amortizable':
        faceValue = 100
        fixedRateBond = ql.Bond(settlementDays,calendar,faceValue,issueDate,maturityDate,cashflows)
        return fixedRateBond

#Gets Bond Zspread
def get_zspread(npv,fixedRateBond,yieldcurve,z_spread=0):
	#Setup Disc. curves.
    #zSpreadQuoteHandle = ql.QuoteHandle(ql.SimpleQuote(z_spread))
    #discountingTermStructure = ql.RelinkableYieldTermStructureHandle()
    #discountingTermStructure.linkTo(yieldcurve)
    #zSpreadedTermStructure = ql.ZeroSpreadedTermStructure(discountingTermStructure, zSpreadQuoteHandle)
    #zSpreadRelinkableHandle = ql.RelinkableYieldTermStructureHandle()
    #zSpreadRelinkableHandle.linkTo(zSpreadedTermStructure)
    #bondEngine_with_added_zspread = ql.DiscountingBondEngine(zSpreadRelinkableHandle)
    #fixedRateBond.setPricingEngine(bondEngine_with_added_zspread)
    z_spread = ql.CashFlows.zSpread(fixedRateBond.cashflows(),npv,yieldcurve,ql.Actual360(),ql.Compounded,ql.Semiannual,False)*100

    #z_spread = ql.BondFunctions.zSpread(fixedRateBond, market_value,yieldcurve, ql.Actual360(), ql.Compounded, ql.Semiannual, today)*100

    return z_spread
## Builds 2y and 20y uf list to price bonds cashflows
def uf_fwd(today,prices,dates,values ='UF'):
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
## Auxiliary functions to print data
def print_amorttable(fixedRateBond):
    for i in fixedRateBond.cashflows():
        print(i.date(),i.amount())
def print_zero(date,yieldcurve):
    day_count = ql.Actual360()
    spots = []
    tenors = []
    for d in yieldcurve.dates():
        yrs = day_count.yearFraction(date, d)
        compounding = ql.Simple
        freq = ql.Annual
        zero_rate = yieldcurve.zeroRate(yrs, compounding, freq)
        tenors.append(yrs)
        eq_rate = zero_rate.equivalentRate(day_count,compounding,freq,date,d).rate()
        spots.append(100*eq_rate)

    datatable = {'Tenor': tenors,'Tasas Zero': spots}
    datatable = pd.DataFrame.from_dict(datatable)
    print(datatable)
def ql_to_dt(date):
    d = date.dayOfMonth()
    m = date.month()
    y = date.year()
    date_str = str(d) + '/' + str(m) + '/' + str(y)
    date_dt = datetime.strptime(date_str, '%d/%m/%Y')
    return date_dt

################# Date Parameters #################

## Get Today's date
now = [datetime.now().day,datetime.now().month,datetime.now().year]

## Date variable used for queries in postGRE
date_str = str(now[0]) + '/' + str(now[1]) + '/' + str(now[2])

## Date variable used in Quantlib
date_ql = ql.Date(now[0],now[1],now[2])
ql.Settings.instance().evaluationDate = date_ql

## Aux date for testing
date = '02/11/2017'
date_ql = ql.Date(2,11,2017)
ql.Settings.instance().evaluationDate = date_ql

## Date variable used in pandas and others
date_dt = datetime.strptime(date, '%d/%m/%Y')

################# Collect Data #################

## Create dataManager
helper = dataManager()

## Get CLP Swap Data
query = 'Select \"Mid\" from swap_clp where \"Fecha\"= \'' + date + '\';'
swap_clp = helper.get_raw_data(query)

TPM = 2.5
swap_clp.insert(0,TPM)

## Get UF Swap Data
query = 'Select \"Mid\" from swap_uf where \"Fecha\"= \'' + date + '\';'
swap_uf = helper.get_raw_data(query)

## Get UF FWD Data
query = 'Select \"Bid\" from fwd_uf where \"Fecha\"= \'' + date + '\';'
fwd_uf = helper.get_raw_data(query)
query = 'Select \"Date\" from fwd_uf where \"Fecha\"= \'' + date + '\';'
uf_dates = helper.get_raw_data(query)
    ## UF Fwd data cleaning and proccesing
uf_dates = [x.replace(tzinfo=None) for x in uf_dates]
first_date = dt.datetime(2017,10,9,0,0)
first_uf = 26672.77

#Bonds Data
query = 'Select * from irf where \"Fecha\"= \'' + date + '\';'
bonds = helper.get_df(query)

################# Rate curve building #################

#Swap Bootstrapping
yieldcurve_clp = get_curve(date_ql,swap_clp)
yieldcurve_uf = get_curve(date_ql,swap_uf,currency='UF')

##UF Full List
fwd_uf.insert(0,first_uf)
uf_dates.insert(0,first_date)
fwd_uf.insert(1,26619.42)
uf_dates.insert(1,dt.datetime(2017,11,9,0,0))

infla_2y = uf_fwd(date_dt,fwd_uf,uf_dates,values='Datatable')
infla_20y = uf_list(date_dt,infla_2y,yieldcurve_clp,yieldcurve_uf)



############ Bond Example, BTP0450326 ############
issueDate = ql.Date(1,3,2015)
maturityDate = ql.Date(1,3,2026)
payments = 'SEMESTRAL'
bond_type ='Bullet'
currency = 'CLP'
couponRate = 4.5/100
tir = 3/100

bond , npv = get_bond(issueDate,maturityDate,tir,bond_type,couponRate,payments,currency,infla_20y)
print('BTP0450326')
print_amorttable(bond)

## Get z-spread
z_spread = get_zspread(npv,bond,yieldcurve_clp)
print('z-spread: ', z_spread)
##################################################

############ Bond Example, BTP0450326 ############
issueDate = ql.Date(1,3,2012)
maturityDate = ql.Date(1,3,2022)
payments = 'SEMESTRAL'
bond_type ='Bullet'
currency = 'UF'
couponRate = 3/100
tir = 1.37/100

bond , npv = get_bond(issueDate,maturityDate,tir,bond_type,couponRate,payments,currency,infla_20y)

print('\nBono UF')
print_amorttable(bond)

## Get z-spread
z_spread = get_zspread(npv,bond,yieldcurve_clp)
print('z-spread: ', z_spread)

##################################################

############ Deposit CLP ############
issueDate = date_ql
maturityDate = ql.Date(1,1,2018)
currency = 'CLP'
tir = 0.23*12/100

bond , npv = get_bond(issueDate,maturityDate,tir,currency=currency,infla = infla_20y)

print('\nDeposito')
print_amorttable(bond)

## Get z-spread
z_spread = get_zspread(npv,bond,yieldcurve_clp)
print('z-spread: ', z_spread)

############ Deposit UF ############
issueDate = date_ql
maturityDate = ql.Date(1,1,2018)
currency = 'UF'
tir = 1.23/100

bond , npv = get_bond(issueDate,maturityDate,tir,currency=currency,infla = infla_20y)

print('\nDeposito')
print_amorttable(bond)

## Get z-spread
z_spread = get_zspread(npv,bond,yieldcurve_clp)
print('z-spread: ', z_spread)




##################################################
