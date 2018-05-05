"""
Author: Jose Melo
Basic bond functions from QL applied to CL fixed income.

This file has two types of CL Bonds, the common Peso Bond (CLPBond class) and Inflation Indexed UFBond.
The UFBond class observes the short term UF contracts and recalculates an auxiliary bond when prices change.
This classes can be used to calculate Z-Spreads and other information.
"""
import QuantLib as ql
from CLCurves import ICPCurve, ShortTermUFValues, LongTermUFValues
from CLAux import *
from pgLoader import dataManager


class CLPBond(ql.FixedRateBond):
    """
        Works as the FixedRateBond from the library. It expects the same parameters.
    """
    def __init__(self, settlement_days, notional, schedule, coupons, int_day_count):
        ql.FixedRateBond.__init__(self, settlement_days, notional, schedule, coupons, int_day_count)
        self.settlement_days = settlement_days
        self.notional = notional
        self.schedule = schedule
        self.coupons = coupons
        self.int_day_count = int_day_count
    def showTable(self):
        print('Date','Amount')
        for _ in self.cashflows():
            print(_.date(), _.amount())
    def dur(self, rate):
        return round(ql.BondFunctions.duration(self, rate, ql.Duration.Modified),2)

class UFBond(CLPBond, PyObserver):
    """
        This kind of bond can be initialized as a common bond (it will considere its cashflows
        as amount of UF to be paid) or if a ShortTermUFValues or LongTermUFValues object is also
        passed in the UFValues variable, an auxiliary bond object can be calculated, which contains
        CLP cashflows.
    """
    def __init__(self, settlement_days, notional, schedule, coupons, int_day_count, UFValues = None):
        CLPBond.__init__(self, settlement_days, notional, schedule, coupons, int_day_count)
        PyObserver.__init__(self)
        self.UFValues = UFValues
        self.fn = self.proyectedCLPBond
    def registerWithUFValues(self):
        self.registerWith(self.UFValues)
    def proyectedCLPBond(self):
        proyected_cashflows = []
        for _ in self.cashflows():
            if _.date() not in self.UFValues.uf_dict:
                self.issue_date = _.date()
                continue
            else:
                proyected_uf = self.UFValues.uf_dict[_.date()]
                proyected_amount = _.amount()*proyected_uf
                proyected_cashflows += [ql.SimpleCashFlow(proyected_amount,_.date())]
                self.maturity_date = _.date()

        leg = ql.Leg(proyected_cashflows)
        self.proyected_bond = ql.Bond(self.settlement_days,
                                    ql.NullCalendar(), #Unsolved issue. Should use CL Calendar
                                    self.notional,
                                    self.maturity_date,
                                    self.issue_date,
                                    leg)

    def showProyectedBondTable(self):
        print('Date','Amount')
        for _ in self.proyected_bond.cashflows():
            print(_.date(), round(_.amount()))

def Curves(helper, date):
    #Define data
    query_swap = 'select \"Mid\" from swap_clp where \"Date\"=\'' + qlToStr(date) + '\';'
    swap = helper.get_raw_data(query_swap)
    swap = [ql.SimpleQuote(x/100) for x in swap]

    clp_curve = ICPCurve(date, swap, 'CLP', 'Swap')

    #Define data
    query_swap = 'select \"Mid\" from swap_uf where \"Date\"=\'' + qlToStr(date) + '\';'
    swap = helper.get_raw_data(query_swap)
    swap = [ql.SimpleQuote(x/100) for x in swap]
    uf_curve = ICPCurve(date, swap, 'UF', 'Swap')
    #Test UF curve
    return clp_curve, uf_curve
