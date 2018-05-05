"""
Author: Jose Melo
Basic CL Curve Objects derived from QL curves.

This file contains a support object, ICPCurve, to make easier to define the local swap
curves with QuantLib. The other two classes, ShortTermUFValues and LongTermUFValues,
contain proyected UF values, derived from UF Forward quotes and UF/CAM swaps. At the
end of the file can be found example functions of the usage.
"""
import QuantLib as ql
from CLAux import PyObserver, CalendarCl
from pgLoader import dataManager
from collections import OrderedDict

class ICPCurve(ql.PiecewiseFlatForward):
    """
        Curve object to simplify the building of local curves via swap quotes.
        Supports CLP/CAM and UF/CAM swap and zero curve.
    """
    def __init__(self, date, swap_rates, cl_currency, type='Zero'):
        self.date = date
        self.swap_rates = swap_rates
        self.cl_currency = cl_currency
        self.type = type

        if self.cl_currency == 'CLP':
            self.tenors = [1,3,6,9,12,18,2,3,4,5,6,7,8,9,10,15,20]
        else:
            self.tenors = [3,6,9,12,2,3,4,5,6,7,8,9,10,15,20]

        self.swap_rates = swap_rates

        self.defineParameters()
        self.initHelpers()
        super(ICPCurve,self).__init__(date, self.helpers, ql.Actual360())
        self.enableExtrapolation()
    def initHelpers(self):
        self.helpers = []
        handle = ql.YieldTermStructureHandle()
        if self.cl_currency == 'CLP':
            if self.type == 'Swap':
                for i in range(len(self.tenors)):
                    if i == 0:
                        self.helpers += [ql.DepositRateHelper(ql.QuoteHandle(self.swap_rates[i]),
                                        ql.Period(1,ql.Days),
                                        self.fixing_days,
                                        self.calendar,
                                        ql.Unadjusted,
                                        False,
                                        ql.Actual360())]
                        continue
                    elif i < 6 and i > 0:
                        period = ql.Period(self.tenors[i], ql.Months)
                        frequency = ql.Monthly
                    elif i >=6:
                        period = ql.Period(self.tenors[i], ql.Years)
                        frequency = ql.Years

                    self.helpers += [ql.OISRateHelper(self.settlement_days,
                                    period,
                                    ql.QuoteHandle(self.swap_rates[i]),
                                    self.ICP,
                                    handle,
                                    False,
                                    0,
                                    ql.Following,
                                    frequency)]

            if self.type == 'Zero':
                for i, quote in enumerate(self.helpers_dict):
                    if i == 0:
                        period = ql.Period(1, ql.Days)
                    elif i < 6:
                        period = ql.Period(self.tenors[i], ql.Months)
                    else:
                        period = ql.Period(self.tenors[i], ql.Years)

                    self.helpers += [ql.DepositRateHelper(ql.QuoteHandle(self.swap_rates[i]),
                                period,
                                fixingDays,
                                calendar,
                                ql.Unadjusted,
                                False,
                                ql.Actual360())]
        elif self.cl_currency == 'UF':
            for i in range(len(self.tenors)):
                if i <= 4:
                    period = ql.Period(self.tenors[i],ql.Months)
                    frequency = ql.Monthly
                else:
                    period = ql.Period(self.tenors[i],ql.Years)
                    frequency = ql.Years

                self.helpers += [ql.OISRateHelper(self.settlement_days,
                            period,
                            ql.QuoteHandle(self.swap_rates[i]),
                            self.ICP,
                            handle,
                            False,
                            0,
                            ql.Following,
                            frequency)]
    def defineParameters(self):
        self.calendar = CalendarCl(2001,50)
        self.day_counter = ql.Actual360()
        self.settlement_days = 2
        self.fixing_days = 0
        self.ICP = ql.OvernightIndex("ICP",
                                    self.settlement_days,
                                    ql.CLPCurrency(),
                                    self.calendar,
                                    self.day_counter)
    def showCurve(self, date):
        day_count = ql.Actual360()
        spots = []
        dates = []
        tenors = []
        df = []
        yield_dict = {}
        for d in self.dates():
            yrs = day_count.yearFraction(date, d)
            compounding = ql.Simple
            freq = ql.Annual
            zero_rate = self.zeroRate(yrs, compounding, freq)
            eq_rate = zero_rate.equivalentRate(day_count, compounding, freq, date, d).rate()
            zero_rate.equivalentRate(day_count, compounding, freq, date, d).rate()
            yield_dict[yrs] = 100*eq_rate

        print('Date','Rate')
        for k, v in yield_dict.items():
            print(round(k,2), round(v,2))

