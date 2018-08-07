import QuantLib as ql
from CLCurves import ICPCurve, ShortTermUFValues, LongTermUFValues
from CLAux import *
from pgLoader import dataManager

"""
Author: Jose Melo
Basic bond functions from QL applied to CL fixed income.

Two types of CL Bonds, the common Peso Bond (CLPBond class) and Inflation Indexed UFBond.
The UFBond class observes the short term UF contracts and it recalculates an auxiliary bond
that can be used to calculate Z-Spreads and others.
"""
class CLPBond(ql.FixedRateBond):
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
    def __init__(self, settlement_days, notional, schedule, coupons, int_day_count, UFValues = None):
        CLPBond.__init__(self, settlement_days, notional, schedule, coupons, int_day_count)
        PyObserver.__init__(self)
        self.UFValues = UFValues
        self.fn = self.proyectCLPBond
    def registerWithUFValues(self):
        self.registerWith(self.UFValues)
    def proyectCLPBond(self):
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
class DPF(ql.ZeroCouponBond):
    def __init__(self, settlement_days, calendar, fv, maturity_date, coupon_day_count):
        self.settlement_days = settlement_days
        self.calendar = calendar
        self.fv = fv
        self.maturity_date = maturity_date
        self.coupon_day_count = coupon_day_count
        ql.ZeroCouponBond.__init__(self, settlement_days, calendar, fv, maturity_date, coupon_day_count)
class DPR(DPF, PyObserver):
    def __init__(self, settlement_days, calendar, fv, maturity_date, coupon_day_count, UFValues = None):
        DPF.__init__(self, settlement_days, calendar, fv, maturity_date, coupon_day_count)
        PyObserver.__init__(self)
        self.UFValues = UFValues
        self.fn = self.proyectDPR
    def registerWithUFValues(self):
        self.registerWith(self.UFValues)
    def proyectDPR(self):
        proyected_uf = self.UFValues.uf_dict[self.maturity_date]
        uf_fv = self.fv * proyected_uf
        self.proyected_DPR = ql.ZeroCouponBond(self.settlement_days, self.calendar, uf_fv, self.maturity_date, self.coupon_day_count)
def Curves(helper, date):
    #Define data
    query_swap = 'select \"Zero\" from swap_clp where \"Date\"=\'' + qlToStr(date) + '\';'
    swap = helper.get_raw_data(query_swap)
    swap = [ql.SimpleQuote(x/100) for x in swap]
    clp_curve = ICPCurve(date, swap, 'CLP', 'Zero')

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
def defineBond(UFValues, currency, issue_date, maturity_date, notional, coupon_rate, tenor = ql.Period(ql.Semiannual)):
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
        bond.proyectCLPBond()
    return bond
def getZSpread(bond, npv, clp_curve):
    spread = ql.CashFlows.zSpread(bond.cashflows(), npv, clp_curve, ql.Actual360(), ql.Simple, ql.Annual, True)*100
    return round(spread,2)

"""
example() contains examples and test cases for debugging.
"""
def example():
    db_market = dataManager(db='Bolsa')
    ql_date = ql.Date(26,6,2018)
    ql.Settings.instance().evaluationDate = ql_date
    calendar = CalendarCl(2001,50)

    #Curvas
    clp_curve, uf_curve = Curves(db_market, ql_date)
    short_uf = ShortUF(db_market, ql_date)
    long_uf = LongUF(ql_date, clp_curve, uf_curve, short_uf)
    issue_date = ql.Date(1,9,2015)
    maturity_date = ql.Date(1,3,2021)
    coupon_rate = [1.5/100]
    tir = 0.87/100
    notional = 100
    bond = defineBond(long_uf, 'UF', issue_date, maturity_date, notional, coupon_rate)
    bond.showTable()
    rate = ql.InterestRate(tir, ql.Actual365Fixed(), ql.Simple, ql.Annual)
    npv = ql.CashFlows.npv(bond.cashflows(), rate, True) * long_uf.uf_dict[ql_date]
    z_spread = getZSpread(bond.proyected_bond, npv, clp_curve)
    print('NPV',npv,'ZSPread',z_spread)
if __name__ == '__main__':
    example()
