import os
import csv 
import alpaca_trade_api as tradeapi

api = tradeapi.REST(key_id="PK985K014CB2YY1DBGWE",secret_key="BOFxWWKvf2UTBUPftLCjz9twmQ1Ly149D6tPVeeF")


storageLocation = os.path.expanduser('~/Downloads/alpacaData/')
os.makedirs(storageLocation, exist_ok=True)
barTimeframe = "1H" # 1Min, 5Min, 15Min, 1H, 1D
assetsToDownload = ["SPY","MSFT","AAPL","NFLX"]

iteratorPos = 0 # Tracks position in list of symbols to download
assetListLen = len(assetsToDownload)
while iteratorPos < assetListLen:
	symbol = assetsToDownload[iteratorPos]
	
	dataFile = ""
	lastDate = "2014-01-01" # ISO8601 Date
	
	# Verifies if symbol file exists	
	try: # If file exists, reads the time of the last bar
		dataFile =  open(storageLocation + '{0}.csv'.format(symbol), 'a+')
		lastDate = list(csv.DictReader(dataFile))[-1]["time"]
	except: # If not, initialises new CSV file
		dataFile = open(storageLocation + '{0}.csv'.format(symbol), 'w')
		dataFile.write("time,open,high,low,close,volume\n")


	returned_data = api.get_bars(symbol,barTimeframe,start=lastDate)

	# Reads, formats and stores the new bars
	writer = csv.writer(dataFile)
	for bar in returned_data:
		ret_time = str(bar.t)
		ret_open = str(bar.o)
		ret_high = str(bar.h)
		ret_low = str(bar.l)
		ret_close = str(bar.c)
		ret_volume = str(bar.v)
		writer.writerow([ret_time, ret_open, ret_high, ret_low, ret_close, ret_volume])
		# Writes formatted line to CSV file
		#dataFile.write(ret_time + "," + ret_open + "," + ret_high + "," + ret_low + "," + ret_close + "," + ret_volume)
	    
	dataFile.close()

	iteratorPos += 1