class ShortTermUFValues(PyObserver, ql.SimpleQuote):
    """
        Recieves an evaluation date, UF FWD contract dates -as QL Date Object-
        and UF prices -as QL Simple Quote Objects-. The ShortTermUFValues object inherits
        from the SimpleQuote SWIG class to simulate the ql.Observeable interface,
        which is not avaible for Python.
    """
    def __init__(self, dates, prices):
        PyObserver.__init__(self)
        ql.SimpleQuote.__init__(self, 0)

        self.dates = dates
        self.prices = prices
        self.fn = self.buildUfFwd
        self.exc = 0
        self.registerCurveWithQuotes()
        self.buildUfFwd()
    def notifyObservers(self):
        tmp = self.value()
        self.setValue(tmp + 1)
    def registerCurveWithQuotes(self):
        for i in self.prices:
            self.registerWith(i)
    def buildUfFwd(self):
        ipc = []
        adj_uf = [self.prices[0].value()]
        contract_dates = []
        period_dates = [self.dates[0]]
        proy_uf = []
        period_days = []
        proy_uf = [self.prices[0].value()]

        #Calculate IPC's to proyect UF values.
        for i in range(len(self.prices)-1):
            #Periods and adjusted IPC
            start_period = ql.Date(9,self.dates[i].month(),self.dates[i].year())
            next_period = ql.Date(9,self.dates[i+1].month(),self.dates[i+1].year())
            next_contract_period = self.dates[i+1]

            if i == 0:
                start_contract_period = self.dates[i]
                dt = (next_period-start_period)/(next_contract_period - start_contract_period)
            else:
                start_contract_period = start_period
                dt = (next_period-start_period)/(next_contract_period - start_contract_period)
                adj_uf.append(adj_uf[-1]*(1+ipc[-1]))

            ipc.append((self.prices[i+1].value()/adj_uf[i])**(dt)-1)
            period_days.append(next_period-start_period)
            contract_dates.append(start_contract_period)
            period_dates.append(next_period)

        #Calculate UF per day giveng parameters calculated before.
        self.uf_dict = {}
        final_dates = self.dates[0]
        total_days = period_dates[-1] - period_dates[0]
        counter = 0
        j = 0
        for i in range(total_days):
            final_dates += 1
            counter += 1
            if counter > period_days[j]:
                counter = 1
                j += 1

            next_uf = proy_uf[-1]*(1+ipc[j])**(1/period_days[j])
            proy_uf.append(next_uf)
            self.uf_dict[final_dates] = next_uf

        self.uf_dict = OrderedDict(self.uf_dict)
        self.notifyObservers()
    def showUfs(self):
        print('Date','Value')
        for k, v in self.uf_dict.items():
            if k.dayOfMonth() == 9:
                print(k, round(v,4))
class LongTermUFValues(PyObserver, ql.SimpleQuote):
    """
        LongTermUFValues is an CPI curve builded from the UF Forward quotes and the UF/CAM swap quotes.
        The idea is to proyect for each future day a UF value that can be used to price future cashflows.
        The uf_dict dictionary holds the proyected prices.
    """
    def __init__(self, date, ICPCurveCLP, ICPCurveUF, ShortUFValues):
        PyObserver.__init__(self)
        ql.SimpleQuote.__init__(self, 0)

        self.date = date
        self.ICPCurveCLP = ICPCurveCLP
        self.ICPCurveUF = ICPCurveUF
        self.ShortUFValues = ShortUFValues
        self.fn = self.buildUfFwd
        self.registerCurveWithQuotes()
        self.buildUfFwd()
    def notifyObservers(self):
        tmp = self.value()
        self.setValue(tmp + 1)
    def registerCurveWithQuotes(self):
        #total_helpers = self.ICPCurveCLP.swap_rates + self.ICPCurveUF.swap_rates + self.ShortUFValues.prices
        #for helper in total_helpers:
        self.registerWith(self.ShortUFValues)
    def buildUfFwd(self):
        self.uf_dict = self.ShortUFValues.uf_dict
        day_count = ql.Actual360()
        compounding = ql.Simple
        freq = ql.Annual
        size = len(self.uf_dict)
        evaluation_date_uf = self.uf_dict[self.date]
        for i in range(7300 - size):
            #next date to calculate UF
            last_uf_dict_date = next(reversed(self.uf_dict))
            next_date = last_uf_dict_date + 1
            yrs = day_count.yearFraction(self.date, next_date)
            rate_clp = self.ICPCurveCLP.zeroRate(yrs, compounding, freq).rate()
            rate_uf = self.ICPCurveUF.zeroRate(yrs, compounding, freq).rate()
            next_uf = (1 + rate_clp * yrs) * evaluation_date_uf / (1 + rate_uf * yrs)
            self.uf_dict[next_date] = next_uf

        self.notifyObservers()
    def showUfs(self):
        print('Date','Value')
        for k, v in self.uf_dict.items():
            if k.dayOfMonth() == 9:
                print(k, round(v,4))
