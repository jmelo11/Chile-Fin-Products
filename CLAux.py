"""
Author: Jose Melo
Auxiliary functions. This file contains an adaptation to include the Chilean calendar and PyOberser,
a helper class to make object be able to recieve update notifications from QuantLib objects
"""

import QuantLib as ql
import pandas as pd
from datetime import datetime

#Creates Chile's calendar.
def CalendarCl(start_year,n_years):
    Chile = ql.WeekendsOnly()
    days = [1,14,15,1,21,26,2,16,15,18,19,9,27,1,19,8,17,25,31]
    months = [1,4,4,5,5,6,8,9,9,10,10,11,12,12,12,12]
    name = ['Año Nuevo','Viernes Santo','Sabado Santo','Dia del Trabajo','Dia de las Glorias Navales','San Pedro y San Pablo','Elecciones Primarias','Dia de la Virgen del Carmen','Asuncion de la Virgen','Independencia Nacional','Glorias del Ejercito','Encuentro de dos mundos','Día de las Iglesias Evangélicas y Protestantes','Día de todos los Santos','Elecciones Presidenciales y Parlamentarias','Inmaculada Concepción','Segunda vuelta Presidenciales','Navidad','Feriado Bancario']
    for i in range(n_years+1):
        for x,y in zip(days,months):
            date = ql.Date(x,y,start_year+i)
            Chile.addHoliday(date)
    return Chile
#Class for maintaning QL Observer capabilities.
class PyObserver(ql.Observer):
    def __init__(self):
        super(PyObserver, self).__init__(self.update)
        self.fn = None
    def update(self):
        self.fn()
