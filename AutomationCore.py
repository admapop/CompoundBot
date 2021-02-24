import re
from web3 import Web3
from constants import *
import time
from web3.middleware import geth_poa_middleware
import requests
import json



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

		BSC.waitForNextBlock()
		return txn
	def waitForNextBlock(self):
		block = self.web3.eth.getBlock('latest').number
		while True:
		 if self.web3.eth.getBlock('latest').number > block+2:
			 break
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
	def smartLiquidity(self, amount, tokenA, tokenB, maxSlippage, eth=False):
			amountB = self.blockchain.smartCall(functionName='getAmountsOut',contract=self.contract, params=[ amount,[tokenA, tokenB]])[-1]
			amountA = self.blockchain.smartCall(functionName='getAmountsIn',contract=self.contract, params=[ amountB,[tokenA, tokenB]])[0]
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
		


def average(data):
	if len(data) > 0 and sum(data) > 0:
		return sum(data)/len(data)
	else:
		0
privatekey = ''
BSC = blockChainInstance("https://bsc-dataseed1.ninicoin.io/", privatekey)

SoupBNB = lpToken('0x284A5D8712C351Ca28417d131003120808dcE48B', ABI.pcsLPPair, BSC)
SoupsBNB = lpToken('0x6304Ae062c6bDf3D24Ac86374C7019A025443247', ABI.pcsLPPair, BSC)
SoupFarm = contract('0x12eFc306d0aDB92085025617F50B7F76D87385BF', ABI.soupFarm, BSC)
SoupsFarm = contract('0x034aF5a55e4316D975A29672733B9791c397b6AF', ABI.soupsFarm, BSC)
pcsRouter = dex('0x05fF2B0DB69458A0750badebc4f9e13aDd608C7F', ABI.pcsRouter, BSC)
soup = token('0x94F559aE621F1c810F31a6a620Ad7376776fe09E', ABI.erc20, BSC)
soups = token('0x69F27E70E820197A6e495219D9aC34C8C6dA7EeE', ABI.erc20, BSC)
wbnb = contract('0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', ABI.bnb, BSC)

pendingsoups = SoupsFarm.smartCall('pendingRewards', [0, BSC.senderAccount.address]) + SoupsFarm.smartCall('pendingRewards', [1, BSC.senderAccount.address])
pendingrewards = (pcsRouter.getPrice(int(pendingsoups), [soups.address, wbnb.address]  ))/(10**18)
soupsprice = pendingrewards/pendingsoups
profits = profitTracker(pendingsoups)
compoundRate = 144