"""
main() contains a test cases for debugging. Not very
"""
def main():
    test_date = ql.Date(1,3,2018)
    ql.Settings.instance().evaluationDate = test_date
    helper = dataManager(ip='192.168.0.3', port='8080')
    clp_curve, uf_curve = exampleSwap(helper, test_date)
    short_uf = exampleShortUf(helper)
    exampleLongUf(helper, test_date, clp_curve, uf_curve, short_uf)
def exampleSwap(helper, date):
    #Define data
    query_swap = 'select \"Mid\" from swap_clp where \"Date\"=\'01/03/2018\';'
    swap = helper.get_raw_data(query_swap)
    swap = [ql.SimpleQuote(x/100) for x in swap]
    clp_curve = ICPCurve(date, swap, 'CLP', 'Swap')

    #Test CLP curve
    print('|---------------CLP CURVE----------------|')
    clp_curve.showCurve(ql.Date(1,3,2018))
    print('|--------------UPDATE TEST---------------|')
    clp_curve.swap_rates[5].setValue(5/100)
    clp_curve.showCurve(ql.Date(1,3,2018))
    print('|----------------------------------------|\n')

    #Define data
    query_swap = 'select \"Mid\" from swap_uf where \"Date\"=\'01/03/2018\';'
    swap = helper.get_raw_data(query_swap)
    swap = [ql.SimpleQuote(x/100) for x in swap]
    uf_curve = ICPCurve(ql.Date(1,3,2018),swap,'UF','Swap')

    #Test UF curve
    print('|---------------UF  CURVE----------------|')
    uf_curve.showCurve(ql.Date(1,3,2018))
    print('|----------------------------------------|\n')

    return clp_curve, uf_curve
def exampleShortUf(helper):
    query_dates = 'select \"Maturity\" from fwd_uf where \"Date\"=\'01/03/2018\';'
    query_prices = 'select \"Mid\" from fwd_uf where \"Date\"=\'01/03/2018\';'

    dates = helper.get_raw_data(query_dates)
    prices = helper.get_raw_data(query_prices)
    tmp = prices[1]
    #Test UF
    dates = [ql.DateParser.parseFormatted(x.strftime("%d-%m-%y"),'%d-%m-%y') for x in dates]
    prices = [ql.SimpleQuote(x) for x in prices]
    short_uf = ShortTermUFValues(dates, prices)

    #Update Test
    print('|------------SHORT UF VALUES-------------|')
    short_uf.showUfs()
    print('|--------------UPDATE TEST---------------|')
    short_uf.prices[1].setValue(1000)
    short_uf.showUfs()
    print('|----------------------------------------|\n')
    #Return to prev. value for next example
    short_uf.prices[1].setValue(tmp)
    return short_uf
def exampleLongUf(helper, date, clp_curve, uf_curve, short_uf):
    long_uf = LongTermUFValues(date, clp_curve, uf_curve, short_uf)
    tmp = short_uf.prices[1].value()
    print('|-------------LONG UF VALUES-------------|')
    long_uf.showUfs()
    print('|--------------UPDATE TEST---------------|')
    short_uf.prices[1].setValue(1000)
    long_uf.showUfs()
    print('|----------------------------------------|\n')

if __name__ == '__main__':
    main()
