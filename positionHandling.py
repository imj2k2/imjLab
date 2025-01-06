import alpaca_trade_api as tradeapi

api = tradeapi.REST(key_id=<your key id>,secret_key=<your secret key>)

class positionHandler:
	def __init__(self,startingBalance=10000,liveTrading=False):
		self.cashBalance = startingBalance
		self.livePositions = {} # Dictionary of currently open positions
		self.openOrders = [] # List of open orders
		self.positionHistory = [] # List of items [Symbol, new position size]
		self.tradeHistory = [] # List of filled trades		
		self.liveTrading = liveTrading
		
	def placeOrder(self, symbol, quantity, side, orderType, time_in_force, limit_price=None, stop_price=None, client_order_id=None):

		if self.liveTrading:
			returned = api.submit_order(symbol, qty, side, orderType, time_in_force, limit_price, stop_price, client_order_id)
			self.tradeHistory.append(returned) # You'll probably want to make a simpler custom order dict format
		else:
			self.tradeHistory.append(<order Dict>)
		
		if orderType == "market":
			try:
				if side == "buy":
					fillPrice = data[symbol]["close"] # You'll need to make adjustments to the backtest fill price assumptions
					
					self.livePositions[symbol][size] = self.livePositions[symbol][size] + quantity
					self.cashBalance -= quantity * fillPrice
				elif side == "sell":
					fillPrice = data[symbol]["close"]
					
					self.livePositions[symbol][size] = self.livePositions[symbol][size] - quantity
					self.cashBalance += quantity * fillPrice
				
				
				if self.livePositions[symbol][size] == 0:
					del self.livePositions[symbol]
				
			except:
				self.livePositions[symbol] = {}
				
				if side == "buy":
					self.livePositions[symbol][size] = quantity
				elif side == "sell":
					self.livePositions[symbol][size] = -quantity
				
			self.positionHistory.append([symbol,self.livePositions[symbol]])
		else:
			self.openOrders.append(<order Dict>) # You'll probably want to make a simpler custom order dict format
		
	def processOpenOrders(self):

		for order in self.openOrders:
			symbol = order["symbol"]
			
			if self.liveTrading:
				returned = api.get_order(order["order_id"])
				
				# Process the live order status into your storage format as necessary
				
			else:
				# Historical data input has to be adjusted for your own data pipeline setup
				timeStepMin = data[symbol]["low"] # Reads the minimum trade price since last data point
				timeStepMax = data[symbol]["high"] # Reads the maximum trade price since last data point
				
				if order["orderType"] == "limit":
					try:
						if order["side"] == "buy" and order["limit"] > timeStepMin:
							# You'll need to make adjustments to the backtest fill price assumptions
							fillPrice = data[symbol]["close"] 
							
							self.livePositions[symbol][size] = self.livePositions[symbol][size] + quantity
							self.cashBalance -= quantity * fillPrice
							self.positionHistory.append([symbol,self.livePositions[symbol]])
						elif order["side"] == "sell" and order["limit"] < timeStepMax:
							fillPrice = data[symbol]["close"]
							
							self.livePositions[symbol][size] = self.livePositions[symbol][size] - quantity
							self.cashBalance += quantity * fillPrice
							self.positionHistory.append([symbol,self.livePositions[symbol]])
						
					except:
						self.livePositions[symbol] = {}
						
						if order["side"] == "buy" and order["limit"] > timeStepMin:
							fillPrice = data[symbol]["close"]
							
							self.livePositions[symbol][size] = quantity
							self.cashBalance -= quantity * fillPrice
							self.positionHistory.append([symbol,self.livePositions[symbol]])
						elif order["side"] == "sell" and order["limit"] < timeStepMax:
							fillPrice = data[symbol]["close"]
							
							self.livePositions[symbol][size] = -quantity
							self.cashBalance += quantity * fillPrice
							self.positionHistory.append([symbol,self.livePositions[symbol]])
					
				elif # Add processing for other required order types
		
	def returnOpenPosition(self,symbol):
		try:
			return self.livePositions[symbol]
		except:
			return 0