def ShortUF(helper, date):
    query_dates = 'select \"Maturity\" from fwd_uf where \"Date\"=\'' + qlToStr(date) + '\';'
    query_prices = 'select \"Mid\" from fwd_uf where \"Date\"=\'' + qlToStr(date) + '\';'
    dates = helper.get_raw_data(query_dates)
    prices = helper.get_raw_data(query_prices)
    #Test UF
    dates = [ql.DateParser.parseFormatted(x.strftime("%d-%m-%y"),'%d-%m-%y') for x in dates]
    prices = [ql.SimpleQuote(x) for x in prices]
    return ShortTermUFValues(dates, prices)
def LongUF(date, clp_curve, uf_curve, short_uf):
    return LongTermUFValues(date, clp_curve, uf_curve, short_uf)
def defineBond(UFValues, currency, issue_date, maturity_date, notional, coupon_rate):
    tenor = ql.Period(ql.Semiannual)
    calendar = ql.NullCalendar()
    coupon_day_count = ql.Unadjusted
    payment_convention = ql.Following
    date_generation = ql.DateGeneration.Forward
    month_end = False
    settlement_days = 0
    interest_day_count = ql.Thirty360()

    schedule = ql.Schedule (issue_date,
                            maturity_date,
                            tenor,
                            calendar,
                            coupon_day_count,
                            payment_convention,
                            date_generation,
                            month_end)
    if currency== '$':
        bond = CLPBond(settlement_days,
                        notional,
                        schedule,
                        coupon_rate,
                        interest_day_count)
    elif currency == 'UF':
        bond = UFBond(settlement_days,
                        notional,
                        schedule,
                        coupon_rate,
                        interest_day_count,
                        UFValues)
        bond.proyectedCLPBond()
    return bond
def qlToStr(date):
    date = str(date.dayOfMonth()) + '/' + str(date.month()) + '/' + str(date.year())
    return date
def dtToQl(date):
    date = pd.to_datetime(str(date))
    date_ql = ql.DateParser.parseFormatted(date.strftime("%d-%m-%y"),'%d-%m-%y')
    return date_ql
def getZSpread(bond, npv, clp_curve):
    spread = ql.CashFlows.zSpread(bond.cashflows(),npv, clp_curve,ql.Actual360(),ql.Compounded,ql.Semiannual,True)*100
    return round(spread,2)

"""
main() contains examples and test cases for debugging.
"""
def exampleBond(UFValues):
    issueDate = ql.Date(1,6,2015)
    maturityDate = ql.Date(1,6,2020)
    tenor = ql.Period(ql.Semiannual)
    calendar = ql.NullCalendar()
    coupon_dayCount = ql.Unadjusted
    payment_convention = ql.Following
    dateGeneration = ql.DateGeneration.Forward
    monthEnd = False
    settlementDays = 0
    interest_dayCount = ql.Thirty360()
    notional = 100
    bond_type ='Bullet'
    currency = 'CLP'
    coupons = [4.5/100]
    tir = 3.22/100

    schedule = ql.Schedule (issueDate,
                            maturityDate,
                            tenor,
                            calendar,
                            coupon_dayCount,
                            payment_convention,
                            dateGeneration,
                            monthEnd)

    bond = UFBond(settlementDays,
                    notional,
                    schedule,
                    coupons,
                    interest_dayCount,
                    UFValues)

    rate = ql.InterestRate(tir,
                            ql.Actual365Fixed(),
                            ql.Compounded,
                            ql.Annual)

    print(bond.dur(rate))
    return bond
def main():
    helper = dataManager(ip='192.168.0.3', port='8080')
    date = ql.Date(1,3,2018)
    ql.Settings.instance().evaluationDate = date

    clp_curve, uf_curve = Swap(helper, date)
    short_ufs = ShortUf(helper)
    long_ufs = LongUf(helper, date, clp_curve, uf_curve, short_ufs)
    bond = exampleBond(long_ufs)

    bond.registerWithUFValues()
    bond.proyectedCLPBond()
    #Test of UF quotes updated
    bond.showProyectedBondTable()
    short_ufs.prices[1].setValue(1000)
    #long_ufs.showUfs()
    bond.showProyectedBondTable()
if __name__ == '__main__':
    main()
