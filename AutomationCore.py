import re
from web3 import Web3
from constants import *
import time
from web3.middleware import geth_poa_middleware
import requests
import json
from dotenv import load_dotenv
import os
load_dotenv()

privatekey = os.getenv("BOT_WALLET_PRIVATE_KEY")

def checkFormat(inputData, typeName):
	rex = re.compile(getattr(formats, typeName))
	assert rex.match(inputData), "Input is not the correct type only " + typeName +" is supported for this input."
	return inputData 

def decimal(value, decimals):
	return value/(10**decimals)


class blockChainInstance():
	def __init__(self, chainRPC, privatekey):
		self.web3 = Web3(Web3.HTTPProvider(chainRPC))
		self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
		self.senderAccount = self.web3.eth.account.privateKeyToAccount(privatekey)
		self.web3.eth.defaultAccount = self.senderAccount.address
		self.nonce = self.web3.eth.getTransactionCount(self.senderAccount.address)

	def smartTransact(self, params=[], contract=None, functionName=None):
		self.updateGasPrice()

		txn = contract.functions[functionName](*params).buildTransaction({'gas': 21000,
			'gasPrice': self.gas,
			'nonce': self.nonce,
			})
		estimatedgas = self.web3.eth.estimateGas({'from':self.web3.eth.defaultAccount,'to':txn['to'],'data':txn['data']})
		if estimatedgas > txn['gas']:
			txn['gas'] += int(estimatedgas*1.2)
		#gasTracking.addGas(txn['gas'])
		return txn

	def smartCall(self, params=[], contract=None, functionName=None):
		try:
			return contract.functions[functionName](*params).call()
		except Exception:
			print(params)
			print(functionName)
	def contract(self, contractAddr, contractABI):
		return self.web3.eth.contract(address=checkFormat(contractAddr, 'address'), abi=contractABI)
	def updateGasPrice(self, price=10000000000):
		self.gas = price if self.web3.eth.gasPrice == 0 else self.web3.eth.gasPrice
	def signAndShip(self, txn):
		while True:
			try:
				txn = self.web3.eth.sendRawTransaction(self.web3.eth.account.signTransaction(txn, private_key=self.senderAccount.privateKey).rawTransaction)
				self.nonce += 1
				break
			except ValueError:
				self.nonce += 1
				txn['nonce'] = self.nonce
				continue
		
		return self.waitForTx(txn)
	def waitForNextBlock(self):
		block = self.web3.eth.getBlock('latest').number
		while True:
		 if self.web3.eth.getBlock('latest').number > block:
			 break
	def waitForTx(self,txid):
		while True:
			try:
				if self.web3.eth.getTransactionReceipt(txid).blockNumber is not None:
					return self.web3.eth.getTransactionReceipt(txid)
			except Exception:
				continue
	def balance(self):
		return self.web3.eth.getBalance(self.senderAccount.address)
class formats():
    address = "^(0x)?(0X)?[0-9a-fA-F]{40}$"
 