## LOGIC ##
while True:
	resp = requests.get('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=wbnb&order=market_cap_desc&per_page=100&page=1&sparkline=false')
	data = resp.json()
	bnbPrice = data[0]['current_price']

	soupBalance = 0
	#soupBalance += ((decimal(SoupBNB.getTokenBalances()[1], 18)*bnbPrice)*2)  *  (decimal(SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])     ,18)/ decimal(SoupBNB.getTotalSupply(),18) )
	soupbnbbalance = decimal(SoupsFarm.smartCall('balanceOf', [0, BSC.senderAccount.address])     ,18)
	soupsbnbbalance = decimal(SoupsFarm.smartCall('balanceOf', [1, BSC.senderAccount.address])     ,18)
	soupbnbtotalsupply = decimal(SoupBNB.getTotalSupply(),18)
	soupsbnbtotalsupply = decimal(SoupsBNB.getTotalSupply(),18)
	
	soupBalance = ((decimal(SoupBNB.getTokenBalances()[1], 18)*bnbPrice)*2)  *  (decimal(SoupsFarm.smartCall('balanceOf', [0, BSC.senderAccount.address])     ,18)/ soupbnbtotalsupply )
	soupsBalance = ((decimal(SoupsBNB.getTokenBalances()[1], 18)*bnbPrice)*2)  *  (decimal(SoupsFarm.smartCall('balanceOf', [1, BSC.senderAccount.address])     ,18)/ soupsbnbtotalsupply )
	soupPercent = (soupbnbbalance/ soupbnbtotalsupply )*100
	soupsPercent = (soupsbnbbalance/ soupsbnbtotalsupply )*100
	accountBalance = soupBalance + soupsBalance
	pendingsoups = SoupsFarm.smartCall('pendingRewards', [0, BSC.senderAccount.address]) + SoupsFarm.smartCall('pendingRewards', [1, BSC.senderAccount.address])
	pendingrewards = (pcsRouter.getPrice(int(pendingsoups), [soups.address, wbnb.address]  ))/(10**18)
	soupsprice = (pendingrewards/pendingsoups)*bnbPrice
	profits.calculateProfit(pendingsoups)
	APR = ((profits.getProfitPerSecond()*soupsprice * 365 * 86400) / accountBalance)*100
	APY = ((1+((APR/100)/(365*compoundRate)))**(365*compoundRate))-1 
	print('total $' + str(accountBalance+(pendingrewards*bnbPrice )) + " : soup $" + str(soupBalance) + " : soups $" + str(soupsBalance) + " : $" + str(pendingrewards*bnbPrice) + " Rewards ready for harvest")
	print(str(soupPercent) + "% soup liquidity owned " + str(soupsPercent) + "% soups liquidity owned")
	print("Yearly ROI $" + str(profits.getProfitPerDay()*soupsprice * 365) + " : Daily ROI $" + str(profits.getProfitPerDay()*soupsprice) + " : Hourly ROI $" + str(profits.getProfitPerHour()*soupsprice) + " : Minute ROI $" + str(profits.getProfitPerMinute()*soupsprice ))
	print("APR " + str(APR) + "% : APY " + str(APY) + "%")
	try:
		if BSC.web3.eth.getBlock('latest').number < 5093750:
			if decimal(SoupFarm.smartCall('pendingRewards', [4, BSC.senderAccount.address]),18) * (bnbPrice) > accountBalance * 0.0001:
				SoupFarm.smartTransact('deposit', [4, 0])
				pcsRouter.smartSwap(int(soup.balanceOf(BSC.senderAccount.address)*0.55), [soup.address, wbnb.address],0.5)
				pcsRouter.smartLiquidity(soup.balanceOf(BSC.senderAccount.address),soup.address, wbnb.address ,5)
				SoupFarm.smartTransact('deposit', [4, SoupBNB.balanceOf(BSC.senderAccount.address)])
				wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])
		else:
			if decimal(SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])     ,18) > 0:
				SoupFarm.smartTransact('withdraw', [4, SoupFarm.smartCall('balanceOf', [4, BSC.senderAccount.address])])
				
			if (pendingrewards*bnbPrice)> accountBalance * 0.001:
				while True:
					try:
						SoupsFarm.smartTransact('deposit', [0, 0])
						break
					except:
						continue
				while True:	
					try:
						SoupsFarm.smartTransact('deposit', [1, 0])
						break
					except:
						continue
				while True:	
					try:
						pcsRouter.smartSwap(int(soups.balanceOf(BSC.senderAccount.address)*0.55), [soups.address, wbnb.address],0.5)
						break
					except:
						continue
				while True:	
					try:
						pcsRouter.smartSwap(int(soups.balanceOf(BSC.senderAccount.address)*0.5), [soups.address, wbnb.address, soup.address],0.5)
						break
					except:
						continue
				while True:	
					try:
						pcsRouter.smartLiquidity(soups.balanceOf(BSC.senderAccount.address),soups.address, wbnb.address ,5)
						break
					except:
						continue
				while True:	
					try:
						pcsRouter.smartLiquidity(soup.balanceOf(BSC.senderAccount.address),soup.address, wbnb.address ,5)
						break
					except:
						continue
				while True:	
					try:
						SoupsFarm.smartTransact('deposit', [1, SoupsBNB.balanceOf(BSC.senderAccount.address)])
						break
					except:
						continue
				while True:	
					try:
						SoupsFarm.smartTransact('deposit', [0, SoupBNB.balanceOf(BSC.senderAccount.address)])
						break
					except:
						continue
				while True:	
					try:
						wbnb.smartTransact('withdraw',[wbnb.smartCall('balanceOf',[BSC.senderAccount.address])])
						break
					except:
						continue
	except Exception:
		continue