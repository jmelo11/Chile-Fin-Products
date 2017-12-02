



# ChileFinance
Python tools for the chilean financial market.

Alpha project. For the excel files to work, you need to install the xlwings add-in. For the postgre connection, pyscopg2 and sqlachemy libraries are needed. A good way to go is using anaconda package manager.


Any contribution is welcome.

# Files:

pgLoader.py - It's a data managament scrip that lets you upload to a postGre db closing market data of the local exchanges and ICAP run. Both are excel files. Still under work.

zspreaSebra.py - The main idea is to get z-spread from each bond listed at Santiago's SEBRA. It has different functions including one to generate implied UF values from forwards and UF/CAM swaps. It's a work in progress.

qlChileCal.py - It has a function that generates de Chilean calendar for QL.