class lpToken():
	def __init__(self, contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.token = [self.blockchain.smartCall(contract=self.contract,functionName='token0'), self.blockchain.smartCall(contract=self.contract,functionName='token1')]
		self.address = contractAddr

	def balanceOf(self, address):
		return self.blockchain.smartCall(contract=self.contract,functionName='balanceOf',params=[address])
	def getTokenBalances(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='getReserves')
	def getTokenPrices(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='price0CumulativeLast'), self.blockchain.smartCall(contract=self.contract,functionName='price1CumulativeLast')
	def getTotalSupply(self):
		return self.blockchain.smartCall(contract=self.contract,functionName='totalSupply')

class contract():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def smartCall(self, functionName, params=[]):
		return self.blockchain.smartCall(params, self.contract, functionName)
	def smartTransact(self, functionName, params=[]):
		return self.blockchain.signAndShip(self.blockchain.smartTransact(params, self.contract, functionName))


class dex():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def smartRoute(self):
		pass # will work on this later
	def smartSwap(self, amount, path, maxSlippage, eth=False): # will be smarter later when smartRoute is done
		sellValue = self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amount,path])[-1]
		buyValue = self.blockchain.smartCall(functionName='getAmountsIn',contract=self.contract, params=[sellValue ,path])[0]
		if eth:
			if path[-1] == '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c':
				return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactTokensForETH'))
			elif path[0] == '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c':
				return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactETHForTokens')) 
		else:
			return self.blockchain.signAndShip(self.blockchain.smartTransact([int(buyValue),int(sellValue*(1-(maxSlippage/100))),path,self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'swapExactTokensForTokens'))
	def smartLiquidity(self, amountA, amountB, tokenA, tokenB, maxSlippage, eth=False):
			amountB = min(self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amountA,[tokenA, tokenB]])[-1], amountB)
			amountA = min(self.blockchain.smartCall(functionName='getAmountsIn',contract=self.contract, params=[ amountB,[tokenA, tokenB]])[0], amountA)
			return self.blockchain.signAndShip(self.blockchain.smartTransact([tokenA, tokenB, amountA, amountB, int(amountA*(1-(maxSlippage/100))), int(amountB*(1-(maxSlippage/100))),self.blockchain.web3.eth.defaultAccount, int(time.time())+300], self.contract, 'addLiquidity'))
	def getPrice(self, amount, path):
			return self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amount,path])[-1]
class token():
	def __init__(self,contractAddr, contractABI, blockchain):
		self.blockchain = blockchain
		self.contract = self.blockchain.contract(contractAddr, contractABI)
		self.address = contractAddr
	def balanceOf(self, address):
		return self.blockchain.smartCall(contract=self.contract,functionName='balanceOf', params=[self.blockchain.web3.eth.defaultAccount])

class profitTracker():
	def __init__(self, amount):
		self.previousAmount = amount
		self.prevTimestamp = time.time()
		self.genesis = self.prevTimestamp
		self.minutes = 0
		self.hours = 0
		self.days = 0

		self.minutesUpdateInterval = 1
		self.hoursUpdateInterval = 5
		self.daysUpdateInterval = 10

		self.profitpersecond = []
		self.profitperminute = []
		self.profitperhour = []
		self.profitperday = []
	
	def calculateProfit(self, amount): # accepts the profits generated from given profit cycle
		cycleprofit = (amount-self.previousAmount) / (time.time() - self.prevTimestamp)
		self.prevTimestamp = time.time()
		self.previousAmount = amount
		if cycleprofit > 0:
			self.profitpersecond.append(cycleprofit)
			if len(self.profitpersecond) > 30:
				self.profitpersecond.pop(0)
			if time.time() >= ((self.minutesUpdateInterval * self.minutes) + self.genesis) or len(self.profitperminute) == 0:
				self.profitperminute.append(average(self.profitpersecond)*60)
				if len(self.profitperminute) > 30:
					self.profitperminute.pop(0)
				self.minutes += 1

			if time.time() >= ((self.hoursUpdateInterval * self.hours) + self.genesis) or len(self.profitperhour) == 0:
				self.profitperhour.append(average(self.profitperminute)*60)
				if len(self.profitperhour) > 30:
					self.profitperhour.pop(0)
				self.hours += 1

			if time.time() >= ((self.daysUpdateInterval * self.days) + self.genesis) or len(self.profitperday) == 0:
				self.profitperday.append(average(self.profitperhour)*24)
				if len(self.profitperday) > 30:
					self.profitperday.pop(0)
				self.days += 1
		
	def getProfitPerSecond(self):
		return average(self.profitpersecond)
	def getProfitPerMinute(self):
		return average(self.profitperminute)
	def getProfitPerHour(self):
		return average(self.profitperhour)
	def getProfitPerDay(self):
		return average(self.profitperday)
		
class gasTracker():
	def __init__(self):
		self.cycleGas = 0
		self.gasHistory = []
		self.averageGas = average(self.gasHistory)
	def endGasCycle(self):
		self.gasHistory.append(self.cycleGas)
		if len(self.gasHistory) > 30:
					self.gasHistory.pop(0)
		self.averageGas = average(self.gasHistory)
	def startGasCycle(self):
		self.cycleGas = 0
	def addGas(self, gas):
		self.cycleGas += gas

def average(data):
	if len(data) > 0 and sum(data) > 0:
		return sum(data)/len(data)
	else:
		return 0

def retry(method, params):
	method(params)

def optimiseGasRate(precision, profitRate):
	bestApy = 0
	for x in range(1,(100*(10**precision))):
		tempGasRate = ((x/(10**precision))/100)
		profitToGas = profitRate*tempGasRate
		compoundRate = 86400/(data['averageGasCost'] / (profitToGas))
		apy = ((1+(((APR/100)*(1-tempGasRate))/(365*compoundRate)) )**(365*compoundRate))-1
		if apy > bestApy:
			gasRate = tempGasRate
			bestApy = apy
	return gasRate

BSC = blockChainInstance("https://bsc-dataseed1.ninicoin.io/", privatekey)

cCakeCake = lpToken('0x5D89e28fbEF459b442e19c3204A281680A48cb82', ABI.pcsLPPair, BSC)
cCakeFarm = contract('0x38571b961896eFBbbcEf7FDd66cd787CC129674F', ABI.cCakeFarm, BSC)
pcsRouter = dex('0x05fF2B0DB69458A0750badebc4f9e13aDd608C7F', ABI.pcsRouter, BSC)
cCake = token('0x47C4f3ffc31c135AFC0C157068f6E0eEA90b7dC9', ABI.erc20, BSC)
cake = token('0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82', ABI.erc20, BSC)
wbnb = contract('0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', ABI.bnb, BSC)

gasTracking = gasTracker()

# print(cCakeFarm.smartCall('pendingCarrotCake', [6, BSC.senderAccount.address]))
pendingCarrotCake = cCakeFarm.smartCall('pendingCarrotCake', [6, BSC.senderAccount.address])
pendingrewards = (pcsRouter.getPrice(int(pendingCarrotCake), [cCake.address, cake.address]  ))/(10**18)
cCakePrice = pendingrewards/pendingCarrotCake
profits = profitTracker(pendingCarrotCake)
gasRate = 0.005

timestamp = 0
data = {}
## LOGIC ##
while True:
	resp = requests.get('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=wbnb&order=market_cap_desc&per_page=100&page=1&sparkline=false')
	bnbData = resp.json()
	bnbPrice = bnbData[0]['current_price']
	BSC.updateGasPrice()

	cCakeBalance = 0
	cCakeCakeBalance = decimal(cCakeFarm.smartCall('userInfo', [6, BSC.senderAccount.address])[0]     ,18)
	cCakeCakeTotalSupply = decimal(cCakeCake.getTotalSupply(),18)
	
	cCakeBalance = ((decimal(cCakeCake.getTokenBalances()[1], 18)*bnbPrice)*2)  *  (cCakeCakeBalance / cCakeCakeTotalSupply )
	cCakePercent = (cCakeCakeBalance/ cCakeCakeTotalSupply )*100
	accountBalance = cCakeBalance
	pendingCarrotCake = cCakeFarm.smartCall('pendingCarrotCake', [6, BSC.senderAccount.address])
	print(pendingCarrotCake)
	pendingrewards = (pcsRouter.getPrice(int(pendingCarrotCake), [cCake.address, cake.address]  ))/(10**18)
	cCakePrice = (pendingrewards/pendingCarrotCake)*bnbPrice
	profits.calculateProfit(pendingCarrotCake)
	APR = ((profits.getProfitPerSecond()*cCakePrice * 365 * 86400) / accountBalance)*100
	if gasTracking.averageGas > 0:
		data['averageGasCost'] = gasTracking.averageGas*(BSC.gas/(10**18))
		profitRate = (pcsRouter.getPrice(int(profits.getProfitPerSecond()), [cCake.address, cake.address]  ))/(10**18)
		profitToGas = profitRate*gasRate
		if time.time() - timestamp > 60:
			gasRate = optimiseGasRate(4,profitRate)
			timestamp = time.time()

		compoundRate = 86400/ (data['averageGasCost'] / profitToGas)
	else:
		compoundRate = 1
	APY = ((1+(((APR/100)*(1-gasRate))/(365*compoundRate)) )**(365*compoundRate))-1
	dailyRoiPercent = ((1+(((APR/100)*(1-gasRate))/(365*compoundRate)) )**(1*compoundRate))-1
	hourlyRoiPercent = ((1+(((APR/100)*(1-gasRate))/(365*compoundRate)) )**((1/24)*compoundRate))-1
	
	tempData = {
		'totalValue' : accountBalance+(pendingrewards*bnbPrice), 
		'cCakeBalance' : cCakeBalance,
		'pendingRewards' : pendingrewards*bnbPrice,
		'yearlyRoi' : APY*accountBalance,
		'dailyRoi' : dailyRoiPercent*accountBalance,
		'hourlyRoi' : hourlyRoiPercent*accountBalance,
		'APR' : APR,
		'APY' : APY,
		'compoundRate' : compoundRate,
		'gasRate' : gasRate,
		# 'cCakeLiquidityPercent' : cCakePercent
	}
	data.update(tempData)

	print(data)

	#print('total $' + str(accountBalance+(pendingrewards*bnbPrice )) + " : soup $" + str(soupBalance) + " : soups $" + str(soupsBalance) + " : $" + str(pendingrewards*bnbPrice) + " Rewards ready for harvest")
	#print(str(soupPercent) + "% soup liquidity owned " + str(soupsPercent) + "% soups liquidity owned")
	#print("Yearly ROI $" + str(APY*accountBalance) + " : Daily ROI $" + str(dailyRoiPercent*accountBalance) + " : Hourly ROI $" + str(hourlyRoiPercent*accountBalance))
	#print("APR " + str(APR) + "% : APY " + str(APY) + "%")

	try:
		if pendingrewards is not None and pendingrewards*gasRate > gasTracking.averageGas*(BSC.gas/(10**18)) and pendingrewards > 0:
			gasTracking.startGasCycle()
			tx = cCakeFarm.smartTransact('deposit', [0, 0])
			
			while True:
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =cCakeFarm.smartTransact('deposit', [0, 0])
					
			tx = cCakeFarm.smartTransact('deposit', [1, 0])
			
			while True:	
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =cCakeFarm.smartTransact('deposit', [1, 0])
					
			
			tx = pcsRouter.smartSwap(int(cCake.balanceOf(BSC.senderAccount.address)*0.55), [cCake.address, cake.address],0.5)
		
			while True:	
				
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =pcsRouter.smartSwap(int(cCake.balanceOf(BSC.senderAccount.address)*0.5), [cCake.address, cake.address],0.5)
					
			
			tx = pcsRouter.smartLiquidity(cCake.balanceOf(BSC.senderAccount.address),cake.smartCall('balanceOf',[BSC.senderAccount.address]),cCake.address, cake.address ,0.5)
			
			while True:	
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =pcsRouter.smartLiquidity(cCake.balanceOf(BSC.senderAccount.address),cake.smartCall('balanceOf',[BSC.senderAccount.address])  ,cCake.address, cake.address ,0.5)
					
			tx = cCakeFarm.smartTransact('deposit', [0, cCakeCake.balanceOf(BSC.senderAccount.address)])

			while True:	
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =cCakeFarm.smartTransact('deposit', [0, cCakeCake.balanceOf(BSC.senderAccount.address)])
					
			tx = wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])
			
			while True:	
				if tx.status == 1:
					gasTracking.addGas(tx.gasUsed)
					break
				elif tx.status == 0:
					tx =wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])
					
			gasTracking.endGasCycle()

	except Exception:
		continue



	array = {}
	array[0] = 1
	array[1] = 2
	number = 3
	str(number)+"," in str(array) or str(number)+"}" in str(array)